from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

P10_DIR = ROOT_DIR / "artifacts" / "p10"
VALIDATION_PATH = P10_DIR / "api_validation.json"
API_LOG_PATH = P10_DIR / "api_events.jsonl"
P9M2_METRICS_PATH = ROOT_DIR / "artifacts" / "p9m2" / "multiturn_metrics.json"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


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
        timeout=20,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def _api_log_secret_scan_passed() -> bool:
    if not API_LOG_PATH.exists():
        return False
    text = API_LOG_PATH.read_text(encoding="utf-8", errors="ignore")
    forbidden = ["OPENAI_API_KEY", "Authorization", "sk-test-", "sk-"]
    return not any(item in text for item in forbidden)


def verify() -> dict[str, Any]:
    from scripts.export_openapi import export_openapi
    from scripts.smoke_p10_api import run_smoke

    smoke = run_smoke()
    openapi_path = export_openapi()
    p9m2_metrics = _read_json(P9M2_METRICS_PATH)
    checks = smoke.get("checks", {})

    p9m2_regression_passed = bool(
        p9m2_metrics
        and p9m2_metrics.get("failures_count") == 0
        and p9m2_metrics.get("state_loss_rate") == 0.0
        and p9m2_metrics.get("rag_core_overwrite_violation") == 0
    )

    result = {
        "status": "ok",
        "branch": _git(["branch", "--show-current"]),
        "commit": _git(["rev-parse", "--short", "HEAD"]),
        "health_passed": bool(checks.get("health_passed")),
        "session_create_passed": bool(checks.get("session_create_passed")),
        "turn_passed": bool(checks.get("turn_passed")),
        "state_passed": bool(checks.get("state_passed")),
        "report_passed": bool(checks.get("report_passed")),
        "replay_passed": bool(checks.get("replay_passed")),
        "openapi_exported": openapi_path.exists(),
        "api_log_secret_scan_passed": _api_log_secret_scan_passed(),
        "p9m2_regression_passed": p9m2_regression_passed,
        "pytest_summary": "",
        "safety_gates": {
            "diagnosis_system": False,
            "prescription_output_allowed": False,
            "raw_user_input_in_api_log_default": False,
            "real_llm_default_enabled": False,
        },
        "artifacts": {
            "api_smoke_result": "artifacts/p10/api_smoke_result.json",
            "api_validation": "artifacts/p10/api_validation.json",
            "openapi": str(openapi_path.relative_to(ROOT_DIR)).replace("\\", "/"),
            "api_events": "artifacts/p10/api_events.jsonl",
        },
    }
    pass_keys = [
        "health_passed",
        "session_create_passed",
        "turn_passed",
        "state_passed",
        "report_passed",
        "replay_passed",
        "openapi_exported",
        "api_log_secret_scan_passed",
        "p9m2_regression_passed",
    ]
    if not all(result[key] for key in pass_keys):
        result["status"] = "failed"
    _write_json(VALIDATION_PATH, result)
    return result


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    result = verify()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
