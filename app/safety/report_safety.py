from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from app.schemas.report_schemas import FinalReport


SAFETY_BOUNDARY_TEXT = (
    "本系统仅用于问诊信息整理和风险提示，不构成诊断或治疗建议，不能替代医生判断。"
    "如出现持续高热、胸痛、呼吸困难、便血、意识异常、剧烈腹痛等高风险信号，应及时线下就医。"
)

FORBIDDEN_PHRASES = [
    "确诊",
    "诊断为",
    "治疗方案",
    "开方",
    "处方",
    "用药方案",
    "替代医生",
    "无需就医",
]

PROTECTED_PHRASES = [
    SAFETY_BOUNDARY_TEXT,
    "不能替代医生判断",
    "不能替代医生",
    "不替代医生判断",
]


@dataclass
class SafetyCheckResult:
    report: FinalReport
    issues: List[str] = field(default_factory=list)
    rewritten: bool = False


def _sanitize_text(text: str) -> tuple[str, List[str]]:
    issues: List[str] = []
    sanitized = text
    protected_values: dict[str, str] = {}

    for index, phrase in enumerate(PROTECTED_PHRASES):
        if phrase in sanitized:
            token = f"__SAFETY_PROTECTED_{index}__"
            protected_values[token] = phrase
            sanitized = sanitized.replace(phrase, token)

    replacements = {
        "确诊": "判断",
        "诊断为": "表现为",
        "治疗方案": "后续处理建议",
        "开方": "记录信息",
        "处方": "建议线下咨询医生",
        "用药方案": "建议线下咨询医生",
        "替代医生": "辅助医生问诊信息整理",
        "无需就医": "若症状持续或加重仍建议线下评估",
    }

    for phrase in FORBIDDEN_PHRASES:
        if phrase in sanitized:
            issues.append(phrase)
            sanitized = sanitized.replace(phrase, replacements.get(phrase, "相关表达"))

    for token, phrase in protected_values.items():
        sanitized = sanitized.replace(token, phrase)

    return sanitized, issues


def safety_post_check_report(report: FinalReport) -> SafetyCheckResult:
    checked = report.model_copy(deep=True)
    issues: List[str] = []

    checked.summary, summary_issues = _sanitize_text(checked.summary)
    checked.impression, impression_issues = _sanitize_text(checked.impression)
    issues.extend(summary_issues)
    issues.extend(impression_issues)

    safe_advice = []
    for item in checked.advice:
        safe_item, item_issues = _sanitize_text(item)
        safe_advice.append(safe_item)
        issues.extend(item_issues)

    if SAFETY_BOUNDARY_TEXT not in checked.impression:
        checked.impression = f"{checked.impression}{SAFETY_BOUNDARY_TEXT}"
    if SAFETY_BOUNDARY_TEXT not in safe_advice:
        safe_advice.append(SAFETY_BOUNDARY_TEXT)

    checked.advice = safe_advice
    checked.metadata = {
        **checked.metadata,
        "safety_post_check_issues": list(dict.fromkeys(issues)),
        "safety_boundary": SAFETY_BOUNDARY_TEXT,
    }

    return SafetyCheckResult(
        report=checked,
        issues=list(dict.fromkeys(issues)),
        rewritten=bool(issues),
    )
