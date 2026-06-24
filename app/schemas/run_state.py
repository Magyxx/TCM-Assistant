from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.evidence import EvidenceChunk
from app.schemas.final_report import FinalReport
from app.schemas.report_schemas import RunState
from app.schemas.risk import RiskEvent, RiskStatus
from app.schemas.turn_output import TurnOutput


class ConsultationState(BaseModel):
    session_id: str
    user_input: str = ""
    normalized_input: str = ""
    turns: list[TurnOutput] = Field(default_factory=list)
    run_state: RunState = Field(default_factory=RunState)
    risk_status: RiskStatus = "unknown"
    risk_reasons: list[RiskEvent] = Field(default_factory=list)
    missing_core_fields: list[str] = Field(default_factory=list)
    next_question: str | None = None
    retrieved_evidence: list[EvidenceChunk] = Field(default_factory=list)
    final_report: FinalReport | None = None
    trace: list[dict[str, Any]] = Field(default_factory=list)


__all__ = ["ConsultationState", "RunState"]
