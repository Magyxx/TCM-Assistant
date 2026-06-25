from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


ExtractorMode = Literal["real_llm", "openai_compatible", "cloud_llm", "fake", "fallback", "local_lora"]


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
    api_version: Optional[str] = None
    graph_available: Optional[bool] = None
    session_store_backend: Optional[str] = None
    sqlite_path: Optional[str] = None
    extractor_backend: Optional[str] = None
    langgraph_runtime: Optional[bool] = None
    timestamp: Optional[str] = None
    storage_status: Optional[Dict[str, Any]] = None
    backend_matrix_summary: Optional[Dict[str, Any]] = None
    backend_matrix: Optional[Dict[str, Any]] = None
    p11_contract_availability: Optional[Dict[str, Any]] = None
    live_vllm: Optional[Dict[str, Any]] = None


class VersionResponse(BaseModel):
    service: str
    api_version: str
    stage: str
    contract_status: str


class CreateSessionRequest(BaseModel):
    extractor_mode: Optional[ExtractorMode] = None
    rag_enabled: bool = True
    metadata: Optional[Dict[str, Any]] = None
    backend: Optional[str] = None
    store_backend: Optional[str] = None


class CreateSessionResponse(BaseModel):
    session_id: str
    extractor_mode: ExtractorMode
    rag_enabled: bool
    created_at: str
    turn_count: int
    store_backend: Optional[str] = None
    api_version: Optional[str] = None


class TurnRequest(BaseModel):
    user_input: str = Field(..., min_length=1)
    session_id: Optional[str] = None
    extractor_backend: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    debug: bool = False


class TurnResponse(BaseModel):
    session_id: str
    turn_id: str
    turn_count: int
    trace_id: Optional[str] = None
    graph_runtime: Optional[str] = None
    risk_status: Optional[str] = None
    next_question: Optional[str] = None
    missing_core_fields: Optional[List[str]] = None
    state: Dict[str, Any]
    state_summary: Optional[Dict[str, Any]] = None
    risk_flags_status: Optional[str] = None
    risk_rule_ids: List[str] = Field(default_factory=list)
    risk_reasons: List[str] = Field(default_factory=list)
    final_report: Optional[Dict[str, Any]] = None
    retrieved_evidence_count: Optional[int] = None
    fallback_used: Optional[bool] = None
    safety_rewrite_used: Optional[bool] = None
    event_count: Optional[int] = None
    p1_evidence_pack: Optional[Dict[str, Any]] = None
    p1_report_skeleton: Optional[Dict[str, Any]] = None
    report_audit: Optional[Dict[str, Any]] = None
    warnings: Optional[List[str]] = None
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
    report_available: Optional[bool] = None
    final_report: Optional[Dict[str, Any]] = None
    risk_status: Optional[str] = None
    risk_reasons: Optional[List[str]] = None
    evidence: Optional[List[Dict[str, Any]]] = None
    p1_evidence_pack: Optional[Dict[str, Any]] = None
    p1_report_skeleton: Optional[Dict[str, Any]] = None
    report_audit: Optional[Dict[str, Any]] = None
    missing_core_fields: List[str] = Field(default_factory=list)
    next_question: Optional[str] = None
    safety_disclaimer: str = SAFETY_DISCLAIMER
    generated_at: Optional[str] = None


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
    store_backend: Optional[str] = None
    has_final_report: Optional[bool] = None
    risk_status: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SessionResponse(BaseModel):
    session_id: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    store_backend: str = "sqlite"
    turn_count: int = 0
    has_final_report: bool = False
    risk_status: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ReplayRequest(BaseModel):
    allow_write: bool = False


class ReplayResponse(BaseModel):
    session_id: str
    turns: List[Dict[str, Any]] = Field(default_factory=list)
    final_state: Dict[str, Any] = Field(default_factory=dict)
    final_report: Optional[Dict[str, Any]] = None
    graph_events: List[Dict[str, Any]] = Field(default_factory=list)
    replay_status: str = "ok_read_only"


class EvalRunRequest(BaseModel):
    run: bool = False


class EvalRunResponse(BaseModel):
    status: str
    metrics: Dict[str, Any] = Field(default_factory=dict)
    artifacts: Dict[str, Any] = Field(default_factory=dict)
    skipped: bool = False
    skip_reason: str = ""


class RagHealthResponse(BaseModel):
    rag_mode: str
    chunks_count: int
    bm25_available: bool
    dense_available: bool
    hybrid_available: bool
    index_dir: str
    chunks_path: str


class RagSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    mode: Literal["bm25", "dense", "hybrid"] = "hybrid"


class SessionRagSearchRequest(BaseModel):
    top_k: int = Field(default=5, ge=1, le=20)
    mode: Literal["bm25", "dense", "hybrid"] = "hybrid"


class RagSearchResponse(BaseModel):
    results: List[Dict[str, Any]] = Field(default_factory=list)
    retrieval_mode: str = "hybrid"
    score_breakdown: Dict[str, Any] = Field(default_factory=dict)
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    query: Optional[str] = None
    session_id: Optional[str] = None


class ReportExportRequest(BaseModel):
    format: Literal["json", "markdown", "summary_markdown"] = "json"
    include_debug_raw_input: bool = False


class ReportExportResponse(BaseModel):
    status: str
    session_id: str
    format: str
    path: str
    report_available: bool


class SafetyRedTeamRequest(BaseModel):
    run: bool = True


class FinalEvalRequest(BaseModel):
    run: bool = True


class ApiErrorDetail(BaseModel):
    code: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)


class ApiErrorResponse(BaseModel):
    error: ApiErrorDetail


ReportResponse = SessionReportResponse


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
