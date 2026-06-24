from __future__ import annotations

import re
from typing import Iterable

from app.rules.risk_rules import evaluate_risk_rules
from app.schemas.report_schemas import RunState, TurnOutput


def _term_negated(text: str, term: str, window: int = 8) -> bool:
    idx = text.find(term)
    if idx < 0:
        return False
    prefix = text[max(0, idx - window) : idx]
    return any(marker in prefix for marker in ["没有", "无", "未见", "否认", "不"])


def _first_term(text: str, terms: Iterable[str]) -> str | None:
    for term in terms:
        if term in text and not _term_negated(text, term):
            return term
    return None


def _first_segment(text: str, terms: Iterable[str]) -> str | None:
    for segment in re.split(r"[，。；;,.、\s]+", text):
        segment = segment.strip()
        if segment and any(term in segment for term in terms):
            return segment
    return None


def _joined_segments(text: str, terms: Iterable[str]) -> str | None:
    values: list[str] = []
    for segment in re.split(r"[，。；;,.、\s]+", text):
        segment = segment.strip()
        if segment and any(term in segment for term in terms):
            values.append(segment)
    return "；".join(dict.fromkeys(values)) if values else None


def extract_duration(text: str) -> str | None:
    patterns = [
        r"半天",
        r"一天",
        r"两天",
        r"三天",
        r"四天",
        r"五天",
        r"六天",
        r"七天",
        r"一周",
        r"两周",
        r"三周",
        r"一个月",
        r"两个月",
        r"三个月",
        r"半年",
        r"一年",
        r"\d+天",
        r"\d+周",
        r"\d+个月",
        r"\d+年",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    return None


def build_rule_turn_output(user_input: str, state: RunState | None = None, *, mode: str = "rule_fallback") -> TurnOutput:
    text = (user_input or "").strip()
    state = state or RunState()
    chief = _first_term(
        text,
        [
            "胃胀",
            "胃痛",
            "胃不舒服",
            "腹胀",
            "腹痛",
            "腹泻",
            "便秘",
            "恶心",
            "反酸",
            "呕吐",
            "头痛",
            "头晕",
            "咳嗽",
            "睡眠差",
            "失眠",
            "胸痛",
            "呼吸困难",
            "便血",
            "呕血",
            "高热",
            "高烧",
        ],
    )
    if chief in {"失眠"}:
        chief = "睡眠差"

    duration = extract_duration(text)
    symptoms: list[str] = []
    for term in ["恶心", "反酸", "乏力", "头晕", "咳嗽", "腹泻", "腹痛", "胸闷", "心慌", "发热"]:
        if term != chief and term in text and not _term_negated(text, term):
            symptoms.append(term)
    symptoms = list(dict.fromkeys(symptoms))
    if any(phrase in text for phrase in ["没有其他症状", "没有别的症状", "无其他症状", "无伴随症状"]):
        symptoms_status = "none"
        symptoms = []
    else:
        symptoms_status = "present" if symptoms else "unknown"

    sleep = _first_segment(text, ["睡眠", "睡得", "失眠", "入睡", "多梦", "睡眠差"])
    appetite = _first_segment(text, ["食欲", "胃口", "饭量", "吃饭", "饭后"])
    stool = _joined_segments(text, ["大便", "排便", "腹泻", "便秘", "便血", "黑便"])
    urination = _joined_segments(text, ["小便", "尿", "尿量"])
    stool_urine = "；".join(item for item in [stool, urination] if item) or None

    risk_eval = evaluate_risk_rules(text, previous_status=state.risk_flags_status)
    risk_flags: list[str] = []
    risk_flags_status = "unknown"
    if risk_eval.risk_status == "present":
        risk_flags_status = "present"
        risk_flags = risk_eval.risk_flags
    elif risk_eval.risk_status == "none":
        risk_flags_status = "none"

    return TurnOutput(
        chief_complaint=chief,
        duration=duration,
        symptoms=symptoms,
        symptoms_status=symptoms_status,
        sleep=sleep,
        appetite=appetite,
        stool_urine=stool_urine,
        stool=stool,
        urination=urination,
        risk_flags=risk_flags,
        risk_flags_status=risk_flags_status,
        summary=f"{mode} structured extractor output.",
        metadata={
            "backend": mode,
            "risk_rule_ids": list(risk_eval.triggered_rule_ids),
            "negated_rule_ids": list(risk_eval.negated_rule_ids),
            "fallback_used": mode != "fake",
            "raw_llm_json_valid": mode != "real_llm",
        },
    )


__all__ = ["build_rule_turn_output", "extract_duration"]
