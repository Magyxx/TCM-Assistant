from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class P1HealthResponse(BaseModel):
    status: str = "ok"
    app: str = "TCM-Assistant"
    mode: str = "local"
    external_dependencies_required: bool = False


class P1CreateSessionRequest(BaseModel):
    extractor_backend: str = "fake"
    rag_enabled: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class P1CreateSessionResponse(BaseModel):
    session_id: str
    extractor_backend: str = "fake"
    rag_enabled: bool = False
    created_at: str
    external_dependencies_skipped: list[str] = Field(default_factory=list)


class P1TurnRequest(BaseModel):
    session_id: str | None = None
    user_input: str
    extractor_backend: str | None = None


class P1TurnResponse(BaseModel):
    session_id: str
    turn_id: str
    graph_runtime: str
    extractor_backend: str
    schema_pass: bool
    risk_status: str
    missing_core_fields: list[str] = Field(default_factory=list)
    next_action: str
    next_question: str
    evidence_pack: dict[str, Any] | None = None
    report_skeleton: dict[str, Any] | None = None
    report_audit: dict[str, Any] | None = None
    audit_event_count: int = 1
    external_dependencies_skipped: list[str] = Field(default_factory=list)


class P1SessionSummary(BaseModel):
    session_id: str
    status: str = "ok"
    turn_count: int = 0
    extractor_backend: str = "fake"
    rag_enabled: bool = False
    risk_status: str | None = None
    missing_core_fields: list[str] = Field(default_factory=list)


class P1ReportResponse(BaseModel):
    session_id: str
    report_status: str = "not_ready"
    skeleton: dict[str, Any] = Field(default_factory=dict)
    evidence_pack: dict[str, Any] | None = None
    report_skeleton: dict[str, Any] | None = None
    report_audit: dict[str, Any] | None = None
    external_dependencies_skipped: list[str] = Field(default_factory=list)


class P1EvalSmokeResponse(BaseModel):
    status: str = "ok"
    sample_count: int = 0
    external_dependencies_required: bool = False
    checks: dict[str, str] = Field(default_factory=dict)
