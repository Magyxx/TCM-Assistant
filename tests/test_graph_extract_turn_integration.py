from __future__ import annotations

import unittest

from app.graph.consultation_graph import run_consultation_graph
from app.schemas.report_schemas import RunState


class GraphExtractTurnIntegrationTests(unittest.TestCase):
    def test_graph_extract_turn_routes_through_backend_contract(self) -> None:
        graph_state = run_consultation_graph(
            RunState(),
            "stomach discomfort for two days, no other symptoms",
            use_langgraph=False,
            extractor_mode="fake",
            rag_enabled=False,
        )

        run_state = graph_state["run_state"]
        extraction = graph_state["extraction_result"]

        self.assertEqual(extraction["metadata"]["adapter"], "structured_output_adapter")
        self.assertEqual(extraction["metadata"]["backend"], "fake")
        self.assertTrue(extraction["schema_pass"])
        self.assertTrue(graph_state["schema_valid"])
        self.assertTrue(run_state.metadata["p8_graph"]["extract_turn_uses_router"])
        self.assertEqual(run_state.metadata["p8_graph"]["extractor_router"], "get_extractor_backend")

    def test_validate_turn_runs_before_memory_update_and_risk_check(self) -> None:
        graph_state = run_consultation_graph(
            RunState(),
            "stomach discomfort for two days, no chest pain",
            use_langgraph=False,
            extractor_mode="fake",
            rag_enabled=False,
        )
        node_order = [event["node"] for event in graph_state["audit_events"] if "node" in event]

        self.assertLess(node_order.index("extract_turn"), node_order.index("validate_turn"))
        self.assertLess(node_order.index("validate_turn"), node_order.index("memory_update"))
        self.assertLess(node_order.index("memory_update"), node_order.index("risk_check"))
        self.assertTrue(any(event.action == "validate_turn_output" for event in graph_state["memory"].audit_events))


if __name__ == "__main__":
    unittest.main()
