from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.extractors.openai_compatible_client import OpenAICompatibleChatClient
from app.graph.runner import run_p9m1_graph
from app.rules.risk_rules import RISK_RULES


class P11M3RiskGuardInWorkflowTests(unittest.TestCase):
    def test_local_lora_candidate_cannot_bypass_risk_rules(self) -> None:
        def mock_completion(self, messages):
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "chief_complaint": "stomach discomfort",
                                    "duration": "half a day",
                                    "symptoms": [],
                                    "symptoms_status": "none",
                                    "risk_flags": [],
                                    "risk_flags_status": "none",
                                    "summary": "candidate attempted to clear risk",
                                }
                            )
                        }
                    }
                ]
            }

        risk_text = f"{RISK_RULES[0].trigger_keywords[0]} {RISK_RULES[1].trigger_keywords[0]}"
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(OpenAICompatibleChatClient, "create_chat_completion", mock_completion):
                result = run_p9m1_graph(
                    risk_text,
                    extractor_backend="local_lora",
                    use_langgraph=False,
                    graph_events_path=Path(temp_dir) / "graph_events.jsonl",
                )

        extraction = result["extracted_turn_output"]

        self.assertEqual(extraction["metadata"]["backend"], "local_lora")
        self.assertEqual(extraction["risk_flags_status"], "none")
        self.assertEqual(result["risk_status"], "present")
        self.assertEqual(result["run_state"]["risk_flags_status"], "present")
        self.assertTrue(result["risk_rule_ids"])


if __name__ == "__main__":
    unittest.main()
