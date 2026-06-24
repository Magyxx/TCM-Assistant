from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from app.extractors.openai_compatible_client import OpenAICompatibleChatClient
from app.graph.consultation_graph import run_consultation_graph
from app.schemas.report_schemas import RunState


class ExtractorRiskBoundaryTests(unittest.TestCase):
    def test_local_lora_candidate_cannot_clear_rule_risk(self) -> None:
        def mock_completion(self, messages):
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "chief_complaint": "stomach discomfort",
                                    "duration": "two days",
                                    "symptoms": [],
                                    "symptoms_status": "unknown",
                                    "risk_flags": [],
                                    "risk_flags_status": "none",
                                    "summary": "model attempted to clear risk",
                                }
                            )
                        }
                    }
                ]
            }

        with patch.object(OpenAICompatibleChatClient, "create_chat_completion", mock_completion):
            graph_state = run_consultation_graph(
                RunState(),
                "chest pain with breathing difficulty",
                use_langgraph=False,
                extractor_mode="local_lora",
                rag_enabled=False,
            )

        self.assertEqual(graph_state["run_state"].risk_flags_status, "present")
        self.assertEqual(graph_state["risk_status"], "present")
        self.assertEqual(graph_state["extraction_result"]["metadata"]["backend"], "local_lora")
        self.assertEqual(graph_state["extraction_result"]["metadata"]["risk_authority"], "risk_rules_layer")

    def test_existing_high_risk_status_remains_sticky_after_fake_candidate(self) -> None:
        state = RunState(
            chief_complaint="chest tightness",
            duration="one day",
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
            any(
                event.reason == "llm_candidate_cannot_write_risk_authority"
                for event in graph_state["memory"].audit_events
            )
        )


if __name__ == "__main__":
    unittest.main()
