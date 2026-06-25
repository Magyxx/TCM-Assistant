from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.graph.runner import run_p9m1_graph


def _run_graph(user_input: str, *, extractor_backend: str = "fake") -> dict:
    with tempfile.TemporaryDirectory() as temp_dir:
        return run_p9m1_graph(
            user_input,
            extractor_backend=extractor_backend,
            use_langgraph=False,
            graph_events_path=Path(temp_dir) / "graph_events.jsonl",
        )


class P11M3WorkflowMainPathTests(unittest.TestCase):
    def test_main_path_runs_schema_state_risk_next_action_order(self) -> None:
        result = _run_graph(
            "stomach discomfort for two days, no other symptoms, no chest pain, sleep normal, appetite normal, stool normal, urination normal"
        )
        nodes = [item["node"] for item in result["trace"]]

        for node in ["extract_turn", "validate_turn", "merge_state", "risk_rule_check", "decide_next"]:
            self.assertIn(node, nodes)
        self.assertLess(nodes.index("extract_turn"), nodes.index("validate_turn"))
        self.assertLess(nodes.index("validate_turn"), nodes.index("merge_state"))
        self.assertLess(nodes.index("merge_state"), nodes.index("risk_rule_check"))
        self.assertLess(nodes.index("risk_rule_check"), nodes.index("decide_next"))
        self.assertTrue(result["schema_valid"])
        self.assertTrue(result["final_schema_pass"])
        self.assertEqual(result["graph_runtime"], "sequential_fallback")
        self.assertTrue(result["graph_events"])


if __name__ == "__main__":
    unittest.main()
