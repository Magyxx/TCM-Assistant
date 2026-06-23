from __future__ import annotations

from app.extractors.base import BackendResult
from app.schemas.report_schemas import RunState


def extract_with_cloud_llm(state: RunState, user_input: str) -> BackendResult:
    from app.chains.turn_extractor import extract_turn

    result = extract_turn(state, user_input, extractor_mode="real_llm")
    parsed_json = result.turn_output.model_dump() if result.turn_output is not None else None
    return BackendResult(
        backend="cloud_llm",
        success=result.success,
        turn_output=result.turn_output,
        raw_output=result.raw_text,
        parsed_json=parsed_json,
        json_valid=result.json_valid,
        schema_pass=result.schema_valid and result.final_schema_pass,
        fallback_used=result.fallback_used,
        latency_ms=None,
        error=result.error,
        model_name=result.model_name,
        error_type=result.error_type,
        schema_error=result.error_message_preview,
    )
