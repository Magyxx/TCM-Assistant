from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from app.graph.runner import run_p9m1_graph
from app.session.sqlite_store import SQLiteSessionStore


ROOT_DIR = Path(__file__).resolve().parents[1]


def test_replay_cli_exports_saved_session(tmp_path: Path) -> None:
    db_path = tmp_path / "sessions.sqlite3"
    store = SQLiteSessionStore(db_path)
    run_p9m1_graph("胃胀一周", session_id="replay-test", session_store=store, use_langgraph=False)
    completed = subprocess.run(
        [sys.executable, "scripts/replay_p9m2_session.py", "--session-id", "replay-test", "--db", str(db_path)],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["replayed_state"]["chief_complaint"] == "胃胀"
    assert payload["replay_turn_count"] >= 1
