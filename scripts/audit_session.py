from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.api.redaction import redact_secrets
from app.api.report_audit import audit_report, contains_secret
from app.api.runtime_config import load_runtime_config
from app.api.sqlite_store import connect, initialize_database
from app.api.state_validator import validate_session_consistency, validate_state_json


SECRET_MARKER_PATTERN = re.compile(
    rb"OPENAI_API_KEY|API[_-]?KEY|SECRET|TOKEN|sk-[A-Za-z0-9_-]{8,}",
    re.IGNORECASE,
)
ALLOWED_SECRET_MARKER_CONTEXTS = (
    b"no_secret",
    b"redacted-secret",
    b"credential_pattern_checked",
)


def _display_path(path: Path) -> str:
    try:
        relative = path.resolve().relative_to(ROOT_DIR.resolve())
        return str(relative)
    except ValueError:
        return f"<external-db>/{redact_secrets(path.name)}"


def _load_json(value: Any) -> Any:
    if value in (None, ""):
        return None
    return json.loads(str(value))


def _count_secret_markers(db_path: Path) -> int:
    candidates = [
        db_path,
        db_path.with_name(f"{db_path.name}-wal"),
        db_path.with_name(f"{db_path.name}-shm"),
    ]
    count = 0
    for path in candidates:
        if path.exists():
            content = path.read_bytes()
            for match in SECRET_MARKER_PATTERN.finditer(content):
                context = content[max(0, match.start() - 32): match.end() + 32].lower()
                if any(allowed in context for allowed in ALLOWED_SECRET_MARKER_CONTEXTS):
                    continue
                count += 1
    return count


def _error_summary(db_path: Path, session_id: str, code: str, message: str) -> dict[str, Any]:
    return {
        "db_path": _display_path(db_path),
        "session_id": redact_secrets(session_id),
        "session_exists": False,
        "passed": False,
        "error": {"code": code, "message": message},
    }


def audit_session(
    db_path: Path,
    session_id: str,
    *,
    check_state: bool = False,
    verbose: bool = False,
) -> dict[str, Any]:
    if not db_path.exists():
        summary = _error_summary(db_path, session_id, "DB_NOT_FOUND", "SQLite database not found.")
        if check_state:
            summary["state_validation"] = {
                "passed": False,
                "errors": [{"code": "db_not_found", "message": "SQLite database not found."}],
                "warnings": [],
            }
        return summary

    try:
        initialize_database(db_path)
    except Exception as exc:  # pragma: no cover - defensive script path
        summary = _error_summary(
            db_path,
            session_id,
            "DB_UNAVAILABLE",
            f"SQLite database could not be opened: {type(exc).__name__}.",
        )
        if check_state:
            summary["state_validation"] = {
                "passed": False,
                "errors": [{"code": "db_unavailable", "message": "SQLite database could not be opened."}],
                "warnings": [],
            }
        return summary

    with connect(db_path) as conn:
        db_summary_row = conn.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM sessions) AS session_count,
              (SELECT COUNT(*) FROM turns) AS turn_count,
              (SELECT COUNT(*) FROM reports) AS report_count,
              (SELECT MAX(updated_at) FROM sessions) AS latest_updated_at
            """
        ).fetchone()
        session_row = conn.execute(
            """
            SELECT session_id, created_at, updated_at, stage, mode, rag_enabled
            FROM sessions
            WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()
        if session_row is None:
            summary = _error_summary(db_path, session_id, "SESSION_NOT_FOUND", "Session not found.")
            if check_state:
                summary["state_validation"] = {
                    "passed": False,
                    "errors": [{"code": "session_not_found", "message": "Session not found."}],
                    "warnings": [],
                }
            return summary

        state_row = conn.execute(
            "SELECT state_json, updated_at FROM session_states WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        turn_count = int(
            conn.execute(
                "SELECT COUNT(*) FROM turns WHERE session_id = ?",
                (session_id,),
            ).fetchone()[0]
        )
        reports = conn.execute(
            """
            SELECT report_id, state_version, report_json, created_at, safety_flags_json
            FROM reports
            WHERE session_id = ?
            ORDER BY created_at DESC, report_id DESC
            """,
            (session_id,),
        ).fetchall()

    state: dict[str, Any] = {}
    state_exists = state_row is not None
    state_validation = None
    state_version = 0
    if state_row is not None:
        if check_state:
            state_validation = validate_state_json(state_row["state_json"])
        try:
            state = _load_json(state_row["state_json"]) or {}
            state_version = int(state.get("state_version", state.get("turn_count", 0)) or 0)
        except (json.JSONDecodeError, TypeError, ValueError):
            state_exists = False
    elif check_state:
        state_validation = {
            "passed": False,
            "errors": [{"code": "state_not_found", "message": "Session state not found."}],
            "warnings": [],
        }

    latest_report_time = None
    latest_report_state_version = None
    latest_audit = None
    latest_report_secret = False
    if reports:
        latest = reports[0]
        latest_report_time = latest["created_at"]
        latest_report_state_version = int(latest["state_version"])
        latest_report = _load_json(latest["report_json"])
        stored_audit = _load_json(latest["safety_flags_json"])
        latest_audit = stored_audit or audit_report(latest_report, state)
        latest_report_secret = contains_secret(latest_report)

    secret_marker_count = _count_secret_markers(db_path)
    report_count = len(reports)
    passed = (
        state_exists
        and report_count > 0
        and bool(latest_audit)
        and bool(latest_audit.get("passed"))
        and not latest_report_secret
        and secret_marker_count == 0
    )

    state_consistency = None
    if check_state:
        state_consistency = validate_session_consistency(db_path, session_id)
        passed = passed and bool(state_consistency.get("passed"))

    summary = {
        "db_path": _display_path(db_path),
        "session_id": redact_secrets(session_id),
        "session_exists": True,
        "created_at": session_row["created_at"],
        "updated_at": session_row["updated_at"],
        "stage": session_row["stage"],
        "mode": session_row["mode"],
        "rag_enabled": bool(session_row["rag_enabled"]),
        "turn_count": turn_count,
        "state_exists": state_exists,
        "current_state_version": state_version,
        "report_count": report_count,
        "latest_report_time": latest_report_time,
        "latest_report_state_version": latest_report_state_version,
        "latest_report_safety_audit": latest_audit,
        "secret_found": latest_report_secret or secret_marker_count > 0,
        "secret_marker_count": secret_marker_count,
        "raw_user_text_included": False,
        "database_summary": {
            "session_count": int(db_summary_row["session_count"]) if db_summary_row is not None else None,
            "turn_count": int(db_summary_row["turn_count"]) if db_summary_row is not None else None,
            "report_count": int(db_summary_row["report_count"]) if db_summary_row is not None else None,
            "latest_updated_at": db_summary_row["latest_updated_at"] if db_summary_row is not None else None,
        },
        "passed": passed,
    }
    if check_state:
        summary["state_validation"] = state_consistency or state_validation
    if verbose:
        summary["state"] = redact_secrets(state)
    return summary


def _emit(summary: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return

    print(f"db_path: {summary.get('db_path')}")
    print(f"db_path_source: {summary.get('db_path_source')}")
    print(f"session_id: {summary.get('session_id')}")
    print(f"session_exists: {summary.get('session_exists')}")
    print(f"turn_count: {summary.get('turn_count')}")
    print(f"current_state_version: {summary.get('current_state_version')}")
    print(f"report_count: {summary.get('report_count')}")
    print(f"latest_report_time: {summary.get('latest_report_time')}")
    if "database_summary" in summary:
        print(f"database_summary: {json.dumps(summary.get('database_summary'), sort_keys=True)}")
    print(f"secret_found: {summary.get('secret_found')}")
    if "state_validation" in summary:
        validation = summary.get("state_validation") or {}
        print(f"state_validation_passed: {validation.get('passed')}")
    print(f"passed: {summary.get('passed')}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit one persisted API session.")
    parser.add_argument(
        "--db",
        help="SQLite database path. Defaults to runtime config DB path.",
    )
    parser.add_argument("--session", required=True, help="Session ID to audit.")
    parser.add_argument("--check-state", action="store_true", help="Run P2.2 state validation.")
    parser.add_argument("--verbose", action="store_true", help="Include redacted state details.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    config = load_runtime_config()
    db_path = Path(args.db) if args.db else Path(config.db_path)
    db_path_source = "cli:--db" if args.db else config.db_path_source
    summary = audit_session(
        db_path,
        args.session,
        check_state=args.check_state,
        verbose=args.verbose,
    )
    summary["db_path_source"] = db_path_source
    _emit(summary, json_output=args.json)
    raise SystemExit(0 if summary.get("passed") else 1)


if __name__ == "__main__":
    main()
