from __future__ import annotations

import unittest

from app.memory.merge_policy import merge_fact
from app.memory.models import ConsultationMemory, MemoryFact


def fact(field_name: str, value: object, *, confidence: float = 1.0, source_kind: str = "validated_turn_output") -> MemoryFact:
    return MemoryFact(
        field_name=field_name,
        value=value,
        source_turn_id="t1",
        raw_text="raw",
        extractor_mode="fake",
        confidence=confidence,
        source_kind=source_kind,  # type: ignore[arg-type]
    )


class MemoryMergePolicyTests(unittest.TestCase):
    def test_empty_candidate_cannot_overwrite_non_empty_fact(self) -> None:
        memory = ConsultationMemory()
        memory, _ = merge_fact(memory, fact("duration", "two days", confidence=0.9))

        memory, event = merge_fact(memory, fact("duration", None, confidence=1.0))

        self.assertFalse(event.applied)
        self.assertEqual(event.reason, "empty_candidate_cannot_overwrite_non_empty_fact")
        self.assertEqual(memory.fact_value("duration"), "two days")

    def test_low_confidence_cannot_overwrite_without_explicit_correction(self) -> None:
        memory = ConsultationMemory()
        memory, _ = merge_fact(memory, fact("chief_complaint", "cough", confidence=0.95))

        memory, event = merge_fact(memory, fact("chief_complaint", "headache", confidence=0.3))

        self.assertFalse(event.applied)
        self.assertEqual(event.reason, "low_confidence_candidate_cannot_overwrite_higher_confidence_fact")
        self.assertEqual(memory.fact_value("chief_complaint"), "cough")

    def test_explicit_correction_can_overwrite_lower_confidence(self) -> None:
        memory = ConsultationMemory()
        memory, _ = merge_fact(memory, fact("duration", "two days", confidence=0.95))

        memory, event = merge_fact(memory, fact("duration", "three days", confidence=0.3), explicit_correction=True)

        self.assertTrue(event.applied)
        self.assertEqual(memory.fact_value("duration"), "three days")

    def test_rag_evidence_cannot_overwrite_core_fields(self) -> None:
        memory = ConsultationMemory()
        memory, _ = merge_fact(memory, fact("chief_complaint", "cough", confidence=0.95))

        memory, event = merge_fact(
            memory,
            fact("chief_complaint", "retrieved diagnosis text", confidence=1.0, source_kind="rag_evidence"),
        )

        self.assertFalse(event.applied)
        self.assertEqual(event.reason, "rag_evidence_forbidden_for_core_field")
        self.assertEqual(memory.fact_value("chief_complaint"), "cough")


if __name__ == "__main__":
    unittest.main()
