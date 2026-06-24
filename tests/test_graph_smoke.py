import unittest

from app.graph.consultation_graph import run_consultation_graph
from app.schemas.report_schemas import RunState


class GraphFacadeSmokeTests(unittest.TestCase):
    def test_graph_facade_runs_without_required_langgraph_runtime(self) -> None:
        graph_state = run_consultation_graph(
            RunState(),
            "stomach discomfort for two days, no chest pain",
            use_langgraph=True,
            extractor_mode="fallback",
            rag_enabled=False,
        )

        state = graph_state["run_state"]
        self.assertIn(graph_state["graph_runtime"], {"langgraph", "sequential_fallback"})
        self.assertEqual(state.metadata["extractor_mode_requested"], "fallback")
        self.assertEqual(graph_state["extractor_mode"], "fallback")


if __name__ == "__main__":
    unittest.main()
