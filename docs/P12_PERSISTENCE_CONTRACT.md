# P12 SQLite Persistence Contract

P12-M3 verifies the existing local persistence loop without adding a new ORM or
requiring PostgreSQL at runtime.

## Covered Stores

| Store | File | Contract |
| --- | --- | --- |
| API SQLite store | `app.api.sqlite_store` | Persists sessions, current state snapshots, turns, and report snapshots. |
| P7 storage store | `app.storage.sqlite_store` | Persists service sessions, turns, run states, final reports, risk events, RAG evidence, audit logs, eval runs, traces, and memory snapshots. |
| Replay session store | `app.session.sqlite_store` | Persists replayable turns and run state used by `ConsultationService`. |

## Requirements

- Tests use temporary SQLite files only.
- Runtime DB files are ignored by `.gitignore`.
- No `.db`, `.sqlite`, or `.sqlite3` files are tracked.
- Session creation is readable after write.
- Turn writes are readable after write.
- State snapshots restore through replay.
- Report snapshots and audit events persist when a report is ready.
- PostgreSQL remains schema-ready only through `app.storage.postgres_store`.

The verifier writes `artifacts/p12/persistence_contract.json`.
