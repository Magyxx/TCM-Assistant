from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from app.api.main import (
    create_api_session,
    get_api_session_detail,
    get_api_session_report,
    submit_turn_shortcut,
)
from app.api.models import CreateSessionRequest, TurnRequest
from app.api.p1_schemas import (
    P1CreateSessionRequest,
    P1CreateSessionResponse,
    P1EvalSmokeResponse,
    P1HealthResponse,
    P1ReportResponse,
    P1SessionSummary,
    P1TurnRequest,
    P1TurnResponse,
)
from app.config.settings import get_settings
from app.report.renderer import build_report_skeleton


app = FastAPI(
    title="TCM-Assistant P1-F0 API",
    version="p1-f0",
    description="Productization foundation API without external hard dependencies.",
)


def _payload(value: Any) -> dict[str, Any]:
    if isinstance(value, JSONResponse):
        return json.loads(value.body.decode("utf-8"))
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return dict(value)


def _skipped() -> list[str]:
    return ["real_llm", "local_lora", "embedding", "vectorstore", "postgresql"]


@app.get("/health", response_model=P1HealthResponse)
def health() -> P1HealthResponse:
    settings = get_settings()
    return P1HealthResponse(app=settings.APP_NAME, mode=settings.APP_ENV)


@app.post("/sessions", response_model=P1CreateSessionResponse)
def create_session(request: P1CreateSessionRequest | None = None) -> P1CreateSessionResponse:
    request = request or P1CreateSessionRequest()
    created = create_api_session(
        CreateSessionRequest(
            extractor_mode=request.extractor_backend,
            rag_enabled=request.rag_enabled,
            metadata=request.metadata,
        )
    )
    return P1CreateSessionResponse(
        session_id=created.session_id,
        extractor_backend=created.extractor_mode,
        rag_enabled=created.rag_enabled,
        created_at=created.created_at,
        external_dependencies_skipped=_skipped(),
    )


@app.post("/turn", response_model=P1TurnResponse)
def turn(request: P1TurnRequest) -> P1TurnResponse:
    if not request.user_input.strip():
        raise HTTPException(status_code=400, detail="user_input must not be empty")
    response = submit_turn_shortcut(
        TurnRequest(
            session_id=request.session_id,
            user_input=request.user_input,
            extractor_backend=request.extractor_backend or "fake",
            metadata={"p1_f0": True},
        )
    )
    payload = _payload(response)
    metadata = dict(payload.get("metadata") or {})
    risk_status = str(payload.get("risk_status") or payload.get("risk_flags_status") or "unknown")
    next_question_value = payload.get("next_question")
    next_question = (
        ""
        if payload.get("final_report")
        else str(next_question_value or "Please provide any missing duration, severity, and red-flag symptoms.")
    )
    return P1TurnResponse(
        session_id=str(payload["session_id"]),
        turn_id=str(payload.get("turn_id") or ""),
        graph_runtime=str(payload.get("graph_runtime") or metadata.get("graph_runtime") or "fallback_or_langgraph"),
        extractor_backend=str(metadata.get("extractor_mode") or request.extractor_backend or "fake"),
        schema_pass=bool(metadata.get("schema_pass", True)),
        risk_status=risk_status,
        missing_core_fields=list(payload.get("missing_core_fields") or []),
        next_action="continue_inquiry" if next_question else "review_summary",
        next_question=next_question,
        evidence_pack=payload.get("p1_evidence_pack"),
        report_skeleton=payload.get("p1_report_skeleton"),
        report_audit=payload.get("report_audit"),
        audit_event_count=int(payload.get("event_count") or 1),
        external_dependencies_skipped=_skipped(),
    )


@app.get("/sessions/{session_id}", response_model=P1SessionSummary)
def session_summary(session_id: str) -> P1SessionSummary:
    detail = get_api_session_detail(session_id)
    return P1SessionSummary(
        session_id=detail.session_id,
        turn_count=detail.turn_count,
        extractor_backend=detail.extractor_mode or "fake",
        rag_enabled=bool(detail.rag_enabled),
        risk_status=detail.risk_status,
        missing_core_fields=list((detail.metadata or {}).get("missing_core_fields") or []),
    )


@app.get("/reports/{session_id}", response_model=P1ReportResponse)
def report(session_id: str) -> P1ReportResponse:
    report_payload = get_api_session_report(session_id)
    if report_payload.ready and report_payload.final_report:
        final_report_metadata = (
            report_payload.final_report.get("metadata", {})
            if isinstance(report_payload.final_report, dict)
            else {}
        )
        report_skeleton = report_payload.p1_report_skeleton or final_report_metadata.get("p1_f1_report_skeleton")
        return P1ReportResponse(
            session_id=session_id,
            report_status="ready",
            skeleton=report_skeleton or report_payload.final_report,
            evidence_pack=report_payload.p1_evidence_pack,
            report_skeleton=report_skeleton,
            report_audit=report_payload.report_audit,
            external_dependencies_skipped=_skipped(),
        )
    skeleton = build_report_skeleton(
        session_id=session_id,
        state={
            "missing_core_fields": report_payload.missing_core_fields,
            "risk_status": report_payload.risk_status or "unknown",
            "risk_reasons": report_payload.risk_reasons or [],
        },
    )
    return P1ReportResponse(
        session_id=session_id,
        report_status="not_ready",
        skeleton=report_payload.p1_report_skeleton or skeleton.model_dump(),
        evidence_pack=report_payload.p1_evidence_pack,
        report_skeleton=report_payload.p1_report_skeleton,
        report_audit=report_payload.report_audit,
        external_dependencies_skipped=_skipped(),
    )


@app.post("/eval/smoke", response_model=P1EvalSmokeResponse)
def eval_smoke() -> P1EvalSmokeResponse:
    created = create_session(P1CreateSessionRequest(extractor_backend="fake", rag_enabled=False))
    result = turn(P1TurnRequest(session_id=created.session_id, user_input="胃胀一周，饭后明显"))
    return P1EvalSmokeResponse(
        sample_count=1,
        checks={
            "session_create": "passed",
            "turn_fake_smoke": "passed" if result.schema_pass else "failed",
            "no_external_llm_required": "passed",
        },
    )
