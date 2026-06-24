from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from app.extractors.local_lora_extractor import LocalLoRAExtractorBackend
from app.extractors.openai_compatible_client import OpenAICompatibleChatClient
from app.graph.runner import run_p9m1_graph
from app.schemas.report_schemas import RunState


class MockChatCompletionClient:
    def __init__(self, content: str) -> None:
        self.content = content

    def create_chat_completion(self, messages):
        return {"choices": [{"message": {"content": self.content}}]}


class LocalLoRASchemaGuardTests(unittest.TestCase):
    def test_schema_mismatch_is_rejected_before_state_merge(self) -> None:
        state = RunState(chief_complaint="既有主诉")
        before = state.model_dump()
        backend = LocalLoRAExtractorBackend(
            client=MockChatCompletionClient(json.dumps({"risk_flags_status": "clear"}, ensure_ascii=False))
        )

        result = backend.extract("胃胀一周", state=state)

        self.assertEqual(state.model_dump(), before)
        self.assertTrue(result.fallback_used)
        self.assertEqual(result.metadata["error_type"], "schema_mismatch")
        self.assertTrue(result.metadata["json_valid"])
        self.assertFalse(result.metadata["schema_pass"])
        self.assertFalse(result.metadata["final_schema_pass"])

    def test_local_lora_risk_candidate_cannot_override_risk_rules(self) -> None:
        def mock_completion(self, messages):
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "chief_complaint": "胸痛",
                                    "duration": "半天",
                                    "symptoms": [],
                                    "symptoms_status": "unknown",
                                    "risk_flags": [],
                                    "risk_flags_status": "none",
                                    "summary": "model attempted to clear risk",
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            }

        with patch.object(OpenAICompatibleChatClient, "create_chat_completion", mock_completion):
            result = run_p9m1_graph("胸痛伴呼吸困难半天", extractor_backend="local_lora", use_langgraph=False)

        self.assertEqual(result["risk_status"], "present")
        self.assertIn("P0_RISK_CHEST_PAIN", result["risk_rule_ids"])
        self.assertIn("P0_RISK_DYSPNEA", result["risk_rule_ids"])
        self.assertEqual(result["extracted_turn_output"]["metadata"]["risk_authority"], "risk_rules_layer")


if __name__ == "__main__":
    unittest.main()
