from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app.extractors.router import get_backend_contract_matrix, get_extractor_backend
from app.schemas.report_schemas import RunState


class P11RuntimeSkipReasonTests(unittest.TestCase):
    def test_backend_matrix_has_skip_reasons_for_optional_backends(self) -> None:
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

        self.assertEqual(matrix["real_llm"]["skip_reason_when_unavailable"], "ENABLE_REAL_LLM=false")
        self.assertEqual(matrix["cloud_llm"]["skip_reason_when_unavailable"], "ENABLE_REAL_LLM=false")
        self.assertEqual(matrix["local_vllm"]["skip_reason_when_unavailable"], "RUN_LOCAL_VLLM_SMOKE is not enabled")
        self.assertEqual(matrix["local_lora"]["skip_reason_when_unavailable"], "RUN_LOCAL_VLLM_SMOKE is not enabled")

    def test_cloud_llm_disabled_is_skipped_with_reason_not_failed(self) -> None:
        with patch.dict(os.environ, {"ENABLE_REAL_LLM": "false"}, clear=False):
            result = get_extractor_backend("cloud_llm").extract("胃胀两天", state=RunState())

        self.assertEqual(result.status, "skipped")
        self.assertEqual(result.skip_reason, "ENABLE_REAL_LLM=false")
        self.assertTrue(result.fallback_used)
        self.assertEqual(result.metadata["error_type"], "real_llm_disabled")

    def test_local_lora_unavailable_service_is_skipped_with_reason_not_failed(self) -> None:
        env = {
            "LOCAL_LLM_BASE_URL": "http://127.0.0.1:9/v1",
            "LOCAL_LLM_TIMEOUT_SECONDS": "0.1",
        }
        with patch.dict(os.environ, env, clear=False):
            result = get_extractor_backend("local_lora").extract("胃胀一周", state=RunState())

        self.assertEqual(result.status, "skipped")
        self.assertTrue(str(result.skip_reason).startswith("service_not_available:"))
        self.assertTrue(result.fallback_used)
        self.assertEqual(result.turn_output.metadata["skip_reason"], result.skip_reason)

    def test_local_vllm_unavailable_service_is_skipped_with_reason_not_failed(self) -> None:
        env = {
            "LOCAL_LLM_BASE_URL": "http://127.0.0.1:9/v1",
            "LOCAL_LLM_TIMEOUT_SECONDS": "0.1",
        }
        with patch.dict(os.environ, env, clear=False):
            result = get_extractor_backend("local_vllm").extract("胃胀一周", state=RunState())

        self.assertEqual(result.status, "skipped")
        self.assertTrue(str(result.skip_reason).startswith("service_not_available:"))
        self.assertTrue(result.fallback_used)
        self.assertEqual(result.metadata["backend"], "local_vllm")


if __name__ == "__main__":
    unittest.main()
