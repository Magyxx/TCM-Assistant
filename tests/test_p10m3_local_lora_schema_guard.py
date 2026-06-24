from __future__ import annotations

import json

from app.extractors.local_lora_extractor import LocalLoRAExtractorBackend
from app.extractors.openai_compatible_client import OpenAICompatibleChatClient
from app.graph.runner import run_p9m1_graph
from app.schemas.report_schemas import RunState


class InvalidJsonClient:
    def create_chat_completion(self, messages):
        return {"choices": [{"message": {"content": "not json at all"}}]}


class BadSchemaClient:
    def create_chat_completion(self, messages):
        return {"choices": [{"message": {"content": json.dumps({"risk_flags_status": "clear"})}}]}


def test_invalid_json_falls_back_without_using_model_payload() -> None:
    backend = LocalLoRAExtractorBackend(client=InvalidJsonClient())
    output = backend.extract_turn("胃胀一周", RunState())

    assert output.chief_complaint == "胃胀"
    assert output.metadata["backend"] == "local_lora"
    assert output.metadata["fallback_used"] is True
    assert output.metadata["error_type"] == "json_invalid"
    assert output.metadata["schema_guard"] == "failed"


def test_schema_mismatch_is_rejected_or_fallback() -> None:
    backend = LocalLoRAExtractorBackend(client=BadSchemaClient())
    output = backend.extract_turn("胃胀一周", RunState())

    assert output.metadata["fallback_used"] is True
    assert output.metadata["error_type"] == "schema_mismatch"
    assert output.metadata["final_schema_pass"] is False


def test_invalid_local_lora_payload_does_not_pollute_run_state(monkeypatch) -> None:
    def mock_completion(self, messages):
        return {"choices": [{"message": {"content": "chief_complaint=胸痛 risk_flags_status=none"}}]}

    monkeypatch.setattr(OpenAICompatibleChatClient, "create_chat_completion", mock_completion)
    result = run_p9m1_graph("胃胀一周，没有胸痛", extractor_backend="local_lora", use_langgraph=False)

    assert result["run_state"]["chief_complaint"] == "胃胀"
    assert result["run_state"]["risk_flags_status"] == "none"
    assert result["extracted_turn_output"]["metadata"]["fallback_used"] is True
