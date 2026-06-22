from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.api.errors import (
    ApiError,
    EXTRACTOR_UNAVAILABLE,
    GRAPH_RUN_FAILED,
    INVALID_REQUEST,
    REAL_LLM_NOT_CONFIGURED,
    REPLAY_FAILED,
    SESSION_NOT_FOUND,
)
from app.api.redaction import redact_secrets
from app.graph.runner import run_p9m1_graph
from app.observability.events import redacted_input_hash, sanitize_event
from app.schemas.report_schemas import RunState, SAFETY_DISCLAIMER
from app.session.memory_store import MemorySessionStore
from app.session.models import SessionRecord, TurnRecord
from app.session.sqlite_store import SQLiteSessionStore
from app.session.store import SessionStore


API_VERSION = "p10m1"
DEFAULT_API_LOG_PATH = Path("artifacts/p10/api_events.jsonl")
DEFAULT_SQLITE_PATH = Path("artifacts/p10/p10_sessions.sqlite3")
TRUE_VALUES = {"1", "true", "yes", "y", "on"}

API_EVENT_FIELDS = (
    "timestamp",
    "request_id",
    "session_id",
    "turn_id",
    "trace_id",
    "method",
    "path",
    "status_code",
    "latency_ms",
    "graph_runtime",
    "extractor_backend",
    "fallback_used",
    "risk_status",
    "risk_rule_ids",
    "retrieved_evidence_count",
    "safety_rewrite_used",
    "error_code",
    "input_length",
    "redacted_input_hash",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def env_bool(name: str, *, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in TRUE_VALUES


def default_sqlite_path() -> Path:
    return Path(os.getenv("SESSION_SQLITE_PATH") or DEFAULT_SQLITE_PATH)


def default_api_log_path() -> Path:
    return Path(os.getenv("API_LOG_PATH") or DEFAULT_API_LOG_PATH)


def default_extractor_backend() -> str:
    return (os.getenv("EXTRACTOR_BACKEND") or "fake").strip() or "fake"


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    return value


def _safe_payload(value: Any) -> Any:
    redacted = redact_secrets(_jsonable(value))
    if isinstance(redacted, dict):
        return sanitize_event(redacted)
    if isinstance(redacted, list):
        return [sanitize_event(item) if isinstance(item, dict) else item for item in redacted]
    return redacted


def append_api_event(event: dict[str, Any], path: str | Path | None = None) -> Path:
    output_path = Path(path or default_api_log_path())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    defaults: dict[str, Any] = {
        "timestamp": utc_now(),
        "request_id": f"req-{uuid4().hex[:12]}",
        "session_id": None,
        "turn_id": None,
        "trace_id": None,
        "method": "",
        "path": "",
        "status_code": 200,
        "latency_ms": 0,
        "graph_runtime": None,
        "extractor_backend": None,
        "fallback_used": False,
        "risk_status": None,
        "risk_rule_ids": [],
        "retrieved_evidence_count": 0,
        "safety_rewrite_used": False,
        "error_code": None,
        "input_length": 0,
        "redacted_input_hash": "",
    }
    payload = {**defaults, **event}
    safe = {field: _safe_payload(payload.get(field)) for field in API_EVENT_FIELDS}
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(safe, ensure_ascii=False, sort_keys=True) + "\n")
    return output_path


def _store_backend_name(store: SessionStore) -> str:
    if isinstance(store, MemorySessionStore):
        return "memory"
    if isinstance(store, SQLiteSessionStore):
        return "sqlite"
    return store.__class__.__name__


def _build_store(store_backend: str | None, sqlite_path: str | Path | None) -> SessionStore:
    backend = (store_backend or os.getenv("SESSION_STORE_BACKEND") or "sqlite").strip().lower()
    if backend == "memory":
        return MemorySessionStore()
    if backend == "sqlite":
        return SQLiteSessionStore(sqlite_path or default_sqlite_path())
    raise ApiError(
        INVALID_REQUEST,
        status_code=400,
        message=f"Unsupported session store backend: {backend}",
        details={"store_backend": backend},
    )


def _get_session_record(store: SessionStore, session_id: str) -> SessionRecord | None:
    getter = getattr(store, "get_session_record", None)
    if callable(getter):
        return getter(session_id)
    state = store.load_state(session_id)
    turns = store.list_turns(session_id)
    if state is None and not turns:
        return None
    return store.create_session(session_id)


def _user_turns(turns: list[TurnRecord]) -> list[TurnRecord]:
    return [turn for turn in turns if turn.role == "user"]


def _missing_core_fields(state: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if not state.get("chief_complaint"):
        missing.append("chief_complaint")
    if not state.get("duration"):
        missing.append("duration")
    if state.get("symptoms_status", "unknown") == "unknown":
        missing.append("symptoms_status")
    if state.get("risk_flags_status", "unknown") == "unknown":
        missing.append("risk_flags_status")
    return missing


def _state_summary(state: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "chief_complaint",
        "duration",
        "symptoms_status",
        "risk_flags_status",
        "triggered_rule_ids",
        "turn_count",
    ]
    return {key: state.get(key) for key in keys}


def _metadata_with_runtime(
    state: dict[str, Any],
    *,
    graph_runtime: str | None,
    extractor_backend: str,
    fallback_used: bool,
    final_schema_pass: bool,
) -> dict[str, Any]:
    metadata = dict(state.get("metadata") or {})
    metadata.update(
        {
            "graph_runtime": graph_runtime,
            "last_extractor_mode": extractor_backend,
            "extractor_backend": extractor_backend,
            "last_fallback_used": fallback_used,
            "last_final_schema_pass": final_schema_pass,
        }
    )
    return metadata


class ConsultationService:
    def __init__(
        self,
        *,
        store: SessionStore | None = None,
        store_backend: str | None = None,
        sqlite_path: str | Path | None = None,
        api_log_path: str | Path | None = None,
        extractor_backend: str | None = None,
    ) -> None:
        self.store = store or _build_store(store_backend, sqlite_path)
        self.store_backend = _store_backend_name(self.store)
        self.sqlite_path = Path(sqlite_path or default_sqlite_path()) if self.store_backend == "sqlite" else None
        self.api_log_path = Path(api_log_path or default_api_log_path())
        self.extractor_backend = extractor_backend or default_extractor_backend()

    def create_session(
        self,
        *,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        backend: str | None = None,
    ) -> dict[str, Any]:
        record = self.store.create_session(session_id)
        if metadata:
            self.store.save_event(
                record.session_id,
                {
                    "event_type": "session_metadata",
                    "metadata": _safe_payload(metadata),
                    "extractor_backend": backend or self.extractor_backend,
                },
            )
        return {
            "session_id": record.session_id,
            "created_at": record.created_at,
            "store_backend": self.store_backend,
            "api_version": API_VERSION,
        }

    def get_session(self, session_id: str) -> dict[str, Any]:
        record = _get_session_record(self.store, session_id)
        if record is None:
            raise ApiError(SESSION_NOT_FOUND, status_code=404, details={"session_id": session_id})
        turns = self.store.list_turns(session_id)
        state = self.store.load_state(session_id) or {}
        final_report = state.get("final_report") if isinstance(state, dict) else None
        return {
            "session_id": record.session_id,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "store_backend": self.store_backend,
            "turn_count": len(_user_turns(turns)),
            "has_final_report": bool(final_report),
            "risk_status": state.get("risk_flags_status") if isinstance(state, dict) else None,
            "metadata": _safe_payload(record.metadata),
        }

    def list_turns(self, session_id: str) -> list[dict[str, Any]]:
        self.get_session(session_id)
        return [_safe_payload(turn.model_dump()) for turn in self.store.list_turns(session_id)]

    def run_turn(
        self,
        session_id: str,
        user_input: str,
        *,
        extractor_backend: str | None = None,
        metadata: dict[str, Any] | None = None,
        debug: bool = False,
    ) -> dict[str, Any]:
        user_input = (user_input or "").strip()
        if not user_input:
            raise ApiError(INVALID_REQUEST, status_code=400, message="user_input must not be empty.")

        self.get_session(session_id)
        backend = (extractor_backend or self.extractor_backend or "fake").strip()
        if backend == "real_llm" and not env_bool("ENABLE_REAL_LLM") and not env_bool("TCM_ALLOW_REAL_LLM"):
            raise ApiError(
                REAL_LLM_NOT_CONFIGURED,
                status_code=503,
                details={"backend": "real_llm", "skip_reason": "real_llm_disabled"},
            )

        turns = self.store.list_turns(session_id)
        turn_id = f"turn-{len(_user_turns(turns)) + 1}"
        trace_id = f"trace-{uuid4().hex[:12]}"
        started = time.perf_counter()
        try:
            result = run_p9m1_graph(
                user_input,
                session_id=session_id,
                trace_id=trace_id,
                turn_id=turn_id,
                extractor_backend=backend,
                rag_enabled=True,
                use_langgraph=True,
                session_store=self.store,
                graph_events_path=self.api_log_path,
            )
        except ValueError as exc:
            raise ApiError(
                EXTRACTOR_UNAVAILABLE,
                status_code=400,
                message="Extractor backend is unavailable.",
                details={"backend": backend, "trace_id": trace_id, "error_type": type(exc).__name__},
            ) from exc
        except NotImplementedError as exc:
            raise ApiError(
                EXTRACTOR_UNAVAILABLE,
                status_code=503,
                message="Extractor backend is reserved or unavailable.",
                details={"backend": backend, "trace_id": trace_id, "error_type": type(exc).__name__},
            ) from exc
        except Exception as exc:
            raise ApiError(
                GRAPH_RUN_FAILED,
                status_code=500,
                message="Graph run failed.",
                details={"trace_id": trace_id, "error_type": type(exc).__name__},
            ) from exc

        latency_ms = int((time.perf_counter() - started) * 1000)
        state = dict(result.get("run_state") or {})
        fallback_used = bool(
            ((result.get("extracted_turn_output") or {}).get("metadata") or {}).get("fallback_used")
        )
        final_schema_pass = bool(result.get("final_report") is None or result.get("final_report"))
        state["metadata"] = _metadata_with_runtime(
            state,
            graph_runtime=str(result.get("graph_runtime") or ""),
            extractor_backend=backend,
            fallback_used=fallback_used,
            final_schema_pass=final_schema_pass,
        )
        self.store.save_state(session_id, state)

        risk_rule_ids = list(state.get("triggered_rule_ids") or [])
        retrieved_evidence_count = int(
            result.get("retrieved_evidence_count")
            or len(result.get("retrieved_evidence") or [])
            or 0
        )
        safety_rewrite_used = bool(result.get("safety_issues") or [])

        if debug and env_bool("ENABLE_DEBUG_RAW_INPUT"):
            self.store.save_event(
                session_id,
                {
                    "event_type": "debug_raw_input",
                    "turn_id": turn_id,
                    "raw_input": _safe_payload(user_input),
                },
            )

        append_api_event(
            {
                "session_id": session_id,
                "turn_id": turn_id,
                "trace_id": str(result.get("trace_id") or trace_id),
                "method": "POST",
                "path": "/sessions/{session_id}/turn",
                "status_code": 200,
                "latency_ms": latency_ms,
                "graph_runtime": result.get("graph_runtime"),
                "extractor_backend": backend,
                "fallback_used": fallback_used,
                "risk_status": state.get("risk_flags_status"),
                "risk_rule_ids": risk_rule_ids,
                "retrieved_evidence_count": retrieved_evidence_count,
                "safety_rewrite_used": safety_rewrite_used,
                "input_length": len(user_input),
                "redacted_input_hash": redacted_input_hash(user_input),
            },
            self.api_log_path,
        )

        return {
            "session_id": session_id,
            "turn_id": turn_id,
            "trace_id": str(result.get("trace_id") or trace_id),
            "graph_runtime": result.get("graph_runtime"),
            "risk_status": state.get("risk_flags_status"),
            "risk_reasons": list(state.get("risk_reasons") or []),
            "risk_rule_ids": risk_rule_ids,
            "missing_core_fields": list(result.get("missing_core_fields") or _missing_core_fields(state)),
            "next_question": result.get("next_question") or state.get("next_question"),
            "final_report": result.get("final_report"),
            "retrieved_evidence_count": retrieved_evidence_count,
            "fallback_used": fallback_used,
            "safety_rewrite_used": safety_rewrite_used,
            "state_summary": _state_summary(state),
            "event_count": len(result.get("graph_events") or []),
            "warnings": list(result.get("errors") or []),
            "run_state": state,
            "raw_result": result,
            "metadata": _safe_payload(metadata or {}),
        }

    def get_state(self, session_id: str) -> dict[str, Any]:
        self.get_session(session_id)
        state = self.store.load_state(session_id) or RunState().model_dump()
        return _safe_payload(state)

    def get_report(self, session_id: str) -> dict[str, Any]:
        self.get_session(session_id)
        state = self.store.load_state(session_id) or RunState().model_dump()
        final_report = state.get("final_report") if isinstance(state, dict) else None
        export = self.store.export_session(session_id)
        evidence = export.get("rag_evidence") or []
        if not final_report:
            return {
                "session_id": session_id,
                "report_available": False,
                "final_report": None,
                "risk_status": state.get("risk_flags_status"),
                "risk_reasons": list(state.get("risk_reasons") or []),
                "evidence": evidence,
                "missing_core_fields": _missing_core_fields(state),
                "next_question": state.get("next_question"),
                "safety_disclaimer": SAFETY_DISCLAIMER,
                "generated_at": None,
            }
        return {
            "session_id": session_id,
            "report_available": True,
            "final_report": _safe_payload(final_report),
            "risk_status": state.get("risk_flags_status"),
            "risk_reasons": list(state.get("risk_reasons") or []),
            "evidence": evidence,
            "missing_core_fields": [],
            "next_question": None,
            "safety_disclaimer": SAFETY_DISCLAIMER,
            "generated_at": utc_now(),
        }

    def replay_session(self, session_id: str, *, allow_write: bool = False) -> dict[str, Any]:
        self.get_session(session_id)
        try:
            replay = self.store.replay_session(session_id)
        except Exception as exc:
            raise ApiError(
                REPLAY_FAILED,
                status_code=500,
                message="Replay failed.",
                details={"session_id": session_id, "error_type": type(exc).__name__},
            ) from exc
        final_state = replay.get("replayed_state") or replay.get("state") or {}
        return {
            "session_id": session_id,
            "turns": _safe_payload(replay.get("turns") or []),
            "final_state": _safe_payload(final_state),
            "final_report": _safe_payload(final_state.get("final_report") if isinstance(final_state, dict) else None),
            "graph_events": _safe_payload(replay.get("graph_events") or replay.get("events") or []),
            "replay_status": "ok_write_allowed" if allow_write else "ok_read_only",
        }

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "api_version": API_VERSION,
            "graph_available": True,
            "session_store_backend": self.store_backend,
            "sqlite_path": str(self.sqlite_path) if self.sqlite_path else None,
            "extractor_backend": self.extractor_backend,
            "langgraph_runtime": True,
            "timestamp": utc_now(),
        }
