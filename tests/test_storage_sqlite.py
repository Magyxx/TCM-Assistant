from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.storage.repositories import SQLiteRepository
from app.storage.sqlite import P1_TABLES, connect, init_db


class P1F0StorageSqliteTests(unittest.TestCase):
    def test_init_and_repository_crud(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "p1.sqlite3"
            init_db(db_path)
            with connect(db_path) as conn:
                tables = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertTrue(set(P1_TABLES).issubset(tables))

            repo = SQLiteRepository(db_path)
            session = repo.create_session({"demo_only": True})
            turn = repo.save_turn(session["session_id"], "redacted demo input", {"schema_pass": True})
            repo.save_run_state(session["session_id"], turn["turn_id"], {"risk_status": "unknown"})
            repo.save_audit_event(session["session_id"], "turn.saved", {"ok": True}, turn_id=turn["turn_id"])
            repo.save_report_skeleton(session["session_id"], {"report_status": "not_ready"}, turn_id=turn["turn_id"])
            repo.save_eval_run("ok", {"sample_count": 1})

            self.assertEqual(repo.get_session(session["session_id"])["metadata"]["demo_only"], True)
            self.assertEqual(len(repo.list_audit_events(session["session_id"])), 1)


if __name__ == "__main__":
    unittest.main()
