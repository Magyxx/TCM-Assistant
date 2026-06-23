from __future__ import annotations

import json
import unittest

from app.extractors.local_lora_extractor import extract_with_local_lora
from app.schemas.report_schemas import RunState, TurnOutput


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

    def create(self, **kwargs):
        return _Completion(self.content)


class _Chat:
    def __init__(self, content: str) -> None:
        self.completions = _Completions(content)


class _Client:
    def __init__(self, content: str) -> None:
        self.chat = _Chat(content)


class LocalLoraExtractorTests(unittest.TestCase):
    def test_valid_json_passes_turn_output_schema(self) -> None:
        payload = {
            "chief_complaint": "stomach discomfort",
            "duration": "two days",
            "symptoms": ["nausea"],
            "symptoms_status": "present",
            "risk_flags": [],
            "risk_flags_status": "unknown",
            "summary": "Candidate extraction only.",
        }

        result = extract_with_local_lora(
            RunState(),
            "stomach discomfort for two days with nausea",
            client=_Client(json.dumps(payload)),
        )

        self.assertTrue(result.success)
        self.assertTrue(result.json_valid)
        self.assertTrue(result.schema_valid)
        self.assertTrue(result.final_schema_pass)
        self.assertFalse(result.fallback_used)
        self.assertIsInstance(result.turn_output, TurnOutput)
        self.assertEqual(result.turn_output.chief_complaint, "stomach discomfort")

    def test_trailing_comma_json_is_lightly_repaired(self) -> None:
        raw = """
        ```json
        {
          "chief_complaint": "stomach discomfort",
          "duration": null,
          "symptoms": [],
          "symptoms_status": "unknown",
          "risk_flags": [],
          "risk_flags_status": "unknown",
        }
        ```
        """

        result = extract_with_local_lora(RunState(), "stomach discomfort", client=_Client(raw))

        self.assertTrue(result.success)
        self.assertTrue(result.json_valid)
        self.assertTrue(result.schema_valid)
        self.assertEqual(result.turn_output.chief_complaint, "stomach discomfort")

    def test_invalid_json_returns_structured_error_without_fallback_by_default(self) -> None:
        result = extract_with_local_lora(RunState(), "stomach discomfort", client=_Client("not json"))

        self.assertFalse(result.success)
        self.assertFalse(result.json_valid)
        self.assertFalse(result.schema_valid)
        self.assertFalse(result.fallback_used)
        self.assertIsNone(result.turn_output)
        self.assertEqual(result.error_type, "json_invalid")


if __name__ == "__main__":
    unittest.main()
