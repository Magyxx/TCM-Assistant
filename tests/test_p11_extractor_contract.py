from __future__ import annotations

import inspect
import unittest
from pathlib import Path

from app.extractors.local_lora_extractor import LocalLoRAExtractorBackend, LocalVLLMExtractorBackend
from app.extractors.result import ExtractorResult
from app.extractors.router import get_extractor_backend
from app.schemas.report_schemas import RunState

ROOT_DIR = Path(__file__).resolve().parents[1]


class P11ExtractorContractTests(unittest.TestCase):
    def test_extractor_result_schema_guard_rejects_invalid_candidate(self) -> None:
        result = ExtractorResult.from_turn_output(
            mode="local_lora",
            raw_output={"risk_flags_status": "clear"},
            turn_output={"risk_flags_status": "clear"},
            metadata={"backend": "local_lora"},
        )

        self.assertFalse(result.schema_pass)
        self.assertEqual(result.metadata["schema_guard"], "failed")
        self.assertEqual(result.metadata["validated_output_schema_guard"], "failed")
        self.assertIsNone(result.turn_output)

    def test_local_backends_expose_new_extract_turn_signature(self) -> None:
        for backend_cls in [LocalLoRAExtractorBackend, LocalVLLMExtractorBackend]:
            with self.subTest(backend=backend_cls.__name__):
                signature = inspect.signature(backend_cls.extract_turn)
                names = list(signature.parameters)
                self.assertEqual(names[:3], ["self", "user_input", "state"])
                self.assertNotEqual(names[:3], ["self", "state", "user_input"])

    def test_no_old_extract_turn_signature_regression_in_local_paths(self) -> None:
        local_paths = [
            ROOT_DIR / "app" / "extractors" / "local_lora_extractor.py",
            ROOT_DIR / "app" / "extractors" / "router.py",
            ROOT_DIR / "app" / "extractors" / "__init__.py",
        ]
        text = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in local_paths)

        self.assertNotIn("extract_turn(state, user_input", text)
        self.assertNotIn("def extract_turn(state, user_input", text)

    def test_legacy_backend_result_alias_absent_in_tests(self) -> None:
        test_text = "\n".join(
            path.read_text(encoding="utf-8", errors="replace")
            for path in (ROOT_DIR / "tests").glob("test*.py")
        )
        legacy_name = "Backend" + "Result"

        self.assertNotIn(legacy_name, test_text)

    def test_fake_and_fallback_return_extractor_result_contract(self) -> None:
        for mode in ["fake", "fallback"]:
            with self.subTest(mode=mode):
                result = get_extractor_backend(mode).extract("胃胀一周，没有胸痛", state=RunState())
                self.assertIsInstance(result, ExtractorResult)
                self.assertTrue(result.schema_pass)
                self.assertEqual(result.metadata["schema_guard"], "passed")
                self.assertIn("fallback_used", result.metadata)


if __name__ == "__main__":
    unittest.main()
