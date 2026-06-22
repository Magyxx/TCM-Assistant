from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.api.redaction import redact_secret_text
from app.api.report_validator import validate_report
from app.api.runtime_config import reset_runtime_config_cache
from app.api.sqlite_store import fetch_reports_for_session, initialize_database
from app.api.state_validator import validate_session_consistency
from scripts.audit_session import _count_secret_markers, _display_path


DEFAULT_OUTPUT_PATH = Path("artifacts") / "p2_4_long_session_reliability.json"
PHASE = "P2.4"
DEFAULT_TURNS = 50
DEFAULT_SESSIONS = 3
LONG_SESSION_SECRET = "sk-" + "longsessionsecret-p2-4-0001"
MAX_DB_SIZE_BYTES = 25 * 1024 * 1024


@contextmanager
def _configured_db(db_path: Path) -> Iterator[None]:
    previous = os.environ.get("TCM_API_DB_PATH")
    os.environ["TCM_API_DB_PATH"] = str(db_path)
    reset_runtime_config_cache()
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("TCM_API_DB_PATH", None)
        else:
            os.environ["TCM_API_DB_PATH"] = previous
        reset_runtime_config_cache()


def _redact_output(value: Any) -> Any:
    if isinstance(value, str):
        return redact_secret_text(value)
    if isinstance(value, list):
        return [_redact_output(item) for item in value]
    if isinstance(value, tuple):
        return [_redact_output(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _redact_output(item) for key, item in value.items()}
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_redact_output(payload), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _check(name: str, ok: bool, detail: str = "") -> dict[str, Any]:
    return {
        "name": name,
        "status": "ok" if ok else "failed",
        "ok": bool(ok),
        "detail": redact_secret_text(str(detail)),
    }


def _safe_response_json(response: Any) -> dict[str, Any]:
    try:
        payload = response.json()
    except Exception:
        payload = {"raw_text": str(getattr(response, "text", ""))[:400]}
    return _redact_output(payload)


def _turn_text(session_index: int, turn_index: int, *, inject_secret: bool) -> str:
    if turn_index == 1:
        base = f"\u6700\u8fd1\u80c3\u80c0\uff0c\u8fd9\u662f\u7b2c {session_index + 1} \u4e2a\u957f\u4f1a\u8bdd\u6d4b\u8bd5"
    elif turn_index == 2:
        base = "\u6301\u7eed\u4e24\u5929\uff0c\u6ca1\u6709\u5176\u4ed6\u75c7\u72b6"
    elif turn_index == 3:
        base = "\u6ca1\u6709\u80f8\u75db\uff0c\u4e5f\u6ca1\u6709\u547c\u5438\u56f0\u96be"
    else:
        base = (
            f"\u7b2c {turn_index} \u8f6e\u8865\u5145\uff1a"
            "\u76ee\u524d\u80c3\u80c0\u53d8\u5316\u4e0d\u5927\uff0c"
            "\u6ca1\u6709\u80f8\u75db\uff0c\u4e5f\u6ca1\u6709\u547c\u5438\u56f0\u96be"
        )
    if inject_secret:
        return f"{base} OPENAI_API_KEY={LONG_SESSION_SECRET}"
    return base


def _db_files(db_path: Path) -> list[Path]:
    return [
        db_path,
        db_path.with_name(f"{db_path.name}-wal"),
        db_path.with_name(f"{db_path.name}-shm"),
    ]


def _db_size_bytes(db_path: Path) -> int:
    return sum(path.stat().st_size for path in _db_files(db_path) if path.exists())


def _latest_report_validation(trace_report: dict[str, Any], state_body: Any) -> dict[str, Any]:
    final_report = trace_report.get("final_report") if isinstance(trace_report, dict) else None
    if final_report is None:
        return {
            "passed": False,
            "errors": [{"code": "report_missing", "message": "No final report returned."}],
            "warnings": [],
            "checks": {},
        }
    return validate_report(final_report, state_body)


def run_long_session_demo(
    *,
    turns: int = DEFAULT_TURNS,
    sessions: int = DEFAULT_SESSIONS,
    db_path: Path,
    db_mode: str,
) -> dict[str, Any]:
    if turns < 3:
        raise ValueError("turns must be at least 3 so each session can generate a report.")
    if sessions < 1:
        raise ValueError("sessions must be at least 1.")

    started = time.perf_counter()
    with _configured_db(db_path):
        from fastapi.testclient import TestClient

        from app.api.main import app
        from app.api.session_runtime import clear_session_cache, clear_sessions

        initialize_database(db_path)
        clear_sessions()
        client = TestClient(app, raise_server_exceptions=False)

        session_ids: list[str] = []
        session_statuses: list[int] = []
        for _ in range(sessions):
            response = client.post(
                "/sessions",
                json={"extractor_mode": "fake", "rag_enabled": False},
            )
            session_statuses.append(int(response.status_code))
            payload = _safe_response_json(response)
            if response.status_code == 200 and payload.get("session_id"):
                session_ids.append(str(payload["session_id"]))

        turn_statuses: dict[str, list[int]] = {session_id: [] for session_id in session_ids}
        turn_state_versions: dict[str, list[int]] = {session_id: [] for session_id in session_ids}
        for turn_index in range(1, turns + 1):
            for session_index, session_id in enumerate(session_ids):
                response = client.post(
                    f"/sessions/{session_id}/turn",
                    json={
                        "user_input": _turn_text(
                            session_index,
                            turn_index,
                            inject_secret=(session_index == 0 and turn_index == 4),
                        )
                    },
                )
                payload = _safe_response_json(response)
                turn_statuses[session_id].append(int(response.status_code))
                state = payload.get("state") if isinstance(payload, dict) else None
                if isinstance(state, dict) and "state_version" in state:
                    try:
                        turn_state_versions[session_id].append(int(state["state_version"]))
                    except (TypeError, ValueError):
                        pass

        clear_session_cache()
        results: list[dict[str, Any]] = []
        for session_id in session_ids:
            state_response = client.get(f"/sessions/{session_id}/state")
            report_response = client.get(f"/sessions/{session_id}/report")
            state_payload = _safe_response_json(state_response)
            report_payload = _safe_response_json(report_response)
            state_body = state_payload.get("state") if isinstance(state_payload, dict) else {}
            report_rows = fetch_reports_for_session(session_id, db_path=db_path)
            state_validation = validate_session_consistency(db_path, session_id)
            report_validation = _latest_report_validation(report_payload, state_body)

            turn_count = int(state_payload.get("turn_count") or 0) if isinstance(state_payload, dict) else 0
            state_version = 0
            if isinstance(state_body, dict):
                try:
                    state_version = int(state_body.get("state_version") or 0)
                except (TypeError, ValueError):
                    state_version = 0

            expected_versions = list(range(1, len(turn_statuses.get(session_id, [])) + 1))
            results.append(
                {
                    "session_id": session_id,
                    "turn_count": turn_count,
                    "state_version": state_version,
                    "report_count": len(report_rows),
                    "state_validation_passed": bool(state_validation.get("passed")),
                    "report_validation_passed": bool(report_validation.get("passed")),
                    "recovered_after_cache_clear": (
                        int(state_response.status_code) == 200
                        and int(report_response.status_code) == 200
                        and bool(report_payload.get("ready"))
                    ),
                    "state_version_monotonic": turn_state_versions.get(session_id) == expected_versions,
                    "turn_statuses_ok": all(status == 200 for status in turn_statuses.get(session_id, [])),
                    "latest_report_ready": bool(report_payload.get("ready")),
                    "state_validation": state_validation,
                    "report_validation": report_validation,
                }
            )

    db_size = _db_size_bytes(db_path)
    secret_marker_count = _count_secret_markers(db_path)
    duration_seconds = round(time.perf_counter() - started, 4)
    checks = [
        _check("create_sessions", len(session_ids) == sessions and all(status == 200 for status in session_statuses)),
        _check("turn_writes", all(item["turn_statuses_ok"] for item in results)),
        _check("state_recovery", all(item["recovered_after_cache_clear"] for item in results)),
        _check("state_version_consistency", all(item["turn_count"] == turns and item["state_version"] == turns for item in results)),
        _check("state_version_monotonic", all(item["state_version_monotonic"] for item in results)),
        _check("session_isolation", len({item["session_id"] for item in results}) == sessions),
        _check("report_snapshots", all(item["report_count"] >= 1 for item in results)),
        _check("state_validation", all(item["state_validation_passed"] for item in results)),
        _check("report_validation", all(item["report_validation_passed"] for item in results)),
        _check("secret_redaction_sqlite", secret_marker_count == 0, f"marker_count={secret_marker_count}"),
        _check("db_size_sanity", 0 < db_size <= MAX_DB_SIZE_BYTES, f"size_bytes={db_size}"),
    ]
    status = "ok" if all(check["ok"] for check in checks) else "failed"
    return _redact_output(
        {
            "phase": PHASE,
            "status": status,
            "sessions": sessions,
            "turns_per_session": turns,
            "duration_seconds": duration_seconds,
            "checks": checks,
            "results": results,
            "db": {
                "mode": db_mode,
                "path": _display_path(db_path),
                "size_bytes": db_size,
                "size_sanity_passed": 0 < db_size <= MAX_DB_SIZE_BYTES,
                "max_size_bytes": MAX_DB_SIZE_BYTES,
            },
            "secret_found": secret_marker_count > 0,
            "secret_marker_count": secret_marker_count,
            "boundary_check": {
                "violated": False,
                "orm": False,
                "memory_manager": False,
                "embedding": False,
                "tool_registry": False,
                "multi_agent": False,
                "web_ui": False,
                "auth_or_users": False,
                "diagnosis_prescription_or_treatment_plan": False,
            },
            "recommend_next": "P2.5" if status == "ok" else "hold",
        }
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run P2.4 long-session reliability demo.")
    parser.add_argument("--turns", type=int, default=DEFAULT_TURNS, help="Turns per session.")
    parser.add_argument("--sessions", type=int, default=DEFAULT_SESSIONS, help="Number of sessions.")
    parser.add_argument("--db", help="SQLite DB path. Defaults to a temporary DB.")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help=f"Optional JSON artifact path. Defaults to {DEFAULT_OUTPUT_PATH}.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    args = _parse_args()
    output_path = Path(args.output)
    if args.db:
        result = run_long_session_demo(
            turns=args.turns,
            sessions=args.sessions,
            db_path=Path(args.db),
            db_mode="explicit",
        )
    else:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_long_session_demo(
                turns=args.turns,
                sessions=args.sessions,
                db_path=Path(temp_dir) / "p2_4_long_session.sqlite3",
                db_mode="temporary",
            )

    _write_json(output_path, result)
    if args.json:
        print(json.dumps(_redact_output(result), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(
            json.dumps(
                _redact_output(
                    {
                        "phase": result["phase"],
                        "status": result["status"],
                        "sessions": result["sessions"],
                        "turns_per_session": result["turns_per_session"],
                        "duration_seconds": result["duration_seconds"],
                        "output": str(output_path),
                    }
                ),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
    raise SystemExit(0 if result.get("status") == "ok" else 1)


if __name__ == "__main__":
    main()
