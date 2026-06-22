from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from app.api.sqlite_store import (
    append_turn_and_update_state,
    clear_all_sessions,
    fetch_session,
    fetch_store_table_counts,
    fetch_table_counts,
    initialize_database,
    insert_session,
)


class P13SQLiteStoreHardeningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "hardening.sqlite3"
        self.previous_db_path = os.environ.get("TCM_API_DB_PATH")
        os.environ["TCM_API_DB_PATH"] = str(self.db_path)
        initialize_database(self.db_path)

    def tearDown(self) -> None:
        if self.previous_db_path is None:
            os.environ.pop("TCM_API_DB_PATH", None)
        else:
            os.environ["TCM_API_DB_PATH"] = self.previous_db_path
        self.temp_dir.cleanup()

    def _insert_session(self, session_id: str = "session-1") -> None:
        insert_session(
            session_id=session_id,
            created_at="2026-06-16T00:00:00+00:00",
            updated_at="2026-06-16T00:00:00+00:00",
            stage="P1.2",
            mode="fake",
            rag_enabled=True,
            state={"turn_count": 0, "metadata": {}},
        )

    def test_clear_all_sessions_preserves_schema_meta(self) -> None:
        self._insert_session()

        clear_all_sessions()

        store_counts = fetch_store_table_counts(self.db_path)
        self.assertGreaterEqual(store_counts["schema_meta"], 3)
        self.assertEqual(fetch_table_counts(self.db_path), {
            "sessions": 0,
            "session_states": 0,
            "turns": 0,
        })

    def test_append_turn_missing_session_raises_without_writing_turn(self) -> None:
        with self.assertRaises(KeyError):
            append_turn_and_update_state(
                session_id="missing-session",
                turn_index=1,
                user_input="safe input",
                response={"turn_count": 1},
                state={"turn_count": 1},
                updated_at="2026-06-16T00:01:00+00:00",
                created_at="2026-06-16T00:01:00+00:00",
            )

        self.assertEqual(fetch_table_counts(self.db_path)["turns"], 0)

    def test_duplicate_turn_rolls_back_state_update(self) -> None:
        self._insert_session()
        append_turn_and_update_state(
            session_id="session-1",
            turn_index=1,
            user_input="first input",
            response={"turn_count": 1},
            state={"turn_count": 1},
            updated_at="2026-06-16T00:01:00+00:00",
            created_at="2026-06-16T00:01:00+00:00",
        )

        with self.assertRaises(sqlite3.IntegrityError):
            append_turn_and_update_state(
                session_id="session-1",
                turn_index=1,
                user_input="duplicate input",
                response={"turn_count": 2},
                state={"turn_count": 2},
                updated_at="2026-06-16T00:02:00+00:00",
                created_at="2026-06-16T00:02:00+00:00",
            )

        payload = fetch_session("session-1")
        self.assertIsNotNone(payload)
        self.assertEqual(payload["state"]["turn_count"], 1)
        self.assertEqual(len(payload["turns"]), 1)
        self.assertEqual(payload["turns"][0]["user_input"], "first input")

    def test_inspect_script_outputs_redacted_json_summary(self) -> None:
        self._insert_session()
        append_turn_and_update_state(
            session_id="session-1",
            turn_index=1,
            user_input="safe input OPENAI_API_KEY=sk-inspectsecret1234567890",
            response={"turn_count": 1},
            state={"turn_count": 1},
            updated_at="2026-06-16T00:01:00+00:00",
            created_at="2026-06-16T00:01:00+00:00",
        )
        project_root = Path(__file__).resolve().parents[1]

        result = subprocess.run(
            [
                sys.executable,
                "scripts/inspect_sqlite_store.py",
                "--db",
                str(self.db_path),
                "--json",
            ],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
        )
        summary = json.loads(result.stdout)

        self.assertTrue(summary["exists"])
        self.assertEqual(summary["schema_meta"]["schema_stage"], "P1.3")
        self.assertEqual(summary["table_counts"]["sessions"], 1)
        self.assertEqual(summary["table_counts"]["turns"], 1)
        self.assertNotIn("sk-inspectsecret1234567890", result.stdout)
        self.assertNotIn("OPENAI_API_KEY", result.stdout)
        self.assertNotIn("safe input", result.stdout)


if __name__ == "__main__":
    unittest.main()
