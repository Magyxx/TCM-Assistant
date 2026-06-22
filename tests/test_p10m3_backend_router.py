from __future__ import annotations

import json

from app.extractors.local_lora_extractor import LocalLoRAExtractorBackend
from app.extractors.router import get_extractor_backend
from app.schemas.report_schemas import RunState


class MockClient:
    def create_chat_completion(self, messages):
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "chief_complaint": "胃胀",
                                "duration": "一周",
                                "symptoms": [],
                                "symptoms_status": "none",
                                "risk_flags": [],
                                "risk_flags_status": "none",
                                "summary": "local_lora mock output",
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }


def test_fake_and_fallback_backends_still_route() -> None:
    assert get_extractor_backend("fake").mode == "fake"
    assert get_extractor_backend("fallback").mode == "rule_fallback"
    assert get_extractor_backend("rule_fallback").mode == "rule_fallback"


def test_local_lora_backend_contract_with_mock_client() -> None:
    backend = LocalLoRAExtractorBackend(client=MockClient())
    output = backend.extract_turn("胃胀一周，没有其他症状", RunState())

    assert backend.mode == "local_lora"
    assert output.chief_complaint == "胃胀"
    assert output.duration == "一周"
    assert output.metadata["backend"] == "local_lora"
    assert output.metadata["fallback_used"] is False
    assert output.metadata["schema_guard"] == "passed"


def test_router_returns_local_lora_backend(monkeypatch) -> None:
    monkeypatch.setenv("EXTRACTOR_BACKEND", "local_lora")
    backend = get_extractor_backend()

    assert backend.mode == "local_lora"
