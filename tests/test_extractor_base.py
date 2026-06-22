from __future__ import annotations

import unittest

from app.extractors.base import BaseExtractor
from app.extractors.result import ExtractorResult
from app.schemas.report_schemas import RunState, TurnOutput


class ExtractorBaseTests(unittest.TestCase):
    def test_extractor_result_schema_contains_required_fields(self) -> None:
        result = ExtractorResult(
            mode="fake",
            raw_output={"chief_complaint": "cough"},
            parsed_output={"chief_complaint": "cough"},
            turn_output=TurnOutput(chief_complaint="cough"),
            schema_pass=True,
            fallback_used=False,
            metadata={"raw_llm_json_valid": True},
        )

        self.assertEqual(result.status, "passed")
        self.assertEqual(result.mode, "fake")
        self.assertTrue(result.schema_pass)
        self.assertFalse(result.fallback_used)
        self.assertIsNone(result.skip_reason)

    def test_base_extractor_coerces_state_dict(self) -> None:
        base = BaseExtractor()
        state = base._coerce_state({"chief_complaint": "cough"})

        self.assertIsInstance(state, RunState)
        self.assertEqual(state.chief_complaint, "cough")

    def test_schema_failure_records_metadata(self) -> None:
        result = ExtractorResult.schema_failure(
            mode="bad",
            raw_output="{bad json",
            error="json_parse_failed",
            metadata={"repair_used": False},
        )

        self.assertEqual(result.status, "failed")
        self.assertFalse(result.schema_pass)
        self.assertIsNone(result.turn_output)
        self.assertEqual(result.metadata["schema_guard"], "failed")
        self.assertFalse(result.metadata["repair_used"])


if __name__ == "__main__":
    unittest.main()
