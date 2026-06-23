from __future__ import annotations

import unittest
from unittest.mock import patch

from app.extractors.local_lora_extractor import (
    DEFAULT_LOCAL_LORA_MODEL,
    get_local_lora_api_key,
    get_local_lora_base_url,
    get_local_lora_model,
)
from app.extractors.local_vllm_extractor import (
    DEFAULT_LOCAL_LLM_BASE_URL,
    DEFAULT_LOCAL_LLM_MAX_TOKENS,
    get_local_llm_max_tokens,
    get_local_llm_response_format_enabled,
    get_local_llm_temperature,
)


class LocalLoraRealpathConfigTests(unittest.TestCase):
    def test_local_lora_defaults(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(get_local_lora_base_url(), DEFAULT_LOCAL_LLM_BASE_URL)
            self.assertEqual(get_local_lora_model(), DEFAULT_LOCAL_LORA_MODEL)
            self.assertEqual(get_local_lora_api_key(), "EMPTY")
            self.assertEqual(get_local_llm_max_tokens(), DEFAULT_LOCAL_LLM_MAX_TOKENS)
            self.assertEqual(get_local_llm_temperature(), 0.0)
            self.assertFalse(get_local_llm_response_format_enabled())

    def test_max_tokens_and_temperature_are_configurable(self) -> None:
        with patch.dict(
            "os.environ",
            {"LOCAL_LLM_MAX_TOKENS": "256", "LOCAL_LLM_TEMPERATURE": "0.1"},
            clear=True,
        ):
            self.assertEqual(get_local_llm_max_tokens(), 256)
            self.assertEqual(get_local_llm_temperature(), 0.1)

    def test_response_format_is_opt_in_only(self) -> None:
        with patch.dict("os.environ", {"LOCAL_LLM_RESPONSE_FORMAT": "true"}, clear=True):
            self.assertTrue(get_local_llm_response_format_enabled())


if __name__ == "__main__":
    unittest.main()
