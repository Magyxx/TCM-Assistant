import unittest

from app.chains.turn_extractor import build_fake_turn_output, extract_turn
from app.schemas.report_schemas import RunState
from scripts.run_p5_real_runtime_validation import run_extractor_mode_checks


class P5ExtractorModeTests(unittest.TestCase):
    def test_fake_extractor_collects_non_risk_supplemental_fields(self) -> None:
        output = build_fake_turn_output(
            RunState(),
            "睡眠一般，食欲下降，大便偏干，小便正常，没有其他症状",
        )

        self.assertEqual(output.sleep, "睡眠一般")
        self.assertEqual(output.appetite, "食欲下降")
        self.assertIn("大便偏干", output.stool_urine or "")
        self.assertEqual(output.symptoms_status, "none")
        self.assertEqual(output.risk_flags_status, "unknown")

    def test_rule_fallback_records_high_risk_without_success_spoofing(self) -> None:
        result = extract_turn(
            RunState(),
            "胸痛、胸闷、喘不上气",
            extractor_mode="fallback",
        )

        self.assertFalse(result.success)
        self.assertTrue(result.fallback_used)
        self.assertEqual(result.mode, "rule_fallback")
        self.assertEqual(result.turn_output.risk_flags_status, "present")

    def test_extractor_mode_summary_keeps_fake_fallback_real_llm_separate(self) -> None:
        result = run_extractor_mode_checks(probe_real_llm=False, real_llm_timeout_seconds=1)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["separated_mode_names"], ["fake", "rule_fallback", "real_llm"])
        self.assertFalse(result["fake_extractor"]["fallback_used"])
        self.assertTrue(result["rule_fallback"]["fallback_used"])
        self.assertEqual(result["real_llm"]["availability"], "not_probed")


if __name__ == "__main__":
    unittest.main()
