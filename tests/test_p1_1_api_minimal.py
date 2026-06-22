from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import app
from app.api.models import SAFETY_DISCLAIMER
from app.api.session_runtime import clear_sessions


class P11ApiMinimalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.previous_db_path = os.environ.get("TCM_API_DB_PATH")
        os.environ["TCM_API_DB_PATH"] = str(Path(self.temp_dir.name) / "p1_1.sqlite3")
        clear_sessions()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        clear_sessions()
        if self.previous_db_path is None:
            os.environ.pop("TCM_API_DB_PATH", None)
        else:
            os.environ["TCM_API_DB_PATH"] = self.previous_db_path
        self.temp_dir.cleanup()

    def test_health(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["service"], "TCM-Assistant")
        self.assertEqual(data["stage"], "P1.1")
        self.assertFalse(data["diagnosis_system"])

    def test_create_session(self) -> None:
        response = self.client.post(
            "/sessions",
            json={"extractor_mode": "fake", "rag_enabled": True},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["extractor_mode"], "fake")
        self.assertTrue(data["rag_enabled"])
        self.assertEqual(data["turn_count"], 0)
        self.assertTrue(data["session_id"])

    def test_invalid_extractor_mode_returns_422(self) -> None:
        response = self.client.post(
            "/sessions",
            json={"extractor_mode": "bad_mode", "rag_enabled": True},
        )
        self.assertEqual(response.status_code, 422)

    def test_submit_turn_and_metadata(self) -> None:
        session = self.client.post(
            "/sessions",
            json={"extractor_mode": "fake", "rag_enabled": True},
        ).json()
        response = self.client.post(
            f"/sessions/{session['session_id']}/turn",
            json={"user_input": "我胃胀两天，没有其他症状，也没有胸痛"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["session_id"], session["session_id"])
        self.assertEqual(data["turn_count"], 1)
        self.assertIn("state", data)
        self.assertEqual(data["metadata"]["graph_runtime"], "langgraph")
        self.assertEqual(data["metadata"]["extractor_mode"], "fake")
        self.assertIn("fallback_used", data["metadata"])
        self.assertEqual(data["safety_disclaimer"], SAFETY_DISCLAIMER)

        serialized = json.dumps(data, ensure_ascii=False)
        self.assertNotIn("OPENAI_API_KEY", serialized)
        self.assertNotIn("sk-", serialized)
        self.assertNotIn(".env", serialized)

    def test_empty_user_input_returns_400_or_422(self) -> None:
        session = self.client.post(
            "/sessions",
            json={"extractor_mode": "fake", "rag_enabled": True},
        ).json()
        response = self.client.post(
            f"/sessions/{session['session_id']}/turn",
            json={"user_input": "   "},
        )
        self.assertIn(response.status_code, {400, 422})

    def test_missing_session_returns_404(self) -> None:
        response = self.client.post(
            "/sessions/not-found/turn",
            json={"user_input": "胃胀两天"},
        )
        self.assertEqual(response.status_code, 404)

    def test_get_state(self) -> None:
        session = self.client.post(
            "/sessions",
            json={"extractor_mode": "fake", "rag_enabled": True},
        ).json()
        self.client.post(
            f"/sessions/{session['session_id']}/turn",
            json={"user_input": "胃胀两天"},
        )
        response = self.client.get(f"/sessions/{session['session_id']}/state")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["session_id"], session["session_id"])
        self.assertIn("state", data)
        self.assertIn("missing_core_fields", data)
        self.assertEqual(data["safety_disclaimer"], SAFETY_DISCLAIMER)

    def test_get_report_ready_false_for_new_session(self) -> None:
        session = self.client.post(
            "/sessions",
            json={"extractor_mode": "fake", "rag_enabled": True},
        ).json()
        response = self.client.get(f"/sessions/{session['session_id']}/report")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data["ready"])
        self.assertIn("missing_core_fields", data)
        self.assertEqual(data["safety_disclaimer"], SAFETY_DISCLAIMER)

    def test_get_report_missing_session_returns_404(self) -> None:
        response = self.client.get("/sessions/not-found/report")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
