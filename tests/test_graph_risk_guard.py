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
            "胃胀两天，没有胸痛",
            use_langgraph=False,
            extractor_mode="fake",
            rag_enabled=False,
        )

        self.assertEqual(graph_state["run_state"].risk_flags_status, "present")
        self.assertTrue(
            any(event.reason == "llm_candidate_cannot_write_risk_authority" for event in graph_state["memory"].audit_events)
        )

    def test_explicit_negation_is_preserved_in_graph_memory(self) -> None:
        graph_state = run_consultation_graph(
            RunState(),
            "胃胀两天，没有其他症状",
            use_langgraph=False,
            extractor_mode="fake",
            rag_enabled=False,
        )

        self.assertEqual(graph_state["memory"].facts["symptoms_status"].value, "none")
        self.assertTrue(graph_state["memory"].facts["symptoms_status"].explicit_negation)


if __name__ == "__main__":
    unittest.main()
