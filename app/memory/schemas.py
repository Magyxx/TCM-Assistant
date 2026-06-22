from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from app.storage.models import utc_now


MemoryLayer = Literal["L1", "L2", "L3", "L4"]


class L1RecentTurn(BaseModel):
    turn_id: str
    turn_index: int
    user_input_preview: str
    risk_status: str
    created_at: str = Field(default_factory=utc_now)


class L2StructuredFact(BaseModel):
    field_name: str
    value: Any
    source_turn_id: str
    source_text_span: Optional[str] = None
    confidence: float = 1.0
    updated_at: str = Field(default_factory=utc_now)
    schema_version: str = "memory.l2.fact.v1"
    source_kind: Literal["validated_schema", "risk_rule_engine"] = "validated_schema"


class L3CaseSummary(BaseModel):
    summary: str
    missing_fields: List[str] = Field(default_factory=list)
    risk_status: str = "unknown"
    generated_from_fact_count: int = 0
    schema_version: str = "memory.l3.summary.v1"


class L4ExperienceItem(BaseModel):
    item_id: str
    item_type: Literal["knowledge", "anonymous_failure_sample", "synthetic_eval_case"]
    title: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    contains_pii: bool = False
    contains_raw_patient_text: bool = False


class MemorySnapshot(BaseModel):
    session_id: str
    turn_id: str
    schema_version: str = "memory.snapshot.p7.v1"
    recent_turns: List[L1RecentTurn] = Field(default_factory=list)
    structured_facts: List[L2StructuredFact] = Field(default_factory=list)
    case_summary: L3CaseSummary
    experience_retrieval: List[L4ExperienceItem] = Field(default_factory=list)
    source_traceability_pass: bool = True
    l4_privacy_pass: bool = True
    memory_write_pass: bool = True
    created_at: str = Field(default_factory=utc_now)
