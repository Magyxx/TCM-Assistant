from __future__ import annotations

import unittest

from app.memory.models import ConsultationMemory, MemoryFact
from app.rag.query_builder import build_rag_query
from app.schemas.report_schemas import RunState


class RagQueryBuilderTests(unittest.TestCase):
    def test_query_includes_state_and_high_risk_terms(self) -> None:
        state = RunState(
            chief_complaint="胃胀",
            duration="两天",
            risk_flags=["胸痛", "便血"],
            risk_flags_status="present",
        )
        query = build_rag_query(state)

        self.assertIn("胃胀", query)
        self.assertIn("两天", query)
        self.assertIn("胸痛", query)
        self.assertIn("便血", query)

    def test_query_preserves_explicit_negation_raw_text(self) -> None:
        memory = ConsultationMemory(
            facts={
                "risk_flags_status": MemoryFact(
                    field_name="risk_flags_status",
                    value="none",
                    source_turn_id="t1",
                    raw_text="没有发热，也没有胸痛",
                    extractor_mode="fake",
                    explicit_negation=True,
                )
            }
        )
        query = build_rag_query(RunState(chief_complaint="胃胀"), memory=memory)

        self.assertIn("没有发热", query)
        self.assertIn("没有胸痛", query)
        self.assertNotIn("发热 present", query)


if __name__ == "__main__":
    unittest.main()
