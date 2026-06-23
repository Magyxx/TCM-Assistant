from __future__ import annotations

import unittest
from unittest.mock import patch

from app.extractors.local_lora_extractor import extract_with_local_lora
from app.schemas.report_schemas import RunState


class _FailingCompletions:
    def create(self, **kwargs):
        raise ConnectionError("local vLLM is not reachable")


class _FailingChat:
    completions = _FailingCompletions()


class _FailingClient:
    chat = _FailingChat()


class LocalLoraNoSilentFallbackTests(unittest.TestCase):
    def test_api_failure_does_not_silently_fallback(self) -> None:
        with patch.dict("os.environ", {"ALLOW_EXTRACTOR_FALLBACK": "false"}, clear=False):
            result = extract_with_local_lora(RunState(), "胸痛", client=_FailingClient())

        self.assertFalse(result.success)
        self.assertFalse(result.fallback_used)
        self.assertIsNone(result.turn_output)
        self.assertEqual(result.error_type, "local_vllm_unavailable")

    def test_explicit_fallback_records_fallback_used(self) -> None:
        with patch.dict("os.environ", {"ALLOW_EXTRACTOR_FALLBACK": "true"}, clear=False):
            result = extract_with_local_lora(RunState(), "胸痛", client=_FailingClient())

        self.assertFalse(result.success)
        self.assertTrue(result.fallback_used)
        self.assertIsNotNone(result.turn_output)
        self.assertEqual(result.turn_output.risk_flags_status, "present")
        self.assertTrue(result.schema_valid)
        self.assertTrue(result.final_schema_pass)


if __name__ == "__main__":
    unittest.main()
