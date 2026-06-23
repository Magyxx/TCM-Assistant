from __future__ import annotations

import unittest
from unittest.mock import patch

from app.extractors.router import (
    CloudLLMExtractorBackend,
    FakeExtractorBackend,
    LocalBaseExtractorBackend,
    LocalLoraExtractorBackend,
    get_extractor_backend,
)


class ExtractorRouterTests(unittest.TestCase):
    def test_fake_backend(self) -> None:
        with patch.dict("os.environ", {"EXTRACTOR_BACKEND": "fake"}, clear=False):
            self.assertIsInstance(get_extractor_backend(), FakeExtractorBackend)

    def test_local_base_backend(self) -> None:
        with patch.dict("os.environ", {"EXTRACTOR_BACKEND": "local_base"}, clear=False):
            self.assertIsInstance(get_extractor_backend(), LocalBaseExtractorBackend)

    def test_local_lora_backend(self) -> None:
        with patch.dict("os.environ", {"EXTRACTOR_BACKEND": "local_lora"}, clear=False):
            self.assertIsInstance(get_extractor_backend(), LocalLoraExtractorBackend)

    def test_cloud_llm_backend(self) -> None:
        with patch.dict("os.environ", {"EXTRACTOR_BACKEND": "cloud_llm"}, clear=False):
            self.assertIsInstance(get_extractor_backend(), CloudLLMExtractorBackend)

    def test_unknown_backend_has_clear_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown EXTRACTOR_BACKEND"):
            get_extractor_backend("unknown_backend")


if __name__ == "__main__":
    unittest.main()
