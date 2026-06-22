from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional

try:
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_openai import ChatOpenAI
except ImportError:  # pragma: no cover - minimal local env fallback
    ChatPromptTemplate = None
    ChatOpenAI = None

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - python-dotenv is optional at runtime
    load_dotenv = None

from app.schemas.report_schemas import RunState, TurnOutput


ExtractionMode = Literal[
    "structured_output",
    "tool_calling_structured_output",
    "fake_structured_output",
    "json_prompt_fallback",
    "rule_fallback",
]

ExtractionStrategy = Literal[
    "provider_native_structured_output",
    "tool_calling_structured_output",
    "json_prompt",
    "fake_structured_output",
    "rule_fallback",
]

if load_dotenv is not None:
    load_dotenv()


EXTRACTION_SYSTEM_PROMPT = """
你是中医问诊辅助系统中的结构化抽取模块。

你只负责从用户自然语言中抽取问诊字段，写入 TurnOutput JSON。
你不能诊断。
你不能判断证型。
你不能开方。
你不能给治疗方案。
你不能输出药物、处方或替代医生判断的内容。

必须只输出 JSON 对象，不要输出 Markdown，不要解释。

字段必须与以下 schema 对齐：
- chief_complaint: string or null，主要不适
- duration: string or null，持续时间
- symptoms: string[]，伴随症状
- symptoms_status: "unknown" | "none" | "present"
- sleep: string or null
- appetite: string or null
- stool_urine: string or null，二便相关信息
- risk_flags: string[]，仅记录胸痛、呼吸困难、持续高热、便血、呕血、意识异常、突发剧烈腹痛等风险信号
- risk_flags_status: "unknown" | "none" | "present"
- next_question: null
- summary: string or null，简短整理本轮抽取信息，不要诊断

重要规则：
- 空列表不等于 none，是否确认必须看 *_status。
- 普通“发热/发烧”不等于“持续高热”。
- “没有胸痛”“不便血”“没有发热”这类否定句不能抽成风险 present。
- 如果用户没有提到某字段，保持 null、空列表或 unknown。
""".strip()


@dataclass
class ExtractionResult:
    success: bool
    turn_output: Optional[TurnOutput]
    raw_text: Optional[str]
    error: Optional[str]
    mode: ExtractionMode
    json_valid: bool = False
    schema_valid: bool = False
    raw_llm_json_valid: bool = False
    final_schema_pass: bool = False
    fallback_used: bool = False
    extractor_mode: str = ""
    model_name: Optional[str] = None
    error_type: Optional[str] = None
    strategy: Optional[str] = None
    error_message_preview: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "turn_output": self.turn_output.model_dump() if self.turn_output else None,
            "raw_text": self.raw_text,
            "error": self.error,
            "mode": self.mode,
            "strategy": self.strategy,
            "json_valid": self.json_valid,
            "schema_valid": self.schema_valid,
            "raw_llm_json_valid": self.raw_llm_json_valid,
            "final_schema_pass": self.final_schema_pass,
            "fallback_used": self.fallback_used,
            "extractor_mode": self.extractor_mode or self.mode,
            "model_name": self.model_name,
            "error_type": self.error_type,
            "error_message_preview": self.error_message_preview,
        }


def state_to_json_dict(state: RunState) -> Dict[str, Any]:
    return state.model_dump()


def get_model_name() -> Optional[str]:
    return os.getenv("OPENAI_MODEL") or os.getenv("MODEL_NAME")


def get_missing_api_config() -> list[str]:
    missing = []
    if not os.getenv("OPENAI_API_KEY"):
        missing.append("OPENAI_API_KEY")
    if not os.getenv("OPENAI_BASE_URL"):
        missing.append("OPENAI_BASE_URL")
    if not os.getenv("OPENAI_MODEL"):
        missing.append("OPENAI_MODEL")
    return missing


def _safe_error_preview(error: Any, limit: int = 240) -> str:
    text = str(error)
    text = re.sub(r"sk-[A-Za-z0-9_\-]+", "[redacted_api_key]", text)
    text = re.sub(r"api key:\s*[^,}]+", "api key: [redacted]", text, flags=re.IGNORECASE)
    text = re.sub(r"key:\s*[^,}]+", "key: [redacted]", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _classify_error(error: Any) -> str:
    text = f"{type(error).__name__}: {error}".lower()
    if "missing_api_config" in text:
        return "missing_api_config"
    if "authentication" in text or "unauthorized" in text or "401" in text or "invalid api key" in text:
        return "authentication_error"
    if "tool" in text or "function" in text or "response_format" in text or "json_schema" in text:
        return "provider_incompatibility"
    if "json" in text and ("decode" in text or "parse" in text or "expecting" in text):
        return "json_invalid"
    if "validation" in text or "model_validate" in text or "schema" in text:
        return "schema_mismatch"
    return type(error).__name__


def _is_fatal_provider_error(error_type: Optional[str]) -> bool:
    return error_type in {"authentication_error", "missing_api_config"}


def _prefer_json_prompt_first() -> bool:
    model_name = (get_model_name() or "").lower()
    base_url = (os.getenv("OPENAI_BASE_URL") or "").lower()
    return "deepseek" in model_name or "deepseek" in base_url


def _content_to_text(response: Any) -> Optional[str]:
    if response is None:
        return None
    if isinstance(response, str):
        return response
    if isinstance(response, TurnOutput):
        return json.dumps(response.model_dump(), ensure_ascii=False)
    content = getattr(response, "content", None)
    if isinstance(content, str):
        return content
    try:
        return json.dumps(response, ensure_ascii=False, default=str)
    except Exception:
        return str(response)


def _extract_json_object_text(raw_text: str) -> str:
    if not raw_text:
        raise ValueError("empty_llm_response")

    text = raw_text.strip()
    text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"^```\s*", "", text).strip()
    text = re.sub(r"\s*```$", "", text).strip()

    if text.startswith("{") and text.endswith("}"):
        return text

    start = text.find("{")
    if start == -1:
        raise ValueError("json_object_start_not_found")

    depth = 0
    end = -1
    for idx in range(start, len(text)):
        if text[idx] == "{":
            depth += 1
        elif text[idx] == "}":
            depth -= 1
            if depth == 0:
                end = idx
                break

    if end == -1:
        raise ValueError("json_object_end_not_found")
    return text[start:end + 1].strip()


def _validate_turn_output(value: Any) -> TurnOutput:
    if isinstance(value, TurnOutput):
        return value
    if isinstance(value, dict):
        return TurnOutput.model_validate(value)
    return TurnOutput.model_validate(json.loads(str(value)))


def _json_loads_turn_output(raw_text: str) -> TurnOutput:
    return TurnOutput.model_validate(json.loads(raw_text))


def _json_prompt_loads_turn_output(raw_text: str) -> TurnOutput:
    json_text = _extract_json_object_text(raw_text)
    return TurnOutput.model_validate(json.loads(json_text))


def _build_chat_model(response_format: Optional[dict[str, Any]] = None) -> Any:
    if ChatOpenAI is None:
        raise ImportError("langchain_openai is not installed")
    model_name = get_model_name()
    if get_missing_api_config() or not model_name:
        raise RuntimeError("missing_api_config")

    llm = ChatOpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL"),
        model=model_name,
        temperature=0.2,
    )
    if response_format:
        return llm.bind(response_format=response_format)
    return llm


def _build_prompt() -> Any:
    if ChatPromptTemplate is None:
        raise ImportError("langchain_core is not installed")
    return ChatPromptTemplate.from_messages(
        [
            ("system", EXTRACTION_SYSTEM_PROMPT),
            (
                "human",
                """
历史累计状态如下（JSON）：
{state_json}

本轮用户输入如下：
{user_input}

请只输出符合 TurnOutput 的 JSON。
""".strip(),
            ),
        ]
    )


def _extract_duration(text: str) -> Optional[str]:
    patterns = [
        r"一天", r"两天", r"三天", r"四天", r"五天", r"六天", r"七天",
        r"一周", r"两周", r"三周", r"一个月", r"两个月", r"三个月",
        r"\d+天", r"\d+周", r"\d+个月", r"\d+年",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    return None


def _fake_term_negated(text: str, term: str, window: int = 6) -> bool:
    idx = text.find(term)
    if idx < 0:
        return False
    prefix = text[max(0, idx - window):idx]
    return any(marker in prefix for marker in ["没有", "无", "未见", "否认", "不"])


def _extract_first_segment(text: str, keywords: list[str]) -> Optional[str]:
    for segment in re.split(r"[，。；;,.、\s]+", text):
        segment = segment.strip()
        if segment and any(keyword in segment for keyword in keywords):
            return segment
    return None


def _extract_joined_segments(text: str, keywords: list[str]) -> Optional[str]:
    segments = []
    for segment in re.split(r"[，。；;,.、\s]+", text):
        segment = segment.strip()
        if segment and any(keyword in segment for keyword in keywords):
            segments.append(segment)
    return "；".join(dict.fromkeys(segments)) if segments else None


def _fake_chief_complaint(text: str) -> Optional[str]:
    for term in ["胃胀", "胃痛", "腹泻", "腹痛", "咳嗽", "头晕", "胸闷", "发热", "发烧", "高烧", "高热"]:
        if term in text and not _fake_term_negated(text, term):
            if term in {"高烧", "高热", "发烧"}:
                return "发热"
            return term
    if "胃不舒服" in text:
        return "胃不舒服"
    if "肚子不舒服" in text:
        return "肚子不舒服"
    return None


def _fake_symptoms(text: str, chief_complaint: Optional[str]) -> tuple[list[str], str]:
    if any(phrase in text for phrase in ["没有其他症状", "没有别的症状", "无其他症状", "无伴随症状"]):
        return [], "none"

    symptoms = []
    for term in ["恶心", "反酸", "乏力", "头晕", "咳嗽", "腹泻", "腹痛", "发热"]:
        if term in text and term != chief_complaint and not _fake_term_negated(text, term):
            symptoms.append(term)

    symptoms = list(dict.fromkeys(symptoms))
    if symptoms:
        return symptoms, "present"
    return [], "unknown"


def build_fake_turn_output(state: RunState, user_input: str) -> TurnOutput:
    from app.rules.risk_rules import evaluate_risk_rules

    text = (user_input or "").strip()
    chief_complaint = _fake_chief_complaint(text)
    duration = _extract_duration(text)
    symptoms, symptoms_status = _fake_symptoms(text, chief_complaint)
    sleep = _extract_first_segment(text, ["睡眠", "睡得", "失眠", "入睡", "多梦"])
    appetite = _extract_first_segment(text, ["食欲", "胃口", "饭量", "吃饭"])
    stool_urine = _extract_joined_segments(text, ["大便", "小便", "二便", "排便", "尿"])
    risk_eval = evaluate_risk_rules(text, previous_status=state.risk_flags_status)

    risk_flags = []
    risk_flags_status = "unknown"
    if risk_eval.risk_status == "present":
        risk_flags_status = "present"
        risk_flags = risk_eval.risk_flags
    elif risk_eval.risk_status == "none":
        risk_flags_status = "none"

    return TurnOutput(
        chief_complaint=chief_complaint,
        duration=duration,
        symptoms=symptoms,
        symptoms_status=symptoms_status,
        sleep=sleep,
        appetite=appetite,
        stool_urine=stool_urine,
        risk_flags=risk_flags,
        risk_flags_status=risk_flags_status,
        summary="fake structured extractor output for deterministic P0 tests.",
    )


def extract_with_fake_structured_output(
    state: RunState,
    user_input: str,
    raw_text: Optional[str] = None,
) -> ExtractionResult:
    try:
        if raw_text is None:
            fake_output = build_fake_turn_output(state, user_input)
            raw_text = json.dumps(fake_output.model_dump(), ensure_ascii=False)
        turn_output = _json_loads_turn_output(raw_text)
        return ExtractionResult(
            success=True,
            turn_output=turn_output,
            raw_text=raw_text,
            error=None,
            mode="fake_structured_output",
            strategy="fake_structured_output",
            json_valid=True,
            schema_valid=True,
            raw_llm_json_valid=True,
            final_schema_pass=True,
            fallback_used=False,
            extractor_mode="fake",
            model_name="fake",
        )
    except Exception as exc:
        return extract_with_rule_fallback(
            state=state,
            user_input=user_input,
            error=f"fake_structured_output failed: {_safe_error_preview(exc)}",
            requested_extractor_mode="fake",
            error_type=_classify_error(exc),
        )


def _structured_result(
    turn_output: TurnOutput,
    response: Any,
    mode: ExtractionMode,
    strategy: ExtractionStrategy,
) -> ExtractionResult:
    raw_text = _content_to_text(response)
    return ExtractionResult(
        success=True,
        turn_output=turn_output,
        raw_text=raw_text,
        error=None,
        mode=mode,
        strategy=strategy,
        json_valid=True,
        schema_valid=True,
        raw_llm_json_valid=True,
        final_schema_pass=True,
        fallback_used=False,
        extractor_mode="real_llm",
        model_name=get_model_name(),
    )


def extract_with_provider_native_structured_output(state: RunState, user_input: str) -> ExtractionResult:
    llm = _build_chat_model()
    structured_llm = llm.with_structured_output(TurnOutput, method="json_schema")
    chain = _build_prompt() | structured_llm
    response = chain.invoke(
        {
            "state_json": json.dumps(state_to_json_dict(state), ensure_ascii=False, indent=2),
            "user_input": user_input,
        }
    )
    turn_output = _validate_turn_output(response)
    return _structured_result(
        turn_output=turn_output,
        response=response,
        mode="structured_output",
        strategy="provider_native_structured_output",
    )


def extract_with_tool_calling_structured_output(state: RunState, user_input: str) -> ExtractionResult:
    llm = _build_chat_model()
    structured_llm = llm.with_structured_output(TurnOutput, method="function_calling")
    chain = _build_prompt() | structured_llm
    response = chain.invoke(
        {
            "state_json": json.dumps(state_to_json_dict(state), ensure_ascii=False, indent=2),
            "user_input": user_input,
        }
    )
    turn_output = _validate_turn_output(response)
    return _structured_result(
        turn_output=turn_output,
        response=response,
        mode="tool_calling_structured_output",
        strategy="tool_calling_structured_output",
    )


def extract_with_json_prompt_fallback(state: RunState, user_input: str) -> ExtractionResult:
    chain = _build_prompt() | _build_chat_model(response_format={"type": "json_object"})
    response = chain.invoke(
        {
            "state_json": json.dumps(state_to_json_dict(state), ensure_ascii=False, indent=2),
            "user_input": user_input,
        }
    )
    raw_text = _content_to_text(response) or ""
    turn_output = _json_prompt_loads_turn_output(raw_text)
    return ExtractionResult(
        success=True,
        turn_output=turn_output,
        raw_text=raw_text,
        error=None,
        mode="json_prompt_fallback",
        strategy="json_prompt",
        json_valid=True,
        schema_valid=True,
        raw_llm_json_valid=True,
        final_schema_pass=True,
        fallback_used=False,
        extractor_mode="real_llm",
        model_name=get_model_name(),
    )


def extract_with_rule_fallback(
    state: RunState,
    user_input: str,
    error: Optional[str] = None,
    requested_extractor_mode: str = "fallback",
    error_type: Optional[str] = None,
) -> ExtractionResult:
    turn_output = TurnOutput(
        summary="模型抽取不可用，本轮仅执行规则兜底，信息可能不完整。",
    )

    try:
        from app.rules.risk_rules import evaluate_risk_rules

        risk_eval = evaluate_risk_rules(user_input)
        if risk_eval.risk_status == "present":
            turn_output.risk_flags_status = "present"
            turn_output.risk_flags = risk_eval.risk_flags
        elif risk_eval.risk_status == "none":
            turn_output.risk_flags_status = "none"
    except Exception:
        pass

    sanitized_error = _safe_error_preview(error) if error else None
    return ExtractionResult(
        success=False,
        turn_output=turn_output,
        raw_text=None,
        error=sanitized_error,
        mode="rule_fallback",
        strategy="rule_fallback",
        json_valid=False,
        schema_valid=True,
        raw_llm_json_valid=False,
        final_schema_pass=True,
        fallback_used=True,
        extractor_mode=requested_extractor_mode,
        model_name=get_model_name(),
        error_type=error_type or (_classify_error(error) if error else None),
        error_message_preview=sanitized_error,
    )


def extract_turn(
    state: RunState,
    user_input: str,
    prefer_structured_output: bool = True,
    extractor_mode: Optional[str] = None,
) -> ExtractionResult:
    selected_mode = extractor_mode or os.getenv("TCM_EXTRACTOR_MODE", "auto")
    if selected_mode == "fake":
        return extract_with_fake_structured_output(state=state, user_input=user_input)
    if selected_mode in {"fallback", "rule_fallback"}:
        return extract_with_rule_fallback(
            state=state,
            user_input=user_input,
            requested_extractor_mode="fallback",
        )
    if selected_mode == "real_llm" and get_missing_api_config():
        missing = ",".join(get_missing_api_config())
        return extract_with_rule_fallback(
            state=state,
            user_input=user_input,
            error=f"missing_api_config: {missing}",
            requested_extractor_mode="real_llm",
            error_type="missing_api_config",
        )

    errors: list[str] = []
    last_error_type: Optional[str] = None

    strategies = []
    if selected_mode == "real_llm" and _prefer_json_prompt_first():
        strategies.append(("json_prompt", extract_with_json_prompt_fallback))
    if prefer_structured_output and selected_mode in {"auto", "structured_output", "real_llm"}:
        strategies.extend(
            [
                ("provider_native_structured_output", extract_with_provider_native_structured_output),
                ("tool_calling_structured_output", extract_with_tool_calling_structured_output),
            ]
        )
    if not any(strategy_name == "json_prompt" for strategy_name, _ in strategies):
        strategies.append(("json_prompt", extract_with_json_prompt_fallback))

    for strategy_name, strategy_func in strategies:
        try:
            return strategy_func(state, user_input)
        except Exception as exc:
            last_error_type = _classify_error(exc)
            errors.append(f"{strategy_name} failed ({last_error_type}): {_safe_error_preview(exc)}")
            if _is_fatal_provider_error(last_error_type):
                break

    return extract_with_rule_fallback(
        state=state,
        user_input=user_input,
        error="; ".join(errors),
        requested_extractor_mode="real_llm" if selected_mode == "real_llm" else "fallback",
        error_type=last_error_type or "import_or_runtime_error",
    )
