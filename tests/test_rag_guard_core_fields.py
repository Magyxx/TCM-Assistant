from __future__ import annotations

import unittest

from app.memory.models import ConsultationMemory, MemoryFact
from app.rag.rag_guard import assert_memory_l2_unchanged, guard_rag_update, report_text_is_safe


class RagGuardCoreFieldTests(unittest.TestCase):
    def test_blocks_core_field_overwrites(self) -> None:
        for field in ["chief_complaint", "duration", "risk_status", "risk_rule_ids"]:
            with self.subTest(field=field):
                result = guard_rag_update({field: "retrieved text"})
                self.assertFalse(result.allowed)
                self.assertIn(field, result.blocked_fields)

    def test_allows_retrieved_evidence_context(self) -> None:
        result = guard_rag_update({"retrieved_evidence": [{"chunk_id": "c1"}]})
        self.assertTrue(result.allowed)

    def test_memory_l2_fact_changes_are_rejected(self) -> None:
        before = ConsultationMemory(
            facts={
                "chief_complaint": MemoryFact(
                    field_name="chief_complaint",
                    value="胃胀",
                    source_turn_id="t1",
                    raw_text="胃胀两天",
                    extractor_mode="fake",
                )
            }
        )
        after = before.model_copy(deep=True)
        after.facts["chief_complaint"] = after.facts["chief_complaint"].model_copy(update={"value": "胸痛"})

        with self.assertRaises(ValueError):
            assert_memory_l2_unchanged(before, after)

    def test_report_text_safety_blocks_diagnosis_and_prescription(self) -> None:
        self.assertTrue(report_text_is_safe("建议继续观察，并在加重时线下就医。"))
        self.assertFalse(report_text_is_safe("诊断为某病，并开方治疗。"))


if __name__ == "__main__":
    unittest.main()
