from __future__ import annotations

import unittest

from app.graph.consultation_graph import NODE_SEQUENCE, run_consultation_graph
from app.schemas.report_schemas import RunState


class GraphFallbackRuntimeTests(unittest.TestCase):
    def test_fallback_runtime_runs_complete_turn_smoke(self) -> None:
        graph_state = run_consultation_graph(
            RunState(),
            "胃胀两天，没有其他症状",
            use_langgraph=False,
            extractor_mode="fake",
            rag_enabled=False,
        )

        run_state = graph_state["run_state"]
        self.assertEqual(graph_state["graph_runtime"], "sequential_fallback")
        self.assertEqual(run_state.metadata["graph_runtime"], "sequential_fallback")
        self.assertEqual(run_state.turn_count, 1)
        self.assertEqual(graph_state["metrics"]["plan_next_action"], "ok")
        self.assertEqual(
            run_state.metadata["p8_graph"]["node_sequence"],
            [name for name, _ in NODE_SEQUENCE],
        )
        self.assertFalse(graph_state["safety_issues"])


if __name__ == "__main__":
    unittest.main()
