from __future__ import annotations

import unittest

from app.extractors.fallback_extractor import FallbackTurnExtractor
from app.schemas.report_schemas import RunState, TurnOutput


class ExtractorFallbackModeTests(unittest.TestCase):
    def test_fallback_mode_is_schema_valid_and_marks_fallback_used(self) -> None:
        result = FallbackTurnExtractor().extract("胸痛，喘不上气", state=RunState())

        self.assertEqual(result.mode, "fallback")
        self.assertTrue(result.schema_pass)
        self.assertTrue(result.fallback_used)
        self.assertIsInstance(result.turn_output, TurnOutput)
        self.assertEqual(result.turn_output.risk_flags_status, "present")


if __name__ == "__main__":
    unittest.main()
