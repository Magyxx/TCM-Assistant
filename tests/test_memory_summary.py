from __future__ import annotations

import unittest

from app.memory.manager import MemoryManager
from app.memory.summary import build_case_summary
from app.schemas.report_schemas import TurnOutput


class MemorySummaryTests(unittest.TestCase):
    def test_case_summary_is_generated_from_l2_facts_only(self) -> None:
        manager = MemoryManager()
        memory = manager.apply_turn(
            turn_output=TurnOutput(chief_complaint="cough", duration="three days"),
            user_input="cough for three days",
            turn_id="t1",
            turn_index=1,
            extractor_mode="fake",
        )

        before = memory.facts["chief_complaint"].value
        summary = build_case_summary(memory)
        summary.summary = "edited summary should not write back"

        self.assertTrue(summary.generated_from_l2_only)
        self.assertEqual(memory.facts["chief_complaint"].value, before)
        self.assertIn("chief_complaint=cough", memory.case_summary.summary)


if __name__ == "__main__":
    unittest.main()
