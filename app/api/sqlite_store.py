from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional
from uuid import uuid4

from app.api.errors import ApiError, STATE_CORRUPTED, STATE_NOT_FOUND
from app.api.redaction import dumps_redacted_json, redact_secret_text, redact_secrets
from app.api.runtime_config import DEFAULT_DB_PATH, load_runtime_config


STORE_SCHEMA_VERSION = 1
STORE_SCHEMA_STAGE = "P1.3"
STORE_NAME = "tcm_assistant_sqlite_store"
SESSION_TABLES = ("sessions", "session_states", "turns")
REPORT_TABLES = ("reports",)
STORE_TABLES = ("schema_meta", *SESSION_TABLES, *REPORT_TABLES)

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
        stage TEXT,
        mode TEXT,
        rag_enabled INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS session_states (
        session_id TEXT PRIMARY KEY,
        state_json TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS turns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        turn_index INTEGER NOT NULL,
        user_input TEXT NOT NULL,
        response_json TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
        UNIQUE(session_id, turn_index)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS reports (
        report_id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        state_version INTEGER NOT NULL,
        report_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        safety_flags_json TEXT,
        FOREIGN KEY(session_id) REFERENCES sessions(session_id)
    )
    """,
)


class SchemaVersionError(RuntimeError):
    pass


def get_db_path() -> Path:
    config = load_runtime_config()
    return Path(config.db_path)


def _ensure_path_parent(path: Path) -> None:
    if path.parent and str(path.parent) not in {"", "."}:
        path.parent.mkdir(parents=True, exist_ok=True)


def dumps_json(value: Any) -> str:
    return dumps_redacted_json(value)


def dumps_report_safety_flags(value: Any) -> str:
    def redact_values(item: Any) -> Any:
        if isinstance(item, str):
            return redact_secret_text(item)
        if isinstance(item, list):
            return [redact_values(child) for child in item]
        if isinstance(item, tuple):
            return [redact_values(child) for child in item]
        if isinstance(item, dict):
            return {str(key): redact_values(child) for key, child in item.items()}
        return item

    return json.dumps(redact_values(value), ensure_ascii=False, sort_keys=True)


def loads_json(value: Optional[str]) -> Any:
    if value is None:
        return None
    return json.loads(value)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connect(db_path: Optional[Path] = None) -> Iterator[sqlite3.Connection]:
    path = db_path or get_db_path()
    _ensure_path_parent(path)
    conn = sqlite3.connect(path)
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


def _upsert_schema_meta(conn: sqlite3.Connection, key: str, value: str, now: str) -> None:
    row = conn.execute(
        "SELECT value FROM schema_meta WHERE key = ?",
        (key,),
    ).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO schema_meta (key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, now),
        )
    elif row["value"] != value:
        conn.execute(
            "UPDATE schema_meta SET value = ?, updated_at = ? WHERE key = ?",
            (value, now, key),
        )


def _assert_supported_schema_version(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT value FROM schema_meta WHERE key = 'schema_version'",
    ).fetchone()
    if row is None:
        return
    try:
        version = int(row["value"])
    except (TypeError, ValueError) as exc:
        raise SchemaVersionError(
            f"Unsupported SQLite schema_version value: {row['value']!r}"
        ) from exc
    if version > STORE_SCHEMA_VERSION:
        raise SchemaVersionError(
            "SQLite store schema_version "
            f"{version} is newer than supported version {STORE_SCHEMA_VERSION}"
        )


def initialize_database(db_path: Optional[Path] = None) -> None:
    with connect(db_path) as conn:
        with conn:
            conn.execute(SCHEMA_STATEMENTS[0])
            _assert_supported_schema_version(conn)
            for statement in SCHEMA_STATEMENTS[1:]:
                conn.execute(statement)

            now = _now_iso()
            _upsert_schema_meta(conn, "schema_version", str(STORE_SCHEMA_VERSION), now)
            _upsert_schema_meta(conn, "schema_stage", STORE_SCHEMA_STAGE, now)
            _upsert_schema_meta(conn, "store_name", STORE_NAME, now)


def fetch_schema_meta(db_path: Optional[Path] = None) -> Dict[str, str]:
    initialize_database(db_path)
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT key, value FROM schema_meta ORDER BY key ASC",
        ).fetchall()
        return {str(row["key"]): str(row["value"]) for row in rows}


def insert_session(
    *,
    session_id: str,
    created_at: str,
    updated_at: str,
    stage: str,
    mode: str,
    rag_enabled: bool,
    state: Dict[str, Any],
) -> None:
    initialize_database()
    with connect() as conn:
        with conn:
            conn.execute(
                """
                INSERT INTO sessions (
                    session_id, created_at, updated_at, stage, mode, rag_enabled
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session_id, created_at, updated_at, stage, mode, int(rag_enabled)),
            )
            conn.execute(
                """
                INSERT INTO session_states (session_id, state_json, updated_at)
                VALUES (?, ?, ?)
                """,
                (session_id, dumps_json(state), updated_at),
            )


def fetch_session(session_id: str) -> Optional[Dict[str, Any]]:
    initialize_database()
    with connect() as conn:
        session_row = conn.execute(
            """
            SELECT session_id, created_at, updated_at, stage, mode, rag_enabled
            FROM sessions
            WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()
        if session_row is None:
            return None

        state_row = conn.execute(
            """
            SELECT state_json, updated_at
            FROM session_states
            WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()

        turn_rows = conn.execute(
            """
            SELECT id, session_id, turn_index, user_input, response_json, created_at
            FROM turns
            WHERE session_id = ?
            ORDER BY turn_index ASC
            """,
            (session_id,),
        ).fetchall()

    if state_row is None:
        raise ApiError(
            STATE_NOT_FOUND,
            details={"session_id": session_id},
        )
    state_json = state_row["state_json"]
    try:
        state = json.loads(state_json)
    except json.JSONDecodeError as exc:
        raise ApiError(
            STATE_CORRUPTED,
            details={"session_id": session_id, "reason": "state_json_invalid"},
        ) from exc
    return {
        "session": dict(session_row),
        "state": state,
        "turns": [dict(row) for row in turn_rows],
    }


def append_turn_and_update_state(
    *,
    session_id: str,
    turn_index: int,
    user_input: str,
    response: Dict[str, Any],
    state: Dict[str, Any],
    updated_at: str,
    created_at: str,
    report_snapshot: Optional[Dict[str, Any]] = None,
    report_safety_flags: Optional[Dict[str, Any]] = None,
) -> int:
    initialize_database()
    with connect() as conn:
        with conn:
            session_exists = conn.execute(
                "SELECT 1 FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if session_exists is None:
                raise KeyError(session_id)

            cursor = conn.execute(
                """
                INSERT INTO turns (
                    session_id, turn_index, user_input, response_json, created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    turn_index,
                    redact_secrets(user_input),
                    dumps_json(response),
                    created_at,
                ),
            )
            conn.execute(
                """
                UPDATE session_states
                SET state_json = ?, updated_at = ?
                WHERE session_id = ?
                """,
                (dumps_json(state), updated_at, session_id),
            )
            conn.execute(
                """
                UPDATE sessions
                SET updated_at = ?
                WHERE session_id = ?
                """,
                (updated_at, session_id),
            )
            if report_snapshot is not None:
                conn.execute(
                    """
                    INSERT INTO reports (
                        report_id, session_id, state_version, report_json,
                        created_at, safety_flags_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid4()),
                        session_id,
                        int(state.get("state_version", turn_index)),
                        dumps_json(report_snapshot),
                        created_at,
                        dumps_report_safety_flags(report_safety_flags or {}),
                    ),
                )
            return int(cursor.lastrowid)


def insert_report_snapshot(
    *,
    session_id: str,
    state_version: int,
    report: Dict[str, Any],
    safety_flags: Optional[Dict[str, Any]] = None,
    created_at: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> str:
    initialize_database(db_path)
    report_id = str(uuid4())
    with connect(db_path) as conn:
        with conn:
            session_exists = conn.execute(
                "SELECT 1 FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if session_exists is None:
                raise KeyError(session_id)
            conn.execute(
                """
                INSERT INTO reports (
                    report_id, session_id, state_version, report_json,
                    created_at, safety_flags_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    report_id,
                    session_id,
                    int(state_version),
                    dumps_json(report),
                    created_at or _now_iso(),
                    dumps_report_safety_flags(safety_flags or {}),
                ),
            )
    return report_id


def fetch_reports_for_session(
    session_id: str,
    *,
    db_path: Optional[Path] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    initialize_database(db_path)
    sql = """
        SELECT report_id, session_id, state_version, report_json,
               created_at, safety_flags_json
        FROM reports
        WHERE session_id = ?
        ORDER BY created_at ASC, report_id ASC
    """
    params: tuple[Any, ...] = (session_id,)
    if limit is not None:
        sql += " LIMIT ?"
        params = (session_id, int(limit))

    with connect(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()

    reports: List[Dict[str, Any]] = []
    for row in rows:
        reports.append(
            {
                "report_id": row["report_id"],
                "session_id": row["session_id"],
                "state_version": int(row["state_version"]),
                "report_json": loads_json(row["report_json"]),
                "created_at": row["created_at"],
                "safety_flags_json": loads_json(row["safety_flags_json"]),
            }
        )
    return reports


def fetch_latest_report_for_session(
    session_id: str,
    *,
    db_path: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    initialize_database(db_path)
    with connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT report_id, session_id, state_version, report_json,
                   created_at, safety_flags_json
            FROM reports
            WHERE session_id = ?
            ORDER BY created_at DESC, report_id DESC
            LIMIT 1
            """,
            (session_id,),
        ).fetchone()
    if row is None:
        return None
    return {
        "report_id": row["report_id"],
        "session_id": row["session_id"],
        "state_version": int(row["state_version"]),
        "report_json": loads_json(row["report_json"]),
        "created_at": row["created_at"],
        "safety_flags_json": loads_json(row["safety_flags_json"]),
    }


def clear_all_sessions(db_path: Optional[Path] = None) -> None:
    initialize_database(db_path)
    with connect(db_path) as conn:
        with conn:
            conn.execute("DELETE FROM reports")
            conn.execute("DELETE FROM turns")
            conn.execute("DELETE FROM session_states")
            conn.execute("DELETE FROM sessions")


def fetch_table_counts(db_path: Optional[Path] = None) -> Dict[str, int]:
    initialize_database(db_path)
    with connect(db_path) as conn:
        return {
            table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in SESSION_TABLES
        }


def fetch_store_table_counts(db_path: Optional[Path] = None) -> Dict[str, int]:
    initialize_database(db_path)
    with connect(db_path) as conn:
        return {
            table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in STORE_TABLES
        }
