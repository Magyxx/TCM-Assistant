from __future__ import annotations

import json
import os
import unittest

from app.extractors.local_lora_extractor import LocalLoRAExtractorBackend, LocalVLLMExtractorBackend
from app.extractors.result import ExtractorResult
from app.schemas.report_schemas import RunState


class MockChatCompletionClient:
    def __init__(self, content: str) -> None:
        self.content = content

    def create_chat_completion(self, messages):
        return {"choices": [{"message": {"content": self.content}}]}


def _valid_turn_json() -> str:
    return json.dumps(
        {
            "chief_complaint": "胃胀",
            "duration": "一周",
            "symptoms": [],
            "symptoms_status": "none",
            "risk_flags": [],
            "risk_flags_status": "none",
            "summary": "mock local LoRA candidate",
        },
        ensure_ascii=False,
    )


class LocalLoRAExtractorPortTests(unittest.TestCase):
    def test_mock_openai_compatible_success_returns_extractor_result(self) -> None:
        backend = LocalLoRAExtractorBackend(client=MockChatCompletionClient(_valid_turn_json()))
        result = backend.extract("胃胀一周，没有其他症状", state=RunState())

        self.assertIsInstance(result, ExtractorResult)
        self.assertTrue(result.schema_pass)
        self.assertFalse(result.fallback_used)
        self.assertEqual(result.turn_output.chief_complaint, "胃胀")
        self.assertEqual(result.metadata["backend"], "local_lora")
        self.assertTrue(result.metadata["json_valid"])
        self.assertTrue(result.metadata["schema_pass"])
        self.assertTrue(result.metadata["final_schema_pass"])
        self.assertFalse(result.metadata["live_vllm_used"])
        self.assertEqual(result.metadata["base_url"], "http://127.0.0.1:8000/v1")
        self.assertEqual(result.metadata["model"], "tcm-extractor-lora")

    def test_local_vllm_alias_uses_current_extractor_result_protocol(self) -> None:
        backend = LocalVLLMExtractorBackend(client=MockChatCompletionClient(_valid_turn_json()))
        result = backend.extract("胃胀一周", state=RunState())

        self.assertIsInstance(result, ExtractorResult)
        self.assertEqual(backend.mode, "local_vllm")
        self.assertEqual(result.mode, "local_vllm")
        self.assertEqual(result.metadata["backend"], "local_vllm")
        self.assertTrue(result.metadata["schema_pass"])

    def test_malformed_json_returns_auditable_fallback_without_mutating_state(self) -> None:
        state = RunState(chief_complaint="既有主诉", risk_flags_status="present", risk_flags=["既有风险"])
        before = state.model_dump()
        backend = LocalLoRAExtractorBackend(client=MockChatCompletionClient("not json at all"))

        result = backend.extract("胃胀一周", state=state)

        self.assertEqual(state.model_dump(), before)
        self.assertTrue(result.fallback_used)
        self.assertEqual(result.metadata["error_type"], "json_invalid")
        self.assertFalse(result.metadata["json_valid"])
        self.assertFalse(result.metadata["schema_pass"])
        self.assertFalse(result.metadata["final_schema_pass"])
        self.assertEqual(result.metadata["risk_authority"], "risk_rules_layer")

    def test_live_vllm_smoke_is_skipped_by_default(self) -> None:
        if os.getenv("RUN_LOCAL_VLLM_SMOKE", "0").strip().lower() not in {"1", "true", "yes"}:
            self.skipTest("RUN_LOCAL_VLLM_SMOKE is not enabled")

        backend = LocalLoRAExtractorBackend()
        result = backend.extract("胃胀一周", state=RunState())
        self.assertIn(result.status, {"passed", "skipped"})


if __name__ == "__main__":
    unittest.main()
