from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.storage.models import utc_now
from app.storage.sqlite import connect, init_db


def _json(data: Any) -> str:
    return json.dumps(data if data is not None else {}, ensure_ascii=False, sort_keys=True)


def _loads(text: str) -> Any:
    return json.loads(text) if text else {}


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


class SQLiteRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        init_db(self.db_path)

    def create_session(self, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        now = utc_now()
        session = {
            "session_id": _id("session"),
            "created_at": now,
            "updated_at": now,
            "status": "active",
            "metadata": metadata or {},
        }
        with connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO sessions (session_id, created_at, updated_at, status, metadata_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session["session_id"], now, now, session["status"], _json(session["metadata"])),
            )
        return session

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with connect(self.db_path) as conn:
            row = conn.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
        if row is None:
            return None
        return {
            "session_id": row["session_id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "status": row["status"],
            "metadata": _loads(row["metadata_json"]),
        }

    def save_turn(
        self,
        session_id: str,
        user_input: str,
        turn_output: dict[str, Any],
        *,
        turn_id: str | None = None,
    ) -> dict[str, Any]:
        now = utc_now()
        turn = {
            "turn_id": turn_id or _id("turn"),
            "session_id": session_id,
            "user_input": user_input,
            "turn_output": turn_output,
            "created_at": now,
        }
        with connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO turns (turn_id, session_id, user_input, turn_output_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (turn["turn_id"], session_id, user_input, _json(turn_output), now),
            )
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                (now, session_id),
            )
        return turn

    def save_run_state(self, session_id: str, turn_id: str, state: dict[str, Any]) -> dict[str, Any]:
        record = {
            "state_id": _id("state"),
            "session_id": session_id,
            "turn_id": turn_id,
            "state": state,
            "created_at": utc_now(),
        }
        with connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO run_states (state_id, session_id, turn_id, state_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (record["state_id"], session_id, turn_id, _json(state), record["created_at"]),
            )
        return record

    def save_audit_event(
        self,
        session_id: str | None,
        event_type: str,
        payload: dict[str, Any],
        *,
        turn_id: str | None = None,
    ) -> dict[str, Any]:
        record = {
            "audit_id": _id("audit"),
            "session_id": session_id,
            "turn_id": turn_id,
            "event_type": event_type,
            "payload": payload,
            "created_at": utc_now(),
        }
        with connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO audit_logs (audit_id, session_id, turn_id, event_type, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record["audit_id"],
                    session_id,
                    turn_id,
                    event_type,
                    _json(payload),
                    record["created_at"],
                ),
            )
        return record

    def list_audit_events(self, session_id: str) -> list[dict[str, Any]]:
        with connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM audit_logs WHERE session_id = ? ORDER BY created_at",
                (session_id,),
            ).fetchall()
        return [
            {
                "audit_id": row["audit_id"],
                "session_id": row["session_id"],
                "turn_id": row["turn_id"],
                "event_type": row["event_type"],
                "payload": _loads(row["payload_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def save_report_skeleton(
        self,
        session_id: str,
        report: dict[str, Any],
        *,
        turn_id: str = "",
    ) -> dict[str, Any]:
        record = {
            "report_id": _id("report"),
            "session_id": session_id,
            "turn_id": turn_id,
            "report": report,
            "created_at": utc_now(),
        }
        with connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO final_reports (report_id, session_id, turn_id, report_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (record["report_id"], session_id, turn_id, _json(report), record["created_at"]),
            )
        return record

    def save_eval_run(self, status: str, metrics: dict[str, Any]) -> dict[str, Any]:
        record = {
            "eval_id": _id("eval"),
            "status": status,
            "metrics": metrics,
            "created_at": utc_now(),
        }
        with connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO eval_runs (eval_id, status, metrics_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (record["eval_id"], status, _json(metrics), record["created_at"]),
            )
        return record
