from __future__ import annotations

import unittest

from app.report.safety import check_report_safety
from app.safety.report_safety import FORBIDDEN_PHRASES, safety_post_check_report
from app.schemas.report_schemas import FinalReport


def _report(impression: str) -> FinalReport:
    return FinalReport(
        summary="Structured intake summary.",
        impression=impression,
        advice=["Track symptom changes and seek offline care for red flags."],
        triage_level="observe",
        info_complete=True,
        missing_core_fields=[],
        followup_needed=False,
    )


class P11M5NoDiagnosisTests(unittest.TestCase):
    def test_text_safety_checker_flags_diagnosis_claims(self) -> None:
        result = check_report_safety("The patient is diagnosed with a named condition.")

        self.assertFalse(result.ok)
        self.assertIn("diagnosis_claim", result.violations)

    def test_final_report_post_check_rewrites_diagnosis_like_terms(self) -> None:
        diagnosis_phrase = FORBIDDEN_PHRASES[0]
        result = safety_post_check_report(_report(f"{diagnosis_phrase}: unsafe claim."))
        text = result.report.summary + result.report.impression + "".join(result.report.advice)

        self.assertTrue(result.rewritten)
        self.assertNotIn(diagnosis_phrase, text)
        self.assertTrue(result.report.metadata["safety_rewrite_used"])
        self.assertEqual(result.report.metadata["safety_violation_type"], "report_boundary_rewrite")


if __name__ == "__main__":
    unittest.main()
