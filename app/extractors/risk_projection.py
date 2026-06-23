from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Literal

from app.rules.risk_rules import RISK_RULES, evaluate_risk_rules, is_keyword_negated


TriState = Literal["unknown", "none", "present"]
NEGATION_MARKERS = ("没有", "未见", "无", "否认", "不")
GENERIC_NEGATED_RISK_TERMS = ("发热", "发烧", "胸口疼", "胸口痛", "胸痛", "呼吸困难", "喘不过气", "便血", "呕血", "黑便")


@dataclass(frozen=True)
class RiskEvidenceSpan:
    text: str
    start: int
    end: int
    rule_id: str | None = None
    negated: bool = False


@dataclass(frozen=True)
class RiskProjection:
    candidate_risk_status: TriState
    candidate_risk_flags: list[str] = field(default_factory=list)
    candidate_risk_rule_ids: list[str] = field(default_factory=list)
    negated_risk_rule_ids: list[str] = field(default_factory=list)
    risk_evidence_spans: list[RiskEvidenceSpan] = field(default_factory=list)
    source: str = "unknown"


def _as_list(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item).strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _dedupe(items: Iterable[str]) -> list[str]:
    return list(dict.fromkeys([item for item in items if item]))


def _find_spans(text: str, keyword: str, rule_id: str | None, negated: bool) -> list[RiskEvidenceSpan]:
    spans: list[RiskEvidenceSpan] = []
    start = 0
    while keyword and start < len(text):
        index = text.find(keyword, start)
        if index < 0:
            break
        spans.append(
            RiskEvidenceSpan(
                text=keyword,
                start=index,
                end=index + len(keyword),
                rule_id=rule_id,
                negated=negated,
            )
        )
        start = index + len(keyword)
    return spans


def _rule_spans(text: str) -> list[RiskEvidenceSpan]:
    spans: list[RiskEvidenceSpan] = []
    for rule in RISK_RULES:
        for keyword in rule.trigger_keywords:
            if keyword not in text:
                continue
            negated = rule.negation_sensitive and is_keyword_negated(text, keyword)
            spans.extend(_find_spans(text, keyword, rule.rule_id, negated))
    return spans


def _has_generic_negated_risk(text: str) -> bool:
    compact = "".join(str(text or "").split())
    for term in GENERIC_NEGATED_RISK_TERMS:
        if term in compact and is_keyword_negated(compact, term):
            return True
    if "胸口不疼" in compact or "不是黑便" in compact:
        return True
    return False


def project_risk_status(
    *,
    user_text: str | None,
    extracted_risk_flags: Any = None,
    negated_risk_flags: Any = None,
    evidence_spans: Any = None,
    previous_status: TriState = "unknown",
    previous_risk_flags: Any = None,
    previous_rule_ids: Any = None,
) -> RiskProjection:
    """Project extractor risk candidates without replacing the main RiskRuleEngine.

    The projection is intentionally conservative: previous present risk is not
    downgraded, current rule matches can upgrade to present, explicit negated
    risk evidence can project none, and otherwise the status stays unknown.
    """

    text = str(user_text or "")
    extracted_flags = _as_list(extracted_risk_flags)
    negated_flags = _as_list(negated_risk_flags)
    previous_flags = _as_list(previous_risk_flags)
    previous_rules = _as_list(previous_rule_ids)
    explicit_spans = []
    if isinstance(evidence_spans, list):
        for item in evidence_spans:
            if isinstance(item, RiskEvidenceSpan):
                explicit_spans.append(item)
            elif isinstance(item, dict) and item.get("text"):
                explicit_spans.append(
                    RiskEvidenceSpan(
                        text=str(item.get("text")),
                        start=int(item.get("start", -1)),
                        end=int(item.get("end", -1)),
                        rule_id=item.get("rule_id"),
                        negated=bool(item.get("negated", False)),
                    )
                )

    rule_projection = evaluate_risk_rules(text, previous_status=previous_status)
    spans = explicit_spans + _rule_spans(text)

    if previous_status == "present":
        return RiskProjection(
            candidate_risk_status="present",
            candidate_risk_flags=_dedupe(previous_flags + extracted_flags + rule_projection.risk_flags),
            candidate_risk_rule_ids=_dedupe(previous_rules + rule_projection.triggered_rule_ids),
            negated_risk_rule_ids=_dedupe(rule_projection.negated_rule_ids),
            risk_evidence_spans=spans,
            source="previous_present_protected",
        )

    if rule_projection.risk_status == "present":
        return RiskProjection(
            candidate_risk_status="present",
            candidate_risk_flags=_dedupe(extracted_flags + rule_projection.risk_flags),
            candidate_risk_rule_ids=_dedupe(rule_projection.triggered_rule_ids),
            negated_risk_rule_ids=_dedupe(rule_projection.negated_rule_ids),
            risk_evidence_spans=spans,
            source="risk_rule_projection",
        )

    non_negated_extracted_flags = [
        flag for flag in extracted_flags if flag not in negated_flags and not is_keyword_negated(text, flag)
    ]
    if non_negated_extracted_flags:
        extracted_spans = []
        for flag in non_negated_extracted_flags:
            extracted_spans.extend(_find_spans(text, flag, None, negated=False))
        return RiskProjection(
            candidate_risk_status="present",
            candidate_risk_flags=_dedupe(non_negated_extracted_flags),
            candidate_risk_rule_ids=[],
            negated_risk_rule_ids=_dedupe(rule_projection.negated_rule_ids),
            risk_evidence_spans=spans + extracted_spans,
            source="extracted_risk_flags",
        )

    if rule_projection.risk_status == "none" or negated_flags or _has_generic_negated_risk(text):
        return RiskProjection(
            candidate_risk_status="none",
            candidate_risk_flags=[],
            candidate_risk_rule_ids=[],
            negated_risk_rule_ids=_dedupe(rule_projection.negated_rule_ids + negated_flags),
            risk_evidence_spans=spans,
            source="negated_risk_projection",
        )

    return RiskProjection(
        candidate_risk_status="unknown",
        candidate_risk_flags=[],
        candidate_risk_rule_ids=[],
        negated_risk_rule_ids=_dedupe(rule_projection.negated_rule_ids),
        risk_evidence_spans=spans,
        source="no_risk_evidence",
    )
