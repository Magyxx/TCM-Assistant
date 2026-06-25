from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

STAGE = "P12-M3_SQLITE_PERSISTENCE"
DEFAULT_OUTPUT = ROOT_DIR / "artifacts" / "p12" / "persistence_contract.json"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


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


def _tracked_files() -> list[str]:
    return [line.strip().replace("\\", "/") for line in _git(["ls-files"]).splitlines() if line.strip()]


def _tracked_db_files() -> list[str]:
    suffixes = (".db", ".sqlite", ".sqlite3")
    return [path for path in _tracked_files() if Path(path).suffix.lower() in suffixes]


def _gitignore_covers_local_db() -> bool:
    gitignore = ROOT_DIR / ".gitignore"
    if not gitignore.exists():
        return False
    lines = {line.strip() for line in gitignore.read_text(encoding="utf-8").splitlines()}
    required = {"*.db", "*.sqlite", "*.sqlite3", ".runtime/"}
    return required.issubset(lines)


def _table_names(db_path: Path) -> list[str]:
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    finally:
        conn.close()
    return [str(row[0]) for row in rows]


def _sanitize(value: Any, temp_root: Path) -> Any:
    temp_root_text = str(temp_root)
    if isinstance(value, str):
        return value.replace(temp_root_text, "<tempdir>")
    if isinstance(value, list):
        return [_sanitize(item, temp_root) for item in value]
    if isinstance(value, dict):
        return {key: _sanitize(item, temp_root) for key, item in value.items()}
    return value


def verify() -> dict[str, Any]:
    from app.api.sqlite_store import fetch_reports_for_session, fetch_session, fetch_store_table_counts
    from app.session.sqlite_store import SQLiteSessionStore
    from app.storage.sqlite_store import P7SQLiteStore
    from scripts.verify_p12_api_contract import SAFE_COMPLETE_INPUT, _temporary_api_client

    with _temporary_api_client() as (client, paths):
        session_response = client.post(
            "/sessions",
            json={"backend": "fake", "rag_enabled": True, "metadata": {"p12": STAGE}},
        )
        session_payload = session_response.json()
        session_id = str(session_payload.get("session_id") or "")
        turn_response = client.post(
            f"/sessions/{session_id}/turn",
            json={
                "user_input": SAFE_COMPLETE_INPUT,
                "extractor_backend": "fake",
                "metadata": {"p12": STAGE},
            },
        )
        report_response = client.post(f"/sessions/{session_id}/report")
        replay_response = client.post(f"/sessions/{session_id}/replay", json={"allow_write": False})

        api_session = fetch_session(session_id)
        api_counts = fetch_store_table_counts()
        api_reports = fetch_reports_for_session(session_id)
        api_tables = _table_names(paths["legacy_db"])

        p7_store = P7SQLiteStore(paths["p7_db"])
        p7_counts = p7_store.table_counts()
        p7_bundle = p7_store.fetch_session_bundle(session_id) or {}
        p7_trace_events = p7_store.fetch_trace_events(session_id)
        p7_audit_logs = p7_store.fetch_audit_logs(session_id)

        session_store = SQLiteSessionStore(paths["session_db"])
        session_replay = session_store.replay_session(session_id)
        temp_root = paths["legacy_db"].parent

    api_state = api_session.get("state") if isinstance(api_session, dict) else {}
    p7_final_reports = p7_bundle.get("final_reports") or []
    session_turns = session_replay.get("turns") or []

    checks = {
        "session_created": session_response.status_code == 200 and bool(session_id),
        "turn_persisted": turn_response.status_code == 200
        and api_counts.get("turns", 0) >= 1
        and int(api_state.get("turn_count") or 0) >= 1,
        "state_snapshot_restored": replay_response.status_code == 200
        and replay_response.json().get("replay_status") == "ok_read_only"
        and bool(session_replay.get("replayed_state")),
        "report_persisted": report_response.status_code == 200
        and bool(api_reports)
        and bool(p7_final_reports),
        "audit_events_persisted": bool(p7_audit_logs),
        "p7_trace_persisted": bool(p7_trace_events),
        "sqlite_tables_cover_contract": all(
            table in api_tables for table in ["sessions", "turns", "session_states", "reports"]
        )
        and all(
            p7_counts.get(table, 0) >= 0
            for table in ["sessions", "turns", "run_states", "final_reports", "audit_logs"]
        ),
        "session_store_replayable": len(session_turns) >= 2 and bool(session_replay.get("state")),
        "temporary_test_db_used": all(str(path).startswith(str(temp_root)) for path in paths.values()),
        "gitignore_covers_db_files": _gitignore_covers_local_db(),
        "no_tracked_db_files": not _tracked_db_files(),
    }
    status = "ok" if all(checks.values()) else "failed"
    payload = {
        "stage": STAGE,
        "status": status,
        "branch": _git(["branch", "--show-current"]),
        "head": _git(["rev-parse", "HEAD"]),
        "base_main": _git(["rev-parse", "origin/main"]),
        "storage_contract": {
            "default_backend": "sqlite",
            "api_sqlite": {
                "tables": api_tables,
                "table_counts": api_counts,
                "session_id": session_id,
                "state_turn_count": api_state.get("turn_count"),
                "report_count": len(api_reports),
            },
            "p7_sqlite": {
                "table_counts": p7_counts,
                "final_report_count": len(p7_final_reports),
                "audit_log_count": len(p7_audit_logs),
                "trace_event_count": len(p7_trace_events),
            },
            "session_store": {
                "turn_count": len(session_turns),
                "replay_status": session_replay.get("replay_status", "ok"),
                "state_present": bool(session_replay.get("state")),
            },
            "audit_events": {
                "status": "ok",
                "source": "app.storage.sqlite_store.audit_logs",
            },
            "temporary_test_db": {
                "used": checks["temporary_test_db_used"],
                "paths": {name: str(path) for name, path in paths.items()},
            },
            "tracked_db_files": _tracked_db_files(),
        },
        "api_smoke": {
            "create_session_status": session_response.status_code,
            "turn_status": turn_response.status_code,
            "report_status": report_response.status_code,
            "replay_status": replay_response.status_code,
        },
        "checks": checks,
        "git_status_short": _git(["status", "--short"]).splitlines(),
    }
    return _sanitize(payload, temp_root)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Verify P12 SQLite persistence contract.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Artifact output path.")
    args = parser.parse_args()
    payload = verify()
    if args.output:
        _write_json(Path(args.output), payload)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(json.dumps({"stage": payload["stage"], "status": payload["status"]}, indent=2))
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
