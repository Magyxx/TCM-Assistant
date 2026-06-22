from __future__ import annotations

import unittest

from app.graph.consultation_graph import run_consultation_graph
from app.memory.models import ConsultationMemory
from app.schemas.report_schemas import RunState


class GraphMemoryUpdateTests(unittest.TestCase):
    def test_memory_update_node_calls_memory_manager_and_exports_run_state(self) -> None:
        graph_state = run_consultation_graph(
            RunState(),
            "胃胀两天，没有其他症状",
            use_langgraph=False,
            extractor_mode="fake",
            rag_enabled=False,
        )

        memory = graph_state["memory"]
        run_state = graph_state["run_state"]

        self.assertIsInstance(memory, ConsultationMemory)
        self.assertEqual(memory.fact_value("chief_complaint"), "胃胀")
        self.assertEqual(run_state.chief_complaint, "胃胀")
        self.assertIn("p8_memory", run_state.metadata)
        self.assertTrue(memory.audit_events)
        self.assertTrue(any(event.action == "validate_turn_output" for event in memory.audit_events))
        self.assertEqual(run_state.metadata["p8_graph"]["memory_update_used"], True)


if __name__ == "__main__":
    unittest.main()
