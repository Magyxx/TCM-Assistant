from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.session.models import SessionRecord, TurnRecord, utc_now


DEFAULT_SQLITE_PATH = Path("artifacts/p9m2/p9m2_sessions.sqlite3")


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def _dumps(value: Any) -> str:
    return json.dumps(_jsonable(value), ensure_ascii=False, sort_keys=True)


def _loads(text: str | None) -> Any:
    if not text:
        return None
    return json.loads(text)


class SQLiteSessionStore:
    def __init__(self, db_path: str | Path = DEFAULT_SQLITE_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                create table if not exists sessions (
                    session_id text primary key,
                    created_at text not null,
                    updated_at text not null,
                    metadata_json text not null
                );
                create table if not exists turns (
                    session_id text not null,
                    turn_id text not null,
                    role text not null,
                    content text not null,
                    metadata_json text not null,
                    created_at text not null,
                    primary key (session_id, turn_id, role)
                );
                create table if not exists run_states (
                    session_id text primary key,
                    state_json text not null,
                    updated_at text not null
                );
                create table if not exists risk_events (
                    id integer primary key autoincrement,
                    session_id text not null,
                    payload_json text not null,
                    created_at text not null
                );
                create table if not exists rag_evidence (
                    id integer primary key autoincrement,
                    session_id text not null,
                    payload_json text not null,
                    created_at text not null
                );
                create table if not exists graph_events (
                    id integer primary key autoincrement,
                    session_id text not null,
                    payload_json text not null,
                    created_at text not null
                );
                create table if not exists final_reports (
                    session_id text primary key,
                    report_json text not null,
                    created_at text not null
                );
                """
            )

    def create_session(self, session_id: str | None = None) -> SessionRecord:
        session_id = session_id or f"p9m2-{uuid4().hex[:12]}"
        with self._connect() as conn:
            row = conn.execute("select * from sessions where session_id = ?", (session_id,)).fetchone()
            if row:
                return SessionRecord(
                    session_id=row["session_id"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    metadata=_loads(row["metadata_json"]) or {},
                )
            record = SessionRecord(session_id=session_id)
            conn.execute(
                "insert into sessions(session_id, created_at, updated_at, metadata_json) values (?, ?, ?, ?)",
                (record.session_id, record.created_at, record.updated_at, _dumps(record.metadata)),
            )
            return record

    def append_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        turn_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TurnRecord:
        self.create_session(session_id)
        turn_id = turn_id or f"turn-{len(self.list_turns(session_id)) + 1}"
        record = TurnRecord(session_id=session_id, turn_id=turn_id, role=role, content=content, metadata=metadata or {})  # type: ignore[arg-type]
        with self._connect() as conn:
            conn.execute(
                """
                insert or replace into turns(session_id, turn_id, role, content, metadata_json, created_at)
                values (?, ?, ?, ?, ?, ?)
                """,
                (session_id, record.turn_id, record.role, record.content, _dumps(record.metadata), record.created_at),
            )
            conn.execute("update sessions set updated_at = ? where session_id = ?", (utc_now(), session_id))
        return record

    def save_state(self, session_id: str, state: Any) -> None:
        self.create_session(session_id)
        with self._connect() as conn:
            conn.execute(
                "insert or replace into run_states(session_id, state_json, updated_at) values (?, ?, ?)",
                (session_id, _dumps(state), utc_now()),
            )

    def load_state(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("select state_json from run_states where session_id = ?", (session_id,)).fetchone()
        return _loads(row["state_json"]) if row else None

    def list_turns(self, session_id: str) -> list[TurnRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "select * from turns where session_id = ? order by created_at, turn_id, role",
                (session_id,),
            ).fetchall()
        return [
            TurnRecord(
                session_id=row["session_id"],
                turn_id=row["turn_id"],
                role=row["role"],
                content=row["content"],
                metadata=_loads(row["metadata_json"]) or {},
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def save_event(self, session_id: str, event: dict[str, Any]) -> None:
        self.create_session(session_id)
        payload = _jsonable(event)
        event_type = str(payload.get("event_type") or payload.get("node") or "graph_event")
        table = {
            "risk_event": "risk_events",
            "rag_evidence": "rag_evidence",
            "final_report": "final_reports",
        }.get(event_type, "graph_events")
        with self._connect() as conn:
            if table == "final_reports":
                conn.execute(
                    "insert or replace into final_reports(session_id, report_json, created_at) values (?, ?, ?)",
                    (session_id, _dumps(payload), utc_now()),
                )
            else:
                conn.execute(
                    f"insert into {table}(session_id, payload_json, created_at) values (?, ?, ?)",
                    (session_id, _dumps(payload), utc_now()),
                )

    def _table_payloads(self, session_id: str, table: str) -> list[dict[str, Any]]:
        column = "report_json" if table == "final_reports" else "payload_json"
        with self._connect() as conn:
            rows = conn.execute(f"select {column} from {table} where session_id = ?", (session_id,)).fetchall()
        return [_loads(row[column]) for row in rows]

    def export_session(self, session_id: str) -> dict[str, Any]:
        session = self.create_session(session_id)
        return {
            "session": session.model_dump(),
            "turns": [turn.model_dump() for turn in self.list_turns(session_id)],
            "state": self.load_state(session_id),
            "risk_events": self._table_payloads(session_id, "risk_events"),
            "rag_evidence": self._table_payloads(session_id, "rag_evidence"),
            "graph_events": self._table_payloads(session_id, "graph_events"),
            "final_reports": self._table_payloads(session_id, "final_reports"),
            "db_path": str(self.db_path),
        }

    def replay_session(self, session_id: str) -> dict[str, Any]:
        export = self.export_session(session_id)
        export["replayed_state"] = export.get("state")
        export["replay_turn_count"] = len(export.get("turns") or [])
        return export

