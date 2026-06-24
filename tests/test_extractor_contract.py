from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app.extractors.result import ExtractorResult
from app.extractors.router import get_extractor_backend
from app.schemas.report_schemas import RunState, TurnOutput


class ExtractorContractTests(unittest.TestCase):
    def test_all_configured_backends_return_contract_result(self) -> None:
        env = {
            "ENABLE_REAL_LLM": "false",
            "LOCAL_LLM_BASE_URL": "http://127.0.0.1:9/v1",
            "LOCAL_LLM_TIMEOUT_SECONDS": "0.1",
        }
        with patch.dict(os.environ, env, clear=False):
            for mode in ["fake", "fallback", "real_llm", "openai_compatible", "local_lora", "local_vllm"]:
                backend = get_extractor_backend(mode)
                result = backend.extract("stomach discomfort for two days", state=RunState())

                self.assertIsInstance(result, ExtractorResult)
                self.assertIn(result.backend, {backend.mode, mode})
                self.assertIn("backend", result.metadata)
                self.assertIn("fallback_used", result.metadata)
                self.assertIn("raw_llm_json_valid", result.metadata)
                self.assertIn("final_schema_pass", result.metadata)
                self.assertIn(result.status, {"passed", "skipped"})
                self.assertTrue(result.turn_output is None or isinstance(result.turn_output, TurnOutput))

    def test_reserved_local_base_is_clean_skip(self) -> None:
        result = get_extractor_backend("local_base").extract("input", state=RunState())

        self.assertEqual(result.status, "skipped")
        self.assertEqual(result.skip_reason, "reserved_for_device2_integration")
        self.assertIsNone(result.turn_output)

    def test_unknown_backend_has_clear_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown extractor backend"):
            get_extractor_backend("does_not_exist")


if __name__ == "__main__":
    unittest.main()
