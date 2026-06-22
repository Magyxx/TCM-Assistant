from __future__ import annotations

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
