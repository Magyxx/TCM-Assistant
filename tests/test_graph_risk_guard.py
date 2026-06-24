from __future__ import annotations

import unittest

from app.graph.consultation_graph import run_consultation_graph
from app.rules.risk_rules import RISK_RULES
from app.schemas.report_schemas import RunState


class GraphRiskGuardTests(unittest.TestCase):
    def test_risk_status_comes_from_rule_engine_fact(self) -> None:
        risk_text = RISK_RULES[0].trigger_keywords[0]
        graph_state = run_consultation_graph(
            RunState(),
            risk_text,
            use_langgraph=False,
            extractor_mode="fallback",
            rag_enabled=False,
        )

        memory = graph_state["memory"]
        run_state = graph_state["run_state"]

        self.assertEqual(run_state.risk_flags_status, "present")
        self.assertEqual(memory.facts["risk_flags_status"].source_kind, "risk_rule_engine")
        self.assertTrue(run_state.triggered_rule_ids)
        self.assertEqual(graph_state["risk_status"], "present")

    def test_high_risk_present_remains_sticky_after_ordinary_text(self) -> None:
        state = RunState(
            chief_complaint="chest tightness",
            duration="one day",
            symptoms_status="unknown",
            risk_flags_status="present",
            risk_flags=["dyspnea"],
            triggered_rule_ids=["P0_RISK_DYSPNEA"],
        )
        graph_state = run_consultation_graph(
            state,
            "stomach discomfort for two days, no chest pain",
            use_langgraph=False,
            extractor_mode="fake",
            rag_enabled=False,
        )

        self.assertEqual(graph_state["run_state"].risk_flags_status, "present")
        self.assertTrue(
            any(event.reason == "llm_candidate_cannot_write_risk_authority" for event in graph_state["memory"].audit_events)
        )

    def test_graph_wrapper_does_not_bypass_memory_manager(self) -> None:
        graph_state = run_consultation_graph(
            RunState(),
            "stomach discomfort for two days, no other symptoms",
            use_langgraph=False,
            extractor_mode="fake",
            rag_enabled=False,
        )

        reasons = [event.reason for event in graph_state["memory"].audit_events]
        self.assertIn("schema_validation_passed", reasons)
        self.assertTrue(graph_state["run_state"].metadata["p8_graph"]["memory_update_used"])


if __name__ == "__main__":
    unittest.main()
