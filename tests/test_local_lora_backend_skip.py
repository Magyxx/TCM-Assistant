from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app.extractors.router import get_extractor_backend
from app.schemas.report_schemas import RunState


class LocalLoRABackendSkipTests(unittest.TestCase):
    def test_local_lora_unavailable_service_is_skipped_not_failed(self) -> None:
        env = {
            "LOCAL_LLM_BASE_URL": "http://127.0.0.1:9/v1",
            "LOCAL_LLM_TIMEOUT_SECONDS": "0.1",
        }
        with patch.dict(os.environ, env, clear=False):
            backend = get_extractor_backend("local_lora")
            result = backend.extract("stomach discomfort for two days", state=RunState())

        self.assertEqual(result.status, "skipped")
        self.assertIsNotNone(result.skip_reason)
        self.assertTrue(str(result.skip_reason).startswith("service_not_available:"))
        self.assertTrue(result.fallback_used)
        self.assertIsNotNone(result.turn_output)
        self.assertEqual(result.turn_output.metadata["skip_reason"], result.skip_reason)


if __name__ == "__main__":
    unittest.main()
