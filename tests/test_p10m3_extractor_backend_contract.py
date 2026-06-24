from __future__ import annotations

from app.extractors.local_lora_extractor import LOCAL_LORA_SYSTEM_PROMPT, build_local_lora_messages, parse_turn_output
from app.schemas.report_schemas import RunState, TurnOutput


def test_local_lora_prompt_restricts_scope_to_turn_output() -> None:
    assert "TurnOutput JSON" in LOCAL_LORA_SYSTEM_PROMPT
    assert "禁止诊断" in LOCAL_LORA_SYSTEM_PROMPT
    assert "禁止开方" in LOCAL_LORA_SYSTEM_PROMPT
    assert "Risk Rules" in LOCAL_LORA_SYSTEM_PROMPT


def test_local_lora_messages_include_user_input_and_minimal_context() -> None:
    messages = build_local_lora_messages("胃胀一周", RunState(chief_complaint="胃胀"))

    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert "胃胀一周" in messages[1]["content"]
    assert "metadata" not in messages[1]["content"]


def test_parse_turn_output_accepts_bounded_json_object_repair() -> None:
    output, metadata = parse_turn_output('```json\n{"chief_complaint":"胃胀","duration":"一周"}\n```')

    assert isinstance(output, TurnOutput)
    assert output.chief_complaint == "胃胀"
    assert metadata["repair_used"] is True
    assert metadata["final_schema_pass"] is True
