from __future__ import annotations

import re
from typing import Any, Mapping

from pydantic import BaseModel, Field

from app.memory.models import ConsultationMemory
from app.rag.models import EvidencePack


FORBIDDEN_RAG_WRITE_FIELDS = frozenset(
    {
        "chief_complaint",
        "duration",
        "risk_status",
        "risk_flags_status",
        "risk_rule_ids",
        "triggered_rule_ids",
        "explicit_negation",
        "source_turn_id",
        "raw_text",
        "extractor_mode",
        "facts",
        "authoritative_facts",
    }
)

ALLOWED_RAG_WRITE_FIELDS = frozenset(
    {
        "evidence",
        "retrieved_evidence",
        "impression",
        "advice",
        "missing_knowledge_notes",
        "citations",
        "metadata",
    }
)

FORBIDDEN_REPORT_TERMS = (
    "诊断为",
    "确诊",
    "处方",
    "开方",
    "替代医生",
    "diagnosed as",
    "prescribe",
    "prescription",
    "replace doctor",
)


class RagGuardResult(BaseModel):
    allowed: bool
    blocked_fields: list[str] = Field(default_factory=list)
    reason: str = ""


def _canonical_field(name: str) -> str:
    if name == "risk_rule_ids":
        return "triggered_rule_ids"
    if name == "risk_status":
        return "risk_flags_status"
    return name


def guard_rag_update(update: Mapping[str, Any]) -> RagGuardResult:
    blocked = sorted(
        key for key in update.keys() if key in FORBIDDEN_RAG_WRITE_FIELDS or _canonical_field(key) in FORBIDDEN_RAG_WRITE_FIELDS
    )
    if blocked:
        return RagGuardResult(
            allowed=False,
            blocked_fields=blocked,
            reason="rag_evidence_cannot_write_core_fields",
        )
    return RagGuardResult(allowed=True, reason="rag_update_allowed")


def assert_rag_update_allowed(update: Mapping[str, Any]) -> None:
    result = guard_rag_update(update)
    if not result.allowed:
        raise ValueError(f"{result.reason}:{','.join(result.blocked_fields)}")


def guard_evidence_pack(pack: EvidencePack) -> EvidencePack:
    if pack.guard_status == "failed":
        return pack
    return pack.model_copy(update={"guard_status": "passed"})


def assert_memory_l2_unchanged(before: ConsultationMemory, after: ConsultationMemory) -> None:
    if before.facts != after.facts:
        raise ValueError("rag_evidence_cannot_modify_memory_l2_facts")


def report_text_is_safe(text: str) -> bool:
    lowered = text.lower()
    return not any(term.lower() in lowered for term in FORBIDDEN_REPORT_TERMS)


P10M2_CORE_FIELDS = frozenset(
    {
        "chief_complaint",
        "duration",
        "risk_status",
        "risk_flags_status",
        "risk_rule_ids",
        "triggered_rule_ids",
        "risk_reasons",
        "user_negations",
        "explicit_negation",
        "negations",
    }
)

P10M2_INJECTION_TERMS = (
    "ignore previous",
    "ignore all",
    "system prompt",
    "developer message",
    "override risk_status",
    "overwrite risk_status",
    "direct diagnosis",
    "you are now a doctor",
    "不要加免责声明",
    "忽略",
    "覆盖",
    "系统提示词",
    "必须诊断",
)

P10M2_DIAGNOSIS_TERMS = (
    "definitive diagnosis",
    "diagnosed as",
    "you have",
    "confirmed diagnosis",
    "确诊",
    "诊断为",
    "就是",
)

P10M2_PRESCRIPTION_TERMS = (
    "prescription",
    "dosage",
    "take this medicine",
    "formula dosage",
    "开方",
    "处方",
    "剂量",
    "服用",
)


def sanitize_rag_text(text: str, *, max_length: int = 500) -> str:
    cleaned = " ".join(str(text or "").split())
    for term in P10M2_INJECTION_TERMS:
        cleaned = re.sub(re.escape(term), " ", cleaned, flags=re.IGNORECASE)
    cleaned = " ".join(cleaned.split())
    return cleaned[:max_length]


def validate_p10m2_rag_payload(payload: Mapping[str, Any]) -> RagGuardResult:
    blocked = sorted(
        str(key)
        for key in payload.keys()
        if str(key) in P10M2_CORE_FIELDS or _canonical_field(str(key)) in P10M2_CORE_FIELDS
    )
    text = " ".join(str(value) for value in payload.values()).lower()
    injection_hits = [term for term in P10M2_INJECTION_TERMS if term.lower() in text]
    if blocked or injection_hits:
        return RagGuardResult(
            allowed=False,
            blocked_fields=blocked,
            reason="p10m2_rag_payload_blocked",
        )
    return RagGuardResult(allowed=True, reason="p10m2_rag_payload_allowed")


def p10m2_report_safety_check(
    report: Mapping[str, Any],
    *,
    high_risk: bool = False,
    citation_required: bool = True,
) -> dict[str, Any]:
    text_parts: list[str] = []
    for key in ("summary", "impression"):
        if report.get(key):
            text_parts.append(str(report[key]))
    for item in report.get("advice") or []:
        text_parts.append(str(item))
    text = " ".join(text_parts).lower()
    issues: list[str] = []
    if any(term.lower() in text for term in P10M2_DIAGNOSIS_TERMS):
        issues.append("diagnosis_expression")
    if any(term.lower() in text for term in P10M2_PRESCRIPTION_TERMS):
        issues.append("prescription_expression")
    if any(term in text for term in ("certainly", "guaranteed", "一定", "必然")):
        issues.append("over_certainty")
    if citation_required and report.get("evidence_citations") and not report.get("evidence_ids"):
        issues.append("missing_evidence_ids")
    if high_risk and not any(term in text for term in ("offline", "urgent", "线下", "就医", "medical")):
        issues.append("missing_high_risk_prompt")
    if not report.get("safety_disclaimer"):
        issues.append("missing_safety_disclaimer")
    return {
        "passed": not issues,
        "issues": sorted(set(issues)),
        "diagnosis_violation": int("diagnosis_expression" in issues),
        "prescription_violation": int("prescription_expression" in issues),
    }
