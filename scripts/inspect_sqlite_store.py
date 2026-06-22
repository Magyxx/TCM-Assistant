from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.api.redaction import redact_secrets
from app.api.runtime_config import load_runtime_config
from app.api.sqlite_store import (
    STORE_TABLES,
    connect,
    fetch_schema_meta,
    initialize_database,
)


def _table_names(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        ORDER BY name ASC
        """
    ).fetchall()
    return [str(row["name"]) for row in rows]


def _table_counts(conn: sqlite3.Connection, table_names: list[str]) -> dict[str, int | None]:
    counts: dict[str, int | None] = {}
    for table in STORE_TABLES:
        if table in table_names:
            counts[table] = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        else:
            counts[table] = None
    return counts


def _sidecar_summary(db_path: Path) -> dict[str, dict[str, Any]]:
    sidecars: dict[str, dict[str, Any]] = {}
    for label, path in {
        "db": db_path,
        "wal": db_path.with_name(f"{db_path.name}-wal"),
        "shm": db_path.with_name(f"{db_path.name}-shm"),
    }.items():
        sidecars[label] = {
            "path": str(redact_secrets(str(path))),
            "exists": path.exists(),
            "bytes": path.stat().st_size if path.exists() else 0,
        }
    return sidecars


def _store_summary(conn: sqlite3.Connection, table_names: list[str]) -> dict[str, Any]:
    if "sessions" not in table_names:
        return {
            "session_count": 0,
            "turn_count": 0,
            "report_count": 0,
            "latest_updated_at": None,
        }
    session_count = int(conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0])
    turn_count = int(conn.execute("SELECT COUNT(*) FROM turns").fetchone()[0]) if "turns" in table_names else 0
    report_count = int(conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]) if "reports" in table_names else 0
    latest_row = conn.execute("SELECT MAX(updated_at) AS latest_updated_at FROM sessions").fetchone()
    return {
        "session_count": session_count,
        "turn_count": turn_count,
        "report_count": report_count,
        "latest_updated_at": latest_row["latest_updated_at"] if latest_row is not None else None,
    }


def inspect_store(db_path: Path, *, initialize: bool = True) -> dict[str, Any]:
    if initialize:
        initialize_database(db_path)

    if not db_path.exists():
        return {
            "db_path": str(redact_secrets(str(db_path))),
            "exists": False,
            "schema_meta": {},
            "summary": {
                "session_count": 0,
                "turn_count": 0,
                "report_count": 0,
                "latest_updated_at": None,
            },
            "tables": {},
            "table_counts": {},
            "sidecars": _sidecar_summary(db_path),
        }

    schema_meta = fetch_schema_meta(db_path) if initialize else {}
    with connect(db_path) as conn:
        table_names = _table_names(conn)
        table_counts = _table_counts(conn, table_names)
        summary = _store_summary(conn, table_names)
        return {
            "db_path": str(redact_secrets(str(db_path))),
            "exists": True,
            "schema_meta": schema_meta,
            "summary": summary,
            "session_count": summary["session_count"],
            "turn_count": summary["turn_count"],
            "report_count": summary["report_count"],
            "latest_updated_at": summary["latest_updated_at"],
            "tables": {
                table: {
                    "exists": table in table_names,
                    "row_count": table_counts[table],
                }
                for table in STORE_TABLES
            },
            "table_counts": table_counts,
            "sqlite_tables": table_names,
            "sidecars": _sidecar_summary(db_path),
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect the local TCM API SQLite store.")
    parser.add_argument(
        "--db",
        help="SQLite database path. Defaults to runtime config DB path.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON.",
    )
    parser.add_argument(
        "--no-init",
        action="store_true",
        help="Inspect without running idempotent schema initialization first.",
    )
    args = parser.parse_args()

    config = load_runtime_config()
    db_path = Path(args.db) if args.db else Path(config.db_path)
    db_path_source = "cli:--db" if args.db else config.db_path_source
    summary = inspect_store(db_path, initialize=not args.no_init)
    summary["db_path_source"] = db_path_source
    if args.json:
        print(json.dumps(redact_secrets(summary), ensure_ascii=False, indent=2, sort_keys=True))
        return

    print(f"db_path: {summary['db_path']}")
    print(f"db_path_source: {summary['db_path_source']}")
    print(f"exists: {summary['exists']}")
    print(f"schema_meta: {json.dumps(summary['schema_meta'], sort_keys=True)}")
    if "summary" in summary:
        print(f"summary: {json.dumps(summary['summary'], sort_keys=True)}")
    print(f"table_counts: {json.dumps(summary['table_counts'], sort_keys=True)}")


if __name__ == "__main__":
    main()
