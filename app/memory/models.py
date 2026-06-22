from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from app.storage.models import utc_now


MemorySourceKind = Literal[
    "validated_turn_output",
    "risk_rule_engine",
    "rag_evidence",
    "manual_correction",
    "run_state_bridge",
]


CANONICAL_FACT_FIELDS = (
    "chief_complaint",
    "duration",
    "symptoms",
    "symptoms_status",
    "sleep",
    "appetite",
    "stool_urine",
    "risk_flags",
    "risk_flags_status",
    "risk_reasons",
    "triggered_rule_ids",
)

FIELD_ALIASES = {
    "risk_status": "risk_flags_status",
    "risk_rule_ids": "triggered_rule_ids",
}

RAG_FORBIDDEN_FACT_FIELDS = frozenset(
    {
        "chief_complaint",
        "duration",
        "risk_flags_status",
        "triggered_rule_ids",
    }
)

LLM_FORBIDDEN_FACT_FIELDS = frozenset(
    {
        "risk_flags",
        "risk_flags_status",
        "risk_reasons",
        "triggered_rule_ids",
    }
)

LIST_FACT_FIELDS = frozenset(
    {
        "symptoms",
        "risk_flags",
        "risk_reasons",
        "triggered_rule_ids",
    }
)


def canonical_fact_field(field_name: str) -> str:
    return FIELD_ALIASES.get(field_name, field_name)


def is_empty_value(value: Any) -> bool:
    return value in (None, "", [], {}, "unknown")


class L1RecentTurn(BaseModel):
    turn_id: str
    turn_index: int = 0
    raw_text_preview: str = ""
    extractor_mode: str = "unknown"
    created_at: str = Field(default_factory=utc_now)


class MemoryFact(BaseModel):
    field_name: str
    value: Any
    source_turn_id: str
    raw_text: str = ""
    extractor_mode: str = "unknown"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_kind: MemorySourceKind = "validated_turn_output"
    explicit_negation: bool = False
    updated_at: str = Field(default_factory=utc_now)
    schema_version: str = "memory.fact.p8.v1"

    def canonical_copy(self) -> "MemoryFact":
        return self.model_copy(update={"field_name": canonical_fact_field(self.field_name)})


class AuditEvent(BaseModel):
    event_id: str
    turn_id: str
    action: str
    field_name: Optional[str] = None
    previous_value: Any = None
    candidate_value: Any = None
    applied: bool = False
    reason: str = ""
    source_kind: Optional[MemorySourceKind] = None
    extractor_mode: str = "unknown"
    confidence: Optional[float] = None
    created_at: str = Field(default_factory=utc_now)


class CaseSummary(BaseModel):
    summary: str = ""
    missing_fields: List[str] = Field(default_factory=list)
    risk_status: str = "unknown"
    generated_from_fact_fields: List[str] = Field(default_factory=list)
    generated_from_l2_only: bool = True
    schema_version: str = "memory.case_summary.p8.v1"


class L4ExperienceInterface(BaseModel):
    enabled: bool = False
    allowed_content: str = "knowledge_or_anonymized_experience_only"
    stored_items: List[Dict[str, Any]] = Field(default_factory=list)
    contains_raw_patient_text: bool = False
    contains_patient_identifier: bool = False
    schema_version: str = "memory.l4.interface.p8.v1"


class ConsultationMemory(BaseModel):
    session_id: str = ""
    schema_version: str = "memory.consultation.p8.v1"
    recent_turns: List[L1RecentTurn] = Field(default_factory=list)
    facts: Dict[str, MemoryFact] = Field(default_factory=dict)
    case_summary: CaseSummary = Field(default_factory=CaseSummary)
    audit_events: List[AuditEvent] = Field(default_factory=list)
    l4_experience: L4ExperienceInterface = Field(default_factory=L4ExperienceInterface)
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)

    def fact_value(self, field_name: str, default: Any = None) -> Any:
        fact = self.facts.get(canonical_fact_field(field_name))
        return fact.value if fact is not None else default


class MergeDecision(BaseModel):
    field_name: str
    applied: bool
    reason: str
    previous_value: Any = None
    candidate_value: Any = None
