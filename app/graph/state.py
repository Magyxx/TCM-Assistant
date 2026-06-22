from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.memory.models import ConsultationMemory
from app.schemas.evidence import EvidenceChunk
from app.schemas.final_report import FinalReport
from app.schemas.report_schemas import RunState, TurnOutput


class ConsultationGraphState(BaseModel):
    session_id: str = ""
    trace_id: str = ""
    turn_id: str = ""
    user_input: str = ""
    normalized_input: str = ""
    turns: List[TurnOutput] = Field(default_factory=list)
    run_state: RunState = Field(default_factory=RunState)
    memory: ConsultationMemory = Field(default_factory=ConsultationMemory)
    turn_output: Optional[TurnOutput] = None
    extraction_result: Dict[str, Any] = Field(default_factory=dict)
    schema_valid: bool = False
    json_valid: bool = False
    raw_llm_json_valid: bool = False
    final_schema_pass: bool = False
    fallback_used: bool = False
    extraction_mode: str = ""
    extractor_mode: str = ""
    extractor_mode_requested: str = "auto"
    model_name: Optional[str] = None
    error_type: Optional[str] = None
    skip_reason: Optional[str] = None
    strategy: Optional[str] = None
    error_message_preview: Optional[str] = None
    graph_runtime: str = "pending"
    errors: List[str] = Field(default_factory=list)
    risk_status: Optional[str] = None
    risk_reasons: List[str] = Field(default_factory=list)
    risk_events: List[Dict[str, Any]] = Field(default_factory=list)
    triggered_rule_ids: List[str] = Field(default_factory=list)
    missing_core_fields: List[str] = Field(default_factory=list)
    next_question: Optional[str] = None
    next_action: str = "pending"
    rag_enabled: bool = True
    retrieved_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    p9_evidence: List[EvidenceChunk] = Field(default_factory=list)
    evidence_pack: Dict[str, Any] = Field(default_factory=dict)
    retrieved_evidence_count: int = 0
    rag_skip_reason: Optional[str] = None
    final_report: Optional[FinalReport] = None
    exported_result: Dict[str, Any] = Field(default_factory=dict)
    trace: List[Dict[str, Any]] = Field(default_factory=list)
    safety_issues: List[str] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    done: bool = False

    def to_legacy_dict(self) -> Dict[str, Any]:
        payload = self.model_dump()
        payload["run_state"] = self.run_state
        payload["memory"] = self.memory
        payload["turn_output"] = self.turn_output
        return payload


ConsultationRuntimeState = ConsultationGraphState
