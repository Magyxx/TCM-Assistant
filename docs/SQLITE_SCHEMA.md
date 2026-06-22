# SQLite Schema

Generated: 2026-06-17

This document freezes the local SQLite schema for the P2.0 baseline.

## Database Path

Default path:

```text
.runtime/tcm_assistant.sqlite3
```

Override:

```bash
export TCM_API_DB_PATH=/path/to/tcm_assistant.sqlite3
```

Runtime SQLite files are local-only and ignored by Git.

P3.1 centralizes DB path config in `app/api/runtime_config.py`. The schema is
unchanged. DB path priority is:

1. CLI `--db` for scripts that expose it.
2. `TCM_API_DB_PATH`.
3. `.runtime/tcm_assistant.sqlite3`.

Runtime config summaries record `db_path_source` as `default`,
`env:TCM_API_DB_PATH`, or `cli:--db`.

## Tables

### sessions

- `session_id TEXT PRIMARY KEY`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`
- `stage TEXT`
- `mode TEXT`
- `rag_enabled INTEGER`

### session_states

- `session_id TEXT PRIMARY KEY`
- `state_json TEXT NOT NULL`
- `updated_at TEXT NOT NULL`
- foreign key to `sessions(session_id)`

`state_json` stores the current `RunState` payload plus additive
`state_version`.

### turns

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `session_id TEXT NOT NULL`
- `turn_index INTEGER NOT NULL`
- `user_input TEXT NOT NULL`
- `response_json TEXT`
- `created_at TEXT NOT NULL`
- foreign key to `sessions(session_id)`
- unique `(session_id, turn_index)`

Secret-like user input is redacted before persistence.

### schema_meta

- `key TEXT PRIMARY KEY`
- `value TEXT NOT NULL`
- `updated_at TEXT NOT NULL`

Current rows:

- `schema_version=1`
- `schema_stage=P1.3`
- `store_name=tcm_assistant_sqlite_store`

`schema_stage` remains `P1.3` for compatibility with the P1.4 gate.

### reports

- `report_id TEXT PRIMARY KEY`
- `session_id TEXT NOT NULL`
- `state_version INTEGER NOT NULL`
- `report_json TEXT NOT NULL`
- `created_at TEXT NOT NULL`
- `safety_flags_json TEXT`
- foreign key to `sessions(session_id)`

Each successful turn that produces `final_report` stores one redacted snapshot
and its safety audit result.

## Migration Rules

- Initialization is idempotent.
- Empty databases create all current tables.
- Legacy P1.2/P1.3 databases gain missing P1 tables without data loss.
- Future `schema_version` values are rejected explicitly.
- No ORM, SQLAlchemy, Alembic, or external migration framework is used.

## Inspection And Audit

Inspect:

```bash
python scripts/inspect_sqlite_store.py --db .runtime/tcm_assistant.sqlite3 --json
```

Audit one session:

```bash
python scripts/audit_session.py --db .runtime/tcm_assistant.sqlite3 --session <session_id> --json
```

Tests must use temporary databases. Demos may use `.runtime/`.

## Cleanup

To reset local runtime state, delete `.runtime/` manually or run API test helpers
that clear sessions. Do not commit SQLite DB, WAL, or SHM files.

## P2.5 Delivery Gate

The current P3.1-era gate uses temporary databases for tests and demo-specific
SQLite files for generated artifacts. It validates runtime config, long-session
state, report snapshots, cache clear recovery, DB/WAL/SHM secret checks, and
inspect/audit scripts keep working without introducing ORM or migration tooling.
