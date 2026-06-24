from __future__ import annotations

import unittest

from app.memory.manager import MemoryManager
from app.schemas.report_schemas import TurnOutput


class MemoryManagerApplyTurnTests(unittest.TestCase):
    def test_valid_turn_output_enters_l2_and_exports_run_state(self) -> None:
        manager = MemoryManager(max_recent_turns=3)
        memory = manager.apply_turn(
            turn_output=TurnOutput(
                chief_complaint="stomach discomfort",
                duration="two days",
                symptoms_status="none",
            ),
            user_input="stomach discomfort for two days, no other symptoms",
            turn_id="t1",
            turn_index=1,
            extractor_mode="fake",
        )
        state = manager.export_run_state(memory)

        self.assertEqual(len(memory.recent_turns), 1)
        self.assertEqual(memory.fact_value("chief_complaint"), "stomach discomfort")
        self.assertEqual(memory.facts["chief_complaint"].source_turn_id, "t1")
        self.assertEqual(memory.facts["chief_complaint"].raw_text, "stomach discomfort for two days, no other symptoms")
        self.assertEqual(memory.facts["chief_complaint"].extractor_mode, "fake")
        self.assertEqual(state.chief_complaint, "stomach discomfort")
        self.assertEqual(state.duration, "two days")
        self.assertIn("p8_memory", state.metadata)
        self.assertTrue(any(event.reason == "schema_validation_passed" for event in memory.audit_events))

    def test_invalid_turn_output_is_audited_and_does_not_enter_l2(self) -> None:
        manager = MemoryManager()
        memory = manager.apply_turn(
            turn_output={"chief_complaint": "cough", "symptoms": "not-a-list"},
            user_input="cough",
            turn_id="t1",
            turn_index=1,
            extractor_mode="broken",
        )

        self.assertEqual(memory.facts, {})
        self.assertTrue(any(event.reason.startswith("schema_validation_failed") for event in memory.audit_events))

    def test_recent_turns_are_bounded(self) -> None:
        manager = MemoryManager(max_recent_turns=2)
        memory = None
        for index in range(3):
            memory = manager.apply_turn(
                memory=memory,
                turn_output=TurnOutput(chief_complaint=f"complaint-{index}"),
                user_input=f"turn {index}",
                turn_id=f"t{index}",
                turn_index=index,
                extractor_mode="fake",
                explicit_corrections=["chief_complaint"],
            )

        self.assertIsNotNone(memory)
        self.assertEqual([turn.turn_id for turn in memory.recent_turns], ["t1", "t2"])


if __name__ == "__main__":
    unittest.main()
