from __future__ import annotations

import unittest
from unittest.mock import patch

from app.chains.turn_extractor import ExtractionResult as LegacyExtractionResult
from app.extractors.openai_compatible_extractor import OpenAICompatibleTurnExtractor
from app.schemas.report_schemas import RunState, TurnOutput


class ExtractorRealLlmSkipTests(unittest.TestCase):
    def test_real_llm_missing_config_is_safe_skip(self) -> None:
        legacy = LegacyExtractionResult(
            success=False,
            turn_output=TurnOutput(summary="fallback"),
            raw_text=None,
            error="missing_api_config",
            mode="rule_fallback",
            schema_valid=True,
            final_schema_pass=True,
            fallback_used=True,
            extractor_mode="real_llm",
            error_type="missing_api_config",
        )
        with patch(
            "app.extractors.openai_compatible_extractor.get_missing_api_config",
            return_value=["OPENAI_API_KEY"],
        ), patch(
            "app.extractors.openai_compatible_extractor.extract_turn",
            return_value=legacy,
        ):
            result = OpenAICompatibleTurnExtractor().extract("胃胀两天", state=RunState())

        self.assertEqual(result.mode, "real_llm")
        self.assertEqual(result.status, "skipped")
        self.assertEqual(result.skip_reason, "missing_api_config:OPENAI_API_KEY")
        self.assertTrue(result.schema_pass)
        self.assertTrue(result.fallback_used)
        self.assertEqual(result.metadata["error_type"], "missing_api_config")


if __name__ == "__main__":
    unittest.main()
