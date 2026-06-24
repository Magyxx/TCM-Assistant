from __future__ import annotations

import os
import tempfile
import unittest
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import app
from app.api.deps import get_p7_store
from app.api.session_runtime import clear_sessions


class P7ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.previous_api_db = os.environ.get("TCM_API_DB_PATH")
        self.previous_p7_db = os.environ.get("TCM_SQLITE_PATH")
        os.environ["TCM_API_DB_PATH"] = str(Path(self.temp_dir.name) / "api.sqlite3")
        os.environ["TCM_SQLITE_PATH"] = str(Path(self.temp_dir.name) / "p7.sqlite3")
        clear_sessions()
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self) -> None:
        self.client.close()
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

    def test_tool_invoke_audit_log_is_traceable_and_redacted(self) -> None:
        created = self.client.post("/sessions", json={"extractor_mode": "fake", "rag_enabled": True})
        self.assertEqual(created.status_code, 200, created.text)
        session_id = created.json()["session_id"]
        request_id = "p1-f3-tool-audit-test"

        blocked = self.client.post(
            "/tools/export_report_tool/invoke",
            headers={"X-Request-ID": request_id},
            json={
                "session_id": session_id,
                "approved": False,
                "payload": {
                    "report": {
                        "summary": "ok",
                        "note": "sk-p1f3syntheticsecret",
                    }
                },
            },
        )
        self.assertEqual(blocked.status_code, 200, blocked.text)
        blocked_payload = blocked.json()
        self.assertEqual(blocked_payload["status"], "blocked")
        self.assertFalse(blocked_payload["allowed"])
        self.assertEqual(blocked_payload["blocked_reason"], "human_approval_required")
        self.assertEqual(blocked_payload["audit_log"]["trace_id"], blocked_payload["trace_id"])
        self.assertEqual(blocked_payload["audit_log"]["request_id"], request_id)
        self.assertNotIn("sk-p1f3syntheticsecret", json.dumps(blocked_payload, ensure_ascii=False))

        allowed = self.client.post(
            "/tools/risk_check_tool/invoke",
            json={
                "session_id": session_id,
                "payload": {"user_input": "没有胸痛 sk-p1f3syntheticsecret"},
            },
        )
        self.assertEqual(allowed.status_code, 200, allowed.text)
        allowed_payload = allowed.json()
        self.assertEqual(allowed_payload["status"], "ok")
        self.assertTrue(allowed_payload["allowed"])
        self.assertEqual(allowed_payload["audit_log"]["trace_id"], allowed_payload["trace_id"])
        self.assertNotIn("sk-p1f3syntheticsecret", json.dumps(allowed_payload, ensure_ascii=False))

        trace = self.client.get(f"/sessions/{session_id}/trace")
        self.assertEqual(trace.status_code, 200, trace.text)
        tool_events = [
            item for item in trace.json()["traces"]
            if item.get("event", {}).get("event_type") == "tool.invoke"
        ]
        self.assertGreaterEqual(len(tool_events), 2)
        self.assertIn(blocked_payload["trace_id"], {item["trace_id"] for item in tool_events})
        self.assertIn(allowed_payload["trace_id"], {item["trace_id"] for item in tool_events})

        audit_logs = [
            item for item in get_p7_store().fetch_audit_logs(session_id)
            if item.get("event_type") == "tool.invoke"
        ]
        self.assertGreaterEqual(len(audit_logs), 2)
        audit_text = json.dumps(audit_logs, ensure_ascii=False)
        self.assertIn(blocked_payload["trace_id"], audit_text)
        self.assertIn(allowed_payload["trace_id"], audit_text)
        self.assertNotIn("sk-p1f3syntheticsecret", audit_text)


if __name__ == "__main__":
    unittest.main()
