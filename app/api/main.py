from __future__ import annotations

import sqlite3
import time
from typing import Any, Dict, List
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError

from app.api.errors import (
    ApiError,
    INTERNAL_ERROR,
    INVALID_REQUEST,
    SESSION_NOT_FOUND,
    STORE_UNAVAILABLE,
    error_response,
)
from app.api.models import (
    CreateSessionRequest,
    CreateSessionResponse,
    EvalP7Request,
    EvalP7Response,
    HealthResponse,
    SAFETY_DISCLAIMER,
    SessionDetailResponse,
    SessionEvidenceResponse,
    SessionReportResponse,
    SessionStateResponse,
    SessionTraceResponse,
    ToolInvokeRequest,
    ToolInvokeResponse,
    ToolListResponse,
    TurnRequest,
    TurnResponse,
    VersionResponse,
)
from app.api.observability import (
    log_event,
    normalize_request_id,
    set_current_request_id,
)
from app.api.redaction import redact_secrets
from app.api.session_runtime import (
    append_turn,
    create_session,
    get_last_turn_id,
    get_session,
)
from app.api.deps import get_p7_store, get_p7_tools
from app.agentic.workflow_adapter import run_p4_workflow
from app.api.versioning import (
    API_CONTRACT_STATUS,
    API_STAGE,
    API_VERSION,
    API_VERSION_HEADER,
    SERVICE_NAME,
)
from app.services.p7_runtime import record_report, record_session, record_turn
from app.storage.models import AuditLogRecord, EvalRunRecord


app = FastAPI(
    title="TCM-Assistant Minimal API",
    version="1.1.0",
    description="P1.1 minimal FastAPI wrapper around the existing LangGraph workflow.",
)


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    request_id = normalize_request_id(request.headers.get("X-Request-ID"))
    set_current_request_id(request_id)
    started = time.perf_counter()
    log_event(
        "request.start",
        component="api.request",
        request_id=request_id,
        status="started",
        extra={
            "method": request.method,
            "path": request.url.path,
        },
    )
    try:
        response = await call_next(request)
    except Exception as exc:
        duration_ms = (time.perf_counter() - started) * 1000
        log_event(
            "request.error",
            level="ERROR",
            component="api.request",
            request_id=request_id,
            status="error",
            duration_ms=duration_ms,
            extra={
                "method": request.method,
                "path": request.url.path,
                "error_type": type(exc).__name__,
            },
        )
        set_current_request_id(None)
        raise

    duration_ms = (time.perf_counter() - started) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers[API_VERSION_HEADER] = API_VERSION
    log_event(
        "request.end",
        component="api.request",
        request_id=request_id,
        status="ok" if response.status_code < 500 else "error",
        duration_ms=duration_ms,
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
        },
    )
    set_current_request_id(None)
    return response


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):  # noqa: ARG001
    return error_response(
        exc.code,
        status_code=exc.status_code,
        message=exc.message,
        details=exc.details,
    )


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(request: Request, exc: RequestValidationError):  # noqa: ARG001
    return error_response(
        INVALID_REQUEST,
        status_code=422,
        details={"validation_errors": exc.errors()},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):  # noqa: ARG001
    code = SESSION_NOT_FOUND if exc.status_code == 404 else INVALID_REQUEST
    return error_response(
        code,
        status_code=exc.status_code,
        message=str(exc.detail) if exc.detail else None,
    )


@app.exception_handler(sqlite3.DatabaseError)
async def sqlite_error_handler(request: Request, exc: sqlite3.DatabaseError):  # noqa: ARG001
    return error_response(
        STORE_UNAVAILABLE,
        status_code=503,
        details={"error_type": type(exc).__name__},
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):  # noqa: ARG001
    return error_response(
        INTERNAL_ERROR,
        status_code=500,
        details={"error_type": type(exc).__name__},
    )


def _redact(value: Any) -> Any:
    return redact_secrets(value)


def _strip_internal_metadata(value: Any) -> Any:
    if isinstance(value, list):
        return [_strip_internal_metadata(item) for item in value]
    if not isinstance(value, dict):
        return value

    hidden_metadata_keys = {
        "p6b_evidence_pack",
        "p6b_rag_trace",
        "p6b_rag_evidence_pack",
        "rag_forbidden_state_writes",
        "rag_core_state_readonly",
        "retrieved_evidence",
    }
    cleaned: Dict[str, Any] = {}
    for key, item in value.items():
        if str(key) in hidden_metadata_keys:
            continue
        if key == "metadata" and isinstance(item, dict):
            cleaned[key] = {
                meta_key: _strip_internal_metadata(meta_value)
                for meta_key, meta_value in item.items()
                if not str(meta_key).startswith("p4_")
                and str(meta_key) not in hidden_metadata_keys
            }
        else:
            cleaned[key] = _strip_internal_metadata(item)
    return cleaned


def _public_state_payload(state: Dict[str, Any]) -> Dict[str, Any]:
    return _redact(_strip_internal_metadata(state))


def _public_report_payload(report: Any) -> Dict[str, Any]:
    return _redact(_strip_internal_metadata(report.model_dump()))


def _state_dict(run_state: Any) -> Dict[str, Any]:
    return _redact(run_state.model_dump())


def _trace_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


def _metadata(run_state: Any) -> Dict[str, Any]:
    raw = dict(getattr(run_state, "metadata", {}) or {})
    metadata = {
        "graph_runtime": raw.get("graph_runtime"),
        "extractor_mode": raw.get("last_extractor_mode"),
        "extractor_mode_requested": raw.get("extractor_mode_requested"),
        "strategy": raw.get("last_strategy"),
        "fallback_used": raw.get("last_fallback_used"),
        "final_schema_pass": raw.get("last_final_schema_pass"),
        "error_type": raw.get("last_error_type"),
    }
    return _redact({key: value for key, value in metadata.items() if value is not None})


def _missing_core_fields(run_state: Any) -> List[str]:
    report = getattr(run_state, "final_report", None)
    if report is not None:
        return list(report.missing_core_fields)

    missing: List[str] = []
    if not getattr(run_state, "chief_complaint", None):
        missing.append("chief_complaint")
    if not getattr(run_state, "duration", None):
        missing.append("duration")
    if getattr(run_state, "symptoms_status", "unknown") == "unknown":
        missing.append("symptoms_status")
    if getattr(run_state, "risk_flags_status", "unknown") == "unknown":
        missing.append("risk_flags_status")
    return missing


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="TCM-Assistant",
        stage="P1.1",
        mode="agentic_workflow",
        diagnosis_system=False,
    )


@app.get("/version", response_model=VersionResponse)
def version() -> VersionResponse:
    return VersionResponse(
        service=SERVICE_NAME,
        api_version=API_VERSION,
        stage=API_STAGE,
        contract_status=API_CONTRACT_STATUS,
    )


@app.post("/sessions", response_model=CreateSessionResponse)
def create_api_session(request: CreateSessionRequest) -> CreateSessionResponse:
    started = time.perf_counter()
    session = create_session(
        extractor_mode=request.extractor_mode,
        rag_enabled=request.rag_enabled,
    )
    record_session(session)
    trace_id = _trace_id("p7-session")
    log_event(
        "session.create.completed",
        component="api.session",
        request_id=None,
        session_id=session.session_id,
        status="ok",
        duration_ms=(time.perf_counter() - started) * 1000,
        extra={
            "extractor_mode": session.extractor_mode,
            "rag_enabled": session.rag_enabled,
        },
    )
    return CreateSessionResponse(
        session_id=session.session_id,
        extractor_mode=session.extractor_mode,
        rag_enabled=session.rag_enabled,
        created_at=session.created_at,
        turn_count=session.turn_count,
    )


@app.get("/sessions/{session_id}", response_model=SessionDetailResponse)
def get_api_session_detail(session_id: str) -> SessionDetailResponse:
    session = get_session(session_id)
    if session is None:
        raise ApiError(SESSION_NOT_FOUND, status_code=404)
    return SessionDetailResponse(
        session_id=session.session_id,
        trace_id=_trace_id("p7-session-read"),
        status="ok",
        extractor_mode=session.extractor_mode,
        rag_enabled=session.rag_enabled,
        created_at=session.created_at,
        updated_at=session.updated_at,
        turn_count=session.turn_count,
        state_version=session.state_version,
        metadata=_metadata(session.run_state),
    )


@app.post("/sessions/{session_id}/turn", response_model=TurnResponse)
def submit_turn(session_id: str, request: TurnRequest) -> TurnResponse:
    started = time.perf_counter()
    session = get_session(session_id)
    if session is None:
        raise ApiError(SESSION_NOT_FOUND, status_code=404)

    user_input = request.user_input.strip()
    if not user_input:
        raise ApiError(
            INVALID_REQUEST,
            status_code=400,
            message="user_input must not be empty.",
        )

    log_event(
        "turn.input.received",
        component="api.turn",
        session_id=session_id,
        status="ok",
        extra={
            "input_length": len(user_input),
            "extractor_mode": session.extractor_mode,
            "rag_enabled": session.rag_enabled,
        },
    )
    previous_state = session.run_state.model_copy(deep=True)
    graph_output = run_p4_workflow(
        session.run_state,
        user_input,
        extractor_mode=session.extractor_mode,
        rag_enabled=session.rag_enabled,
    )
    session = append_turn(session_id, user_input, graph_output)
    run_state = session.run_state
    final_report = getattr(run_state, "final_report", None)
    turn_id = get_last_turn_id(session) or ""
    p7_record = record_turn(
        session=session,
        previous_state=previous_state,
        user_input=user_input,
        graph_output=graph_output,
        turn_id=turn_id,
        latency_ms=int((time.perf_counter() - started) * 1000),
    )
    log_event(
        "turn.output.completed",
        component="api.turn",
        session_id=session.session_id,
        turn_id=turn_id,
        status="ok",
        duration_ms=(time.perf_counter() - started) * 1000,
        extra={
            "turn_count": session.turn_count,
            "state_version": session.state_version,
            "report_ready": final_report is not None,
        },
    )

    return TurnResponse(
        session_id=session.session_id,
        turn_id=turn_id,
        turn_count=session.turn_count,
        next_question=run_state.next_question,
        state=_public_state_payload(session.state),
        risk_flags_status=run_state.risk_flags_status,
        risk_rule_ids=list(run_state.triggered_rule_ids),
        risk_reasons=list(run_state.risk_reasons),
        final_report=_public_report_payload(final_report) if final_report is not None else None,
        metadata={
            **_metadata(run_state),
            "p7_trace_id": str(p7_record.get("trace_id") or ""),
            "p7_status": "ok",
        },
        safety_disclaimer=SAFETY_DISCLAIMER,
    )


@app.get("/sessions/{session_id}/state", response_model=SessionStateResponse)
def get_api_session_state(session_id: str) -> SessionStateResponse:
    session = get_session(session_id)
    if session is None:
        raise ApiError(SESSION_NOT_FOUND, status_code=404)

    run_state = session.run_state
    return SessionStateResponse(
        session_id=session.session_id,
        turn_count=session.turn_count,
        state=_public_state_payload(session.state),
        risk_flags_status=run_state.risk_flags_status,
        risk_rule_ids=list(run_state.triggered_rule_ids),
        missing_core_fields=_missing_core_fields(run_state),
        next_question=run_state.next_question,
        metadata=_metadata(run_state),
        safety_disclaimer=SAFETY_DISCLAIMER,
    )


@app.get("/sessions/{session_id}/report", response_model=SessionReportResponse)
def get_api_session_report(session_id: str) -> SessionReportResponse:
    session = get_session(session_id)
    if session is None:
        raise ApiError(SESSION_NOT_FOUND, status_code=404)

    run_state = session.run_state
    final_report = getattr(run_state, "final_report", None)
    if final_report is None:
        return SessionReportResponse(
            session_id=session.session_id,
            ready=False,
            missing_core_fields=_missing_core_fields(run_state),
            next_question=run_state.next_question,
            safety_disclaimer=SAFETY_DISCLAIMER,
        )

    return SessionReportResponse(
        session_id=session.session_id,
        ready=True,
        final_report=_public_report_payload(final_report),
        safety_disclaimer=SAFETY_DISCLAIMER,
    )


@app.post("/sessions/{session_id}/report", response_model=SessionReportResponse)
def post_api_session_report(session_id: str) -> SessionReportResponse:
    session = get_session(session_id)
    if session is None:
        raise ApiError(SESSION_NOT_FOUND, status_code=404)
    turn_id = get_last_turn_id(session) or "0"
    record_report(session=session, turn_id=turn_id)
    return get_api_session_report(session_id)


@app.get("/sessions/{session_id}/trace", response_model=SessionTraceResponse)
def get_api_session_trace(session_id: str) -> SessionTraceResponse:
    session = get_session(session_id)
    if session is None:
        raise ApiError(SESSION_NOT_FOUND, status_code=404)
    traces = get_p7_store().fetch_trace_events(session_id)
    trace_id = traces[-1]["trace_id"] if traces else _trace_id("p7-trace-read")
    return SessionTraceResponse(
        session_id=session_id,
        trace_id=str(trace_id),
        status="ok",
        traces=traces,
    )


@app.get("/sessions/{session_id}/evidence", response_model=SessionEvidenceResponse)
def get_api_session_evidence(session_id: str) -> SessionEvidenceResponse:
    session = get_session(session_id)
    if session is None:
        raise ApiError(SESSION_NOT_FOUND, status_code=404)
    store = get_p7_store()
    retrieved = store.fetch_rag_evidence(session_id, used_only=False)
    used = [item for item in retrieved if item.get("is_used")]
    return SessionEvidenceResponse(
        session_id=session_id,
        trace_id=_trace_id("p7-evidence-read"),
        status="ok",
        retrieved_evidence=retrieved,
        used_evidence=used,
    )


@app.get("/tools", response_model=ToolListResponse)
def get_api_tools() -> ToolListResponse:
    tools = [definition.model_dump() for definition in get_p7_tools().definitions()]
    return ToolListResponse(trace_id=_trace_id("p7-tools"), status="ok", tools=tools)


@app.post("/tools/{tool_name}/invoke", response_model=ToolInvokeResponse)
def invoke_api_tool(tool_name: str, request: ToolInvokeRequest) -> ToolInvokeResponse:
    result = get_p7_tools().call(tool_name, request.payload, approved=request.approved)
    status = "ok" if result.allowed else "blocked"
    get_p7_store().save_audit_log(
        AuditLogRecord(
            session_id=request.session_id,
            turn_id=None,
            event_type="tool.invoke",
            payload=result.audit_log,
        )
    )
    return ToolInvokeResponse(
        session_id=request.session_id,
        trace_id=_trace_id("p7-tool"),
        status=status,
        tool_name=result.tool_name,
        allowed=result.allowed,
        output=result.output,
        audit_log=result.audit_log,
        blocked_reason=result.blocked_reason,
    )


@app.post("/eval/p7", response_model=EvalP7Response)
def run_p7_eval(request: EvalP7Request) -> EvalP7Response:
    result = get_p7_tools().call("eval_case_tool", {"case": request.case}, approved=False)
    metrics = {
        "case_valid": bool(result.output.get("case_valid")),
        "turn_count": int(result.output.get("turn_count") or 0),
        "diagnosis_system": False,
    }
    get_p7_store().save_eval_run(EvalRunRecord(status="ok", metrics=metrics))
    return EvalP7Response(
        session_id="p7-eval",
        trace_id=_trace_id("p7-eval"),
        status="ok",
        metrics=metrics,
    )
