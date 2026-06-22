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


def _assert_error_shape(testcase: unittest.TestCase, payload: dict, code: str) -> None:
    testcase.assertEqual(set(payload.keys()), {"error"})
    error = payload["error"]
    testcase.assertEqual(set(error.keys()), {"code", "message", "details"})
    testcase.assertEqual(error["code"], code)
    testcase.assertIsInstance(error["message"], str)
    testcase.assertIsInstance(error["details"], dict)
    serialized = json.dumps(payload, ensure_ascii=False)
    testcase.assertNotIn("Traceback", serialized)
    testcase.assertNotIn("File \"", serialized)
    testcase.assertNotIn("OPENAI_API_KEY", serialized)
    testcase.assertNotIn("sk-", serialized)


class P14ApiErrorContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "p1_4_errors.sqlite3"
        self.previous_db_path = os.environ.get("TCM_API_DB_PATH")
        os.environ["TCM_API_DB_PATH"] = str(self.db_path)
        clear_sessions()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        try:
            os.environ["TCM_API_DB_PATH"] = str(self.db_path)
            clear_sessions()
        finally:
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

    def test_missing_session_returns_stable_error(self) -> None:
        response = self.client.get("/sessions/not-found/state")

        self.assertEqual(response.status_code, 404)
        _assert_error_shape(self, response.json(), "SESSION_NOT_FOUND")

    def test_state_missing_returns_stable_error(self) -> None:
        session = self._create_session()
        clear_session_cache()
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "DELETE FROM session_states WHERE session_id = ?",
                (session["session_id"],),
            )
            conn.commit()
        finally:
            conn.close()

        response = self.client.get(f"/sessions/{session['session_id']}/state")

        self.assertEqual(response.status_code, 500)
        _assert_error_shape(self, response.json(), "STATE_NOT_FOUND")

    def test_corrupted_state_returns_stable_error(self) -> None:
        session = self._create_session()
        clear_session_cache()
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "UPDATE session_states SET state_json = ? WHERE session_id = ?",
                ("{not-json", session["session_id"]),
            )
            conn.commit()
        finally:
            conn.close()

        response = self.client.get(f"/sessions/{session['session_id']}/state")

        self.assertEqual(response.status_code, 500)
        _assert_error_shape(self, response.json(), "STATE_CORRUPTED")

    def test_store_unavailable_returns_stable_error(self) -> None:
        os.environ["TCM_API_DB_PATH"] = self.temp_dir.name

        response = self.client.post(
            "/sessions",
            json={"extractor_mode": "fake", "rag_enabled": True},
        )

        self.assertEqual(response.status_code, 503)
        _assert_error_shape(self, response.json(), "STORE_UNAVAILABLE")

    def test_invalid_request_error_does_not_leak_secret(self) -> None:
        response = self.client.post(
            "/sessions",
            json={
                "extractor_mode": "bad_mode",
                "rag_enabled": True,
                "OPENAI_API_KEY": "sk-" + "errorsecret1234567890",
            },
        )

        self.assertEqual(response.status_code, 422)
        _assert_error_shape(self, response.json(), "INVALID_REQUEST")

    def test_health_contract_is_unchanged(self) -> None:
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "status": "ok",
                "service": "TCM-Assistant",
                "stage": "P1.1",
                "mode": "agentic_workflow",
                "diagnosis_system": False,
            },
        )


if __name__ == "__main__":
    unittest.main()
