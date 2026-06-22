from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import app
from app.api.session_runtime import clear_sessions


FORBIDDEN_OUTPUT = ["诊断为", "处方", "治疗方案", "prescription", "treatment_plan"]


class P14ApiInputBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "p1_4_inputs.sqlite3"
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

    def _post_turn(self, session_id: str, value) -> object:
        return self.client.post(
            f"/sessions/{session_id}/turn",
            json={"user_input": value},
        )

    def _assert_no_forbidden_output(self, payload: dict) -> None:
        serialized = json.dumps(payload, ensure_ascii=False)
        for term in FORBIDDEN_OUTPUT:
            self.assertNotIn(term, serialized)

    def test_empty_message_returns_invalid_request(self) -> None:
        session = self._create_session()

        response = self._post_turn(session["session_id"], "")

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "INVALID_REQUEST")

    def test_whitespace_message_returns_invalid_request(self) -> None:
        session = self._create_session()

        response = self._post_turn(session["session_id"], "   ")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "INVALID_REQUEST")

    def test_missing_message_returns_invalid_request(self) -> None:
        session = self._create_session()

        response = self.client.post(f"/sessions/{session['session_id']}/turn", json={})

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "INVALID_REQUEST")

    def test_non_string_message_returns_invalid_request(self) -> None:
        session = self._create_session()

        response = self._post_turn(session["session_id"], 12345)

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "INVALID_REQUEST")

    def test_missing_session_id_path_is_stable_404(self) -> None:
        response = self.client.post(
            "/sessions//turn",
            json={"user_input": "special path"},
        )

        self.assertEqual(response.status_code, 404)

    def test_nonexistent_session_id_returns_stable_error(self) -> None:
        response = self._post_turn("not-found", "hello")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "SESSION_NOT_FOUND")

    def test_special_unicode_and_long_messages_are_stable(self) -> None:
        session = self._create_session()
        special = "特殊字符 !@#$%^&*() [] {} <xml> \n\t"
        unicode_input = "最近睡眠一般，胃口一般。"
        long_input = "long-input " * 600

        for value in (special, unicode_input, long_input):
            response = self._post_turn(session["session_id"], value)
            self.assertEqual(response.status_code, 200)
            self.assertIn("turn_count", response.json())
            self._assert_no_forbidden_output(response.json())

    def test_secret_like_input_is_redacted_from_api_and_sqlite(self) -> None:
        session = self._create_session()
        synthetic_secret = "sk-" + "boundarysecret1234567890"

        response = self._post_turn(
            session["session_id"],
            f"胃胀两天 OPENAI_API_KEY={synthetic_secret}",
        )

        self.assertEqual(response.status_code, 200)
        serialized = json.dumps(response.json(), ensure_ascii=False)
        self.assertNotIn("OPENAI_API_KEY", serialized)
        self.assertNotIn(synthetic_secret, serialized)

        candidates = [
            self.db_path,
            self.db_path.with_name(f"{self.db_path.name}-wal"),
            self.db_path.with_name(f"{self.db_path.name}-shm"),
        ]
        persisted = b"".join(path.read_bytes() for path in candidates if path.exists())
        decoded = persisted.decode("utf-8", errors="ignore")
        self.assertNotIn("OPENAI_API_KEY", decoded)
        self.assertNotIn(synthetic_secret, decoded)

    def test_multiple_turns_and_report_not_ready_are_stable(self) -> None:
        session = self._create_session()

        for value in ("hello", "still incomplete", "no severe signs"):
            response = self._post_turn(session["session_id"], value)
            self.assertEqual(response.status_code, 200)

        report_response = self.client.get(f"/sessions/{session['session_id']}/report")
        self.assertEqual(report_response.status_code, 200)
        report = report_response.json()
        self.assertIn("ready", report)
        self.assertIsInstance(report["ready"], bool)
        self._assert_no_forbidden_output(report)

        conn = sqlite3.connect(self.db_path)
        try:
            turn_count = conn.execute("SELECT COUNT(*) FROM turns").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(turn_count, 3)

    def test_repeated_session_creation_returns_distinct_ids(self) -> None:
        first = self._create_session()
        second = self._create_session()

        self.assertNotEqual(first["session_id"], second["session_id"])
        self.assertEqual(first["turn_count"], 0)
        self.assertEqual(second["turn_count"], 0)


if __name__ == "__main__":
    unittest.main()
