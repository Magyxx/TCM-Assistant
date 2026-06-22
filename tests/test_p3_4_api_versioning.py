from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import app
from app.api.sqlite_store import STORE_SCHEMA_VERSION, STORE_TABLES, fetch_schema_meta
from app.api.versioning import API_CONTRACT_STATUS, API_STAGE, API_VERSION, API_VERSION_HEADER
from scripts.check_api_contract import ABSOLUTE_PATH_PATTERN, build_contract_snapshot
from scripts.run_p2_gate import default_check_specs, summarize_p2_gate


ROOT_DIR = Path(__file__).resolve().parents[1]
DOC_PATH = ROOT_DIR / "docs" / "API_VERSIONING.md"
P1_SNAPSHOT_PATH = ROOT_DIR / "artifacts" / "p1_api_contract_snapshot.json"


class P34ApiVersioningTests(unittest.TestCase):
    def test_versioning_constants_are_importable_and_frozen(self) -> None:
        self.assertEqual(API_VERSION, "v1")
        self.assertEqual(API_CONTRACT_STATUS, "frozen")
        self.assertEqual(API_STAGE, "P3.4")

    def test_fastapi_openapi_includes_current_public_paths(self) -> None:
        schema = app.openapi()

        self.assertIn("/health", schema["paths"])
        self.assertIn("/version", schema["paths"])
        self.assertIn("/sessions", schema["paths"])
        self.assertIn("/sessions/{session_id}/turn", schema["paths"])
        self.assertIn("/sessions/{session_id}/state", schema["paths"])
        self.assertIn("/sessions/{session_id}/report", schema["paths"])

    def test_headers_are_additive_and_health_body_is_unchanged(self) -> None:
        snapshot = json.loads(P1_SNAPSHOT_PATH.read_text(encoding="utf-8"))
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/health", headers={"X-Request-ID": "p3-4-unit"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), snapshot["health_contract"])
        self.assertEqual(response.headers.get("X-Request-ID"), "p3-4-unit")
        self.assertEqual(response.headers.get(API_VERSION_HEADER), API_VERSION)

    def test_version_endpoint_is_additive_metadata_only(self) -> None:
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/version")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "service": "TCM-Assistant",
                "api_version": "v1",
                "stage": "P3.4",
                "contract_status": "frozen",
            },
        )
        serialized = json.dumps(response.json(), ensure_ascii=False)
        self.assertNotIn("sk-", serialized)
        self.assertNotIn("OPENAI_API_KEY", serialized)
        self.assertIsNone(ABSOLUTE_PATH_PATTERN.search(serialized))

    def test_contract_snapshot_is_parseable_and_safe(self) -> None:
        snapshot = build_contract_snapshot()
        text = json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
        paths = {(item["method"], item["path"]) for item in snapshot["public_endpoints"]}

        self.assertEqual(snapshot["phase"], "P3.4")
        self.assertEqual(snapshot["api_version"], "v1")
        self.assertEqual(snapshot["contract_status"], "frozen")
        self.assertIn(("GET", "/health"), paths)
        self.assertIn(("GET", "/version"), paths)
        self.assertIn(("POST", "/sessions"), paths)
        json.loads(text)
        self.assertNotIn("sk-", text)
        self.assertNotIn("OPENAI_API_KEY", text)
        self.assertIsNone(ABSOLUTE_PATH_PATTERN.search(text))

    def test_docs_include_freeze_and_safety_policies(self) -> None:
        text = DOC_PATH.read_text(encoding="utf-8")

        self.assertIn("breaking change policy", text)
        self.assertIn("non-breaking additive change policy", text)
        self.assertIn("P3.4 freezes current public API as v1-compatible surface", text)
        for phrase in ["不诊断", "不开方", "不替代医生", "高风险提示线下就医"]:
            self.assertIn(phrase, text)

    def test_run_p2_gate_integrates_api_contract_check(self) -> None:
        specs = default_check_specs(skip_long_session=False)
        names = [spec["name"] for spec in specs]

        self.assertEqual(len(specs), 10)
        self.assertIn("api_contract_check", names)

        fake_checks = [
            {
                "name": name,
                "command": "python -c pass",
                "status": "ok",
                "return_code": 0,
                "duration_seconds": 0.0,
                "stdout_tail": "",
                "stderr_tail": "",
            }
            for name in names
        ]
        result = summarize_p2_gate(fake_checks)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["total_checks"], 10)
        self.assertEqual(result["passed"], 10)
        self.assertEqual(result["current_gate_phase"], "P3.4")
        self.assertEqual(result["recommend_next"], "P3.5")
        self.assertIn("api_contract_check", result)

    def test_sqlite_schema_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            meta = fetch_schema_meta(Path(temp_dir) / "p3_4_schema.sqlite3")

        self.assertEqual(meta["schema_version"], str(STORE_SCHEMA_VERSION))
        self.assertEqual(meta["schema_stage"], "P1.3")
        self.assertIn("sessions", STORE_TABLES)
        self.assertIn("session_states", STORE_TABLES)
        self.assertIn("turns", STORE_TABLES)
        self.assertIn("reports", STORE_TABLES)


if __name__ == "__main__":
    unittest.main()