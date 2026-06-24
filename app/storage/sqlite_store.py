from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, Optional

from app.storage.base import StorageBackend
from app.storage.errors import StorageRecordNotFound
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
    utc_now,
)
from app.storage.serializers import from_json_text, to_json_text


P7_SQLITE_SCHEMA_VERSION = 7
P7_SQLITE_SCHEMA_STAGE = "P7"
DEFAULT_SQLITE_PATH = Path("data") / "tcm_assistant.sqlite3"
P7_TABLES = (
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


SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS schema_meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        mode TEXT NOT NULL,
        rag_enabled INTEGER NOT NULL,
        status TEXT NOT NULL,
        metadata_json TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS turns (
        turn_id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        turn_index INTEGER NOT NULL,
        user_input TEXT NOT NULL,
        turn_output_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
        UNIQUE(session_id, turn_index)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS run_states (
        snapshot_id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        turn_id TEXT NOT NULL,
        state_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS final_reports (
        report_id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        turn_id TEXT NOT NULL,
        report_json TEXT NOT NULL,
        safety_check_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS risk_events (
        event_id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        turn_id TEXT NOT NULL,
        risk_status TEXT NOT NULL,
        rule_ids_json TEXT NOT NULL,
        reasons_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS rag_evidence (
        evidence_id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        turn_id TEXT NOT NULL,
        source_id TEXT NOT NULL,
        chunk_id TEXT NOT NULL,
        chunk_hash TEXT NOT NULL,
        index_version TEXT NOT NULL,
        score REAL NOT NULL,
        retrieval_mode TEXT NOT NULL,
        used_in_report_section TEXT,
        is_used INTEGER NOT NULL,
        evidence_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_logs (
        audit_id TEXT PRIMARY KEY,
        session_id TEXT,
        turn_id TEXT,
        event_type TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS eval_runs (
        eval_id TEXT PRIMARY KEY,
        status TEXT NOT NULL,
        metrics_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS trace_events (
        trace_event_id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        turn_id TEXT NOT NULL,
        trace_id TEXT NOT NULL,
        event_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS memory_snapshots (
        snapshot_id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        turn_id TEXT NOT NULL,
        snapshot_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
    )
    """,
)


def default_sqlite_path() -> Path:
    configured = os.getenv("TCM_SQLITE_PATH")
    return Path(configured) if configured else DEFAULT_SQLITE_PATH


def _ensure_parent(path: Path) -> None:
    if str(path.parent) not in {"", "."}:
        path.parent.mkdir(parents=True, exist_ok=True)


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {str(key): row[key] for key in row.keys()}


class P7SQLiteStore(StorageBackend):
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else default_sqlite_path()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        _ensure_parent(self.db_path)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        try:
            conn.execute("PRAGMA journal_mode = WAL")
        except sqlite3.DatabaseError:
            pass
        try:
            yield conn
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.connect() as conn:
            with conn:
                for statement in SCHEMA_STATEMENTS:
                    conn.execute(statement)
                now = utc_now()
                meta = {
                    "schema_version": str(P7_SQLITE_SCHEMA_VERSION),
                    "schema_stage": P7_SQLITE_SCHEMA_STAGE,
                    "store_name": "p7_service_memory_persistence",
                }
                for key, value in meta.items():
                    conn.execute(
                        """
                        INSERT INTO schema_meta (key, value, updated_at)
                        VALUES (?, ?, ?)
                        ON CONFLICT(key) DO UPDATE
                        SET value = excluded.value, updated_at = excluded.updated_at
                        """,
                        (key, value, now),
                    )

    def create_session(self, session: StorageSession) -> None:
        self.initialize()
        with self.connect() as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO sessions (
                        session_id, created_at, updated_at, mode,
                        rag_enabled, status, metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(session_id) DO UPDATE
                    SET updated_at = excluded.updated_at,
                        mode = excluded.mode,
                        rag_enabled = excluded.rag_enabled,
                        status = excluded.status,
                        metadata_json = excluded.metadata_json
                    """,
                    (
                        session.session_id,
                        session.created_at,
                        session.updated_at,
                        session.mode,
                        int(session.rag_enabled),
                        session.status,
                        to_json_text(session.metadata),
                    ),
                )

    def _insert_turn(self, conn: sqlite3.Connection, turn: StorageTurn) -> None:
        conn.execute(
            """
            INSERT INTO turns (
                turn_id, session_id, turn_index, user_input,
                turn_output_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(turn_id) DO UPDATE
            SET turn_output_json = excluded.turn_output_json
            """,
            (
                turn.turn_id,
                turn.session_id,
                int(turn.turn_index),
                turn.user_input,
                to_json_text(turn.turn_output),
                turn.created_at,
            ),
        )
        conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
            (turn.created_at, turn.session_id),
        )

    def _insert_run_state(self, conn: sqlite3.Connection, snapshot: RunStateSnapshot) -> None:
        conn.execute(
            """
            INSERT INTO run_states (
                snapshot_id, session_id, turn_id, state_json, created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                snapshot.snapshot_id,
                snapshot.session_id,
                snapshot.turn_id,
                to_json_text(snapshot.state),
                snapshot.created_at,
            ),
        )

    def _insert_risk_event(self, conn: sqlite3.Connection, record: RiskEventRecord) -> None:
        conn.execute(
            """
            INSERT INTO risk_events (
                event_id, session_id, turn_id, risk_status,
                rule_ids_json, reasons_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.event_id,
                record.session_id,
                record.turn_id,
                record.risk_status,
                to_json_text(record.rule_ids),
                to_json_text(record.reasons),
                record.created_at,
            ),
        )

    def _insert_evidence(self, conn: sqlite3.Connection, record: RagEvidenceRecord) -> None:
        conn.execute(
            """
            INSERT INTO rag_evidence (
                evidence_id, session_id, turn_id, source_id, chunk_id,
                chunk_hash, index_version, score, retrieval_mode,
                used_in_report_section, is_used, evidence_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.evidence_id,
                record.session_id,
                record.turn_id,
                record.source_id,
                record.chunk_id,
                record.chunk_hash,
                record.index_version,
                float(record.score),
                record.retrieval_mode,
                record.used_in_report_section,
                int(record.is_used),
                to_json_text(record.evidence),
                record.created_at,
            ),
        )

    def _insert_memory(self, conn: sqlite3.Connection, record: MemorySnapshotRecord) -> None:
        conn.execute(
            """
            INSERT INTO memory_snapshots (
                snapshot_id, session_id, turn_id, snapshot_json, created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                record.snapshot_id,
                record.session_id,
                record.turn_id,
                to_json_text(record.snapshot),
                record.created_at,
            ),
        )

    def _insert_trace(self, conn: sqlite3.Connection, record: TraceEventRecord) -> None:
        conn.execute(
            """
            INSERT INTO trace_events (
                trace_event_id, session_id, turn_id, trace_id,
                event_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                record.trace_event_id,
                record.session_id,
                record.turn_id,
                record.trace_id,
                to_json_text(record.event),
                record.created_at,
            ),
        )

    def _insert_audit(self, conn: sqlite3.Connection, record: AuditLogRecord) -> None:
        conn.execute(
            """
            INSERT INTO audit_logs (
                audit_id, session_id, turn_id, event_type, payload_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                record.audit_id,
                record.session_id,
                record.turn_id,
                record.event_type,
                to_json_text(record.payload),
                record.created_at,
            ),
        )

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
        with self.connect() as conn:
            with conn:
                if conn.execute("SELECT 1 FROM sessions WHERE session_id = ?", (turn.session_id,)).fetchone() is None:
                    raise StorageRecordNotFound(f"session not found: {turn.session_id}")
                self._insert_turn(conn, turn)
                self._insert_run_state(conn, run_state)
                for record in risk_events:
                    self._insert_risk_event(conn, record)
                for record in rag_evidence:
                    self._insert_evidence(conn, record)
                if memory_snapshot is not None:
                    self._insert_memory(conn, memory_snapshot)
                if trace_event is not None:
                    self._insert_trace(conn, trace_event)
                for record in audit_logs:
                    self._insert_audit(conn, record)

    def save_final_report_bundle(
        self,
        *,
        report: FinalReportRecord,
        evidence_updates: Iterable[RagEvidenceRecord] = (),
        audit_logs: Iterable[AuditLogRecord] = (),
        trace_event: Optional[TraceEventRecord] = None,
    ) -> None:
        self.initialize()
        with self.connect() as conn:
            with conn:
                if conn.execute("SELECT 1 FROM sessions WHERE session_id = ?", (report.session_id,)).fetchone() is None:
                    raise StorageRecordNotFound(f"session not found: {report.session_id}")
                conn.execute(
                    """
                    INSERT INTO final_reports (
                        report_id, session_id, turn_id, report_json,
                        safety_check_json, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        report.report_id,
                        report.session_id,
                        report.turn_id,
                        to_json_text(report.report),
                        to_json_text(report.safety_check),
                        report.created_at,
                    ),
                )
                for record in evidence_updates:
                    self._insert_evidence(conn, record)
                if trace_event is not None:
                    self._insert_trace(conn, trace_event)
                for record in audit_logs:
                    self._insert_audit(conn, record)

    def save_eval_run(self, record: EvalRunRecord) -> None:
        self.initialize()
        with self.connect() as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO eval_runs (eval_id, status, metrics_json, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        record.eval_id,
                        record.status,
                        to_json_text(record.metrics),
                        record.created_at,
                    ),
                )

    def save_audit_log(self, record: AuditLogRecord) -> None:
        self.initialize()
        with self.connect() as conn:
            with conn:
                self._insert_audit(conn, record)

    def save_trace_event(self, record: TraceEventRecord) -> None:
        self.initialize()
        with self.connect() as conn:
            with conn:
                self._insert_trace(conn, record)

    def fetch_session_bundle(self, session_id: str) -> Optional[Dict[str, Any]]:
        self.initialize()
        with self.connect() as conn:
            session = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if session is None:
                return None
            turns = conn.execute(
                "SELECT * FROM turns WHERE session_id = ? ORDER BY turn_index ASC",
                (session_id,),
            ).fetchall()
            states = conn.execute(
                "SELECT * FROM run_states WHERE session_id = ? ORDER BY created_at ASC",
                (session_id,),
            ).fetchall()
            reports = conn.execute(
                "SELECT * FROM final_reports WHERE session_id = ? ORDER BY created_at ASC",
                (session_id,),
            ).fetchall()
            memories = conn.execute(
                "SELECT * FROM memory_snapshots WHERE session_id = ? ORDER BY created_at ASC",
                (session_id,),
            ).fetchall()
        return {
            "session": self._decode_session(session),
            "turns": [self._decode_turn(row) for row in turns],
            "run_states": [self._decode_run_state(row) for row in states],
            "final_reports": [self._decode_report(row) for row in reports],
            "memory_snapshots": [self._decode_memory(row) for row in memories],
        }

    def fetch_trace_events(self, session_id: str) -> list[Dict[str, Any]]:
        self.initialize()
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM trace_events WHERE session_id = ? ORDER BY created_at ASC",
                (session_id,),
            ).fetchall()
        return [self._decode_trace(row) for row in rows]

    def fetch_audit_logs(self, session_id: str) -> list[Dict[str, Any]]:
        self.initialize()
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_logs WHERE session_id = ? ORDER BY created_at ASC",
                (session_id,),
            ).fetchall()
        return [self._decode_audit(row) for row in rows]

    def fetch_rag_evidence(self, session_id: str, *, used_only: bool = False) -> list[Dict[str, Any]]:
        self.initialize()
        sql = "SELECT * FROM rag_evidence WHERE session_id = ?"
        params: tuple[Any, ...] = (session_id,)
        if used_only:
            sql += " AND is_used = ?"
            params = (session_id, 1)
        sql += " ORDER BY created_at ASC"
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._decode_evidence(row) for row in rows]

    def table_counts(self) -> Dict[str, int]:
        self.initialize()
        with self.connect() as conn:
            return {
                table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                for table in P7_TABLES
            }

    def _decode_session(self, row: sqlite3.Row) -> dict[str, Any]:
        payload = _row_to_dict(row)
        payload["rag_enabled"] = bool(payload["rag_enabled"])
        payload["metadata"] = from_json_text(payload.pop("metadata_json"), {})
        return payload

    def _decode_turn(self, row: sqlite3.Row) -> dict[str, Any]:
        payload = _row_to_dict(row)
        payload["turn_output"] = from_json_text(payload.pop("turn_output_json"), {})
        return payload

    def _decode_run_state(self, row: sqlite3.Row) -> dict[str, Any]:
        payload = _row_to_dict(row)
        payload["state"] = from_json_text(payload.pop("state_json"), {})
        return payload

    def _decode_report(self, row: sqlite3.Row) -> dict[str, Any]:
        payload = _row_to_dict(row)
        payload["report"] = from_json_text(payload.pop("report_json"), {})
        payload["safety_check"] = from_json_text(payload.pop("safety_check_json"), {})
        return payload

    def _decode_evidence(self, row: sqlite3.Row) -> dict[str, Any]:
        payload = _row_to_dict(row)
        payload["is_used"] = bool(payload["is_used"])
        payload["evidence"] = from_json_text(payload.pop("evidence_json"), {})
        return payload

    def _decode_trace(self, row: sqlite3.Row) -> dict[str, Any]:
        payload = _row_to_dict(row)
        payload["event"] = from_json_text(payload.pop("event_json"), {})
        return payload

    def _decode_audit(self, row: sqlite3.Row) -> dict[str, Any]:
        payload = _row_to_dict(row)
        payload["payload"] = from_json_text(payload.pop("payload_json"), {})
        return payload

    def _decode_memory(self, row: sqlite3.Row) -> dict[str, Any]:
        payload = _row_to_dict(row)
        payload["snapshot"] = from_json_text(payload.pop("snapshot_json"), {})
        return payload


def get_default_store(db_path: str | Path | None = None) -> P7SQLiteStore:
    return P7SQLiteStore(db_path=db_path)
