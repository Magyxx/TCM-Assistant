from __future__ import annotations

import unittest

from app.extractors.adapter import P11_EXTRACTOR_CONTRACT_FIELDS, validate_extractor_result_contract
from app.extractors.result import ExtractorResult
from app.schemas.report_schemas import TurnOutput


class P11M2ExtractorResultContractTests(unittest.TestCase):
    def test_contract_summary_exposes_required_fields(self) -> None:
        result = ExtractorResult.from_turn_output(
            mode="fake",
            turn_output=TurnOutput(summary="candidate"),
            metadata={"backend": "fake", "repair_used": False},
            latency_ms=1.25,
        )

        summary = result.contract_summary()

        for field in P11_EXTRACTOR_CONTRACT_FIELDS:
            with self.subTest(field=field):
                self.assertIn(field, summary)
        self.assertEqual(summary["backend_name"], "fake")
        self.assertEqual(summary["backend_mode"], "fake")
        self.assertTrue(summary["schema_pass"])
        self.assertFalse(summary["fallback_used"])
        self.assertEqual(summary["retry_count"], 0)
        self.assertEqual(validate_extractor_result_contract(result), [])

    def test_schema_failure_summary_keeps_error_and_raw_json_state(self) -> None:
        result = ExtractorResult.schema_failure(
            mode="local_lora",
            raw_output="not json",
            error="json_parse_failed",
            metadata={"raw_llm_json_valid": False, "json_valid": False, "repair_used": False},
        )

        summary = result.contract_summary()

        self.assertFalse(summary["schema_pass"])
        self.assertFalse(summary["candidate_schema_pass"])
        self.assertEqual(summary["schema_guard"], "failed")
        self.assertEqual(summary["error_type"], "extractor_error")
        self.assertFalse(summary["raw_llm_json_valid"])
        self.assertFalse(summary["repair_used"])
        self.assertEqual(summary["retry_count"], 0)


if __name__ == "__main__":
    unittest.main()
