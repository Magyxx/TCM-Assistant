import unittest

from app.memory.consultation_memory import ConsultationMemoryManager
from app.schemas.report_schemas import RunState


class P42MemoryManagerTests(unittest.TestCase):
    def test_high_risk_present_is_sticky(self) -> None:
        manager = ConsultationMemoryManager()
        previous = RunState(
            risk_flags_status="present",
            risk_flags=["胸痛"],
            risk_reasons=["user mentioned chest pain"],
            triggered_rule_ids=["P0_RISK_CHEST_PAIN"],
        )
        candidate = RunState(risk_flags_status="none")

        protected = manager.enforce_high_risk_sticky(previous, candidate)

        self.assertEqual(protected.risk_flags_status, "present")
        self.assertIn("胸痛", protected.risk_flags)
        self.assertIn("P0_RISK_CHEST_PAIN", protected.triggered_rule_ids)
        self.assertTrue(protected.metadata["p4_memory_high_risk_sticky_applied"])

    def test_memory_snapshot_is_not_user_profile(self) -> None:
        manager = ConsultationMemoryManager()
        current = RunState(chief_complaint="胃胀", duration="两天", risk_flags_status="none", turn_count=1)

        snapshot = manager.update(
            previous_state=RunState(),
            current_state=current,
            user_input="胃胀两天",
            trace=[{"name": "merge_state"}],
        )

        self.assertFalse(snapshot.is_user_profile)
        self.assertTrue(snapshot.l2_authoritative_state["authoritative"])
        self.assertFalse(snapshot.l4_long_term_memory["contains_raw_patient_pii"])
        self.assertEqual(snapshot.field_sources["chief_complaint"], "current_turn_validated_extraction")
        self.assertEqual(snapshot.trace[0]["name"], "merge_state")


if __name__ == "__main__":
    unittest.main()

