from __future__ import annotations

import json

from app.extractors.openai_compatible_client import OpenAICompatibleChatClient
from app.graph.runner import run_p9m1_graph
from tests.p10_api_helpers import make_p10_client


def test_local_lora_mock_runs_through_graph(monkeypatch) -> None:
    def mock_completion(self, messages):
        assert "RunState context JSON" in messages[1]["content"]
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
                                "sleep": "睡眠一般",
                                "appetite": "食欲一般",
                                "stool": "大便正常",
                                "urination": "小便正常",
                                "risk_flags": [],
                                "risk_flags_status": "none",
                                "summary": "mock local_lora extraction",
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }

    monkeypatch.setattr(OpenAICompatibleChatClient, "create_chat_completion", mock_completion)
    result = run_p9m1_graph(
        "胃胀一周，睡眠一般，食欲一般，大便正常，小便正常，没有发热，也不胸痛",
        extractor_backend="local_lora",
        use_langgraph=False,
    )

    assert result["run_state"]["chief_complaint"] == "胃胀"
    assert result["run_state"]["duration"] == "一周"
    assert result["risk_status"] == "none"
    assert result["extracted_turn_output"]["metadata"]["backend"] == "local_lora"
    assert result["extracted_turn_output"]["metadata"]["fallback_used"] is False
    assert result["extracted_turn_output"]["metadata"]["final_schema_pass"] is True


def test_p10_api_local_lora_session_uses_p10_backend_path(tmp_path, monkeypatch) -> None:
    def mock_completion(self, messages):
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
                                "summary": "api local_lora mock extraction",
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }

    monkeypatch.setattr(OpenAICompatibleChatClient, "create_chat_completion", mock_completion)
    client, _paths = make_p10_client(tmp_path, monkeypatch)
    created = client.post("/sessions", json={"extractor_mode": "local_lora", "rag_enabled": True})
    assert created.status_code == 200, created.text
    session_id = created.json()["session_id"]

    response = client.post(
        f"/sessions/{session_id}/turn",
        json={"user_input": "胃胀一周，没有发热，也不胸痛"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["metadata"]["extractor_mode"] == "local_lora"
    assert data["metadata"]["final_schema_pass"] is True
    assert data["risk_status"] == "none"
