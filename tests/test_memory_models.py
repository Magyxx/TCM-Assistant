from __future__ import annotations

import unittest

from app.memory.models import ConsultationMemory, MemoryFact


class MemoryModelTests(unittest.TestCase):
    def test_fact_requires_traceability_fields(self) -> None:
        fact = MemoryFact(
            field_name="chief_complaint",
            value="stomach discomfort",
            source_turn_id="t1",
            raw_text="I have stomach discomfort",
            extractor_mode="fake",
            confidence=0.9,
        )

        self.assertEqual(fact.source_turn_id, "t1")
        self.assertEqual(fact.raw_text, "I have stomach discomfort")
        self.assertEqual(fact.extractor_mode, "fake")
        self.assertEqual(fact.confidence, 0.9)

    def test_consultation_memory_has_disabled_l4_interface(self) -> None:
        memory = ConsultationMemory(session_id="s1")

        self.assertFalse(memory.l4_experience.enabled)
        self.assertFalse(memory.l4_experience.contains_raw_patient_text)
        self.assertFalse(memory.l4_experience.contains_patient_identifier)
        self.assertEqual(memory.l4_experience.stored_items, [])


if __name__ == "__main__":
    unittest.main()
