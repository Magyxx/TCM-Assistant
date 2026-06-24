import unittest

from app.extractors import (
    FakeTurnExtractor,
    FallbackTurnExtractor,
    OpenAICompatibleTurnExtractor,
    run_extractor_probe,
)
from app.schemas.report_schemas import RunState


class ExtractorBoundaryTests(unittest.TestCase):
    def test_fake_extractor_reports_schema_valid_non_fallback(self) -> None:
        probe = run_extractor_probe(
            FakeTurnExtractor(),
            "stomach discomfort for two days, no other symptoms",
            RunState(),
        )

        self.assertEqual(probe.requested_mode, "fake")
        self.assertEqual(probe.status, "ok")
        self.assertFalse(probe.fallback_used)
        self.assertTrue(probe.final_schema_pass)

    def test_fallback_extractor_keeps_rule_risk_auditable(self) -> None:
        probe = run_extractor_probe(
            FallbackTurnExtractor(),
            "\u80f8\u75db\uff0c\u5598\u4e0d\u4e0a\u6c14",
            RunState(),
        )

        self.assertEqual(probe.requested_mode, "fallback")
        self.assertEqual(probe.status, "ok")
        self.assertTrue(probe.fallback_used)
        self.assertTrue(probe.final_schema_pass)
        self.assertEqual(probe.risk_flags_status, "present")

    def test_real_llm_extractor_safely_falls_back_or_reports_real_result(self) -> None:
        extractor = OpenAICompatibleTurnExtractor()
        probe = run_extractor_probe(
            extractor,
            "stomach discomfort for two days, no chest pain",
            RunState(),
        )

        self.assertEqual(probe.requested_mode, "real_llm")
        self.assertIn(probe.status, {"ok", "skipped"})
        self.assertTrue(probe.final_schema_pass)
        if extractor.missing_config():
            self.assertTrue(probe.fallback_used)
            self.assertEqual(probe.error_type, "missing_api_config")


if __name__ == "__main__":
    unittest.main()
