from __future__ import annotations

import json
import unittest

from app.api.errors import ApiError
from app.api.report_audit import assert_report_safe, audit_report
from app.schemas.report_schemas import FinalReport


BOUNDARY = "\u672c\u7cfb\u7edf\u4e0d\u662f\u8bca\u65ad\uff0c\u4ec5\u7528\u4e8e\u95ee\u8bca\u4fe1\u606f\u6574\u7406\u3002"


def make_report(impression: str | None = None, advice: list[str] | None = None) -> FinalReport:
    return FinalReport(
        summary="\u4e3b\u8bc9\uff1a\u80c3\u80c0",
        impression=impression or f"\u5f53\u524d\u4fe1\u606f\u7528\u4e8e\u95ee\u8bca\u6574\u7406\u3002{BOUNDARY}",
        advice=advice or ["\u5efa\u8bae\u8bb0\u5f55\u75c7\u72b6\u53d8\u5316\u3002"],
        triage_level="observe",
        info_complete=True,
        missing_core_fields=[],
        followup_needed=False,
    )


class P15ReportAuditTests(unittest.TestCase):
    def _codes(self, audit: dict) -> set[str]:
        return {flag["code"] for flag in audit["flags"]}

    def test_safe_report_passes(self) -> None:
        audit = audit_report(make_report())

        self.assertTrue(audit["passed"])
        self.assertEqual(audit["flags"], [])
        assert_report_safe(make_report())

    def test_diagnosis_phrase_fails(self) -> None:
        audit = audit_report(make_report("\u8bca\u65ad\u4e3a\u67d0\u75c5\u3002"))

        self.assertFalse(audit["passed"])
        self.assertIn("diagnosis_phrase", self._codes(audit))

    def test_prescription_phrase_fails(self) -> None:
        audit = audit_report(make_report(advice=["\u5efa\u8bae\u4f7f\u7528\u5904\u65b9\u836f\u3002"]))

        self.assertFalse(audit["passed"])
        self.assertIn("prescription_phrase", self._codes(audit))

    def test_treatment_plan_phrase_fails(self) -> None:
        audit = audit_report(make_report("\u8fd9\u662f\u4e00\u4e2a\u6cbb\u7597\u65b9\u6848\u3002"))

        self.assertFalse(audit["passed"])
        self.assertIn("treatment_plan_phrase", self._codes(audit))

    def test_drug_dose_like_text_is_flagged(self) -> None:
        audit = audit_report(make_report(advice=["\u963f\u83ab\u897f\u6797 500mg \u6bcf\u65e5\u4e24\u6b21\u3002"]))

        self.assertFalse(audit["passed"])
        self.assertIn("drug_dose_like", self._codes(audit))

    def test_secret_like_text_fails_and_is_redacted(self) -> None:
        secret = "sk-" + "auditsecret1234567890"
        audit = audit_report(make_report(advice=[f"OPENAI_API_KEY={secret}"]))
        serialized = json.dumps(audit, ensure_ascii=False)

        self.assertFalse(audit["passed"])
        self.assertIn("secret_like", self._codes(audit))
        self.assertNotIn(secret, serialized)
        self.assertNotIn("OPENAI_API_KEY", serialized)

    def test_empty_report_behavior_is_clear(self) -> None:
        audit = audit_report({})

        self.assertFalse(audit["passed"])
        self.assertIn("empty_report", self._codes(audit))

    def test_dict_and_list_reports_are_supported(self) -> None:
        report = {
            "summary": "\u4e3b\u8bc9\uff1a\u80c3\u80c0",
            "impression": BOUNDARY,
            "advice": ["\u8bb0\u5f55\u75c7\u72b6\u53d8\u5316\u3002"],
        }

        self.assertTrue(audit_report(report)["passed"])
        self.assertTrue(audit_report([report])["passed"])

    def test_audit_payload_is_json_serializable(self) -> None:
        audit = audit_report(make_report())

        encoded = json.dumps(audit, ensure_ascii=False)
        self.assertIn("checked_at", encoded)
        self.assertIn("rules", encoded)

    def test_assert_report_safe_raises_api_error(self) -> None:
        with self.assertRaises(ApiError):
            assert_report_safe(make_report("\u8bca\u65ad\u4e3a\u67d0\u75c5\u3002"))


if __name__ == "__main__":
    unittest.main()
