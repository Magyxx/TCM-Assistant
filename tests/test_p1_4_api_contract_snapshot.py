from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import app
from app.api.models import (
    CreateSessionResponse,
    HealthResponse,
    SessionReportResponse,
    SessionStateResponse,
    TurnResponse,
)
from app.api.session_runtime import clear_sessions


class P14ApiContractSnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project_root = Path(__file__).resolve().parents[1]
        self.snapshot_path = self.project_root / "artifacts" / "p1_api_contract_snapshot.json"
        self.snapshot = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
        self.temp_dir = tempfile.TemporaryDirectory()
        self.previous_db_path = os.environ.get("TCM_API_DB_PATH")
        os.environ["TCM_API_DB_PATH"] = str(Path(self.temp_dir.name) / "snapshot.sqlite3")
        clear_sessions()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        clear_sessions()
        if self.previous_db_path is None:
            os.environ.pop("TCM_API_DB_PATH", None)
        else:
            os.environ["TCM_API_DB_PATH"] = self.previous_db_path
        self.temp_dir.cleanup()

    def _endpoint_map(self) -> dict[tuple[str, str], dict]:
        return {
            (endpoint["method"], endpoint["path"]): endpoint
            for endpoint in self.snapshot["endpoints"]
        }

    def test_endpoint_paths_are_stable(self) -> None:
        expected = {
            ("GET", "/health"),
            ("POST", "/sessions"),
            ("POST", "/sessions/{session_id}/turn"),
            ("GET", "/sessions/{session_id}/state"),
            ("GET", "/sessions/{session_id}/report"),
        }

        self.assertEqual(set(self._endpoint_map()), expected)

    def test_success_response_required_fields_match_models(self) -> None:
        endpoint_map = self._endpoint_map()
        model_map = {
            ("GET", "/health"): HealthResponse,
            ("POST", "/sessions"): CreateSessionResponse,
            ("POST", "/sessions/{session_id}/turn"): TurnResponse,
            ("GET", "/sessions/{session_id}/state"): SessionStateResponse,
            ("GET", "/sessions/{session_id}/report"): SessionReportResponse,
        }

        for key, model in model_map.items():
            required = set(endpoint_map[key]["success_response_required_fields"])
            model_fields = set(model.model_fields)
            self.assertTrue(required.issubset(model_fields), key)

    def test_health_contract_is_exact(self) -> None:
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), self.snapshot["health_contract"])

    def test_error_response_shape_is_stable(self) -> None:
        response = self.client.get("/sessions/not-found/state")

        self.assertEqual(response.status_code, 404)
        payload = response.json()
        shape = self.snapshot["error_response_shape"]
        self.assertEqual(set(payload.keys()), set(shape["top_level_required_fields"]))
        self.assertEqual(set(payload["error"].keys()), set(shape["error_required_fields"]))
        self.assertIn(payload["error"]["code"], shape["codes"])


if __name__ == "__main__":
    unittest.main()
