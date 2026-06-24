from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.deps import get_p7_store, set_consultation_service_override
from app.api.app import app as p1_app
from app.api.main import app as main_app
from app.api.session_runtime import clear_sessions
from app.report.audit import REPORT_AUDIT_SCHEMA_VERSION, build_report_audit
from app.report.safety import check_report_safety
from app.services.consultation_service import ConsultationService


COMPLETE_P1_INPUT = (
    "\u80c3\u80c0\u4e00\u5468\uff0c\u6ca1\u6709\u5176\u4ed6\u75c7\u72b6\uff0c"
    "\u7761\u7720\u4e00\u822c\uff0c\u98df\u6b32\u4e00\u822c\uff0c"
    "\u5927\u4fbf\u6b63\u5e38\uff0c\u5c0f\u4fbf\u6b63\u5e38\uff0c"
    "\u6ca1\u6709\u80f8\u75db\uff0c\u6ca1\u6709\u547c\u5438\u56f0\u96be\uff0c\u6ca1\u6709\u4fbf\u8840"
)
SYNTHETIC_SECRET = "sk-p1f5syntheticsecret"


class P1F5ReportAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        tmp_path = Path(self.tmp.name)
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
        self.session_db = tmp_path / "sessions.sqlite3"
        os.environ["API_LOG_PATH"] = str(tmp_path / "api_events.jsonl")
        os.environ["ENABLE_REAL_LLM"] = "false"
        os.environ["EXTRACTOR_BACKEND"] = "fake"
        os.environ["SESSION_SQLITE_PATH"] = str(self.session_db)
        os.environ["SESSION_STORE_BACKEND"] = "sqlite"
        os.environ["TCM_API_DB_PATH"] = str(tmp_path / "api.sqlite3")
        os.environ["TCM_SQLITE_PATH"] = str(tmp_path / "p7.sqlite3")
        clear_sessions()
        set_consultation_service_override(
            ConsultationService(sqlite_path=self.session_db, api_log_path=tmp_path / "api_events.jsonl")
        )
        self.client = TestClient(main_app, raise_server_exceptions=False)

    def tearDown(self) -> None:
        self.client.close()
        clear_sessions()
        set_consultation_service_override(None)
        for name, value in self.previous_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        self.tmp.cleanup()

    def test_safety_checker_flags_chinese_claims_and_dose_like_text(self) -> None:
        result = check_report_safety("\u8bca\u65ad\u4e3a\u67d0\u75c5\uff0c\u6cbb\u7597\u65b9\u6848\uff1a\u6bcf\u65e5 10mg")
        self.assertFalse(result.ok)
        self.assertIn("diagnosis_claim", result.violations)
        self.assertIn("treatment_plan_claim", result.violations)
        self.assertIn("drug_dose_like", result.violations)

    def test_report_audit_redacts_secret_and_fails_when_secret_present(self) -> None:
        audit = build_report_audit(
            {
                "summary": f"safe summary {SYNTHETIC_SECRET}",
                "advice": ["Continue observation."],
                "safety_disclaimer": "This system is not a diagnosis.",
            },
            {"risk_flags_status": "none"},
            route="unit",
            session_id="session",
            ready=True,
        )

        serialized = json.dumps(audit, ensure_ascii=False, sort_keys=True)
        self.assertEqual(audit["schema_version"], REPORT_AUDIT_SCHEMA_VERSION)
        self.assertFalse(audit["passed"])
        self.assertFalse(audit["checks"]["no_secret"])
        self.assertNotIn(SYNTHETIC_SECRET, serialized)
        self.assertTrue(audit["redacted_report_hash"])

    def test_api_report_paths_return_safe_audit_and_persist_it(self) -> None:
        created = self.client.post(
            "/sessions",
            json={"backend": "fake", "metadata": {"test": "p1_f5_report_audit"}},
        )
        self.assertEqual(created.status_code, 200, created.text)
        session_id = created.json()["session_id"]

        turn = self.client.post(
            f"/sessions/{session_id}/turn",
            json={"user_input": COMPLETE_P1_INPUT, "extractor_backend": "fake"},
        )
        self.assertEqual(turn.status_code, 200, turn.text)
        turn_payload = turn.json()
        self.assertEqual(turn_payload["report_audit"]["schema_version"], REPORT_AUDIT_SCHEMA_VERSION)
        self.assertTrue(turn_payload["report_audit"]["passed"])
        self.assertTrue(turn_payload["report_audit"]["checks"]["no_secret"])

        report = self.client.get(f"/sessions/{session_id}/report")
        self.assertEqual(report.status_code, 200, report.text)
        report_payload = report.json()
        self.assertTrue(report_payload["report_available"])
        self.assertTrue(report_payload["report_audit"]["passed"])
        self.assertEqual(report_payload["report_audit"]["route"], "GET /sessions/{session_id}/report")

        with TestClient(p1_app, raise_server_exceptions=False) as p1_client:
            wrapper_report = p1_client.get(f"/reports/{session_id}")
        self.assertEqual(wrapper_report.status_code, 200, wrapper_report.text)
        wrapper_payload = wrapper_report.json()
        self.assertEqual(wrapper_payload["report_status"], "ready")
        self.assertTrue(wrapper_payload["report_audit"]["passed"])

        persisted = self.client.post(f"/sessions/{session_id}/report")
        self.assertEqual(persisted.status_code, 200, persisted.text)
        bundle = get_p7_store().fetch_session_bundle(session_id) or {}
        final_reports = bundle.get("final_reports") or []
        self.assertTrue(final_reports)
        safety_check = final_reports[-1]["safety_check"]
        self.assertTrue(safety_check["passed"])
        self.assertTrue(safety_check["p1_f5_report_audit"]["passed"])
        self.assertEqual(
            safety_check["p1_f5_report_audit"]["schema_version"],
            REPORT_AUDIT_SCHEMA_VERSION,
        )


if __name__ == "__main__":
    unittest.main()
