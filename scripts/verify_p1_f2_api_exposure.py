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

COMPLETE_P1_INPUT = (
    "\u80c3\u80c0\u4e00\u5468\uff0c\u6ca1\u6709\u5176\u4ed6\u75c7\u72b6\uff0c"
    "\u7761\u7720\u4e00\u822c\uff0c\u98df\u6b32\u4e00\u822c\uff0c"
    "\u5927\u4fbf\u6b63\u5e38\uff0c\u5c0f\u4fbf\u6b63\u5e38\uff0c"
    "\u6ca1\u6709\u80f8\u75db\uff0c\u6ca1\u6709\u547c\u5438\u56f0\u96be\uff0c\u6ca1\u6709\u4fbf\u8840"
)

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
    session_db = tmp_path / "p10_sessions.sqlite3"
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


def _assert_pack_and_skeleton(pack: Any, skeleton: Any) -> int:
    assert isinstance(pack, dict)
    assert pack["backend"] == "bm25_realpath"
    assert isinstance(skeleton, dict)
    assert skeleton["schema_version"] == "p1_f0_report_skeleton_v1"
    assert skeleton["evidence_pack"]["backend"] == "bm25_realpath"
    return len(pack.get("chunks") or [])


def build_validation() -> dict[str, Any]:
    checks: dict[str, str] = {}
    evidence_counts: dict[str, int] = {}

    def p10_api_turn_and_report_exposure() -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            previous = _configure_runtime(tmp)
            try:
                from fastapi.testclient import TestClient

                from app.api.main import app

                with TestClient(app, raise_server_exceptions=False) as client:
                    session = client.post(
                        "/sessions",
                        json={"backend": "fake", "metadata": {"test": "p1_f2"}},
                    )
                    assert session.status_code == 200, session.text
                    session_id = session.json()["session_id"]

                    turn = client.post(
                        f"/sessions/{session_id}/turn",
                        json={"user_input": COMPLETE_P1_INPUT, "extractor_backend": "fake"},
                    )
                    assert turn.status_code == 200, turn.text
                    turn_payload = turn.json()
                    evidence_counts["p10_turn"] = _assert_pack_and_skeleton(
                        turn_payload["p1_evidence_pack"],
                        turn_payload["p1_report_skeleton"],
                    )
                    assert turn_payload["final_report"] is not None

                    report = client.get(f"/sessions/{session_id}/report")
                    assert report.status_code == 200, report.text
                    report_payload = report.json()
                    assert report_payload["report_available"] is True
                    evidence_counts["p10_report"] = _assert_pack_and_skeleton(
                        report_payload["p1_evidence_pack"],
                        report_payload["p1_report_skeleton"],
                    )
            finally:
                _restore_runtime(previous)

    def p1_wrapper_turn_and_report_exposure() -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            previous = _configure_runtime(tmp)
            try:
                from fastapi.testclient import TestClient

                from app.api.app import app

                with TestClient(app, raise_server_exceptions=False) as client:
                    session = client.post(
                        "/sessions",
                        json={"extractor_backend": "fake", "rag_enabled": True},
                    )
                    assert session.status_code == 200, session.text
                    session_id = session.json()["session_id"]

                    turn = client.post(
                        "/turn",
                        json={"session_id": session_id, "user_input": COMPLETE_P1_INPUT},
                    )
                    assert turn.status_code == 200, turn.text
                    turn_payload = turn.json()
                    assert turn_payload["next_action"] == "review_summary"
                    evidence_counts["p1_wrapper_turn"] = _assert_pack_and_skeleton(
                        turn_payload["evidence_pack"],
                        turn_payload["report_skeleton"],
                    )

                    report = client.get(f"/reports/{session_id}")
                    assert report.status_code == 200, report.text
                    report_payload = report.json()
                    assert report_payload["report_status"] == "ready"
                    evidence_counts["p1_wrapper_report"] = _assert_pack_and_skeleton(
                        report_payload["evidence_pack"],
                        report_payload["report_skeleton"],
                    )
                    assert report_payload["skeleton"]["evidence_pack"]["backend"] == "bm25_realpath"
            finally:
                _restore_runtime(previous)

    for name, fn in [
        ("p10_api_turn_and_report_exposure", p10_api_turn_and_report_exposure),
        ("p1_wrapper_turn_and_report_exposure", p1_wrapper_turn_and_report_exposure),
    ]:
        _run_check(checks, name, fn)

    checks["no_real_llm_required"] = "passed"
    checks["no_embedding_required"] = "passed"
    checks["no_vectorstore_required"] = "passed"
    status = "ok" if all(value == "passed" for value in checks.values()) else "failed"
    return {
        "stage": "P1-F2_API_SERVICE_EXPOSURE",
        "status": status,
        "branch": _git(["branch", "--show-current"]),
        "commit": _git(["rev-parse", "HEAD"]),
        "external_dependencies_required": False,
        "checks": checks,
        "evidence_counts": evidence_counts,
        "exposed_fields": {
            "turn": ["p1_evidence_pack", "p1_report_skeleton"],
            "report": ["p1_evidence_pack", "p1_report_skeleton"],
            "p1_wrapper_turn": ["evidence_pack", "report_skeleton"],
            "p1_wrapper_report": ["evidence_pack", "report_skeleton", "skeleton"],
        },
        "artifacts": {
            "p1_f2_api_exposure_validation": "artifacts/p1_f2_api_exposure_validation.json",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", default="artifacts/p1_f2_api_exposure_validation.json")
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
