from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.api.redaction import redact_secrets


DEFAULT_OUTPUT = Path("artifacts") / "release_candidate_audit.json"
TAIL_CHARS = 3000
FORBIDDEN_WEIGHT_RE = re.compile(r"(adapter|checkpoint|lora|model).*\.(bin|safetensors|pt|pth|ckpt|gguf|onnx)$", re.I)
FORBIDDEN_PRIVATE_RE = re.compile(r"(^|/)(\.env|private_data|patient_data|raw_patient_data|data/private|data/patient)(/|$)", re.I)
REQUIRED_PACKAGE_GROUPS = {"app", "scripts", "tests", "docs", "artifacts"}


@dataclass(frozen=True)
class CommandSpec:
    name: str
    command: tuple[str, ...]
    timeout_seconds: int = 1200


@dataclass(frozen=True)
class ArtifactSpec:
    name: str
    path: Path
    expected_status: str = "ok"


def _git(args: list[str], *, timeout: int = 30) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except Exception:
        return ""
    return completed.stdout.strip() if completed.returncode == 0 else ""


def _command_to_text(command: Sequence[str]) -> str:
    return str(redact_secrets(subprocess.list2cmdline([str(part) for part in command])))


def _tail(value: str, limit: int = TAIL_CHARS) -> str:
    return str(redact_secrets((value or "")[-limit:]))


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def rc_artifact_specs() -> list[ArtifactSpec]:
    return [
        ArtifactSpec("p2_p10_release_hardening", Path("artifacts/p2_p10_release_hardening.json")),
        ArtifactSpec("p1_f6_post_p8_productization_final", Path("artifacts/p1_f6_post_p8_productization_final.json")),
        ArtifactSpec("p10m2_core_validation", Path("artifacts/p10m2/core_validation.json")),
        ArtifactSpec("p10m3_local_lora_backend", Path("artifacts/p10m3/local_lora_backend_validation.json")),
        ArtifactSpec("p10_m4a_extractor_contract", Path("artifacts/p10_extractor_contract_validation.json")),
        ArtifactSpec("release_packaging_check", Path("artifacts/p3_3_release_packaging_check.json")),
        ArtifactSpec("secret_scan", Path("artifacts/secret_scan_result.json")),
    ]


def default_command_specs(*, full_unittest: bool = False) -> list[CommandSpec]:
    py = sys.executable
    unittest_command = (
        (py, "-m", "unittest", "discover", "-s", "tests")
        if full_unittest
        else (
            py,
            "-m",
            "unittest",
            "tests.test_release_candidate_audit",
            "tests.test_p2_p10_release_hardening",
            "tests.test_p1_f6_post_p8_productization_final",
            "tests.test_extractor_contract",
            "tests.test_api_contract",
        )
    )
    return [
        CommandSpec("compileall", (py, "-m", "compileall", "-q", "app", "scripts", "tests")),
        CommandSpec(
            "p2_p10_release_hardening",
            (
                py,
                "scripts/verify_p2_p10_release_hardening.py",
                "--json",
                "--output",
                "artifacts/p2_p10_release_hardening.json",
            ),
        ),
        CommandSpec("focused_rc_unittest", unittest_command, timeout_seconds=1200 if full_unittest else 420),
        CommandSpec(
            "secret_scan",
            (py, "scripts/secret_scan.py", "--json", "--output", "artifacts/secret_scan_result.json"),
        ),
        CommandSpec("git_diff_check", ("git", "diff", "--check")),
    ]


def run_command(spec: CommandSpec) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            [str(part) for part in spec.command],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=spec.timeout_seconds,
        )
        return_code = int(completed.returncode)
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        status = "ok" if return_code == 0 else "failed"
    except subprocess.TimeoutExpired as exc:
        return_code = -1
        stdout = exc.stdout or ""
        stderr = (exc.stderr or "") + f"\nTimeout after {spec.timeout_seconds} seconds."
        status = "failed"

    return {
        "name": spec.name,
        "command": _command_to_text(spec.command),
        "status": status,
        "return_code": return_code,
        "duration_seconds": round(time.perf_counter() - started, 3),
        "stdout_tail": _tail(stdout),
        "stderr_tail": _tail(stderr),
    }


def run_commands(specs: Sequence[CommandSpec], *, fail_fast: bool = False) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for spec in specs:
        result = run_command(spec)
        results.append(result)
        if fail_fast and result["status"] != "ok":
            break
    return results


def _all_checks_ok(checks: Any) -> bool:
    if isinstance(checks, dict):
        return all(value is True or value == "passed" for value in checks.values())
    if isinstance(checks, list):
        return all(bool(item.get("ok")) for item in checks if isinstance(item, dict))
    return False


def summarize_artifacts(root: Path = ROOT, specs: Sequence[ArtifactSpec] | None = None) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for spec in specs or rc_artifact_specs():
        target = root / spec.path
        payload = _load_json(target)
        status = payload.get("status") if payload else None
        summary: dict[str, Any] = {
            "name": spec.name,
            "path": str(spec.path).replace("\\", "/"),
            "exists": target.exists(),
            "status": status,
            "expected_status": spec.expected_status,
            "ok": target.exists() and status == spec.expected_status,
        }
        if payload.get("stage"):
            summary["stage"] = payload.get("stage")
        if spec.name == "p2_p10_release_hardening":
            summary["release_hardening_ready"] = payload.get("release_hardening_ready")
            summary["failed_commands"] = payload.get("failed_commands")
            summary["failed_artifacts"] = payload.get("failed_artifacts")
            summary["ok"] = (
                summary["ok"]
                and payload.get("release_hardening_ready") is True
                and not payload.get("failed_commands")
                and not payload.get("failed_artifacts")
            )
        elif spec.name == "p1_f6_post_p8_productization_final":
            completion = payload.get("completion") if isinstance(payload.get("completion"), dict) else {}
            summary["post_p8_productization_ready"] = completion.get("post_p8_productization_ready")
            summary["ok"] = summary["ok"] and completion.get("post_p8_productization_ready") is True
        elif spec.name == "p10m3_local_lora_backend":
            live_smoke = payload.get("live_smoke") if isinstance(payload.get("live_smoke"), dict) else {}
            summary["checks_ok"] = _all_checks_ok(payload.get("checks"))
            summary["live_smoke_status"] = live_smoke.get("status")
            summary["ok"] = summary["ok"] and summary["checks_ok"] and live_smoke.get("status") in {"passed", "skipped"}
        elif spec.name == "p10_m4a_extractor_contract":
            lora_artifacts = payload.get("lora_artifacts") if isinstance(payload.get("lora_artifacts"), dict) else {}
            summary["checks_ok"] = _all_checks_ok(payload.get("checks"))
            summary["model_weights_committed"] = lora_artifacts.get("model_weights_committed")
            summary["ok"] = summary["ok"] and summary["checks_ok"] and lora_artifacts.get("model_weights_committed") is False
        elif spec.name == "release_packaging_check":
            summary["checks_total"] = payload.get("checks_total")
            summary["checks_passed"] = payload.get("checks_passed")
            summary["errors"] = payload.get("errors")
            summary["ok"] = (
                summary["ok"]
                and payload.get("checks_total") == payload.get("checks_passed")
                and not payload.get("errors")
                and payload.get("boundary_violated") is False
            )
        elif spec.name == "secret_scan":
            summary["finding_count"] = payload.get("finding_count")
            summary["ok"] = summary["ok"] and payload.get("finding_count") == 0
        summaries.append(summary)
    return summaries


def parse_status_lines(lines: Sequence[str]) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for raw in lines:
        if not raw.strip():
            continue
        status = raw[:2]
        path = raw[3:].strip() if len(raw) > 3 else ""
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip()
        normalized = path.replace("\\", "/")
        top_level = normalized.split("/", 1)[0] if normalized else ""
        entries.append({"status": status, "path": normalized, "top_level": top_level})
    return entries


def _forbidden_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return bool(FORBIDDEN_WEIGHT_RE.search(normalized) or FORBIDDEN_PRIVATE_RE.search(normalized))


def build_worktree_package(status_lines: Sequence[str] | None = None, tracked_and_untracked: Sequence[str] | None = None) -> dict[str, Any]:
    if status_lines is None:
        status_lines = _git(["status", "--porcelain=v1", "-uall"], timeout=60).splitlines()
    if tracked_and_untracked is None:
        tracked_and_untracked = _git(["ls-files", "--cached", "--others", "--exclude-standard"], timeout=60).splitlines()

    entries = parse_status_lines(status_lines)
    categories: dict[str, int] = {}
    untracked = 0
    modified = 0
    for entry in entries:
        categories[entry["top_level"]] = categories.get(entry["top_level"], 0) + 1
        if entry["status"] == "??":
            untracked += 1
        else:
            modified += 1

    forbidden_status_paths = [entry["path"] for entry in entries if _forbidden_path(entry["path"])]
    forbidden_candidate_paths = [path.replace("\\", "/") for path in tracked_and_untracked if _forbidden_path(path)]
    required_groups_present = {group: categories.get(group, 0) > 0 for group in sorted(REQUIRED_PACKAGE_GROUPS)}
    return {
        "changed_file_count": len(entries),
        "modified_file_count": modified,
        "untracked_file_count": untracked,
        "categories": dict(sorted(categories.items())),
        "required_groups_present": required_groups_present,
        "required_groups_ok": all(required_groups_present.values()),
        "forbidden_status_paths": forbidden_status_paths,
        "forbidden_candidate_paths": sorted(set(forbidden_candidate_paths)),
        "forbidden_paths_ok": not forbidden_status_paths and not forbidden_candidate_paths,
        "dirty_worktree_expected": True,
        "git_commit_performed": False,
        "commit_package_ready": bool(entries) and all(required_groups_present.values()) and not forbidden_status_paths and not forbidden_candidate_paths,
    }


def build_boundary_summary() -> dict[str, Any]:
    return {
        "release_candidate_local_engineering_package": True,
        "not_production_medical_product": True,
        "no_diagnosis_prescription_or_treatment_plan": True,
        "no_device2_lora_merge": True,
        "no_model_weights_or_adapters_committed": True,
        "real_llm_optional_and_disabled_by_default": True,
        "local_lora_runtime_optional": True,
        "legacy_p1_gate_authoritative": False,
        "git_commit_requires_explicit_user_approval": True,
    }


def decide_status(
    command_results: Sequence[dict[str, Any]],
    artifact_summaries: Sequence[dict[str, Any]],
    worktree_package: dict[str, Any],
    boundary: dict[str, Any],
) -> str:
    commands_ok = all(item.get("status") == "ok" for item in command_results)
    artifacts_ok = all(item.get("ok") is True for item in artifact_summaries)
    worktree_ok = worktree_package.get("commit_package_ready") is True and worktree_package.get("forbidden_paths_ok") is True
    boundary_ok = (
        boundary.get("release_candidate_local_engineering_package") is True
        and boundary.get("not_production_medical_product") is True
        and boundary.get("no_diagnosis_prescription_or_treatment_plan") is True
        and boundary.get("no_device2_lora_merge") is True
        and boundary.get("no_model_weights_or_adapters_committed") is True
        and boundary.get("git_commit_requires_explicit_user_approval") is True
    )
    return "ok" if commands_ok and artifacts_ok and worktree_ok and boundary_ok else "failed"


def build_audit_result(command_results: Sequence[dict[str, Any]]) -> dict[str, Any]:
    artifact_summaries = summarize_artifacts()
    worktree_package = build_worktree_package()
    boundary = build_boundary_summary()
    failed_commands = [item["name"] for item in command_results if item.get("status") != "ok"]
    failed_artifacts = [item["name"] for item in artifact_summaries if item.get("ok") is not True]
    status = decide_status(command_results, artifact_summaries, worktree_package, boundary)
    return {
        "stage": "RELEASE_CANDIDATE_AUDIT_COMMIT_PACKAGING",
        "status": status,
        "branch": _git(["branch", "--show-current"]),
        "commit": _git(["rev-parse", "HEAD"]),
        "external_dependencies_required": False,
        "commands_total": len(command_results),
        "commands_passed": len(command_results) - len(failed_commands),
        "commands_failed": len(failed_commands),
        "failed_commands": failed_commands,
        "failed_artifacts": failed_artifacts,
        "commands": list(command_results),
        "artifacts": artifact_summaries,
        "worktree_package": worktree_package,
        "boundary": boundary,
        "release_candidate_ready": status == "ok",
        "git_commit_performed": False,
        "recommend_next": "manual git stage/commit/push after explicit user approval" if status == "ok" else "hold",
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Run release candidate audit and commit-package validation.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--full-unittest", action="store_true")
    args = parser.parse_args()

    command_results = run_commands(default_command_specs(full_unittest=args.full_unittest), fail_fast=args.fail_fast)
    result = build_audit_result(command_results)
    _write_json(Path(args.output), result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(f"{result['stage']} {result['status']} -> {ROOT / args.output}")
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
