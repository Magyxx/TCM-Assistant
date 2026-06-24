from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.graph.runner import run_p9m1_graph
from app.graph.runtime import is_langgraph_available


class P11M3OptionalGraphRuntimeTests(unittest.TestCase):
    def test_fallback_runtime_is_always_available(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_p9m1_graph(
                "stomach discomfort for two days",
                extractor_backend="fake",
                use_langgraph=False,
                graph_events_path=Path(temp_dir) / "graph_events.jsonl",
            )

        self.assertEqual(result["graph_runtime"], "sequential_fallback")
        self.assertTrue(result["trace"])

    def test_optional_langgraph_runtime_passes_or_is_skipped(self) -> None:
        if not is_langgraph_available():
            self.skipTest("langgraph is not installed")

        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_p9m1_graph(
                "stomach discomfort for two days",
                extractor_backend="fake",
                use_langgraph=True,
                graph_events_path=Path(temp_dir) / "graph_events.jsonl",
            )

        self.assertEqual(result["graph_runtime"], "langgraph")
        self.assertTrue(result["trace"])


if __name__ == "__main__":
    unittest.main()
