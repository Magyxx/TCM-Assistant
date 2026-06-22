from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


ExtractorMode = Literal["real_llm", "fake", "fallback"]


SAFETY_DISCLAIMER = (
    "本系统仅用于问诊信息整理和风险提示，不构成诊断或治疗建议，不能替代医生判断。"
    "如出现持续高热、胸痛、呼吸困难、便血、意识异常、剧烈腹痛等高风险信号，"
    "应及时线下就医。"
)


class HealthResponse(BaseModel):
    status: str
    service: str
    stage: str
    mode: str
    diagnosis_system: bool


class VersionResponse(BaseModel):
    service: str
    api_version: str
    stage: str
    contract_status: str


class CreateSessionRequest(BaseModel):
    extractor_mode: ExtractorMode = "real_llm"
    rag_enabled: bool = True


class CreateSessionResponse(BaseModel):
    session_id: str
    extractor_mode: ExtractorMode
    rag_enabled: bool
    created_at: str
    turn_count: int


class TurnRequest(BaseModel):
    user_input: str = Field(..., min_length=1)


class TurnResponse(BaseModel):
    session_id: str
    turn_id: str
    turn_count: int
    next_question: Optional[str] = None
    state: Dict[str, Any]
    risk_flags_status: Optional[str] = None
    risk_rule_ids: List[str] = Field(default_factory=list)
    risk_reasons: List[str] = Field(default_factory=list)
    final_report: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    safety_disclaimer: str = SAFETY_DISCLAIMER


class SessionStateResponse(BaseModel):
    session_id: str
    turn_count: int
    state: Dict[str, Any]
    risk_flags_status: Optional[str] = None
    risk_rule_ids: List[str] = Field(default_factory=list)
    missing_core_fields: List[str] = Field(default_factory=list)
    next_question: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    safety_disclaimer: str = SAFETY_DISCLAIMER


class SessionReportResponse(BaseModel):
    session_id: str
    ready: bool
    final_report: Optional[Dict[str, Any]] = None
    missing_core_fields: List[str] = Field(default_factory=list)
    next_question: Optional[str] = None
    safety_disclaimer: str = SAFETY_DISCLAIMER


class SessionDetailResponse(BaseModel):
    session_id: str
    trace_id: str = ""
    status: str = "ok"
    extractor_mode: Optional[ExtractorMode] = None
    rag_enabled: Optional[bool] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    turn_count: int = 0
    state_version: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SessionTraceResponse(BaseModel):
    session_id: str
    trace_id: str = ""
    status: str = "ok"
    traces: List[Dict[str, Any]] = Field(default_factory=list)


class SessionEvidenceResponse(BaseModel):
    session_id: str
    trace_id: str = ""
    status: str = "ok"
    retrieved_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    used_evidence: List[Dict[str, Any]] = Field(default_factory=list)


class ToolListResponse(BaseModel):
    session_id: Optional[str] = None
    trace_id: str = ""
    status: str = "ok"
    tools: List[Dict[str, Any]] = Field(default_factory=list)


class ToolInvokeRequest(BaseModel):
    payload: Dict[str, Any] = Field(default_factory=dict)
    approved: bool = False
    session_id: Optional[str] = None


class ToolInvokeResponse(BaseModel):
    session_id: Optional[str] = None
    trace_id: str = ""
    status: str = "ok"
    tool_name: str
    allowed: bool
    output: Dict[str, Any] = Field(default_factory=dict)
    audit_log: Dict[str, Any] = Field(default_factory=dict)
    blocked_reason: Optional[str] = None


class EvalP7Request(BaseModel):
    case: Dict[str, Any] = Field(default_factory=dict)


class EvalP7Response(BaseModel):
    session_id: str = "p7-eval"
    trace_id: str = ""
    status: str = "ok"
    metrics: Dict[str, Any] = Field(default_factory=dict)
