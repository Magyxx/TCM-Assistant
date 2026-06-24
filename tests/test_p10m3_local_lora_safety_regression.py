from __future__ import annotations

import json

from app.extractors.openai_compatible_client import OpenAICompatibleChatClient
from app.graph.runner import run_p9m1_graph


def test_local_lora_cannot_clear_rule_detected_high_risk(monkeypatch) -> None:
    def mock_completion(self, messages):
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "chief_complaint": "胸痛",
                                "duration": "半天",
                                "symptoms": [],
                                "symptoms_status": "unknown",
                                "risk_flags": [],
                                "risk_flags_status": "none",
                                "summary": "model incorrectly downplayed risk",
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }

    monkeypatch.setattr(OpenAICompatibleChatClient, "create_chat_completion", mock_completion)
    result = run_p9m1_graph("胸痛伴呼吸困难半天", extractor_backend="local_lora", use_langgraph=False)

    assert result["risk_status"] == "present"
    assert "P0_RISK_CHEST_PAIN" in result["risk_rule_ids"]
    assert "P0_RISK_DYSPNEA" in result["risk_rule_ids"]


def test_local_lora_negation_is_preserved_by_risk_rules(monkeypatch) -> None:
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
                                "summary": "negated risk preserved",
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }

    monkeypatch.setattr(OpenAICompatibleChatClient, "create_chat_completion", mock_completion)
    result = run_p9m1_graph("胃胀一周，没有发热，也不胸痛", extractor_backend="local_lora", use_langgraph=False)

    assert result["risk_status"] == "none"
    assert result["risk_rule_ids"] == []
    assert "P0_RISK_CHEST_PAIN" not in result["run_state"]["triggered_rule_ids"]
