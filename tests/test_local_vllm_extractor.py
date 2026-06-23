from __future__ import annotations

import json
import unittest

from app.extractors.local_lora_extractor import extract_with_local_lora
from app.extractors.local_vllm_extractor import (
    DEFAULT_LOCAL_LLM_BASE_URL,
    DEFAULT_LOCAL_LLM_MAX_TOKENS,
    DEFAULT_LOCAL_LLM_MODEL,
    extract_with_local_vllm,
)
from app.schemas.report_schemas import RunState


class _Message:
    def __init__(self, content: str) -> None:
        self.content = content


class _Choice:
    def __init__(self, content: str) -> None:
        self.message = _Message(content)


class _Completion:
    def __init__(self, content: str) -> None:
        self.choices = [_Choice(content)]


class _Completions:
    def __init__(self, content: str) -> None:
        self.content = content
        self.kwargs = {}

    def create(self, **kwargs):
        self.kwargs = kwargs
        return _Completion(self.content)


class _Chat:
    def __init__(self, content: str) -> None:
        self.completions = _Completions(content)


class _Client:
    def __init__(self, content: str) -> None:
        self.chat = _Chat(content)


class _FailingCompletions:
    def create(self, **kwargs):
        raise ConnectionError("local vLLM is not reachable")


class _FailingChat:
    completions = _FailingCompletions()


class _FailingClient:
    chat = _FailingChat()


class LocalVLLMExtractorTests(unittest.TestCase):
    def test_defaults_are_local_lora_smoke_values(self) -> None:
        self.assertEqual(DEFAULT_LOCAL_LLM_BASE_URL, "http://127.0.0.1:8000/v1")
        self.assertEqual(DEFAULT_LOCAL_LLM_MODEL, "tcm-extractor-lora")
        self.assertEqual(DEFAULT_LOCAL_LLM_MAX_TOKENS, 512)

    def test_extract_with_local_vllm_validates_json_schema_and_uses_temperature_zero(self) -> None:
        payload = {
            "chief_complaint": "胃胀",
            "duration": "一周",
            "symptoms": [],
            "symptoms_status": "none",
            "risk_flags": [],
            "risk_flags_status": "none",
            "summary": "饭后胃胀约一周，否认发热和胸痛。",
        }
        client = _Client(json.dumps(payload, ensure_ascii=False))

        result = extract_with_local_vllm(RunState(), "最近胃胀，饭后明显，差不多一周，没有发热，也不胸痛。", client=client)

        self.assertTrue(result.success)
        self.assertTrue(result.json_valid)
        self.assertTrue(result.schema_valid)
        self.assertFalse(result.fallback_used)
        self.assertEqual(result.turn_output.chief_complaint, "胃胀")
        self.assertEqual(client.chat.completions.kwargs["temperature"], 0)
        self.assertEqual(client.chat.completions.kwargs["max_tokens"], 512)

    def test_local_lora_alias_preserves_clear_error_without_fake_fallback(self) -> None:
        result = extract_with_local_lora(RunState(), "胸痛", client=_FailingClient())

        self.assertFalse(result.success)
        self.assertFalse(result.fallback_used)
        self.assertIsNone(result.turn_output)
        self.assertEqual(result.error_type, "local_vllm_unavailable")
        self.assertIn("local vLLM is not reachable", result.error or "")

    def test_risk_guard_keeps_red_flags_from_being_bypassed(self) -> None:
        payload = {
            "chief_complaint": "胸痛",
            "duration": None,
            "symptoms": [],
            "symptoms_status": "unknown",
            "risk_flags": [],
            "risk_flags_status": "none",
            "summary": "用户提到胸痛。",
        }
        result = extract_with_local_vllm(RunState(), "我现在胸痛，喘不上气。", client=_Client(json.dumps(payload, ensure_ascii=False)))

        self.assertTrue(result.success)
        self.assertEqual(result.turn_output.risk_flags_status, "present")
        self.assertTrue(result.turn_output.risk_flags)


if __name__ == "__main__":
    unittest.main()
