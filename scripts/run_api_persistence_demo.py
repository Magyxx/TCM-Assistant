from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

DEFAULT_DEMO_DB = ROOT_DIR / ".runtime" / "p1_2_demo.sqlite3"
from app.api.redaction import redact_secret_text
from app.api.runtime_config import reset_runtime_config_cache


def table_counts(db_path: Path) -> dict[str, int]:
    conn = sqlite3.connect(db_path)
    try:
        return {
            table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in ("sessions", "session_states", "turns")
        }
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a local P1.2 SQLite persistence demo.")
    parser.add_argument(
        "--db-path",
        default=None,
        help="SQLite path for this demo. Defaults to .runtime/p1_2_demo.sqlite3.",
    )
    args = parser.parse_args()
    configured_db_path = args.db_path or os.environ.get("TCM_API_DB_PATH", str(DEFAULT_DEMO_DB))
    db_path_source = (
        "cli:--db-path"
        if args.db_path
        else "env:TCM_API_DB_PATH"
        if os.environ.get("TCM_API_DB_PATH")
        else "default"
    )
    os.environ["TCM_API_DB_PATH"] = configured_db_path
    reset_runtime_config_cache()
    db_path = Path(configured_db_path)

    from fastapi.testclient import TestClient

    from app.api.main import app
    from app.api.session_runtime import clear_session_cache, clear_sessions

    clear_sessions()
    client = TestClient(app)

    session_resp = client.post(
        "/sessions",
        json={"extractor_mode": "fake", "rag_enabled": True},
    )
    session_resp.raise_for_status()
    session = session_resp.json()
    session_id = session["session_id"]

    turn_resp = client.post(
        f"/sessions/{session_id}/turn",
        json={"user_input": "胃胀两天，没有其他症状，也没有胸痛"},
    )
    turn_resp.raise_for_status()
    turn = turn_resp.json()

    before_restart = table_counts(db_path)
    clear_session_cache()

    state_resp = client.get(f"/sessions/{session_id}/state")
    state_resp.raise_for_status()
    state = state_resp.json()

    report_resp = client.get(f"/sessions/{session_id}/report")
    report_resp.raise_for_status()
    report = report_resp.json()

    print(
        json.dumps(
            {
                "db_path": redact_secret_text(str(db_path)),
                "db_path_source": db_path_source,
                "session_id": session_id,
                "turn_id": turn["turn_id"],
                "turn_count_after_restart": state["turn_count"],
                "final_report_ready_after_restart": report["ready"],
                "table_counts": before_restart,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
