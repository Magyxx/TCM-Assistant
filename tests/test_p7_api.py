from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import app
from app.api.session_runtime import clear_sessions


class P7ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.previous_api_db = os.environ.get("TCM_API_DB_PATH")
        self.previous_p7_db = os.environ.get("TCM_SQLITE_PATH")
        os.environ["TCM_API_DB_PATH"] = str(Path(self.temp_dir.name) / "api.sqlite3")
        os.environ["TCM_SQLITE_PATH"] = str(Path(self.temp_dir.name) / "p7.sqlite3")
        clear_sessions()
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self) -> None:
        clear_sessions()
        if self.previous_api_db is None:
            os.environ.pop("TCM_API_DB_PATH", None)
        else:
            os.environ["TCM_API_DB_PATH"] = self.previous_api_db
        if self.previous_p7_db is None:
            os.environ.pop("TCM_SQLITE_PATH", None)
        else:
            os.environ["TCM_SQLITE_PATH"] = self.previous_p7_db
        self.temp_dir.cleanup()

    def test_p7_session_turn_trace_and_evidence_endpoints(self) -> None:
        created = self.client.post("/sessions", json={"extractor_mode": "fake", "rag_enabled": True})
        self.assertEqual(created.status_code, 200, created.text)
        session_id = created.json()["session_id"]

        turn = self.client.post(
            f"/sessions/{session_id}/turn",
            json={"user_input": "胃胀一周，没有其他症状，也没有胸痛，没有呼吸困难，没有便血"},
        )
        self.assertEqual(turn.status_code, 200, turn.text)
        self.assertEqual(turn.json()["metadata"]["p7_status"], "ok")
        self.assertTrue(turn.json()["metadata"]["p7_trace_id"])

        for path in [
            f"/sessions/{session_id}",
            f"/sessions/{session_id}/trace",
            f"/sessions/{session_id}/evidence",
            "/tools",
        ]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertIn("status", response.json())

        for path in [
            f"/sessions/{session_id}/state",
            f"/sessions/{session_id}/report",
        ]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertNotIn("status", response.json())


if __name__ == "__main__":
    unittest.main()
