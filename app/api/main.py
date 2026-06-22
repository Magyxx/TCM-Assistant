from __future__ import annotations

import sqlite3
import time
import os
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

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
    EvalRunRequest,
    EvalRunResponse,
    HealthResponse,
    FinalEvalRequest,
    ReplayRequest,
    ReplayResponse,
    RagHealthResponse,
    RagSearchRequest,
    RagSearchResponse,
    ReportExportRequest,
    ReportExportResponse,
    SAFETY_DISCLAIMER,
    SafetyRedTeamRequest,
    SessionDetailResponse,
    SessionEvidenceResponse,
    SessionRagSearchRequest,
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
from app.api.deps import get_consultation_service, get_eval_service, get_p7_store, get_p7_tools
from app.agentic.workflow_adapter import run_p4_workflow
from app.api.versioning import (
    API_CONTRACT_STATUS,
    API_STAGE,
    API_VERSION,
    API_VERSION_HEADER,
    SERVICE_NAME,
)
from app.observability.events import redacted_input_hash
from app.rag.hybrid_retriever import P10M2HybridRetriever
from app.rag.knowledge_builder import DEFAULT_CHUNKS_PATH, ROOT_DIR as RAG_ROOT_DIR, build_p10m2_knowledge, load_knowledge_chunks
from app.rag.query_builder import build_p10m2_rag_query
from app.schemas.report_schemas import RunState
from app.services.consultation_service import append_api_event
from app.services.export_service import ExportService
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


def _resolve_extractor_mode(request: CreateSessionRequest | TurnRequest, fallback: str = "fake") -> str:
    raw = getattr(request, "extractor_mode", None) or getattr(request, "extractor_backend", None) or getattr(request, "backend", None) or fallback
    value = str(raw or fallback).strip()
    if value == "rule_fallback":
        return "fallback"
    if value not in {"real_llm", "fake", "fallback"}:
        raise ApiError(
            INVALID_REQUEST,
            status_code=400,
            message="Unsupported extractor backend.",
            details={"backend": value},
        )
    return value


def _p10_metadata(request: CreateSessionRequest) -> Dict[str, Any] | None:
    p10_style = bool(request.backend or request.store_backend or request.metadata is not None)
    if not p10_style:
        return None
    metadata = dict(request.metadata or {})
    metadata["api_surface"] = "p10"
    return metadata


def _session_prefers_p10(session_id: str) -> bool:
    try:
        replay = get_consultation_service().replay_session(session_id)
    except Exception:
        return False
    for event in replay.get("graph_events") or []:
        if not isinstance(event, dict) or event.get("event_type") != "session_metadata":
            continue
        metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
        if metadata.get("api_surface") == "p10" or metadata:
            return True
    return False


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


def _p10m2_chunks_path() -> Path:
    raw = os.getenv("RAG_CHUNKS_PATH")
    path = Path(raw) if raw else DEFAULT_CHUNKS_PATH
    return path if path.is_absolute() else RAG_ROOT_DIR / path


def _p10m2_index_dir() -> Path:
    raw = os.getenv("RAG_INDEX_DIR") or "knowledge/indexes"
    path = Path(raw)
    return path if path.is_absolute() else RAG_ROOT_DIR / path


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(RAG_ROOT_DIR)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


@app.get("/health", response_model=HealthResponse, response_model_exclude_none=True)
def health(extended: bool = False) -> HealthResponse:
    if extended:
        p10_health = get_consultation_service().health()
        return HealthResponse(
            status="ok",
            service="TCM-Assistant",
            stage="P1.1",
            mode="agentic_workflow",
            diagnosis_system=False,
            **{key: value for key, value in p10_health.items() if key != "status"},
        )
    return HealthResponse(
        status="ok",
        service="TCM-Assistant",
        stage="P1.1",
        mode="agentic_workflow",
        diagnosis_system=False,
    )


@app.get("/rag/health", response_model=RagHealthResponse)
def rag_health() -> RagHealthResponse:
    chunks_path = _p10m2_chunks_path()
    chunks = load_knowledge_chunks(chunks_path)
    if not chunks:
        build_p10m2_knowledge()
        chunks = load_knowledge_chunks(chunks_path)
    return RagHealthResponse(
        rag_mode=os.getenv("RAG_MODE", "hybrid"),
        chunks_count=len(chunks),
        bm25_available=bool(chunks),
        dense_available=bool(chunks) and os.getenv("RAG_ENABLE_DENSE_FALLBACK", "true").lower() not in {"0", "false", "no"},
        hybrid_available=bool(chunks),
        index_dir=_relative(_p10m2_index_dir()),
        chunks_path=_relative(chunks_path),
    )


@app.post("/rag/search", response_model=RagSearchResponse)
def rag_search(request: RagSearchRequest) -> RagSearchResponse:
    started = time.perf_counter()
    result = P10M2HybridRetriever(chunks_path=_p10m2_chunks_path()).search(
        request.query,
        top_k=request.top_k,
        mode=request.mode,
    )
    append_api_event(
        {
            "method": "POST",
            "path": "/rag/search",
            "status_code": 200,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "retrieved_evidence_count": len(result.get("results") or []),
            "input_length": len(request.query),
            "redacted_input_hash": redacted_input_hash(request.query),
        }
    )
    return RagSearchResponse(**result, query=request.query)


@app.get("/version", response_model=VersionResponse)
def version() -> VersionResponse:
    return VersionResponse(
        service=SERVICE_NAME,
        api_version=API_VERSION,
        stage=API_STAGE,
        contract_status=API_CONTRACT_STATUS,
    )


@app.post("/sessions", response_model=CreateSessionResponse, response_model_exclude_none=True)
def create_api_session(request: CreateSessionRequest) -> CreateSessionResponse:
    started = time.perf_counter()
    extractor_mode = _resolve_extractor_mode(request)
    p10_metadata = _p10_metadata(request)
    session = create_session(
        extractor_mode=extractor_mode,  # type: ignore[arg-type]
        rag_enabled=request.rag_enabled,
    )
    p10_session = get_consultation_service().create_session(
        session_id=session.session_id,
        metadata=p10_metadata,
        backend=extractor_mode,
    )
    record_session(session)
    trace_id = _trace_id("p7-session")
    duration_ms = (time.perf_counter() - started) * 1000
    log_event(
        "session.create.completed",
        component="api.session",
        request_id=None,
        session_id=session.session_id,
        status="ok",
        duration_ms=duration_ms,
        extra={
            "extractor_mode": session.extractor_mode,
            "rag_enabled": session.rag_enabled,
        },
    )
    append_api_event(
        {
            "session_id": session.session_id,
            "trace_id": trace_id,
            "method": "POST",
            "path": "/sessions",
            "status_code": 200,
            "latency_ms": int(duration_ms),
            "extractor_backend": extractor_mode,
        }
    )
    return CreateSessionResponse(
        session_id=session.session_id,
        extractor_mode=session.extractor_mode,
        rag_enabled=session.rag_enabled,
        created_at=session.created_at,
        turn_count=session.turn_count,
        store_backend=str(p10_session.get("store_backend") or "sqlite") if p10_metadata else None,
        api_version=str(p10_session.get("api_version") or "p10m1") if p10_metadata else None,
    )


@app.get("/sessions/{session_id}", response_model=SessionDetailResponse)
def get_api_session_detail(session_id: str) -> SessionDetailResponse:
    session = get_session(session_id)
    if session is None:
        raise ApiError(SESSION_NOT_FOUND, status_code=404)
    try:
        p10_session = get_consultation_service().get_session(session_id)
    except ApiError:
        p10_session = {}
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
        store_backend=p10_session.get("store_backend"),
        has_final_report=p10_session.get("has_final_report"),
        risk_status=p10_session.get("risk_status"),
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
    extractor_backend = request.extractor_backend or session.extractor_mode or "fake"
    p10_result = get_consultation_service().run_turn(
        session_id,
        user_input,
        extractor_backend=extractor_backend,
        metadata=request.metadata,
        debug=request.debug,
    )
    run_state = RunState.model_validate(p10_result["run_state"])
    graph_output = {
        **dict(p10_result.get("raw_result") or {}),
        "run_state": run_state,
        "turn_output": (p10_result.get("raw_result") or {}).get("extracted_turn_output"),
    }
    legacy_request = (
        request.extractor_backend is None
        and request.metadata is None
        and not request.debug
        and not _session_prefers_p10(session_id)
    )
    if legacy_request and getattr(run_state, "final_report", None) is None:
        graph_output = run_p4_workflow(
            previous_state,
            user_input,
            extractor_mode=session.extractor_mode,
            rag_enabled=session.rag_enabled,
        )
    session = append_turn(session_id, user_input, graph_output)
    run_state = session.run_state
    final_report = getattr(run_state, "final_report", None)
    turn_id = p10_result.get("turn_id") or get_last_turn_id(session) or ""
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

    base_payload = {
        "session_id": session.session_id,
        "turn_id": turn_id,
        "turn_count": session.turn_count,
        "next_question": run_state.next_question,
        "state": _public_state_payload(session.state),
        "risk_flags_status": run_state.risk_flags_status,
        "risk_rule_ids": list(run_state.triggered_rule_ids),
        "risk_reasons": list(run_state.risk_reasons),
        "final_report": _public_report_payload(final_report) if final_report is not None else None,
        "metadata": {
            **_metadata(run_state),
            "p7_trace_id": str(p7_record.get("trace_id") or ""),
            "p7_status": "ok",
        },
        "safety_disclaimer": SAFETY_DISCLAIMER,
    }
    if legacy_request:
        return JSONResponse(content=base_payload)

    return TurnResponse(
        **base_payload,
        trace_id=str(p10_result.get("trace_id") or ""),
        graph_runtime=str(p10_result.get("graph_runtime") or ""),
        risk_status=getattr(run_state, "risk_flags_status", None),
        missing_core_fields=list(p10_result.get("missing_core_fields") or _missing_core_fields(run_state)),
        state_summary=dict(p10_result.get("state_summary") or {}),
        retrieved_evidence_count=int(p10_result.get("retrieved_evidence_count") or 0),
        fallback_used=bool(p10_result.get("fallback_used")),
        safety_rewrite_used=bool(p10_result.get("safety_rewrite_used")),
        event_count=int(p10_result.get("event_count") or 0),
        warnings=list(p10_result.get("warnings") or []),
    )


@app.post("/turn", response_model=TurnResponse)
def submit_turn_shortcut(request: TurnRequest) -> TurnResponse:
    session_id = request.session_id
    if not session_id:
        created = create_api_session(
            CreateSessionRequest(
                backend=request.extractor_backend or "fake",
                metadata=request.metadata,
            )
        )
        session_id = created.session_id
    return submit_turn(session_id, request)


@app.get("/sessions/{session_id}/turns")
def list_api_session_turns(session_id: str) -> Dict[str, Any]:
    started = time.perf_counter()
    turns = get_consultation_service().list_turns(session_id)
    append_api_event(
        {
            "session_id": session_id,
            "method": "GET",
            "path": "/sessions/{session_id}/turns",
            "status_code": 200,
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }
    )
    return {"session_id": session_id, "turns": turns}


@app.get("/sessions/{session_id}/state", response_model=SessionStateResponse)
def get_api_session_state(session_id: str) -> SessionStateResponse:
    started = time.perf_counter()
    session = get_session(session_id)
    if session is None:
        raise ApiError(SESSION_NOT_FOUND, status_code=404)

    run_state = session.run_state
    append_api_event(
        {
            "session_id": session_id,
            "method": "GET",
            "path": "/sessions/{session_id}/state",
            "status_code": 200,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "risk_status": run_state.risk_flags_status,
            "risk_rule_ids": list(run_state.triggered_rule_ids),
        }
    )
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


@app.post("/sessions/{session_id}/rag/search", response_model=RagSearchResponse)
def rag_search_for_session(session_id: str, request: SessionRagSearchRequest | None = None) -> RagSearchResponse:
    started = time.perf_counter()
    session = get_session(session_id)
    if session is None:
        raise ApiError(SESSION_NOT_FOUND, status_code=404)
    request = request or SessionRagSearchRequest()
    query = build_p10m2_rag_query(session.run_state)
    result = P10M2HybridRetriever(chunks_path=_p10m2_chunks_path()).search(
        query,
        top_k=request.top_k,
        mode=request.mode,
    )
    append_api_event(
        {
            "session_id": session_id,
            "method": "POST",
            "path": "/sessions/{session_id}/rag/search",
            "status_code": 200,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "retrieved_evidence_count": len(result.get("results") or []),
            "input_length": len(query),
            "redacted_input_hash": redacted_input_hash(query),
            "risk_status": session.run_state.risk_flags_status,
            "risk_rule_ids": list(session.run_state.triggered_rule_ids),
        }
    )
    return RagSearchResponse(**result, query=query, session_id=session_id)


@app.post("/sessions/{session_id}/report/export", response_model=ReportExportResponse)
def export_api_session_report(session_id: str, request: ReportExportRequest | None = None) -> ReportExportResponse:
    started = time.perf_counter()
    session = get_session(session_id)
    if session is None:
        raise ApiError(SESSION_NOT_FOUND, status_code=404)
    request = request or ReportExportRequest()
    result = ExportService(get_consultation_service()).export_report(
        session_id,
        format=request.format,
        include_debug_raw_input=request.include_debug_raw_input,
    )
    append_api_event(
        {
            "session_id": session_id,
            "method": "POST",
            "path": "/sessions/{session_id}/report/export",
            "status_code": 200,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "risk_status": session.run_state.risk_flags_status,
            "risk_rule_ids": list(session.run_state.triggered_rule_ids),
        }
    )
    return ReportExportResponse(**result)


@app.get("/sessions/{session_id}/report", response_model=SessionReportResponse)
def get_api_session_report(session_id: str) -> SessionReportResponse:
    started = time.perf_counter()
    session = get_session(session_id)
    if session is None:
        raise ApiError(SESSION_NOT_FOUND, status_code=404)

    run_state = session.run_state
    final_report = getattr(run_state, "final_report", None)
    try:
        p10_report = get_consultation_service().get_report(session_id)
    except ApiError:
        p10_report = {}
    include_p10_fields = _session_prefers_p10(session_id)
    append_api_event(
        {
            "session_id": session_id,
            "method": "GET",
            "path": "/sessions/{session_id}/report",
            "status_code": 200,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "risk_status": run_state.risk_flags_status,
            "risk_rule_ids": list(run_state.triggered_rule_ids),
        }
    )
    if final_report is None:
        base_payload = {
            "session_id": session.session_id,
            "ready": False,
            "final_report": None,
            "missing_core_fields": _missing_core_fields(run_state),
            "next_question": run_state.next_question,
            "safety_disclaimer": SAFETY_DISCLAIMER,
        }
        if not include_p10_fields:
            return JSONResponse(content=base_payload)
        return SessionReportResponse(
            **base_payload,
            report_available=False,
            risk_status=getattr(run_state, "risk_flags_status", None),
            risk_reasons=list(getattr(run_state, "risk_reasons", []) or []),
            evidence=list(p10_report.get("evidence") or []),
        )

    base_payload = {
        "session_id": session.session_id,
        "ready": True,
        "final_report": _public_report_payload(final_report),
        "missing_core_fields": [],
        "next_question": None,
        "safety_disclaimer": SAFETY_DISCLAIMER,
    }
    if not include_p10_fields:
        return JSONResponse(content=base_payload)
    return SessionReportResponse(
        **base_payload,
        report_available=True,
        risk_status=getattr(run_state, "risk_flags_status", None),
        risk_reasons=list(getattr(run_state, "risk_reasons", []) or []),
        evidence=list(p10_report.get("evidence") or []),
        generated_at=p10_report.get("generated_at"),
    )


@app.post("/sessions/{session_id}/report", response_model=SessionReportResponse)
def post_api_session_report(session_id: str) -> SessionReportResponse:
    session = get_session(session_id)
    if session is None:
        raise ApiError(SESSION_NOT_FOUND, status_code=404)
    turn_id = get_last_turn_id(session) or "0"
    record_report(session=session, turn_id=turn_id)
    return get_api_session_report(session_id)


@app.post("/sessions/{session_id}/replay", response_model=ReplayResponse)
def replay_api_session(session_id: str, request: ReplayRequest | None = None) -> ReplayResponse:
    started = time.perf_counter()
    allow_write = bool(request.allow_write) if request is not None else False
    replay = get_consultation_service().replay_session(session_id, allow_write=allow_write)
    append_api_event(
        {
            "session_id": session_id,
            "method": "POST",
            "path": "/sessions/{session_id}/replay",
            "status_code": 200,
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }
    )
    return ReplayResponse(**replay)


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


@app.post("/eval/p9m2-multiturn", response_model=EvalRunResponse)
def run_p9m2_multiturn_eval(request: EvalRunRequest) -> EvalRunResponse:
    started = time.perf_counter()
    result = get_eval_service().run_or_load_p9m2_multiturn_eval(run=request.run)
    append_api_event(
        {
            "method": "POST",
            "path": "/eval/p9m2-multiturn",
            "status_code": 200,
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }
    )
    return EvalRunResponse(**result)


@app.post("/safety/redteam", response_model=EvalRunResponse)
def run_p10m2_safety_redteam(request: SafetyRedTeamRequest | None = None) -> EvalRunResponse:
    started = time.perf_counter()
    request = request or SafetyRedTeamRequest()
    from scripts.eval_p10m2_safety_redteam import run_eval as run_safety_redteam

    result = run_safety_redteam(write_artifacts=True) if request.run else run_safety_redteam(write_artifacts=False)
    append_api_event(
        {
            "method": "POST",
            "path": "/safety/redteam",
            "status_code": 200,
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }
    )
    return EvalRunResponse(
        status=str(result.get("status") or "ok"),
        metrics=dict(result.get("metrics") or {}),
        artifacts=dict(result.get("artifacts") or {}),
        skipped=bool(result.get("skipped", False)),
        skip_reason=str(result.get("skip_reason") or ""),
    )


@app.post("/eval/final", response_model=EvalRunResponse)
def run_p10m2_final_eval(request: FinalEvalRequest | None = None) -> EvalRunResponse:
    started = time.perf_counter()
    request = request or FinalEvalRequest()
    from scripts.eval_p10m2_final import run_final_eval

    result = run_final_eval(run_dependencies=request.run)
    append_api_event(
        {
            "method": "POST",
            "path": "/eval/final",
            "status_code": 200,
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }
    )
    return EvalRunResponse(
        status=str(result.get("status") or "ok"),
        metrics=dict(result.get("metrics") or {}),
        artifacts=dict(result.get("artifacts") or {}),
        skipped=bool(result.get("skipped", False)),
        skip_reason=str(result.get("skip_reason") or ""),
    )
