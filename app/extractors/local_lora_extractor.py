from __future__ import annotations

import os
from typing import Any

from app.extractors.local_vllm_extractor import (
    DEFAULT_LOCAL_LLM_API_KEY,
    DEFAULT_LOCAL_LLM_BASE_URL,
    DEFAULT_LOCAL_LLM_MAX_TOKENS,
    DEFAULT_LOCAL_LLM_TEMPERATURE,
    LocalVLLMExtractionResult,
    extract_with_local_vllm,
    get_local_llm_api_key,
    get_local_llm_base_url,
    get_local_llm_max_tokens,
    get_local_llm_temperature,
)
from app.rules.risk_rules import evaluate_risk_rules
from app.schemas.report_schemas import RunState, TurnOutput


DEFAULT_LOCAL_LORA_MODEL = "tcm-extractor-lora"


def get_local_lora_base_url() -> str:
    return os.getenv("LOCAL_LORA_BASE_URL") or get_local_llm_base_url() or DEFAULT_LOCAL_LLM_BASE_URL


def get_local_lora_model() -> str:
    return os.getenv("LOCAL_LORA_MODEL") or os.getenv("LOCAL_LLM_MODEL") or DEFAULT_LOCAL_LORA_MODEL


def get_local_lora_api_key() -> str:
    return os.getenv("LOCAL_LORA_API_KEY") or get_local_llm_api_key() or DEFAULT_LOCAL_LLM_API_KEY


def allow_extractor_fallback() -> bool:
    return os.getenv("ALLOW_EXTRACTOR_FALLBACK", "").strip().lower() in {"1", "true", "yes"}


def _explicit_rule_fallback(
    state: RunState,
    user_input: str,
    failed_result: LocalVLLMExtractionResult,
) -> LocalVLLMExtractionResult:
    turn_output = TurnOutput(summary="local_lora unavailable; explicit rule fallback used.")
    risk_eval = evaluate_risk_rules(user_input, previous_status=state.risk_flags_status)
    if risk_eval.risk_status == "present":
        turn_output.risk_flags_status = "present"
        turn_output.risk_flags = risk_eval.risk_flags
    elif risk_eval.risk_status == "none":
        turn_output.risk_flags_status = "none"

    return LocalVLLMExtractionResult(
        success=False,
        turn_output=turn_output,
        raw_text=failed_result.raw_text,
        error=failed_result.error,
        model_name=failed_result.model_name,
        base_url=failed_result.base_url,
        json_valid=failed_result.json_valid,
        schema_valid=True,
        final_schema_pass=True,
        fallback_used=True,
        latency_ms=failed_result.latency_ms,
        error_type=failed_result.error_type,
        parsed_json=turn_output.model_dump(),
        schema_error=failed_result.schema_error,
    )


def extract_with_local_lora(
    state: RunState,
    user_input: str,
    *,
    client: Any | None = None,
    base_url: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    response_format_enabled: bool = False,
    allow_fallback: bool | None = None,
    **kwargs: Any,
) -> LocalVLLMExtractionResult:
    result = extract_with_local_vllm(
        state,
        user_input,
        client=client,
        base_url=base_url or get_local_lora_base_url(),
        model=model or get_local_lora_model(),
        api_key=api_key or get_local_lora_api_key(),
        max_tokens=max_tokens or get_local_llm_max_tokens() or DEFAULT_LOCAL_LLM_MAX_TOKENS,
        temperature=get_local_llm_temperature() if temperature is None else temperature,
        response_format_enabled=response_format_enabled,
        **kwargs,
    )
    fallback_allowed = allow_extractor_fallback() if allow_fallback is None else allow_fallback
    if result.success or not fallback_allowed:
        return result
    return _explicit_rule_fallback(state, user_input, result)
