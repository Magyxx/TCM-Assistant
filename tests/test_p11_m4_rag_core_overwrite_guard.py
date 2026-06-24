from __future__ import annotations

import unittest

from app.memory.models import ConsultationMemory, MemoryFact
from app.rag.rag_guard import assert_memory_l2_unchanged, guard_rag_update


class P11M4RagCoreOverwriteGuardTests(unittest.TestCase):
    def test_rag_cannot_write_core_inquiry_or_risk_fields(self) -> None:
        for field in ["chief_complaint", "duration", "risk_status", "risk_rule_ids", "triggered_rule_ids"]:
            with self.subTest(field=field):
                result = guard_rag_update({field: "retrieved evidence"})
                self.assertFalse(result.allowed)
                self.assertIn(field, result.blocked_fields)

    def test_rag_can_write_evidence_context_only(self) -> None:
        result = guard_rag_update({"retrieved_evidence": [{"chunk_id": "c1"}], "citations": [{"chunk_id": "c1"}]})

        self.assertTrue(result.allowed)

    def test_rag_cannot_mutate_authoritative_memory_facts(self) -> None:
        before = ConsultationMemory(
            facts={
                "chief_complaint": MemoryFact(
                    field_name="chief_complaint",
                    value="stomach discomfort",
                    source_turn_id="turn-1",
                    raw_text="stomach discomfort",
                    extractor_mode="fake",
                )
            }
        )
        after = before.model_copy(deep=True)
        after.facts["chief_complaint"] = after.facts["chief_complaint"].model_copy(update={"value": "retrieved text"})

        with self.assertRaises(ValueError):
            assert_memory_l2_unchanged(before, after)


if __name__ == "__main__":
    unittest.main()
