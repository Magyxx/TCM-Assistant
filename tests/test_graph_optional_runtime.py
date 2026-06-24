from __future__ import annotations

import unittest

from app.graph.consultation_graph import build_consultation_graph, run_consultation_graph
from app.graph.runtime import is_langgraph_available
from app.schemas.report_schemas import RunState


class GraphOptionalRuntimeTests(unittest.TestCase):
    def test_fallback_runtime_is_available_when_langgraph_is_absent(self) -> None:
        graph_state = run_consultation_graph(
            RunState(),
            "stomach discomfort for two days",
            use_langgraph=False,
            extractor_mode="fake",
            rag_enabled=False,
        )

        self.assertEqual(graph_state["graph_runtime"], "sequential_fallback")
        self.assertEqual(graph_state["run_state"].metadata["p8_graph"]["fallback_runtime_available"], True)

    def test_langgraph_optional_runtime_passes_or_is_skipped(self) -> None:
        if not is_langgraph_available():
            self.skipTest("langgraph is not installed; fallback runtime is covered separately")

        self.assertIsNotNone(build_consultation_graph())
        graph_state = run_consultation_graph(
            RunState(),
            "stomach discomfort for two days",
            use_langgraph=True,
            extractor_mode="fake",
            rag_enabled=False,
        )

        self.assertEqual(graph_state["graph_runtime"], "langgraph")
        self.assertEqual(graph_state["run_state"].metadata["graph_runtime"], "langgraph")


if __name__ == "__main__":
    unittest.main()
