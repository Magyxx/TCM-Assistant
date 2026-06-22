from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.memory.models import AuditEvent, MemoryFact, MemorySourceKind


def make_audit_event(
    *,
    turn_id: str,
    action: str,
    field_name: str | None = None,
    previous_value: Any = None,
    candidate_value: Any = None,
    applied: bool = False,
    reason: str = "",
    source_kind: MemorySourceKind | None = None,
    extractor_mode: str = "unknown",
    confidence: float | None = None,
) -> AuditEvent:
    return AuditEvent(
        event_id=str(uuid4()),
        turn_id=turn_id,
        action=action,
        field_name=field_name,
        previous_value=previous_value,
        candidate_value=candidate_value,
        applied=applied,
        reason=reason,
        source_kind=source_kind,
        extractor_mode=extractor_mode,
        confidence=confidence,
    )


def audit_from_fact(
    *,
    candidate: MemoryFact,
    previous_value: Any = None,
    applied: bool,
    reason: str,
) -> AuditEvent:
    return make_audit_event(
        turn_id=candidate.source_turn_id,
        action="merge_fact",
        field_name=candidate.field_name,
        previous_value=previous_value,
        candidate_value=candidate.value,
        applied=applied,
        reason=reason,
        source_kind=candidate.source_kind,
        extractor_mode=candidate.extractor_mode,
        confidence=candidate.confidence,
    )
