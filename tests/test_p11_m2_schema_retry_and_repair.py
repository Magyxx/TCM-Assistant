from __future__ import annotations

import unittest

from app.extractors.local_lora_extractor import LocalLoRAExtractorBackend
from app.schemas.report_schemas import RunState


class MockChatCompletionClient:
    def __init__(self, content: str) -> None:
        self.content = content

    def create_chat_completion(self, messages):
        return {"choices": [{"message": {"content": self.content}}]}


class P11M2SchemaRetryAndRepairTests(unittest.TestCase):
    def test_malformed_json_is_recorded_and_falls_back(self) -> None:
        backend = LocalLoRAExtractorBackend(client=MockChatCompletionClient("not json"))

        result = backend.extract("stomach discomfort for two days", state=RunState())
        summary = result.contract_summary()

        self.assertTrue(summary["fallback_used"])
        self.assertEqual(summary["schema_guard"], "failed")
        self.assertEqual(summary["validated_output_schema_guard"], "passed")
        self.assertEqual(summary["error_type"], "json_invalid")
        self.assertFalse(summary["raw_llm_json_valid"])
        self.assertFalse(summary["candidate_schema_pass"])
        self.assertFalse(summary["repair_used"])
        self.assertEqual(summary["retry_count"], 0)

    def test_lightweight_json_unwrap_records_repair_used(self) -> None:
        payload = (
            'Here is JSON: {"chief_complaint":"stomach discomfort","duration":"two days",'
            '"symptoms":[],"symptoms_status":"none","risk_flags":[],'
            '"risk_flags_status":"none","summary":"mock candidate"}'
        )
        backend = LocalLoRAExtractorBackend(client=MockChatCompletionClient(payload))

        result = backend.extract("stomach discomfort for two days", state=RunState())
        summary = result.contract_summary()

        self.assertTrue(result.schema_pass)
        self.assertFalse(summary["raw_llm_json_valid"])
        self.assertTrue(summary["repair_used"])
        self.assertEqual(summary["retry_count"], 0)


if __name__ == "__main__":
    unittest.main()
