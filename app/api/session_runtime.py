from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import ValidationError

from app.api.errors import ApiError, STATE_CORRUPTED, TURN_REJECTED
from app.api.models import ExtractorMode
from app.api.observability import log_event
from app.api.report_audit import assert_report_safe, audit_report
from app.api.redaction import redact_secrets
from app.api.report_validator import validate_report
from app.api.sqlite_store import (
    append_turn_and_update_state,
    clear_all_sessions,
    fetch_session,
    insert_session,
)
from app.schemas.report_schemas import RunState


PERSISTENCE_STAGE = "P1.2"
DEFAULT_SESSION_MODE: ExtractorMode = "real_llm"


@dataclass
class ApiSession:
    session_id: str
    extractor_mode: ExtractorMode
    rag_enabled: bool
    created_at: str
    updated_at: str
    stage: str = PERSISTENCE_STAGE
    turn_count: int = 0
    state_version: int = 0
    run_state: RunState = field(default_factory=RunState)
    turns: List[Dict[str, Any]] = field(default_factory=list)
    final_report: Optional[Dict[str, Any]] = None
    last_metadata: Dict[str, Any] = field(default_factory=dict)
    next_question: Optional[str] = None

    @property
    def state(self) -> Dict[str, Any]:
        state = self.run_state.model_dump()
        state["state_version"] = self.state_version
        return state


_SESSIONS: Dict[str, ApiSession] = {}
_LOCK = RLock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_extractor_mode(value: Any) -> ExtractorMode:
    return value if value in {"real_llm", "openai_compatible", "cloud_llm", "fake", "fallback", "local_lora"} else DEFAULT_SESSION_MODE


def _coerce_state_version(state_payload: Dict[str, Any], run_state: RunState) -> int:
    raw_value = state_payload.get("state_version")
    if raw_value is None:
        return int(getattr(run_state, "turn_count", 0) or 0)
    try:
        return max(0, int(raw_value))
    except (TypeError, ValueError):
        return int(getattr(run_state, "turn_count", 0) or 0)


def _session_from_persisted(payload: Dict[str, Any]) -> ApiSession:
    session_row = payload["session"]
    state_payload = dict(payload["state"])
    try:
        run_state = RunState.model_validate(state_payload)
    except ValidationError as exc:
        raise ApiError(
            STATE_CORRUPTED,
            details={
                "session_id": session_row.get("session_id"),
                "reason": "state_schema_invalid",
            },
        ) from exc
    turns: List[Dict[str, Any]] = []
    for row in payload["turns"]:
        turns.append(
            {
                "turn_id": str(row["id"]),
                "turn_index": row["turn_index"],
                "user_input": row["user_input"],
                "created_at": row["created_at"],
                "response": row["response_json"],
            }
        )

    final_report = run_state.final_report.model_dump() if run_state.final_report else None
    state_version = _coerce_state_version(state_payload, run_state)
    return ApiSession(
        session_id=session_row["session_id"],
        extractor_mode=_normalize_extractor_mode(session_row["mode"]),
        rag_enabled=bool(session_row["rag_enabled"]),
        created_at=session_row["created_at"],
        updated_at=session_row["updated_at"],
        stage=session_row.get("stage") or PERSISTENCE_STAGE,
        turn_count=int(getattr(run_state, "turn_count", 0)),
        state_version=state_version,
        run_state=run_state,
        turns=turns,
        final_report=final_report,
        last_metadata=dict(getattr(run_state, "metadata", {}) or {}),
        next_question=getattr(run_state, "next_question", None),
    )


def _cache_session(session: ApiSession) -> None:
    with _LOCK:
        _SESSIONS[session.session_id] = session


def create_session(extractor_mode: ExtractorMode, rag_enabled: bool) -> ApiSession:
    started = time.perf_counter()
    now = _now_iso()
    session = ApiSession(
        session_id=str(uuid4()),
        extractor_mode=extractor_mode,
        rag_enabled=rag_enabled,
        created_at=now,
        updated_at=now,
    )
    try:
        insert_session(
            session_id=session.session_id,
            created_at=session.created_at,
            updated_at=session.updated_at,
            stage=session.stage,
            mode=session.extractor_mode,
            rag_enabled=session.rag_enabled,
            state=session.state,
        )
    except Exception as exc:
        log_event(
            "persistence.session.write",
            level="ERROR",
            component="api.persistence",
            session_id=session.session_id,
            status="error",
            duration_ms=(time.perf_counter() - started) * 1000,
            extra={"error_type": type(exc).__name__},
        )
        raise
    _cache_session(session)
    log_event(
        "persistence.session.write",
        component="api.persistence",
        session_id=session.session_id,
        status="ok",
        duration_ms=(time.perf_counter() - started) * 1000,
        extra={
            "stage": session.stage,
            "extractor_mode": session.extractor_mode,
            "rag_enabled": session.rag_enabled,
        },
    )
    return session


def get_session(session_id: str) -> Optional[ApiSession]:
    started = time.perf_counter()
    try:
        persisted = fetch_session(session_id)
    except Exception as exc:
        log_event(
            "persistence.session.read",
            level="ERROR",
            component="api.persistence",
            session_id=session_id,
            status="error",
            duration_ms=(time.perf_counter() - started) * 1000,
            extra={"error_type": type(exc).__name__},
        )
        raise
    if persisted is not None:
        session = _session_from_persisted(persisted)
        _cache_session(session)
        log_event(
            "persistence.session.read",
            component="api.persistence",
            session_id=session_id,
            status="ok",
            duration_ms=(time.perf_counter() - started) * 1000,
            extra={"source": "sqlite", "turn_count": session.turn_count},
        )
        return session

    with _LOCK:
        session = _SESSIONS.get(session_id)
    log_event(
        "persistence.session.read",
        component="api.persistence",
        session_id=session_id,
        status="miss" if session is None else "ok",
        duration_ms=(time.perf_counter() - started) * 1000,
        extra={"source": "memory" if session is not None else "none"},
    )
    return session


def append_turn(session_id: str, user_input: str, graph_output: Dict[str, Any]) -> ApiSession:
    started = time.perf_counter()
    with _LOCK:
        session = _SESSIONS[session_id]
        run_state = graph_output.get("run_state") or session.run_state
        session.run_state = run_state
        session.turn_count = int(getattr(run_state, "turn_count", session.turn_count + 1))
        session.next_question = getattr(run_state, "next_question", None)
        session.last_metadata = dict(getattr(run_state, "metadata", {}) or {})

        final_report = getattr(run_state, "final_report", None)
        session.final_report = final_report.model_dump() if final_report is not None else None
        next_state_version = session.state_version + 1

        now = _now_iso()
        session.updated_at = now
        response_summary = {
            "turn_count": session.turn_count,
            "next_question": session.next_question,
            "risk_flags_status": getattr(run_state, "risk_flags_status", None),
            "risk_rule_ids": list(getattr(run_state, "triggered_rule_ids", []) or []),
            "risk_reasons": list(getattr(run_state, "risk_reasons", []) or []),
            "final_report": session.final_report,
            "metadata": session.last_metadata,
        }
        state_for_store = run_state.model_dump()
        state_for_store["state_version"] = next_state_version
        report_audit = None
        if session.final_report is not None:
            report_audit = audit_report(session.final_report, state_for_store)
            assert_report_safe(session.final_report, state_for_store)
            report_validation = validate_report(session.final_report, state_for_store)
            if not report_validation["passed"]:
                raise ApiError(
                    TURN_REJECTED,
                    status_code=409,
                    message="Generated report failed report validation.",
                    details={"validation": report_validation},
                )
            report_audit = {
                **report_audit,
                "validator": report_validation,
            }

        try:
            turn_row_id = append_turn_and_update_state(
                session_id=session_id,
                turn_index=session.turn_count,
                user_input=user_input,
                response=response_summary,
                state=state_for_store,
                updated_at=now,
                created_at=now,
                report_snapshot=session.final_report,
                report_safety_flags=report_audit,
            )
        except Exception as exc:
            log_event(
                "persistence.turn.write",
                level="ERROR",
                component="api.persistence",
                session_id=session_id,
                status="error",
                duration_ms=(time.perf_counter() - started) * 1000,
                extra={"error_type": type(exc).__name__, "turn_index": session.turn_count},
            )
            raise
        session.state_version = next_state_version
        turn_id = str(turn_row_id)
        session.turns.append(
            {
                "turn_id": turn_id,
                "turn_index": session.turn_count,
                "user_input": redact_secrets(user_input),
                "created_at": now,
                "response": response_summary,
            }
        )
        log_event(
            "persistence.turn.write",
            component="api.persistence",
            session_id=session_id,
            turn_id=turn_id,
            status="ok",
            duration_ms=(time.perf_counter() - started) * 1000,
            extra={
                "turn_index": session.turn_count,
                "state_version": session.state_version,
                "report_snapshot": session.final_report is not None,
            },
        )
        return session


def get_last_turn_id(session: ApiSession) -> Optional[str]:
    if not session.turns:
        return None
    return session.turns[-1]["turn_id"]


def clear_sessions() -> None:
    """Test helper for SQLite and in-memory state isolation."""
    with _LOCK:
        _SESSIONS.clear()
    clear_all_sessions()


def clear_session_cache() -> None:
    """Test helper that simulates process restart without deleting SQLite rows."""
    with _LOCK:
        _SESSIONS.clear()
