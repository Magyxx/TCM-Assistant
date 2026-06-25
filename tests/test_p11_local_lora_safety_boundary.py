from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.extractors.local_lora_extractor import LocalLoRAExtractorBackend
from app.extractors.openai_compatible_client import OpenAICompatibleChatClient
from app.graph.runner import run_p9m1_graph
from app.schemas.report_schemas import RunState


class MalformedJsonClient:
    def create_chat_completion(self, messages):
        return {"choices": [{"message": {"content": "chief_complaint=便血 risk_flags_status=none"}}]}


class P11LocalLoRASafetyBoundaryTests(unittest.TestCase):
    def _run_graph(self, *args, **kwargs):
        with tempfile.TemporaryDirectory() as temp_dir:
            return run_p9m1_graph(
                *args,
                graph_events_path=Path(temp_dir) / "graph_events.jsonl",
                **kwargs,
            )

    def test_local_lora_cannot_bypass_schema_guard(self) -> None:
        result = LocalLoRAExtractorBackend(client=MalformedJsonClient()).extract("胃胀一周", state=RunState())

        self.assertTrue(result.fallback_used)
        self.assertEqual(result.metadata["error_type"], "json_invalid")
        self.assertEqual(result.metadata["schema_guard"], "failed")
        self.assertFalse(result.metadata["raw_llm_json_valid"])
        self.assertEqual(result.turn_output.chief_complaint, "胃胀")
        self.assertNotEqual(result.turn_output.chief_complaint, "便血")

    def test_local_lora_malformed_candidate_cannot_directly_write_run_state(self) -> None:
        with patch.object(
            OpenAICompatibleChatClient,
            "create_chat_completion",
            lambda self, messages: {"choices": [{"message": {"content": "chief_complaint=便血"}}]},
        ):
            result = self._run_graph("胃胀一周，没有胸痛", extractor_backend="local_lora", use_langgraph=False)

        self.assertEqual(result["run_state"]["chief_complaint"], "胃胀")
        self.assertEqual(result["run_state"]["risk_flags_status"], "none")
        self.assertTrue(result["extracted_turn_output"]["metadata"]["fallback_used"])
        self.assertEqual(result["extracted_turn_output"]["metadata"]["schema_guard"], "failed")

    def test_local_lora_cannot_set_final_risk_authority(self) -> None:
        def mock_completion(self, messages):
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "chief_complaint": "胃胀",
                                    "duration": "半天",
                                    "symptoms": [],
                                    "symptoms_status": "none",
                                    "risk_flags": [],
                                    "risk_flags_status": "none",
                                    "summary": "candidate attempted to clear risk",
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            }

        with patch.object(OpenAICompatibleChatClient, "create_chat_completion", mock_completion):
            result = self._run_graph("胸痛伴呼吸困难半天", extractor_backend="local_lora", use_langgraph=False)

        self.assertEqual(result["risk_status"], "present")
        self.assertIn("P0_RISK_CHEST_PAIN", result["risk_rule_ids"])
        self.assertIn("P0_RISK_DYSPNEA", result["risk_rule_ids"])
        self.assertEqual(result["extracted_turn_output"]["metadata"]["risk_authority"], "risk_rules_layer")


if __name__ == "__main__":
    unittest.main()
