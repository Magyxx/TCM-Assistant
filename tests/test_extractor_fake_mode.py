from __future__ import annotations

import unittest

from app.extractors.fake_extractor import FakeTurnExtractor
from app.schemas.report_schemas import RunState, TurnOutput


class ExtractorFakeModeTests(unittest.TestCase):
    def test_fake_mode_returns_schema_valid_turn_output(self) -> None:
        result = FakeTurnExtractor().extract("胃胀两天，没有其他症状", state=RunState())

        self.assertEqual(result.mode, "fake")
        self.assertTrue(result.schema_pass)
        self.assertFalse(result.fallback_used)
        self.assertIsInstance(result.turn_output, TurnOutput)
        self.assertEqual(result.turn_output.chief_complaint, "胃胀")
        self.assertEqual(result.metadata["adapter"] if "adapter" in result.metadata else result.metadata["legacy_extractor_mode"], "fake")


if __name__ == "__main__":
    unittest.main()
