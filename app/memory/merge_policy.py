from __future__ import annotations

from typing import Any

from app.memory.audit import audit_from_fact
from app.memory.models import (
    LLM_FORBIDDEN_FACT_FIELDS,
    LIST_FACT_FIELDS,
    RAG_FORBIDDEN_FACT_FIELDS,
    AuditEvent,
    ConsultationMemory,
    MemoryFact,
    MergeDecision,
    canonical_fact_field,
    is_empty_value,
)


def _dedupe_list(value: Any) -> list[Any]:
    if not isinstance(value, list):
        return [value] if value not in (None, "") else []
    deduped: list[Any] = []
    for item in value:
        if item not in deduped and item not in (None, ""):
            deduped.append(item)
    return deduped


def _candidate_with_merged_list(existing: MemoryFact, candidate: MemoryFact) -> MemoryFact:
    merged = _dedupe_list(existing.value) + [
        item for item in _dedupe_list(candidate.value) if item not in _dedupe_list(existing.value)
    ]
    return candidate.model_copy(update={"value": merged})


def decide_merge(
    memory: ConsultationMemory,
    candidate: MemoryFact,
    *,
    explicit_correction: bool = False,
) -> MergeDecision:
    candidate = candidate.canonical_copy()
    field_name = canonical_fact_field(candidate.field_name)
    existing = memory.facts.get(field_name)
    previous_value = existing.value if existing is not None else None

    if candidate.source_kind == "rag_evidence" and field_name in RAG_FORBIDDEN_FACT_FIELDS:
        return MergeDecision(
            field_name=field_name,
            applied=False,
            reason="rag_evidence_forbidden_for_core_field",
            previous_value=previous_value,
            candidate_value=candidate.value,
        )

    if candidate.source_kind == "validated_turn_output" and field_name in LLM_FORBIDDEN_FACT_FIELDS:
        return MergeDecision(
            field_name=field_name,
            applied=False,
            reason="llm_candidate_cannot_write_risk_authority",
            previous_value=previous_value,
            candidate_value=candidate.value,
        )

    if existing is not None and not is_empty_value(existing.value) and is_empty_value(candidate.value):
        return MergeDecision(
            field_name=field_name,
            applied=False,
            reason="empty_candidate_cannot_overwrite_non_empty_fact",
            previous_value=previous_value,
            candidate_value=candidate.value,
        )

    if (
        field_name == "risk_flags_status"
        and existing is not None
        and existing.value == "present"
        and candidate.value != "present"
        and candidate.source_kind != "manual_correction"
    ):
        return MergeDecision(
            field_name=field_name,
            applied=False,
            reason="high_risk_present_is_sticky",
            previous_value=previous_value,
            candidate_value=candidate.value,
        )

    if (
        existing is not None
        and candidate.confidence < existing.confidence
        and not explicit_correction
    ):
        return MergeDecision(
            field_name=field_name,
            applied=False,
            reason="low_confidence_candidate_cannot_overwrite_higher_confidence_fact",
            previous_value=previous_value,
            candidate_value=candidate.value,
        )

    if existing is not None and existing.value == candidate.value and not explicit_correction:
        return MergeDecision(
            field_name=field_name,
            applied=False,
            reason="candidate_matches_existing_fact",
            previous_value=previous_value,
            candidate_value=candidate.value,
        )

    return MergeDecision(
        field_name=field_name,
        applied=True,
        reason="accepted",
        previous_value=previous_value,
        candidate_value=candidate.value,
    )


def merge_fact(
    memory: ConsultationMemory,
    candidate: MemoryFact,
    *,
    explicit_correction: bool = False,
) -> tuple[ConsultationMemory, AuditEvent]:
    candidate = candidate.canonical_copy()
    field_name = canonical_fact_field(candidate.field_name)
    existing = memory.facts.get(field_name)
    decision = decide_merge(memory, candidate, explicit_correction=explicit_correction)
    updated = memory.model_copy(deep=True)

    if decision.applied:
        if existing is not None and field_name in LIST_FACT_FIELDS:
            candidate = _candidate_with_merged_list(existing, candidate)
        updated.facts[field_name] = candidate.model_copy(update={"field_name": field_name})

    event = audit_from_fact(
        candidate=candidate.model_copy(update={"field_name": field_name}),
        previous_value=decision.previous_value,
        applied=decision.applied,
        reason=decision.reason,
    )
    updated.audit_events.append(event)
    return updated, event
