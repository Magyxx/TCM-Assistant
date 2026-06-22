from __future__ import annotations

import json
import re
from time import perf_counter
from typing import Any, Protocol

from pydantic import ValidationError

from app.extractors.openai_compatible_client import (
    LocalLLMClientError,
    OpenAICompatibleChatClient,
    extract_message_content,
)
from app.extractors.simple_rules import build_rule_turn_output
from app.schemas.report_schemas import RunState, TurnOutput


LOCAL_LORA_SYSTEM_PROMPT = """
你是 TCM-Assistant 的 local_lora 单轮结构化抽取器。

只允许做一件事：从本轮 user_input 和可选 RunState context 中抽取 TurnOutput JSON。
禁止诊断，禁止判断证型，禁止开方，禁止输出药物或治疗方案。
只输出一个 JSON object，不要 Markdown，不要解释，不要包裹代码块。

TurnOutput 字段：
- chief_complaint: string or null
- duration: string or null
- symptoms: string[]
- symptoms_status: "unknown" | "none" | "present"
- sleep: string or null
- appetite: string or null
- stool_urine: string or null
- stool: string or null
- urination: string or null
- risk_flags: string[]
- risk_flags_status: "unknown" | "none" | "present"
- next_question: null
- summary: string or null
- metadata: object

边界：
- 你输出的 risk_flags/risk_flags_status 只是候选抽取，主系统 Risk Rules 才能决定权威风险状态。
- "没有胸痛""不胸痛""没有发热" 等否定句必须保持否定，不能误升为风险 present。
- 未提到的字段保持 null、空列表或 unknown。
""".strip()


class ChatCompletionClient(Protocol):
    def create_chat_completion(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        ...


def _safe_error_preview(error: Any, limit: int = 240) -> str:
    text = str(error)
    text = re.sub(r"Bearer\s+\S+", "Bearer [redacted-secret]", text, flags=re.I)
    text = re.sub(r"sk-[A-Za-z0-9_\-]+", "[redacted-secret]", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _state_context(state: RunState) -> dict[str, Any]:
    return {
        "chief_complaint": state.chief_complaint,
        "duration": state.duration,
        "symptoms": list(state.symptoms),
        "symptoms_status": state.symptoms_status,
        "sleep": state.sleep,
        "appetite": state.appetite,
        "stool_urine": state.stool_urine,
        "stool": state.stool,
        "urination": state.urination,
        "risk_flags_status": state.risk_flags_status,
        "turn_count": state.turn_count,
    }


def build_local_lora_messages(user_input: str, state: RunState | None = None) -> list[dict[str, str]]:
    run_state = state or RunState()
    context_json = json.dumps(_state_context(run_state), ensure_ascii=False, sort_keys=True)
    return [
        {"role": "system", "content": LOCAL_LORA_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "RunState context JSON:\n"
                f"{context_json}\n\n"
                "user_input:\n"
                f"{user_input}\n\n"
                "请只输出 TurnOutput JSON。"
            ),
        },
    ]


def _extract_json_object_text(raw_text: str) -> tuple[str, bool]:
    if not raw_text or not raw_text.strip():
        raise ValueError("empty_llm_response")
    text = raw_text.strip()
    unwrapped = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I).strip()
    unwrapped = re.sub(r"\s*```$", "", unwrapped).strip()
    if unwrapped.startswith("{") and unwrapped.endswith("}"):
        return unwrapped, unwrapped != text

    start = unwrapped.find("{")
    if start < 0:
        raise ValueError("json_object_start_not_found")
    depth = 0
    end = -1
    in_string = False
    escaped = False
    for idx in range(start, len(unwrapped)):
        char = unwrapped[idx]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                end = idx
                break
    if end < 0:
        raise ValueError("json_object_end_not_found")
    return unwrapped[start : end + 1].strip(), True


def parse_turn_output(raw_text: str) -> tuple[TurnOutput, dict[str, Any]]:
    raw = (raw_text or "").strip()
    raw_llm_json_valid = False
    repair_used = False
    try:
        parsed = json.loads(raw)
        raw_llm_json_valid = True
    except json.JSONDecodeError:
        json_text, repair_used = _extract_json_object_text(raw)
        parsed = json.loads(json_text)
    output = TurnOutput.model_validate(parsed)
    return output, {
        "json_valid": True,
        "raw_llm_json_valid": raw_llm_json_valid,
        "repair_used": repair_used,
        "schema_valid": True,
        "final_schema_pass": True,
    }


class LocalLoRAExtractorBackend:
    mode = "local_lora"

    def __init__(self, client: ChatCompletionClient | None = None) -> None:
        self.client = client or OpenAICompatibleChatClient()

    def _fallback_output(
        self,
        user_input: str,
        state: RunState,
        *,
        error_type: str,
        error_message_preview: str,
        raw_output: Any = None,
        metadata: dict[str, Any] | None = None,
        latency_ms: float | None = None,
    ) -> TurnOutput:
        output = build_rule_turn_output(user_input, state=state, mode=self.mode)
        output.metadata.update(
            {
                "backend": self.mode,
                "fallback_backend": "rule_fallback",
                "fallback_used": True,
                "schema_guard": "failed",
                "error_type": error_type,
                "error_message_preview": error_message_preview,
                "raw_output_preview": _safe_error_preview(raw_output) if raw_output is not None else None,
                "json_valid": False,
                "raw_llm_json_valid": False,
                "schema_valid": False,
                "final_schema_pass": False,
                "repair_used": False,
                "risk_authority": "risk_rules_layer",
                "latency_ms": latency_ms,
            }
        )
        if metadata:
            output.metadata.update(metadata)
        return output

    def extract_turn(self, user_input: str, state: RunState | None = None) -> TurnOutput:
        started = perf_counter()
        run_state = state or RunState()
        messages = build_local_lora_messages(user_input, run_state)
        try:
            response = self.client.create_chat_completion(messages)
            raw_content = extract_message_content(response)
            output, parse_metadata = parse_turn_output(raw_content)
        except LocalLLMClientError as exc:
            return self._fallback_output(
                user_input,
                run_state,
                error_type=exc.error_type,
                error_message_preview=_safe_error_preview(exc.message),
                latency_ms=round((perf_counter() - started) * 1000, 3),
            )
        except ValidationError as exc:
            return self._fallback_output(
                user_input,
                run_state,
                error_type="schema_mismatch",
                error_message_preview=_safe_error_preview(exc),
                raw_output=locals().get("raw_content"),
                metadata={"json_valid": True},
                latency_ms=round((perf_counter() - started) * 1000, 3),
            )
        except (json.JSONDecodeError, ValueError) as exc:
            return self._fallback_output(
                user_input,
                run_state,
                error_type="json_invalid",
                error_message_preview=_safe_error_preview(exc),
                raw_output=locals().get("raw_content"),
                latency_ms=round((perf_counter() - started) * 1000, 3),
            )
        except Exception as exc:
            return self._fallback_output(
                user_input,
                run_state,
                error_type=type(exc).__name__,
                error_message_preview=_safe_error_preview(exc),
                raw_output=locals().get("raw_content"),
                latency_ms=round((perf_counter() - started) * 1000, 3),
            )

        output = TurnOutput.model_validate(output)
        output.metadata.update(
            {
                "backend": self.mode,
                "fallback_used": False,
                "schema_guard": "passed",
                "risk_authority": "risk_rules_layer",
                "latency_ms": round((perf_counter() - started) * 1000, 3),
                **parse_metadata,
            }
        )
        return output


__all__ = [
    "LOCAL_LORA_SYSTEM_PROMPT",
    "LocalLoRAExtractorBackend",
    "build_local_lora_messages",
    "parse_turn_output",
]
