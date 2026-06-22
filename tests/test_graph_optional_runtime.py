from __future__ import annotations

import unittest

from app.graph.consultation_graph import build_consultation_graph, run_consultation_graph
from app.graph.runtime import is_langgraph_available
from app.schemas.report_schemas import RunState


class GraphOptionalRuntimeTests(unittest.TestCase):
    def test_langgraph_optional_runtime_passes_when_available(self) -> None:
        if not is_langgraph_available():
            self.skipTest("langgraph is not installed; fallback runtime is covered separately")

        self.assertIsNotNone(build_consultation_graph())
        graph_state = run_consultation_graph(
            RunState(),
            "胃胀两天，没有其他症状",
            use_langgraph=True,
            extractor_mode="fake",
            rag_enabled=False,
        )

        self.assertEqual(graph_state["graph_runtime"], "langgraph")
        self.assertEqual(graph_state["run_state"].metadata["graph_runtime"], "langgraph")


if __name__ == "__main__":
    unittest.main()
