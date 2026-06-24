from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.graph.runner import run_p9m1_graph
from app.rag.rag_guard import guard_rag_update


class P11PostLoRARegressionTests(unittest.TestCase):
    def _run_graph(self, *args, **kwargs):
        with tempfile.TemporaryDirectory() as temp_dir:
            return run_p9m1_graph(
                *args,
                graph_events_path=Path(temp_dir) / "graph_events.jsonl",
                **kwargs,
            )

    def test_fake_and_fallback_paths_remain_stable_after_local_lora_merge(self) -> None:
        fake = self._run_graph("胃胀一周，没有胸痛，没有呼吸困难", extractor_backend="fake", use_langgraph=False)
        fallback = self._run_graph("便血两天", extractor_backend="fallback", use_langgraph=False)

        self.assertEqual(fake["extracted_turn_output"]["metadata"]["backend"], "fake")
        self.assertEqual(fake["risk_status"], "none")
        self.assertEqual(fallback["extracted_turn_output"]["metadata"]["backend"], "rule_fallback")
        self.assertEqual(fallback["risk_status"], "present")
        self.assertIn("P0_RISK_GI_BLEEDING", fallback["risk_rule_ids"])

    def test_risk_rules_fallback_handles_core_high_risk_terms(self) -> None:
        cases = {
            "胸痛半天": "P0_RISK_CHEST_PAIN",
            "呼吸困难一小时": "P0_RISK_DYSPNEA",
            "便血两天": "P0_RISK_GI_BLEEDING",
            "持续高热三天": "P0_RISK_HIGH_FEVER",
        }
        for text, expected_rule in cases.items():
            with self.subTest(text=text):
                result = self._run_graph(text, extractor_backend="fake", use_langgraph=False)
                self.assertEqual(result["risk_status"], "present")
                self.assertIn(expected_rule, result["risk_rule_ids"])

    def test_rag_core_overwrite_guard_remains_enabled(self) -> None:
        for field in ["chief_complaint", "duration", "risk_status", "risk_rule_ids"]:
            with self.subTest(field=field):
                result = guard_rag_update({field: "retrieved evidence should not overwrite state"})
                self.assertFalse(result.allowed)
                self.assertIn(field, result.blocked_fields)


if __name__ == "__main__":
    unittest.main()
