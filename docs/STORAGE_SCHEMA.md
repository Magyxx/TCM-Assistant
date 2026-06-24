# Storage Schema

P1-F0 local demo storage uses SQLite through `sqlite3`. PostgreSQL remains an optional future profile represented by `DATABASE_URL` documentation only; this stage does not open a PostgreSQL connection.

## Tables

- `sessions`: session id, timestamps, status, metadata JSON.
- `turns`: turn id, session id, redacted or demo input, turn output JSON.
- `run_states`: state snapshots as JSON.
- `final_reports`: deterministic report skeletons as JSON.
- `risk_events`: rule-first risk status and rule ids.
- `rag_evidence`: evidence pack records as JSON.
- `audit_logs`: auditable events as JSON.
- `eval_runs`: smoke/eval metrics as JSON.

## Privacy

The P1-F0 repository is demo-only. It should not store real patient identity data or non-redacted sensitive raw text. JSON fields are serialized with `json.dumps` and parsed with `json.loads`.
