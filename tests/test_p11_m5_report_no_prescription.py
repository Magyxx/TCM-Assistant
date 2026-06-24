from __future__ import annotations

import unittest

from app.report.safety import check_report_safety
from app.safety.report_safety import FORBIDDEN_PHRASES, safety_post_check_report
from app.schemas.report_schemas import FinalReport


def _report(advice: list[str]) -> FinalReport:
    return FinalReport(
        summary="Structured intake summary.",
        impression="Inquiry support only.",
        advice=advice,
        triage_level="followup",
        info_complete=True,
        missing_core_fields=[],
        followup_needed=False,
    )


class P11M5NoPrescriptionTests(unittest.TestCase):
    def test_text_safety_checker_flags_prescription_claims(self) -> None:
        result = check_report_safety("Please prescribe 10mg medicine.")

        self.assertFalse(result.ok)
        self.assertIn("prescription_claim", result.violations)

    def test_final_report_post_check_rewrites_prescription_like_terms(self) -> None:
        prescription_phrase = FORBIDDEN_PHRASES[4]
        result = safety_post_check_report(_report([f"{prescription_phrase}: unsafe claim."]))
        text = result.report.summary + result.report.impression + "".join(result.report.advice)

        self.assertTrue(result.rewritten)
        self.assertNotIn(prescription_phrase, text)
        self.assertTrue(result.report.metadata["safety_rewrite_used"])
        self.assertIn("safety_post_check_issues", result.report.metadata)


if __name__ == "__main__":
    unittest.main()
