from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.deps import set_consultation_service_override
from app.api.app import app
from app.api.session_runtime import clear_sessions
from app.services.consultation_service import ConsultationService


COMPLETE_P1_INPUT = (
    "\u80c3\u80c0\u4e00\u5468\uff0c\u6ca1\u6709\u5176\u4ed6\u75c7\u72b6\uff0c"
    "\u7761\u7720\u4e00\u822c\uff0c\u98df\u6b32\u4e00\u822c\uff0c"
    "\u5927\u4fbf\u6b63\u5e38\uff0c\u5c0f\u4fbf\u6b63\u5e38\uff0c"
    "\u6ca1\u6709\u80f8\u75db\uff0c\u6ca1\u6709\u547c\u5438\u56f0\u96be\uff0c\u6ca1\u6709\u4fbf\u8840"
)


class P1F0ApiContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.previous_env = {
            name: os.environ.get(name)
            for name in [
                "API_LOG_PATH",
                "ENABLE_REAL_LLM",
                "EXTRACTOR_BACKEND",
                "SESSION_SQLITE_PATH",
                "SESSION_STORE_BACKEND",
                "TCM_API_DB_PATH",
                "TCM_SQLITE_PATH",
            ]
        }
        session_db = Path(self.temp_dir.name) / "p10_sessions.sqlite3"
        api_log = Path(self.temp_dir.name) / "api_events.jsonl"
        os.environ["API_LOG_PATH"] = str(api_log)
        os.environ["ENABLE_REAL_LLM"] = "false"
        os.environ["EXTRACTOR_BACKEND"] = "fake"
        os.environ["SESSION_SQLITE_PATH"] = str(session_db)
        os.environ["SESSION_STORE_BACKEND"] = "sqlite"
        os.environ["TCM_API_DB_PATH"] = str(Path(self.temp_dir.name) / "api.sqlite3")
        os.environ["TCM_SQLITE_PATH"] = str(Path(self.temp_dir.name) / "p7.sqlite3")
        clear_sessions()
        set_consultation_service_override(
            ConsultationService(sqlite_path=session_db, api_log_path=api_log)
        )
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self) -> None:
        self.client.close()
        clear_sessions()
        set_consultation_service_override(None)
        for name, value in self.previous_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        self.temp_dir.cleanup()

    def test_health_contract(self) -> None:
        self.assertEqual(
            self.client.get("/health").json(),
            {
                "status": "ok",
                "app": "TCM-Assistant",
                "mode": "local",
                "external_dependencies_required": False,
            },
        )

    def test_sessions_turn_report_and_eval_smoke(self) -> None:
        session = self.client.post("/sessions", json={"extractor_backend": "fake"}).json()
        self.assertTrue(session["session_id"])
        turn = self.client.post(
            "/turn",
            json={"session_id": session["session_id"], "user_input": "胃胀一周，饭后明显"},
        )
        self.assertEqual(turn.status_code, 200, turn.text)
        payload = turn.json()
        self.assertTrue(payload["schema_pass"])
        self.assertIn("real_llm", payload["external_dependencies_skipped"])
        self.assertEqual(self.client.get(f"/sessions/{session['session_id']}").status_code, 200)
        report = self.client.get(f"/reports/{session['session_id']}")
        self.assertEqual(report.status_code, 200, report.text)
        self.assertIn(report.json()["report_status"], {"not_ready", "ready"})
        smoke = self.client.post("/eval/smoke")
        self.assertEqual(smoke.status_code, 200, smoke.text)
        self.assertFalse(smoke.json()["external_dependencies_required"])

    def test_p1_f2_turn_and_report_expose_evidence_pack_and_skeleton(self) -> None:
        session = self.client.post(
            "/sessions",
            json={"extractor_backend": "fake", "rag_enabled": True},
        )
        self.assertEqual(session.status_code, 200, session.text)
        session_id = session.json()["session_id"]

        turn = self.client.post(
            "/turn",
            json={"session_id": session_id, "user_input": COMPLETE_P1_INPUT},
        )
        self.assertEqual(turn.status_code, 200, turn.text)
        turn_payload = turn.json()
        self.assertEqual(turn_payload["next_action"], "review_summary")
        self.assertEqual(turn_payload["evidence_pack"]["backend"], "bm25_realpath")
        self.assertEqual(
            turn_payload["report_skeleton"]["evidence_pack"]["backend"],
            "bm25_realpath",
        )
        self.assertEqual(
            turn_payload["report_skeleton"]["schema_version"],
            "p1_f0_report_skeleton_v1",
        )

        report = self.client.get(f"/reports/{session_id}")
        self.assertEqual(report.status_code, 200, report.text)
        report_payload = report.json()
        self.assertEqual(report_payload["report_status"], "ready")
        self.assertEqual(report_payload["evidence_pack"]["backend"], "bm25_realpath")
        self.assertEqual(
            report_payload["report_skeleton"]["evidence_pack"]["backend"],
            "bm25_realpath",
        )
        self.assertEqual(
            report_payload["skeleton"]["evidence_pack"]["backend"],
            "bm25_realpath",
        )


if __name__ == "__main__":
    unittest.main()
