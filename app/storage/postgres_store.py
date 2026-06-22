from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

from app.storage.base import StorageBackend
from app.storage.errors import StorageUnavailable
from app.storage.models import (
    AuditLogRecord,
    EvalRunRecord,
    FinalReportRecord,
    MemorySnapshotRecord,
    RagEvidenceRecord,
    RiskEventRecord,
    RunStateSnapshot,
    StorageSession,
    StorageTurn,
    TraceEventRecord,
)


POSTGRES_SCHEMA_TABLES = (
    "sessions",
    "turns",
    "run_states",
    "final_reports",
    "risk_events",
    "rag_evidence",
    "audit_logs",
    "eval_runs",
    "trace_events",
    "memory_snapshots",
)


@dataclass(frozen=True)
class PostgresSchemaReady:
    backend: str = "postgres"
    env_var: str = "TCM_DB_URL"
    schema_ready: bool = True
    tables: tuple[str, ...] = POSTGRES_SCHEMA_TABLES


class P7PostgresStore(StorageBackend):
    """Schema-ready adapter placeholder for deployments that set TCM_DB_URL."""

    def __init__(self, db_url: str | None = None) -> None:
        self.db_url = db_url or os.getenv("TCM_DB_URL")

    def initialize(self) -> None:
        if not self.db_url:
            raise StorageUnavailable("TCM_DB_URL is not configured.")
        raise StorageUnavailable("PostgreSQL runtime driver is not installed in P7 local profile.")

    def create_session(self, session: StorageSession) -> None:
        self.initialize()

    def append_turn_bundle(
        self,
        *,
        turn: StorageTurn,
        run_state: RunStateSnapshot,
        risk_events: Iterable[RiskEventRecord] = (),
        rag_evidence: Iterable[RagEvidenceRecord] = (),
        memory_snapshot: Optional[MemorySnapshotRecord] = None,
        trace_event: Optional[TraceEventRecord] = None,
        audit_logs: Iterable[AuditLogRecord] = (),
    ) -> None:
        self.initialize()

    def save_final_report_bundle(
        self,
        *,
        report: FinalReportRecord,
        evidence_updates: Iterable[RagEvidenceRecord] = (),
        audit_logs: Iterable[AuditLogRecord] = (),
        trace_event: Optional[TraceEventRecord] = None,
    ) -> None:
        self.initialize()

    def save_eval_run(self, record: EvalRunRecord) -> None:
        self.initialize()

    def fetch_session_bundle(self, session_id: str) -> Optional[Dict[str, Any]]:
        self.initialize()
        return None

    def fetch_trace_events(self, session_id: str) -> list[Dict[str, Any]]:
        self.initialize()
        return []

    def fetch_rag_evidence(self, session_id: str, *, used_only: bool = False) -> list[Dict[str, Any]]:
        self.initialize()
        return []

    def table_counts(self) -> Dict[str, int]:
        self.initialize()
        return {}


def schema_ready_status() -> dict[str, Any]:
    status = PostgresSchemaReady()
    return {
        "backend": status.backend,
        "env_var": status.env_var,
        "schema_ready": status.schema_ready,
        "configured": bool(os.getenv(status.env_var)),
        "tables": list(status.tables),
    }
