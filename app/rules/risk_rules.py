from __future__ import annotations

import re
from typing import Iterable, List, Optional

from app.rules.rule_types import RiskEvaluation, RiskRule, RiskRuleMatch
from app.schemas.report_schemas import RunState, TriState


NEGATION_MARKERS = ["没有", "并无", "未见", "未出现", "无", "否认", "不"]
CONTRAST_MARKERS = ["但是", "但", "不过", "然而", "可是"]


RISK_RULES: List[RiskRule] = [
    RiskRule(
        rule_id="P0_RISK_CHEST_PAIN",
        name="胸痛风险",
        description="出现胸痛或持续胸痛时，应优先提示线下评估。",
        trigger_keywords=["持续胸痛", "胸痛", "胸口痛", "心口痛"],
        negation_sensitive=True,
        risk_level="urgent",
        risk_flag="胸痛",
        reason_template="用户提到「{keyword}」，属于需要优先关注的风险信号。",
    ),
    RiskRule(
        rule_id="P0_RISK_DYSPNEA",
        name="呼吸困难风险",
        description="呼吸困难、喘不上气等表达需要优先识别。",
        trigger_keywords=["呼吸困难", "喘不上气", "喘不过气", "气喘明显", "呼吸费力"],
        negation_sensitive=True,
        risk_level="urgent",
        risk_flag="呼吸困难",
        reason_template="用户提到「{keyword}」，提示可能存在呼吸困难相关风险。",
    ),
    RiskRule(
        rule_id="P0_RISK_HIGH_FEVER",
        name="持续高热风险",
        description="普通发热不等于持续高热，只有明确高热或高烧不退表达才触发。",
        trigger_keywords=["持续高热", "高热", "高烧不退", "高烧", "持续高烧", "反复高热", "体温39", "39度", "39℃", "39°C"],
        negation_sensitive=True,
        risk_level="urgent",
        risk_flag="持续高热",
        reason_template="用户提到「{keyword}」，属于持续高热相关风险信号。",
    ),
    RiskRule(
        rule_id="P0_RISK_GI_BLEEDING",
        name="消化道出血风险",
        description="便血、呕血、黑便等表达需要提示线下评估。",
        trigger_keywords=["便血", "大便带血", "血便", "呕血", "吐血", "黑便", "柏油样便"],
        negation_sensitive=True,
        risk_level="urgent",
        risk_flag="便血/呕血",
        reason_template="用户提到「{keyword}」，属于消化道出血相关风险信号。",
    ),
    RiskRule(
        rule_id="P0_RISK_CONSCIOUSNESS",
        name="意识异常风险",
        description="意识模糊、意识异常等需要优先识别。",
        trigger_keywords=["意识模糊", "意识异常", "意识不清", "反应迟钝"],
        negation_sensitive=True,
        risk_level="urgent",
        risk_flag="意识异常",
        reason_template="用户提到「{keyword}」，属于意识状态异常相关风险信号。",
    ),
    RiskRule(
        rule_id="P0_RISK_SEVERE_ABDOMINAL_PAIN",
        name="突发剧烈腹痛风险",
        description="突发、剧烈或明显加重的腹痛需要优先识别。",
        trigger_keywords=["突发剧烈腹痛", "剧烈腹痛", "腹痛明显加重", "突然明显腹痛"],
        negation_sensitive=True,
        risk_level="urgent",
        risk_flag="突发剧烈腹痛",
        reason_template="用户提到「{keyword}」，属于腹痛明显加重相关风险信号。",
    ),
]

NEGATED_RISK_ALIASES = {
    "P0_RISK_HIGH_FEVER": ["发热", "发烧", "高热", "高烧"],
    "P0_RISK_CHEST_PAIN": ["胸痛", "胸口痛", "心口痛"],
    "P0_RISK_DYSPNEA": ["呼吸困难", "喘不上气", "喘不过气"],
    "P0_RISK_GI_BLEEDING": ["便血", "大便带血", "血便", "呕血", "吐血", "黑便"],
    "P0_RISK_CONSCIOUSNESS": ["意识异常", "意识模糊", "意识不清"],
    "P0_RISK_SEVERE_ABDOMINAL_PAIN": ["剧烈腹痛", "突发腹痛", "腹痛明显加重"],
}


def normalize_text(text: Optional[str]) -> str:
    if not text:
        return ""
    text = str(text).strip()
    text = re.sub(r"\s+", "", text)
    return text


def _dedupe(items: Iterable[str]) -> List[str]:
    return list(dict.fromkeys([item for item in items if item]))


def _has_contrast_after_last_negation(prefix: str) -> bool:
    last_neg = -1
    for marker in NEGATION_MARKERS:
        idx = prefix.rfind(marker)
        if idx > last_neg:
            last_neg = idx

    if last_neg == -1:
        return False

    tail = prefix[last_neg:]
    return any(marker in tail for marker in CONTRAST_MARKERS)


def is_keyword_negated(text: str, keyword: str, window: int = 12) -> bool:
    text = normalize_text(text)
    if not text or not keyword:
        return False

    start = 0
    while True:
        idx = text.find(keyword, start)
        if idx == -1:
            return False

        prefix = text[max(0, idx - window):idx]
        prefix_segment = re.split(r"[，。；;,.、！？\s]+", prefix)[-1]
        if _has_contrast_after_last_negation(prefix_segment):
            start = idx + len(keyword)
            continue

        if any(marker in prefix_segment for marker in NEGATION_MARKERS):
            return True

        start = idx + len(keyword)


def _match_rule(rule: RiskRule, text: str) -> tuple[list[RiskRuleMatch], bool]:
    matches: List[RiskRuleMatch] = []
    negated = False

    if rule.detector is not None and rule.detector(text):
        matches.append(
            RiskRuleMatch(
                rule_id=rule.rule_id,
                name=rule.name,
                risk_flag=rule.risk_flag,
                risk_level=rule.risk_level,
                keyword=rule.name,
                reason=rule.reason_template.format(keyword=rule.name),
                evidence_text=text,
                negated=False,
            )
        )
        return matches, negated

    for keyword in rule.trigger_keywords:
        if keyword not in text:
            continue

        if rule.negation_sensitive and is_keyword_negated(text, keyword):
            negated = True
            continue

        matches.append(
            RiskRuleMatch(
                rule_id=rule.rule_id,
                name=rule.name,
                risk_flag=rule.risk_flag,
                risk_level=rule.risk_level,
                keyword=keyword,
                reason=rule.reason_template.format(keyword=keyword),
                evidence_text=keyword,
                negated=False,
            )
        )

    if rule.negation_sensitive and not matches:
        for keyword in NEGATED_RISK_ALIASES.get(rule.rule_id, []):
            if keyword in text and is_keyword_negated(text, keyword):
                negated = True
                break

    return matches, negated


def evaluate_risk_rules(user_input: str, previous_status: TriState = "unknown") -> RiskEvaluation:
    text = normalize_text(user_input)
    if not text:
        return RiskEvaluation(risk_status=None)

    matches: List[RiskRuleMatch] = []
    negated_rule_ids: List[str] = []

    for rule in RISK_RULES:
        rule_matches, negated = _match_rule(rule, text)
        matches.extend(rule_matches)
        if negated:
            negated_rule_ids.append(rule.rule_id)

    if matches:
        return RiskEvaluation(
            risk_status="present",
            risk_flags=_dedupe(match.risk_flag for match in matches),
            triggered_rule_ids=_dedupe(match.rule_id for match in matches),
            risk_reasons=_dedupe(match.reason for match in matches),
            matches=matches,
            negated_rule_ids=_dedupe(negated_rule_ids),
        )

    if negated_rule_ids:
        return RiskEvaluation(
            risk_status="none",
            negated_rule_ids=_dedupe(negated_rule_ids),
        )

    return RiskEvaluation(risk_status=None)


def apply_risk_evaluation_to_state(state: RunState, evaluation: RiskEvaluation) -> RunState:
    new_state = state.model_copy(deep=True)

    if evaluation.triggered_rule_ids:
        new_state.triggered_rule_ids = _dedupe(new_state.triggered_rule_ids + evaluation.triggered_rule_ids)
    if evaluation.risk_reasons:
        new_state.risk_reasons = _dedupe(new_state.risk_reasons + evaluation.risk_reasons)

    if evaluation.risk_status == "present":
        new_state.risk_flags_status = "present"
        new_state.risk_flags = _dedupe(new_state.risk_flags + evaluation.risk_flags)
    elif evaluation.risk_status == "none":
        if new_state.risk_flags_status != "present":
            new_state.risk_flags_status = "none"
            if not new_state.risk_flags:
                new_state.risk_flags = []

    new_state.metadata = {
        **new_state.metadata,
        "last_risk_rule_eval": {
            "risk_status": evaluation.risk_status,
            "triggered_rule_ids": evaluation.triggered_rule_ids,
            "negated_rule_ids": evaluation.negated_rule_ids,
            "risk_reasons": evaluation.risk_reasons,
        },
    }
    return new_state


def should_stop_routine_followup(state: RunState) -> bool:
    return state.risk_flags_status == "present"
