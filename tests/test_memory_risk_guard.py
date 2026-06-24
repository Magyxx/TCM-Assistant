from __future__ import annotations

import unittest

from app.memory.manager import MemoryManager
from app.memory.merge_policy import merge_fact
from app.memory.models import ConsultationMemory, MemoryFact
from app.schemas.report_schemas import TurnOutput


class MemoryRiskGuardTests(unittest.TestCase):
    def test_llm_turn_output_cannot_write_risk_status(self) -> None:
        manager = MemoryManager()
        memory = manager.apply_turn(
            turn_output=TurnOutput(risk_flags_status="present", risk_flags=["chest pain"]),
            user_input="ordinary text from extractor",
            turn_id="t1",
            turn_index=1,
            extractor_mode="fake",
        )

        self.assertIsNone(memory.facts.get("risk_flags_status"))
        self.assertTrue(
            any(event.reason == "llm_candidate_cannot_write_risk_authority" for event in memory.audit_events)
        )

    def test_high_risk_present_is_sticky_against_later_none(self) -> None:
        manager = MemoryManager()
        memory = manager.apply_turn(
            turn_output=TurnOutput(chief_complaint="chest tightness"),
            user_input="chest tightness and shortness of breath",
            turn_id="t1",
            turn_index=1,
            extractor_mode="fake",
            risk_evaluation={
                "risk_status": "present",
                "risk_flags": ["dyspnea"],
                "risk_rule_ids": ["P0_RISK_DYSPNEA"],
                "risk_reasons": ["shortness of breath"],
            },
        )

        memory = manager.apply_turn(
            memory=memory,
            turn_output=TurnOutput(symptoms_status="none"),
            user_input="no chest pain now",
            turn_id="t2",
            turn_index=2,
            extractor_mode="fake",
            risk_evaluation={
                "risk_status": "none",
                "negated_rule_ids": ["P0_RISK_CHEST_PAIN"],
            },
        )

        self.assertEqual(memory.fact_value("risk_flags_status"), "present")
        self.assertTrue(any(event.reason == "high_risk_present_is_sticky" for event in memory.audit_events))

    def test_explicit_negation_is_recorded_as_negation_not_unknown(self) -> None:
        manager = MemoryManager()
        memory = manager.apply_turn(
            turn_output=TurnOutput(symptoms_status="none"),
            user_input="no other symptoms",
            turn_id="t1",
            turn_index=1,
            extractor_mode="fake",
        )

        fact = memory.facts["symptoms_status"]
        self.assertEqual(fact.value, "none")
        self.assertTrue(fact.explicit_negation)

    def test_rag_evidence_cannot_write_risk_aliases(self) -> None:
        memory = ConsultationMemory()
        memory, event = merge_fact(
            memory,
            MemoryFact(
                field_name="risk_status",
                value="none",
                source_turn_id="rag1",
                raw_text="retrieved text",
                extractor_mode="bm25",
                confidence=1.0,
                source_kind="rag_evidence",
            ),
        )

        self.assertFalse(event.applied)
        self.assertEqual(event.reason, "rag_evidence_forbidden_for_core_field")
        self.assertNotIn("risk_flags_status", memory.facts)


if __name__ == "__main__":
    unittest.main()
