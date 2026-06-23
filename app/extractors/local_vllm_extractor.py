from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any

from app.rules.risk_rules import evaluate_risk_rules
from app.schemas.report_schemas import RunState, TurnOutput
from app.utils.json_repair import (
    extract_json_object_text as _extract_json_object_text,
    loads_json_object_with_repair,
)


DEFAULT_LOCAL_LLM_BASE_URL = "http://127.0.0.1:8000/v1"
DEFAULT_LOCAL_LLM_MODEL = "tcm-extractor-lora"
DEFAULT_LOCAL_BASE_LLM_MODEL = "/mnt/e/models/Qwen2.5-1.5B-Instruct"
DEFAULT_LOCAL_LLM_API_KEY = "EMPTY"
DEFAULT_LOCAL_LLM_MAX_TOKENS = 512
DEFAULT_LOCAL_LLM_TEMPERATURE = 0.0


@dataclass
class LocalVLLMExtractionResult:
    success: bool
    turn_output: TurnOutput | None
    raw_text: str | None
    error: str | None
    model_name: str
    base_url: str
    json_valid: bool = False
    schema_valid: bool = False
    final_schema_pass: bool = False
    fallback_used: bool = False
    latency_ms: float | None = None
    error_type: str | None = None
    parsed_json: dict[str, Any] | None = None
    schema_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "turn_output": self.turn_output.model_dump() if self.turn_output else None,
            "raw_text": self.raw_text,
            "raw_output": self.raw_text,
            "parsed_json": self.parsed_json,
            "error": self.error,
            "model_name": self.model_name,
            "base_url": self.base_url,
            "json_valid": self.json_valid,
            "schema_valid": self.schema_valid,
            "schema_pass": self.schema_valid,
            "final_schema_pass": self.final_schema_pass,
            "fallback_used": self.fallback_used,
            "latency_ms": self.latency_ms,
            "error_type": self.error_type,
            "schema_error": self.schema_error,
        }


def get_local_llm_base_url() -> str:
    return os.getenv("LOCAL_LLM_BASE_URL") or DEFAULT_LOCAL_LLM_BASE_URL


def get_local_llm_model() -> str:
    return os.getenv("LOCAL_LLM_MODEL") or DEFAULT_LOCAL_LLM_MODEL


def get_local_llm_api_key() -> str:
    return os.getenv("LOCAL_LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or DEFAULT_LOCAL_LLM_API_KEY


def get_local_llm_max_tokens() -> int:
    raw = os.getenv("LOCAL_LLM_MAX_TOKENS")
    if not raw:
        return DEFAULT_LOCAL_LLM_MAX_TOKENS
    try:
        return max(1, int(raw))
    except ValueError:
        return DEFAULT_LOCAL_LLM_MAX_TOKENS


def get_local_llm_temperature() -> float:
    raw = os.getenv("LOCAL_LLM_TEMPERATURE")
    if not raw:
        return DEFAULT_LOCAL_LLM_TEMPERATURE
    try:
        return float(raw)
    except ValueError:
        return DEFAULT_LOCAL_LLM_TEMPERATURE


def get_local_llm_response_format_enabled() -> bool:
    raw = os.getenv("LOCAL_LLM_RESPONSE_FORMAT") or os.getenv("LOCAL_LLM_ENABLE_RESPONSE_FORMAT")
    return str(raw or "").strip().lower() in {"1", "true", "yes", "json", "json_object"}


def _safe_error_preview(error: Any, limit: int = 240) -> str:
    text = str(error)
    text = re.sub(r"sk-[A-Za-z0-9_\-]+", "[redacted_api_key]", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _classify_error(error: Any) -> str:
    text = f"{type(error).__name__}: {error}".lower()
    if "connection" in text or "connect" in text or "timeout" in text:
        return "local_vllm_unavailable"
    if "authentication" in text or "unauthorized" in text or "401" in text:
        return "authentication_error"
    if "json_object_" in text or "empty_llm_response" in text:
        return "json_invalid"
    if "json" in text and ("decode" in text or "parse" in text):
        return "json_invalid"
    if "validation" in text or "schema" in text:
        return "schema_mismatch"
    return type(error).__name__


def extract_json_object_text(raw_text: str) -> str:
    return _extract_json_object_text(raw_text)


def _build_messages(state: RunState, user_input: str) -> list[dict[str, str]]:
    schema_hint = {
        "chief_complaint": None,
        "duration": None,
        "symptoms": [],
        "symptoms_status": "unknown",
        "sleep": None,
        "appetite": None,
        "stool_urine": None,
        "risk_flags": [],
        "risk_flags_status": "unknown",
        "next_question": None,
        "summary": None,
    }
    return [
        {
            "role": "system",
            "content": (
                "你是中医问诊辅助系统的结构化抽取器。"
                "你只负责从用户输入中抽取 TurnOutput JSON 候选。"
                "只输出合法 JSON，不输出 Markdown 或解释。"
                "不要诊断，不要开方，不要给治疗方案，不要替代医生判断。"
                "输出字段必须严格对齐 TurnOutput schema。"
            ),
        },
        {
            "role": "user",
            "content": (
                "Previous RunState JSON:\n"
                f"{json.dumps(state.model_dump(), ensure_ascii=False, indent=2)}\n\n"
                "Required TurnOutput shape:\n"
                f"{json.dumps(schema_hint, ensure_ascii=False, indent=2)}\n\n"
                f"User input:\n{user_input}"
            ),
        },
    ]


def _apply_risk_guard(turn_output: TurnOutput, state: RunState, user_input: str) -> TurnOutput:
    guarded = turn_output.model_copy(deep=True)
    guarded.risk_flags = []
    guarded.risk_flags_status = "unknown"
    risk_eval = evaluate_risk_rules(user_input, previous_status=state.risk_flags_status)
    if risk_eval.risk_status == "present":
        guarded.risk_flags_status = "present"
        guarded.risk_flags = list(dict.fromkeys(risk_eval.risk_flags))
    elif risk_eval.risk_status == "none":
        guarded.risk_flags_status = "none"
    return guarded


def _build_client(base_url: str, api_key: str) -> Any:
    from openai import OpenAI

    return OpenAI(base_url=base_url, api_key=api_key)


def extract_with_local_vllm(
    state: RunState,
    user_input: str,
    *,
    client: Any | None = None,
    base_url: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    response_format_enabled: bool | None = None,
) -> LocalVLLMExtractionResult:
    selected_base_url = base_url or get_local_llm_base_url()
    selected_model = model or get_local_llm_model()
    selected_api_key = api_key or get_local_llm_api_key()
    selected_max_tokens = max_tokens or get_local_llm_max_tokens()
    selected_temperature = get_local_llm_temperature() if temperature is None else temperature
    selected_response_format = (
        get_local_llm_response_format_enabled()
        if response_format_enabled is None
        else response_format_enabled
    )
    started = time.perf_counter()
    raw_text: str | None = None
    parsed: dict[str, Any] | None = None

    try:
        active_client = client or _build_client(selected_base_url, selected_api_key)
        request_payload: dict[str, Any] = {
            "model": selected_model,
            "messages": _build_messages(state, user_input),
            "temperature": selected_temperature,
            "max_tokens": selected_max_tokens,
        }
        if selected_response_format:
            request_payload["response_format"] = {"type": "json_object"}

        completion = active_client.chat.completions.create(
            **request_payload,
        )
        raw_text = completion.choices[0].message.content or ""
    except Exception as exc:  # noqa: BLE001
        return LocalVLLMExtractionResult(
            success=False,
            turn_output=None,
            raw_text=raw_text,
            error=_safe_error_preview(exc),
            model_name=selected_model,
            base_url=selected_base_url,
            json_valid=False,
            schema_valid=False,
            final_schema_pass=False,
            fallback_used=False,
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
            error_type=_classify_error(exc),
        )

    try:
        repair_result = loads_json_object_with_repair(raw_text)
        parsed = repair_result.data
    except Exception as exc:  # noqa: BLE001
        return LocalVLLMExtractionResult(
            success=False,
            turn_output=None,
            raw_text=raw_text,
            error=_safe_error_preview(exc),
            model_name=selected_model,
            base_url=selected_base_url,
            json_valid=False,
            schema_valid=False,
            final_schema_pass=False,
            fallback_used=False,
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
            error_type=_classify_error(exc),
        )

    try:
        candidate = TurnOutput.model_validate(parsed)
    except Exception as exc:  # noqa: BLE001
        schema_error = _safe_error_preview(exc)
        return LocalVLLMExtractionResult(
            success=False,
            turn_output=None,
            raw_text=raw_text,
            error=schema_error,
            model_name=selected_model,
            base_url=selected_base_url,
            json_valid=True,
            schema_valid=False,
            final_schema_pass=False,
            fallback_used=False,
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
            error_type=_classify_error(exc),
            parsed_json=parsed,
            schema_error=schema_error,
        )

    try:
        turn_output = _apply_risk_guard(candidate, state, user_input)
        TurnOutput.model_validate(turn_output.model_dump())
        return LocalVLLMExtractionResult(
            success=True,
            turn_output=turn_output,
            raw_text=raw_text,
            error=None,
            model_name=selected_model,
            base_url=selected_base_url,
            json_valid=True,
            schema_valid=True,
            final_schema_pass=True,
            fallback_used=False,
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
            parsed_json=parsed,
        )
    except Exception as exc:  # noqa: BLE001
        schema_error = _safe_error_preview(exc)
        return LocalVLLMExtractionResult(
            success=False,
            turn_output=None,
            raw_text=raw_text,
            error=schema_error,
            model_name=selected_model,
            base_url=selected_base_url,
            json_valid=parsed is not None,
            schema_valid=False,
            final_schema_pass=False,
            fallback_used=False,
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
            error_type=_classify_error(exc),
            parsed_json=parsed,
            schema_error=schema_error,
        )
