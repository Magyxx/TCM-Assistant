from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app.extractors.router import build_extractor_backend_registry, get_backend_contract_matrix, get_extractor_backend


class P11BackendMatrixTests(unittest.TestCase):
    def test_backend_matrix_covers_registered_mainline_backends(self) -> None:
        registry = build_extractor_backend_registry()
        matrix = get_backend_contract_matrix()

        for mode in [
            "fake",
            "fallback",
            "rule_fallback",
            "real_llm",
            "openai_compatible",
            "cloud_llm",
            "local_vllm",
            "local_lora",
        ]:
            with self.subTest(mode=mode):
                self.assertIn(mode, registry)
                self.assertIn(mode, matrix)

    def test_backend_matrix_has_required_contract_fields(self) -> None:
        required = {
            "backend_name",
            "enabled_by_default",
            "required_env",
            "optional_dependency",
            "live_service_required",
            "output_contract",
            "schema_guard_required",
            "malformed_json_behavior",
            "risk_authority",
            "fallback_behavior",
            "skip_reason_when_unavailable",
            "tests_covered",
        }

        for mode, contract in get_backend_contract_matrix().items():
            with self.subTest(mode=mode):
                self.assertTrue(required.issubset(contract))
                self.assertEqual(contract["risk_authority"], "risk_rules_layer")
                self.assertTrue(contract["schema_guard_required"])
                self.assertIsInstance(contract["tests_covered"], list)

    def test_optional_backend_matrix_has_skip_reasons(self) -> None:
        env = {
            "ENABLE_REAL_LLM": "false",
            "TCM_ALLOW_REAL_LLM": "false",
            "RUN_LOCAL_VLLM_SMOKE": "0",
            "OPENAI_API_KEY": "",
            "OPENAI_BASE_URL": "",
            "OPENAI_MODEL": "",
        }
        with patch.dict(os.environ, env, clear=False):
            matrix = get_backend_contract_matrix()

        for mode in ["real_llm", "openai_compatible", "cloud_llm", "local_vllm", "local_lora"]:
            with self.subTest(mode=mode):
                self.assertIsInstance(matrix[mode]["skip_reason_when_unavailable"], str)
                self.assertTrue(matrix[mode]["skip_reason_when_unavailable"])

    def test_backend_router_preserves_existing_default_and_modes(self) -> None:
        env = {
            "EXTRACTOR_BACKEND": "",
            "TCM_EXTRACTOR_MODE": "",
        }
        with patch.dict(os.environ, env, clear=False):
            self.assertEqual(get_extractor_backend().mode, "fake")

        self.assertEqual(get_extractor_backend("fake").mode, "fake")
        self.assertEqual(get_extractor_backend("fallback").mode, "rule_fallback")
        self.assertEqual(get_extractor_backend("rule_fallback").mode, "rule_fallback")
        self.assertEqual(get_extractor_backend("local_lora").mode, "local_lora")
        self.assertEqual(get_extractor_backend("local_vllm").mode, "local_vllm")


if __name__ == "__main__":
    unittest.main()
