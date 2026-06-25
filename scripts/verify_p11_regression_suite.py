from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

STAGE = "P11-M6_REGRESSION_SUITE"
DEFAULT_OUTPUT = ROOT_DIR / "artifacts" / "p11" / "p11_regression_suite.json"
PROTECTED_TAG = "v0.10.0-rc3"
PROTECTED_TAG_OBJECT = "896e60e6509041b9d89d7d14d13ed6167a9447bd"
PROTECTED_TAG_PEELED = "5c404f245172736bdb5b8ad515a3fbbcb9251c12"

CONTRACT_ARTIFACTS = {
    "M1": ROOT_DIR / "artifacts" / "p11" / "post_lora_runtime_contract.json",
    "M2": ROOT_DIR / "artifacts" / "p11" / "extractor_adapter_contract.json",
    "M3": ROOT_DIR / "artifacts" / "p11" / "workflow_path_contract.json",
    "M4": ROOT_DIR / "artifacts" / "p11" / "rag_evidence_contract.json",
    "M5": ROOT_DIR / "artifacts" / "p11" / "report_safety_contract.json",
}

CONTRACT_VERIFIERS = {
    "M1": "scripts.verify_p11_post_lora_contract",
    "M2": "scripts.verify_p11_extractor_adapter",
    "M3": "scripts.verify_p11_workflow_path",
    "M4": "scripts.verify_p11_rag_evidence_contract",
    "M5": "scripts.verify_p11_report_safety_contract",
}

MODEL_WEIGHT_PATTERNS = (
    ".safetensors",
    ".bin",
    ".pt",
    ".pth",
    ".ckpt",
    ".gguf",
)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _git(args: list[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def _run_command(args: list[str], *, timeout: int) -> dict[str, Any]:
    started = time.perf_counter()
    completed = subprocess.run(
        args,
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    elapsed = round(time.perf_counter() - started, 3)
    return {
        "passed": completed.returncode == 0,
        "returncode": completed.returncode,
        "elapsed_seconds": elapsed,
        "command": _display_command(args),
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
    }


def _display_command(args: list[str]) -> list[str]:
    if args and Path(args[0]).name.lower().startswith("python"):
        return ["python", *args[1:]]
    if args and Path(args[0]).name.lower() in {"python.exe", "python3"}:
        return ["python", *args[1:]]
    return args


def _parse_unittest_output(text: str, returncode: int) -> dict[str, Any]:
    ran_match = re.search(r"Ran\s+(\d+)\s+tests", text)
    skipped_match = re.search(r"OK\s+\(skipped=(\d+)\)", text)
    failed_match = re.search(r"FAILED\s+\((.*?)\)", text)
    return {
        "passed": returncode == 0 and ran_match is not None and failed_match is None,
        "test_count": int(ran_match.group(1)) if ran_match else 0,
        "skipped": int(skipped_match.group(1)) if skipped_match else 0,
        "failure_summary": failed_match.group(1) if failed_match else "",
    }


def _run_unittest() -> dict[str, Any]:
    started = time.perf_counter()
    output_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", errors="replace", delete=False) as output:
            output_path = Path(output.name)
            completed = subprocess.run(
                [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                cwd=ROOT_DIR,
                stdout=output,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=900,
            )
        text = output_path.read_text(encoding="utf-8", errors="replace")
    finally:
        if output_path is not None:
            output_path.unlink(missing_ok=True)
    elapsed = round(time.perf_counter() - started, 3)
    parsed = _parse_unittest_output(text, completed.returncode)
    return {
        **parsed,
        "returncode": completed.returncode,
        "elapsed_seconds": elapsed,
        "command": ["python", "-m", "unittest", "discover", "-s", "tests"],
        "output_tail": text[-6000:],
    }


def _load_contract_artifacts() -> dict[str, Any]:
    artifacts: dict[str, Any] = {}
    for milestone, path in CONTRACT_ARTIFACTS.items():
        if not path.exists():
            artifacts[milestone] = {
                "path": path.relative_to(ROOT_DIR).as_posix(),
                "status": "missing",
                "passed": False,
            }
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            artifacts[milestone] = {
                "path": path.relative_to(ROOT_DIR).as_posix(),
                "status": "invalid_json",
                "error": str(exc),
                "passed": False,
            }
            continue
        artifacts[milestone] = {
            "path": path.relative_to(ROOT_DIR).as_posix(),
            "stage": payload.get("stage"),
            "status": payload.get("status"),
            "commit": payload.get("commit"),
            "passed": payload.get("status") == "ok",
        }
    return artifacts


def _run_contract_verifiers() -> dict[str, Any]:
    results: dict[str, Any] = {}
    for milestone, module_name in CONTRACT_VERIFIERS.items():
        try:
            module = importlib.import_module(module_name)
            payload = module.verify()
            results[milestone] = {
                "stage": payload.get("stage"),
                "status": payload.get("status"),
                "passed": payload.get("status") == "ok",
            }
        except Exception as exc:
            results[milestone] = {
                "status": "failed",
                "passed": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
    return results


def _secret_scan_probe() -> dict[str, Any]:
    from scripts.secret_scan import scan_paths

    result = scan_paths([ROOT_DIR], include_runtime=False)
    return {
        "status": result.get("status"),
        "passed": result.get("status") == "ok" and result.get("finding_count") == 0,
        "finding_count": result.get("finding_count"),
        "allowed_count": result.get("allowed_count"),
        "scanned_files": result.get("scanned_files"),
    }


def _release_packaging_probe() -> dict[str, Any]:
    from scripts.check_release_packaging import build_release_packaging_payload

    result = build_release_packaging_payload()
    return {
        "status": result.get("status"),
        "passed": result.get("status") == "ok",
        "checks_total": result.get("checks_total"),
        "checks_passed": result.get("checks_passed"),
        "errors": result.get("errors"),
    }


def _tracked_sensitive_files_probe() -> dict[str, Any]:
    files = [line.strip().replace("\\", "/") for line in _git(["ls-files"]).splitlines() if line.strip()]
    model_weights = [
        path
        for path in files
        if Path(path).name.startswith(("adapter_model", "pytorch_model", "checkpoint"))
        or Path(path).suffix.lower() in MODEL_WEIGHT_PATTERNS
    ]
    env_files = [
        path
        for path in files
        if Path(path).name == ".env" or (Path(path).name.startswith(".env.") and Path(path).name != ".env.example")
    ]
    return {
        "passed": not model_weights and not env_files,
        "tracked_model_weights": model_weights,
        "tracked_env_files": env_files,
    }


def _tag_protection_probe() -> dict[str, Any]:
    tag_type = _git(["cat-file", "-t", PROTECTED_TAG])
    tag_object = _git(["rev-parse", PROTECTED_TAG])
    tag_peeled = _git(["rev-parse", f"{PROTECTED_TAG}^{{}}"])
    return {
        "passed": tag_type == "tag"
        and tag_object == PROTECTED_TAG_OBJECT
        and tag_peeled == PROTECTED_TAG_PEELED,
        "tag": PROTECTED_TAG,
        "type": tag_type,
        "object": tag_object,
        "peeled": tag_peeled,
        "expected_object": PROTECTED_TAG_OBJECT,
        "expected_peeled": PROTECTED_TAG_PEELED,
    }


def _live_vllm_probe() -> dict[str, Any]:
    enabled = os.getenv("RUN_LOCAL_VLLM_SMOKE", "").strip().lower() in {"1", "true", "yes", "on"}
    return {
        "status": "enabled_not_run_by_regression_aggregation" if enabled else "skipped",
        "passed": True,
        "enabled": enabled,
        "skip_reason": "" if enabled else "RUN_LOCAL_VLLM_SMOKE is not enabled",
    }


def verify(*, run_unittest: bool = True, run_compile: bool = True) -> dict[str, Any]:
    compile_probe = (
        _run_command([sys.executable, "-m", "compileall", "-q", "app", "scripts", "tests"], timeout=180)
        if run_compile
        else {"passed": True, "status": "skipped_by_caller", "command": ["python", "-m", "compileall", "-q", "app", "scripts", "tests"]}
    )
    unittest_probe = (
        _run_unittest()
        if run_unittest
        else {"passed": True, "status": "skipped_by_caller", "test_count": 0, "skipped": 0}
    )
    artifacts = _load_contract_artifacts()
    verifier_results = _run_contract_verifiers()
    secret_scan = _secret_scan_probe()
    release_packaging = _release_packaging_probe()
    sensitive_files = _tracked_sensitive_files_probe()
    tag_protection = _tag_protection_probe()
    live_vllm = _live_vllm_probe()
    checks = {
        "compileall_passed": bool(compile_probe["passed"]),
        "unittest_passed": bool(unittest_probe["passed"]),
        "contract_artifacts_ok": all(item["passed"] for item in artifacts.values()),
        "contract_verifiers_ok": all(item["passed"] for item in verifier_results.values()),
        "secret_scan_clean": bool(secret_scan["passed"]),
        "release_packaging_12_of_12": release_packaging["checks_total"] == 12
        and release_packaging["checks_passed"] == 12
        and bool(release_packaging["passed"]),
        "tracked_sensitive_files_clean": bool(sensitive_files["passed"]),
        "protected_tag_unchanged": bool(tag_protection["passed"]),
        "live_vllm_not_required": bool(live_vllm["passed"]),
    }
    git_status = _git(["status", "--short"])
    return {
        "stage": STAGE,
        "status": "ok" if all(checks.values()) else "failed",
        "branch": _git(["branch", "--show-current"]),
        "commit": _git(["rev-parse", "HEAD"]),
        "origin_main": _git(["rev-parse", "origin/main"]),
        "checks": checks,
        "compileall": compile_probe,
        "unittest": unittest_probe,
        "contract_artifacts": artifacts,
        "contract_verifiers": verifier_results,
        "secret_scan": secret_scan,
        "release_packaging": release_packaging,
        "sensitive_files": sensitive_files,
        "tag_protection": tag_protection,
        "live_vllm_smoke": live_vllm,
        "git_status_short": git_status.splitlines(),
        "contract": {
            "milestones": ["M1", "M2", "M3", "M4", "M5", "M6"],
            "required_release_packaging_checks": 12,
            "protected_tag": PROTECTED_TAG,
            "live_vllm_policy": "skip unless RUN_LOCAL_VLLM_SMOKE=1",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify P11-M6 aggregate regression suite.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Artifact output path.")
    parser.add_argument("--skip-unittest", action="store_true", help="Skip full unittest run for fast local inspection.")
    parser.add_argument("--skip-compile", action="store_true", help="Skip compileall for fast local inspection.")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    result = verify(run_unittest=not args.skip_unittest, run_compile=not args.skip_compile)
    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT_DIR / output
    _write_json(output, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(result["status"])
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
