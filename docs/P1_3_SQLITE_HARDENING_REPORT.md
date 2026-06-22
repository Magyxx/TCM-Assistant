# P1.3 SQLite Persistence Hardening Report

Generated: 2026-06-17

## 1. What P1.3 Implemented

P1.3 hardens the P1.2 local SQLite persistence layer without changing the
P1.1 FastAPI endpoint contract or the P1.2 session/state/turn recovery model.

Added:

- `schema_meta` table for store schema metadata.
- Idempotent SQLite initialization for empty and existing P1.2 databases.
- Future schema-version rejection via `SchemaVersionError`.
- Shared API redaction utility in `app/api/redaction.py`.
- SQLite inspect script in `scripts/inspect_sqlite_store.py`.
- Exception-path tests for missing sessions, duplicate turns, rollback behavior,
  schema metadata, and inspect output.

## 2. What P1.3 Did Not Implement

P1.3 does not add product capability beyond SQLite store hardening.

Not introduced:

- ORM, SQLAlchemy, or Alembic
- MemoryManager
- Embedding or vector storage
- Tool Registry
- multi-agent workflow
- Web UI
- user or permission system
- diagnosis, prescription, or treatment-plan output

The existing P0/P1 safety boundary remains unchanged.

## 3. SQLite Schema And Migration Summary

P1.3 keeps the three P1.2 application tables unchanged:

- `sessions`
- `session_states`
- `turns`

P1.3 adds one metadata table:

```sql
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

Current metadata rows:

- `schema_version = 1`
- `schema_stage = P1.3`
- `store_name = tcm_assistant_sqlite_store`

Initialization is safe to run repeatedly. Existing P1.2 rows are preserved, and
the existing `sessions.stage` value remains `P1.2` for P1.2 compatibility.

If a database declares a `schema_version` newer than this code supports,
initialization raises `SchemaVersionError` instead of silently operating on an
unknown schema.

## 4. Redaction Summary

P1.3 moves redaction into `app/api/redaction.py` and reuses it from:

- API response shaping
- session runtime turn caching
- SQLite JSON serialization
- SQLite inspect output

The utility recursively redacts string values, list/tuple items, and
secret-like dictionary keys. It preserves non-secret fields such as session
metadata, turn counts, risk metadata, and public table counts.

## 5. Inspect Script

Command:

```powershell
python scripts/inspect_sqlite_store.py --db .runtime/tcm_assistant.sqlite3 --json
```

The script runs idempotent schema initialization by default, then emits only
store metadata, table existence, row counts, SQLite table names, and DB/WAL/SHM
sidecar file summaries. It does not print session contents, turn text, state
JSON, or response JSON.

## 6. API Compatibility

The P1.1 `/health` contract is unchanged:

```json
{
  "status": "ok",
  "service": "TCM-Assistant",
  "stage": "P1.1",
  "mode": "agentic_workflow",
  "diagnosis_system": false
}
```

The P1.2 persistence behavior is unchanged:

- create session persists session metadata and initial state
- submit turn inserts a turn and updates state in one transaction
- state/report can be recovered after clearing runtime cache
- secret-like values are redacted before persistence

## 7. Test Results

Validated commands in this environment:

```powershell
python -m unittest tests.test_p1_3_redaction
python -m unittest tests.test_p1_3_sqlite_schema_meta
python -m unittest tests.test_p1_3_sqlite_store_hardening
python -m unittest tests.test_p1_2_sqlite_persistence
python -m unittest tests.test_p1_1_api_minimal
python -m unittest discover -s tests
python scripts/run_api_persistence_demo.py
python scripts/inspect_sqlite_store.py --db .runtime/tcm_assistant.sqlite3 --json
git diff --check
```

Final results:

- P1.3 redaction tests: 4 tests OK
- P1.3 schema/meta tests: 4 tests OK
- P1.3 store hardening tests: 4 tests OK
- P1.2 SQLite persistence tests: 8 tests OK
- P1.1 API minimal tests: 9 tests OK
- Full unittest discovery: 76 tests OK
- Persistence demo: restored `turn_count_after_restart=1` and
  `final_report_ready_after_restart=true`
- Inspect script: returned `schema_stage=P1.3`, `schema_version=1`,
  `schema_meta=3`, `sessions=1`, `session_states=1`, `turns=1`
- Secret scan: broad scan found environment variable names, historical
  documentation notes, and synthetic test secrets only; high-entropy `sk-...`
  scan found no hits outside tests
- `git diff --check`: OK, no whitespace errors; Windows LF/CRLF warnings only

## 8. Safety Boundary

P1.3 remains a persistence hardening step only. It does not change graph
behavior, output domain semantics, or safety posture.

## 9. Next Step Recommendation

If the full unittest discovery, persistence demo, inspect script, secret scan,
and `git diff --check` remain green, P1.3 can be considered complete and the
project can plan P1.4 under the same explicit boundary controls.
