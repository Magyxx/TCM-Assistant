from __future__ import annotations

import unittest

from app.graph.consultation_graph import run_consultation_graph
from app.schemas.report_schemas import RunState


class GraphRagIntegrationTests(unittest.TestCase):
    def test_rag_node_records_retrieved_evidence_count_when_report_ready(self) -> None:
        state = RunState(
            chief_complaint="胃胀",
            duration="两天",
            symptoms_status="none",
            risk_flags_status="none",
        )
        graph_state = run_consultation_graph(
            state,
            "睡眠不好",
            use_langgraph=False,
            extractor_mode="fake",
            rag_enabled=True,
        )

        self.assertEqual(graph_state["next_action"], "ready_for_structured_consultation_summary")
        self.assertGreaterEqual(graph_state["retrieved_evidence_count"], 1)
        self.assertEqual(
            graph_state["run_state"].metadata["p8_graph"]["retrieved_evidence_count"],
            graph_state["retrieved_evidence_count"],
        )
        self.assertTrue(graph_state["run_state"].metadata["p8_graph"]["rag_node_optional"])

    def test_rag_evidence_does_not_enter_memory_l2(self) -> None:
        state = RunState(
            chief_complaint="胃胀",
            duration="两天",
            symptoms_status="none",
            risk_flags_status="none",
        )
        graph_state = run_consultation_graph(
            state,
            "睡眠不好",
            use_langgraph=False,
            extractor_mode="fake",
            rag_enabled=True,
        )

        facts = graph_state["memory"].facts
        self.assertIn("chief_complaint", facts)
        self.assertNotIn("retrieved_evidence", facts)
        self.assertNotIn("evidence", facts)
        self.assertEqual(facts["chief_complaint"].source_kind, "run_state_bridge")

    def test_rag_node_is_optional_for_regular_smoke(self) -> None:
        graph_state = run_consultation_graph(
            RunState(),
            "胃胀两天，没有其他症状",
            use_langgraph=False,
            extractor_mode="fake",
            rag_enabled=False,
        )

        self.assertEqual(graph_state["retrieved_evidence_count"], 0)
        self.assertEqual(graph_state["rag_skip_reason"], "rag_disabled")


if __name__ == "__main__":
    unittest.main()
