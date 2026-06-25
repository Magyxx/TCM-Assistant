from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app.extractors.adapter import validate_extractor_result_contract
from app.extractors.local_lora_extractor import LocalLoRAExtractorBackend, LocalVLLMExtractorBackend
from app.extractors.router import build_extractor_backend_registry, get_backend_contract_matrix, get_extractor_backend
from app.schemas.report_schemas import RunState


class MockChatCompletionClient:
    def create_chat_completion(self, messages):
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"chief_complaint":"stomach discomfort","duration":"two days",'
                            '"symptoms":[],"symptoms_status":"none","risk_flags":[],'
                            '"risk_flags_status":"none","summary":"mock candidate"}'
                        )
                    }
                }
            ]
        }


class P11M2ExtractorAdapterTests(unittest.TestCase):
    def test_registered_backends_share_extractor_backend_contract(self) -> None:
        registry = build_extractor_backend_registry()
        matrix = get_backend_contract_matrix()

        for mode in ["fake", "fallback", "rule_fallback", "real_llm", "openai_compatible", "cloud_llm"]:
            with self.subTest(mode=mode):
                self.assertIn(mode, registry)
                self.assertIn(mode, matrix)
                self.assertTrue(hasattr(registry[mode], "extract"))
                self.assertTrue(hasattr(registry[mode], "extract_turn"))
                self.assertTrue(matrix[mode]["schema_guard_required"])
                self.assertEqual(matrix[mode]["risk_authority"], "risk_rules_layer")

    def test_mainline_backend_results_validate_against_adapter_contract(self) -> None:
        env = {
            "ENABLE_REAL_LLM": "false",
            "TCM_ALLOW_REAL_LLM": "false",
            "OPENAI_API_KEY": "",
            "OPENAI_BASE_URL": "",
            "OPENAI_MODEL": "",
        }
        with patch.dict(os.environ, env, clear=False):
            for mode in ["fake", "fallback", "real_llm", "openai_compatible"]:
                with self.subTest(mode=mode):
                    backend = get_extractor_backend(mode)
                    result = backend.extract("stomach discomfort for two days", state=RunState())
                    self.assertEqual(validate_extractor_result_contract(result), [])
                    summary = result.contract_summary()
                    self.assertEqual(summary["backend_mode"], backend.mode)
                    self.assertIn(summary["schema_guard"], {"passed", "failed", "skipped"})

    def test_local_backends_can_be_validated_without_live_vllm(self) -> None:
        for backend in [
            LocalLoRAExtractorBackend(client=MockChatCompletionClient()),
            LocalVLLMExtractorBackend(client=MockChatCompletionClient()),
        ]:
            with self.subTest(mode=backend.mode):
                result = backend.extract("stomach discomfort for two days", state=RunState())
                self.assertEqual(validate_extractor_result_contract(result), [])
                self.assertTrue(result.schema_pass)
                self.assertFalse(result.fallback_used)
                self.assertFalse(result.contract_summary()["fallback_used"])

    def test_optional_backends_have_explicit_skip_reasons(self) -> None:
        env = {
            "ENABLE_REAL_LLM": "false",
            "TCM_ALLOW_REAL_LLM": "false",
            "RUN_LOCAL_VLLM_SMOKE": "0",
        }
        with patch.dict(os.environ, env, clear=False):
            matrix = get_backend_contract_matrix()

        for mode in ["real_llm", "openai_compatible", "cloud_llm", "local_vllm", "local_lora"]:
            with self.subTest(mode=mode):
                self.assertIsInstance(matrix[mode]["skip_reason_when_unavailable"], str)
                self.assertTrue(matrix[mode]["skip_reason_when_unavailable"])


if __name__ == "__main__":
    unittest.main()
