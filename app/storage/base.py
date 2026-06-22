from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, Optional

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


class StorageBackend(ABC):
    @abstractmethod
    def initialize(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def create_session(self, session: StorageSession) -> None:
        raise NotImplementedError

    @abstractmethod
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
        raise NotImplementedError

    @abstractmethod
    def save_final_report_bundle(
        self,
        *,
        report: FinalReportRecord,
        evidence_updates: Iterable[RagEvidenceRecord] = (),
        audit_logs: Iterable[AuditLogRecord] = (),
        trace_event: Optional[TraceEventRecord] = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def save_eval_run(self, record: EvalRunRecord) -> None:
        raise NotImplementedError

    @abstractmethod
    def fetch_session_bundle(self, session_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def fetch_trace_events(self, session_id: str) -> list[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def fetch_rag_evidence(self, session_id: str, *, used_only: bool = False) -> list[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def table_counts(self) -> Dict[str, int]:
        raise NotImplementedError
