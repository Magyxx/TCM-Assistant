from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


SAFETY_DISCLAIMER = (
    "This system only organizes inquiry information and risk prompts. "
    "It does not provide a diagnosis, prescription, or replacement for clinician judgment."
)


class ReportSafetyCheck(BaseModel):
    ok: bool
    violations: list[str] = Field(default_factory=list)
    rewritten_text: str | None = None


class FinalReportSkeleton(BaseModel):
    session_id: str
    summary: str = "Structured inquiry summary is not ready yet."
    collected_facts: dict[str, Any] = Field(default_factory=dict)
    missing_core_fields: list[str] = Field(default_factory=list)
    risk_status: str = "unknown"
    risk_reasons: list[str] = Field(default_factory=list)
    evidence_pack: dict[str, Any] | None = None
    advice: list[str] = Field(default_factory=lambda: ["Continue collecting structured information and seek offline medical care for red-flag symptoms."])
    safety_disclaimer: str = SAFETY_DISCLAIMER
    generated_by: str = "deterministic_p1_f0_skeleton"
    schema_version: str = "p1_f0_report_skeleton_v1"
    safety_check: ReportSafetyCheck = Field(default_factory=lambda: ReportSafetyCheck(ok=True))
