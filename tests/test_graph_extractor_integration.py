from __future__ import annotations

import unittest

from app.graph.consultation_graph import run_consultation_graph
from app.schemas.report_schemas import RunState


class GraphExtractorIntegrationTests(unittest.TestCase):
    def test_graph_extract_turn_uses_unified_adapter(self) -> None:
        graph_state = run_consultation_graph(
            RunState(),
            "胃胀两天，没有其他症状",
            use_langgraph=False,
            extractor_mode="fake",
            rag_enabled=False,
        )

        self.assertEqual(graph_state["extractor_mode"], "fake")
        self.assertTrue(graph_state["schema_valid"])
        self.assertEqual(graph_state["extraction_result"]["metadata"]["adapter"], "structured_output_adapter")
        self.assertEqual(graph_state["run_state"].metadata["p8_graph"]["extractor_adapter"], "structured_output_adapter")

    def test_llm_candidate_still_cannot_override_risk_authority(self) -> None:
        state = RunState(
            chief_complaint="胸闷",
            duration="一天",
            risk_flags_status="present",
            risk_flags=["呼吸困难"],
            triggered_rule_ids=["P0_RISK_DYSPNEA"],
        )
        graph_state = run_consultation_graph(
            state,
            "胃胀两天，没有胸痛",
            use_langgraph=False,
            extractor_mode="fake",
            rag_enabled=False,
        )

        self.assertEqual(graph_state["run_state"].risk_flags_status, "present")
        self.assertTrue(
            any(event.reason == "llm_candidate_cannot_write_risk_authority" for event in graph_state["memory"].audit_events)
        )


if __name__ == "__main__":
    unittest.main()
