from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.schemas.report_schemas import RiskStatus, TriageLevel


RiskLevel = Literal["caution", "urgent"]


class RiskEvent(BaseModel):
    rule_id: str
    risk_level: RiskLevel = "urgent"
    triage_level: TriageLevel = "urgent_visit"
    reason: str
    evidence_text: str
    negated: bool = False


RiskReason = RiskEvent

__all__ = ["RiskEvent", "RiskReason", "RiskStatus", "TriageLevel"]
