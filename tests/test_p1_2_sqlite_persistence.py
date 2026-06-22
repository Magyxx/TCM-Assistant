from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import app
from app.api.session_runtime import clear_session_cache, clear_sessions


COMPLETE_FAKE_INPUT = "胃胀两天，没有其他症状，也没有胸痛"


class P12SQLitePersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "p1_2.sqlite3"
        self.previous_db_path = os.environ.get("TCM_API_DB_PATH")
        os.environ["TCM_API_DB_PATH"] = str(self.db_path)
        clear_sessions()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        clear_sessions()
        if self.previous_db_path is None:
            os.environ.pop("TCM_API_DB_PATH", None)
        else:
            os.environ["TCM_API_DB_PATH"] = self.previous_db_path
        self.temp_dir.cleanup()

    def _create_session(self) -> dict:
        response = self.client.post(
            "/sessions",
            json={"extractor_mode": "fake", "rag_enabled": True},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def _submit_complete_turn(self, session_id: str, user_input: str = COMPLETE_FAKE_INPUT) -> dict:
        response = self.client.post(
            f"/sessions/{session_id}/turn",
            json={"user_input": user_input},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def _fetch_one(self, sql: str, params: tuple = ()) -> sqlite3.Row:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(sql, params).fetchone()
            self.assertIsNotNone(row)
            return row
        finally:
            conn.close()

    def test_create_session_persists_session_and_initial_state(self) -> None:
        session = self._create_session()

        row = self._fetch_one(
            "SELECT session_id, stage, mode, rag_enabled FROM sessions WHERE session_id = ?",
            (session["session_id"],),
        )
        self.assertEqual(row["session_id"], session["session_id"])
        self.assertEqual(row["stage"], "P1.2")
        self.assertEqual(row["mode"], "fake")
        self.assertEqual(row["rag_enabled"], 1)

        state_row = self._fetch_one(
            "SELECT state_json FROM session_states WHERE session_id = ?",
            (session["session_id"],),
        )
        state = json.loads(state_row["state_json"])
        self.assertEqual(state["turn_count"], 0)

    def test_submit_turn_persists_turn_and_updates_state(self) -> None:
        session = self._create_session()
        data = self._submit_complete_turn(session["session_id"])

        turn_row = self._fetch_one(
            "SELECT turn_index, user_input, response_json FROM turns WHERE session_id = ?",
            (session["session_id"],),
        )
        self.assertEqual(turn_row["turn_index"], 1)
        self.assertIn("胃胀", turn_row["user_input"])
        response_json = json.loads(turn_row["response_json"])
        self.assertEqual(response_json["turn_count"], 1)
        self.assertEqual(response_json["metadata"]["last_extractor_mode"], "fake")

        state_row = self._fetch_one(
            "SELECT state_json FROM session_states WHERE session_id = ?",
            (session["session_id"],),
        )
        state = json.loads(state_row["state_json"])
        self.assertEqual(state["turn_count"], 1)
        self.assertEqual(state["chief_complaint"], data["state"]["chief_complaint"])

    def test_session_state_recovers_after_runtime_restart(self) -> None:
        session = self._create_session()
        self._submit_complete_turn(session["session_id"])

        clear_session_cache()
        response = self.client.get(f"/sessions/{session['session_id']}/state")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["session_id"], session["session_id"])
        self.assertEqual(data["turn_count"], 1)
        self.assertEqual(data["state"]["turn_count"], 1)
        self.assertEqual(data["state"]["chief_complaint"], "胃胀")

    def test_get_state_reads_persisted_state(self) -> None:
        session = self._create_session()
        self._submit_complete_turn(session["session_id"])

        response = self.client.get(f"/sessions/{session['session_id']}/state")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("state", data)
        self.assertEqual(data["state"]["turn_count"], 1)
        self.assertIn("missing_core_fields", data)

    def test_get_report_reads_persisted_state(self) -> None:
        session = self._create_session()
        self._submit_complete_turn(session["session_id"])

        clear_session_cache()
        response = self.client.get(f"/sessions/{session['session_id']}/report")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ready"])
        self.assertIn("final_report", data)
        self.assertNotIn("prescription", json.dumps(data, ensure_ascii=False).lower())

    def test_missing_session_returns_404(self) -> None:
        state_response = self.client.get("/sessions/not-found/state")
        report_response = self.client.get("/sessions/not-found/report")
        turn_response = self.client.post(
            "/sessions/not-found/turn",
            json={"user_input": "胃胀两天"},
        )
        self.assertEqual(state_response.status_code, 404)
        self.assertEqual(report_response.status_code, 404)
        self.assertEqual(turn_response.status_code, 404)

    def test_sqlite_persistence_redacts_secret_like_values(self) -> None:
        session = self._create_session()
        self._submit_complete_turn(
            session["session_id"],
            "胃胀两天 OPENAI_API_KEY=sk-testsecret1234567890",
        )

        candidates = [
            self.db_path,
            self.db_path.with_name(f"{self.db_path.name}-wal"),
            self.db_path.with_name(f"{self.db_path.name}-shm"),
        ]
        persisted = b"".join(path.read_bytes() for path in candidates if path.exists())
        decoded = persisted.decode("utf-8", errors="ignore")
        self.assertNotIn("OPENAI_API_KEY", decoded)
        self.assertNotIn("sk-testsecret1234567890", decoded)

    def test_api_persistence_does_not_add_forbidden_p1_2_capabilities(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        checked_paths = [
            project_root / "app" / "api" / "sqlite_store.py",
            project_root / "app" / "api" / "session_runtime.py",
            project_root / "app" / "api" / "main.py",
        ]
        combined = "\n".join(path.read_text(encoding="utf-8") for path in checked_paths)
        forbidden_terms = [
            "MemoryManager",
            "EmbeddingRetriever",
            "ToolRegistry",
            "MultiAgent",
            "streamlit",
            "gradio",
        ]
        for term in forbidden_terms:
            self.assertNotIn(term, combined)


if __name__ == "__main__":
    unittest.main()
