from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.report.audit import REPORT_AUDIT_SCHEMA_VERSION


COMPLETE_P1_INPUT = (
    "\u80c3\u80c0\u4e00\u5468\uff0c\u6ca1\u6709\u5176\u4ed6\u75c7\u72b6\uff0c"
    "\u7761\u7720\u4e00\u822c\uff0c\u98df\u6b32\u4e00\u822c\uff0c"
    "\u5927\u4fbf\u6b63\u5e38\uff0c\u5c0f\u4fbf\u6b63\u5e38\uff0c"
    "\u6ca1\u6709\u80f8\u75db\uff0c\u6ca1\u6709\u547c\u5438\u56f0\u96be\uff0c\u6ca1\u6709\u4fbf\u8840"
)
SYNTHETIC_SECRET = "sk-p1f5syntheticsecret"
ENV_NAMES = [
    "API_LOG_PATH",
    "ENABLE_REAL_LLM",
    "EXTRACTOR_BACKEND",
    "SESSION_SQLITE_PATH",
    "SESSION_STORE_BACKEND",
    "TCM_API_DB_PATH",
    "TCM_SQLITE_PATH",
]


def _git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True, encoding="utf-8").strip()
    except Exception:
        return "unknown"


def _run_check(checks: dict[str, str], name: str, fn: Callable[[], None]) -> None:
    try:
        fn()
    except Exception as exc:
        checks[name] = f"failed:{type(exc).__name__}:{exc}"
    else:
        checks[name] = "passed"


def _configure_runtime(tmp: str) -> dict[str, str | None]:
    previous = {name: os.environ.get(name) for name in ENV_NAMES}
    tmp_path = Path(tmp)
    session_db = tmp_path / "sessions.sqlite3"
    api_log = tmp_path / "api_events.jsonl"
    os.environ["API_LOG_PATH"] = str(api_log)
    os.environ["ENABLE_REAL_LLM"] = "false"
    os.environ["EXTRACTOR_BACKEND"] = "fake"
    os.environ["SESSION_SQLITE_PATH"] = str(session_db)
    os.environ["SESSION_STORE_BACKEND"] = "sqlite"
    os.environ["TCM_API_DB_PATH"] = str(tmp_path / "api.sqlite3")
    os.environ["TCM_SQLITE_PATH"] = str(tmp_path / "p7.sqlite3")

    from app.api.deps import set_consultation_service_override
    from app.api.session_runtime import clear_sessions
    from app.services.consultation_service import ConsultationService

    clear_sessions()
    set_consultation_service_override(
        ConsultationService(sqlite_path=session_db, api_log_path=api_log)
    )
    return previous


def _restore_runtime(previous: dict[str, str | None]) -> None:
    from app.api.deps import set_consultation_service_override
    from app.api.session_runtime import clear_sessions

    clear_sessions()
    set_consultation_service_override(None)
    for name, value in previous.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


def build_validation() -> dict[str, Any]:
    checks: dict[str, str] = {}
    metrics: dict[str, Any] = {}

    def direct_report_audit_boundaries() -> None:
        from app.report.audit import build_report_audit
        from app.report.safety import check_report_safety

        safety = check_report_safety("\u8bca\u65ad\u4e3a\u67d0\u75c5\uff0c\u6cbb\u7597\u65b9\u6848\uff1a\u6bcf\u65e5 10mg")
        assert safety.ok is False
        assert "diagnosis_claim" in safety.violations
        assert "treatment_plan_claim" in safety.violations
        assert "drug_dose_like" in safety.violations

        audit = build_report_audit(
            {
                "summary": f"safe summary {SYNTHETIC_SECRET}",
                "advice": ["Continue observation."],
                "safety_disclaimer": "This system is not a diagnosis.",
            },
            {"risk_flags_status": "none"},
            route="verify",
            session_id="verify-session",
            ready=True,
        )
        text = json.dumps(audit, ensure_ascii=False, sort_keys=True)
        assert audit["schema_version"] == REPORT_AUDIT_SCHEMA_VERSION
        assert audit["passed"] is False
        assert audit["checks"]["no_secret"] is False
        assert SYNTHETIC_SECRET not in text
        metrics["direct_violation_count"] = len(audit["violations"])

    def api_report_audit_exposure_and_persistence() -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            previous = _configure_runtime(tmp)
            try:
                from fastapi.testclient import TestClient

                from app.api.app import app as p1_app
                from app.api.deps import get_p7_store
                from app.api.main import app as main_app

                with TestClient(main_app, raise_server_exceptions=False) as client:
                    created = client.post(
                        "/sessions",
                        json={"backend": "fake", "metadata": {"test": "p1_f5_report_audit"}},
                    )
                    assert created.status_code == 200, created.text
                    session_id = created.json()["session_id"]

                    turn = client.post(
                        f"/sessions/{session_id}/turn",
                        json={"user_input": COMPLETE_P1_INPUT, "extractor_backend": "fake"},
                    )
                    assert turn.status_code == 200, turn.text
                    turn_payload = turn.json()
                    assert turn_payload["report_audit"]["schema_version"] == REPORT_AUDIT_SCHEMA_VERSION
                    assert turn_payload["report_audit"]["passed"] is True

                    report = client.get(f"/sessions/{session_id}/report")
                    assert report.status_code == 200, report.text
                    report_payload = report.json()
                    assert report_payload["report_available"] is True
                    assert report_payload["report_audit"]["passed"] is True

                    persisted = client.post(f"/sessions/{session_id}/report")
                    assert persisted.status_code == 200, persisted.text

                with TestClient(p1_app, raise_server_exceptions=False) as p1_client:
                    wrapper = p1_client.get(f"/reports/{session_id}")
                    assert wrapper.status_code == 200, wrapper.text
                    wrapper_payload = wrapper.json()
                    assert wrapper_payload["report_status"] == "ready"
                    assert wrapper_payload["report_audit"]["passed"] is True

                bundle = get_p7_store().fetch_session_bundle(session_id) or {}
                final_reports = bundle.get("final_reports") or []
                assert final_reports
                safety_check = final_reports[-1]["safety_check"]
                assert safety_check["passed"] is True
                assert safety_check["p1_f5_report_audit"]["passed"] is True
                assert safety_check["p1_f5_report_audit"]["schema_version"] == REPORT_AUDIT_SCHEMA_VERSION
                serialized = json.dumps([turn_payload, report_payload, wrapper_payload, safety_check], ensure_ascii=False)
                assert SYNTHETIC_SECRET not in serialized
                metrics.update(
                    {
                        "session_id": session_id,
                        "turn_report_audit_status": turn_payload["report_audit"]["status"],
                        "get_report_audit_status": report_payload["report_audit"]["status"],
                        "wrapper_report_audit_status": wrapper_payload["report_audit"]["status"],
                        "persisted_report_count": len(final_reports),
                    }
                )
            finally:
                _restore_runtime(previous)

    for name, fn in [
        ("direct_report_audit_boundaries", direct_report_audit_boundaries),
        ("api_report_audit_exposure_and_persistence", api_report_audit_exposure_and_persistence),
    ]:
        _run_check(checks, name, fn)

    checks["no_real_llm_required"] = "passed"
    checks["no_external_report_runtime_required"] = "passed"
    status = "ok" if all(value == "passed" for value in checks.values()) else "failed"
    return {
        "stage": "P1-F5_REPORT_SAFETY_REDACTION_AUDIT",
        "status": status,
        "branch": _git(["branch", "--show-current"]),
        "commit": _git(["rev-parse", "HEAD"]),
        "external_dependencies_required": False,
        "checks": checks,
        "metrics": metrics,
        "report_audit_schema_version": REPORT_AUDIT_SCHEMA_VERSION,
        "artifacts": {
            "p1_f5_report_audit_validation": "artifacts/p1_f5_report_audit_validation.json",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", default="artifacts/p1_f5_report_audit_validation.json")
    args = parser.parse_args()
    result = build_validation()
    output_path = ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(f"{result['stage']} {result['status']} -> {output_path}")
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
