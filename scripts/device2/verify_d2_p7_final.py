from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "artifacts" / "device2" / "d2_p7_final_validation.json"
STAGE = "D2-P7_FINAL_DOCS_AND_HANDOFF"

REQUIRED_DOCS = {
    "README_DEVICE2.md": ROOT / "README_DEVICE2.md",
    "docs/DEVICE2_RESUME_SUMMARY.md": ROOT / "docs" / "DEVICE2_RESUME_SUMMARY.md",
    "docs/DEVICE2_BRANCH_HANDOFF.md": ROOT / "docs" / "DEVICE2_BRANCH_HANDOFF.md",
    "reports/device2/final_summary.md": ROOT / "reports" / "device2" / "final_summary.md",
    "reports/device2/final_badcase_summary.md": ROOT / "reports" / "device2" / "final_badcase_summary.md",
}

PRIOR_ARTIFACTS = {
    "d2_p6a_integration_validation": ROOT / "artifacts" / "device2" / "d2_p6_integration_validation.json",
    "d2_p6b_e2e_validation": ROOT / "artifacts" / "device2" / "d2_p6b_e2e_validation.json",
    "d2_p6c_backend_compare_validation": ROOT
    / "artifacts"
    / "device2"
    / "d2_p6c_backend_compare_validation.json",
    "d2_p6c_backend_metrics": ROOT / "artifacts" / "device2" / "d2_p6c_backend_metrics.json",
    "d2_p6c_predictions_sample": ROOT
    / "artifacts"
    / "device2"
    / "d2_p6c_backend_predictions.sample.jsonl",
    "d2_p6c_badcases_sample": ROOT
    / "artifacts"
    / "device2"
    / "d2_p6c_backend_badcases.sample.jsonl",
}

README_CAVEATS = {
    "minimal_7_case_eval": "7-case minimal eval",
    "live_vllm_skipped_by_default": "live vllm skipped unless run_local_vllm_smoke=1",
    "cloud_llm_skipped": "cloud_llm skipped",
    "full_unittest_preexisting_blockers": "full unittest discover pre-existing blockers",
}

FORBIDDEN_RESUME_PHRASES = {
    "\u81ea\u52a8\u8bca\u65ad",
    "\u81ea\u52a8\u5f00\u65b9",
    "\u533b\u7597\u53ef\u7528",
    "\u5927\u89c4\u6a21\u8bc4\u6d4b\u8bc1\u660e",
    "\u5904\u65b9\u63a8\u8350",
    "clinical readiness",
    "large-scale proof",
    "autonomous clinical decisioning",
    "prescription recommendation",
    "physician replacement",
}


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", f"safe.directory={ROOT.as_posix()}", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )


def _git_info() -> dict[str, Any]:
    branch = _run_git(["branch", "--show-current"])
    head = _run_git(["rev-parse", "--short", "HEAD"])
    recent = _run_git(["log", "--oneline", "-10"])
    return {
        "branch": branch.stdout.strip() if branch.returncode == 0 else "unknown",
        "head": head.stdout.strip() if head.returncode == 0 else "unknown",
        "recent_commits": recent.stdout.strip().splitlines() if recent.returncode == 0 else [],
    }


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _presence(paths: dict[str, Path]) -> dict[str, str]:
    return {name: "present" if path.exists() else "missing" for name, path in paths.items()}


def _weights_not_tracked() -> tuple[bool, list[str]]:
    tracked = _run_git(["ls-files"])
    if tracked.returncode != 0:
        return False, [tracked.stderr.strip() or "git ls-files failed"]

    banned_suffixes = (".safetensors", ".bin", ".ckpt", ".pt", ".pth", ".gguf", ".onnx")
    banned_segments = ("artifacts/device2/checkpoints/", "artifacts/device2/adapters/")
    offending = [
        path
        for path in tracked.stdout.splitlines()
        if path.endswith(banned_suffixes) or any(segment in path for segment in banned_segments)
    ]
    return not offending, offending


def _secret_scan_passed() -> bool:
    payload = _read_json(ROOT / "artifacts" / "secret_scan_result.json")
    return payload.get("status") == "ok" and payload.get("finding_count") == 0


def _resume_has_no_forbidden_claims(text: str) -> tuple[bool, list[str]]:
    lowered = text.lower()
    found = sorted(phrase for phrase in FORBIDDEN_RESUME_PHRASES if phrase.lower() in lowered)
    return not found, found


def run_validation() -> dict[str, Any]:
    git = _git_info()
    docs = _presence(REQUIRED_DOCS)
    prior_artifacts = _presence(PRIOR_ARTIFACTS)
    readme = _read_text(ROOT / "README_DEVICE2.md").lower()
    resume = _read_text(ROOT / "docs" / "DEVICE2_RESUME_SUMMARY.md")

    caveats = {
        key: expected in readme
        for key, expected in README_CAVEATS.items()
    }
    no_forbidden_resume_claims, forbidden_resume_phrases = _resume_has_no_forbidden_claims(resume)
    weights_ok, tracked_weight_findings = _weights_not_tracked()
    secret_ok = _secret_scan_passed()
    risk_rule_ownership_documented = "riskruleengine ownership" in resume.lower() or "risk rule ownership" in readme

    checks = {
        "required_docs_present": all(value == "present" for value in docs.values()),
        "prior_artifacts_present": all(value == "present" for value in prior_artifacts.values()),
        "caveats_documented": all(caveats.values()),
        "secret_scan_passed": secret_ok,
        "resume_no_forbidden_claims": no_forbidden_resume_claims,
        "risk_rule_ownership_documented": risk_rule_ownership_documented,
        "weights_not_tracked": weights_ok,
    }
    status = "ok" if all(checks.values()) else "failed"

    return {
        "stage": STAGE,
        "status": status,
        "branch": git["branch"],
        "commit": git["head"],
        "recent_commits": git["recent_commits"],
        "docs": docs,
        "prior_artifacts": prior_artifacts,
        "caveats_documented": caveats,
        "safety": {
            "no_diagnosis_claim": no_forbidden_resume_claims,
            "no_prescription_claim": no_forbidden_resume_claims,
            "risk_rule_ownership_documented": risk_rule_ownership_documented,
            "weights_not_tracked": weights_ok,
            "secret_scan_passed": secret_ok,
            "forbidden_resume_phrases": forbidden_resume_phrases,
            "tracked_weight_findings": tracked_weight_findings,
        },
        "handoff": {
            "merge_ready_for_review": status == "ok",
            "merge_strategy": "review_or_cherry_pick_only",
            "do_not_merge_weights": weights_ok,
        },
        "checks": checks,
        "notes": {
            "git_status_clean": "manual final check after committing D2-P7 files",
            "full_unittest_discover": "failed_due_preexisting_local_env_blockers",
            "live_vllm": "skipped unless RUN_LOCAL_VLLM_SMOKE=1",
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify D2-P7 final docs and handoff readiness.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()
    payload = run_validation()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2))
    else:
        print(f"D2-P7 final validation: {payload['status']} -> {args.output}")
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
