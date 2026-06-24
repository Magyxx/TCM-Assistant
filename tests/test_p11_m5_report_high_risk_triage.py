from __future__ import annotations

import unittest

from app.safety.report_safety import SAFETY_BOUNDARY_TEXT, safety_post_check_report
from app.schemas.report_schemas import FinalReport


class P11M5HighRiskTriageTests(unittest.TestCase):
    def test_high_risk_triage_is_preserved_and_boundary_is_added(self) -> None:
        report = FinalReport(
            summary="Structured intake summary.",
            impression="High risk signal reported; offline medical evaluation is recommended.",
            advice=["Seek urgent offline medical evaluation."],
            triage_level="urgent_visit",
            info_complete=True,
            missing_core_fields=[],
            followup_needed=False,
            metadata={"risk_status": "present"},
        )

        result = safety_post_check_report(report)

        self.assertFalse(result.rewritten)
        self.assertEqual(result.report.triage_level, "urgent_visit")
        self.assertIn("Seek urgent offline medical evaluation.", result.report.advice)
        self.assertIn(SAFETY_BOUNDARY_TEXT, result.report.impression)
        self.assertIn(SAFETY_BOUNDARY_TEXT, result.report.advice)
        self.assertFalse(result.report.metadata["safety_rewrite_used"])


if __name__ == "__main__":
    unittest.main()
