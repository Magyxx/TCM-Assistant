# P7 Storage Schema

## Backend
Default backend is SQLite at `data/tcm_assistant.sqlite3` or `TCM_SQLITE_PATH`. PostgreSQL is schema-ready through `TCM_DB_URL`.

## Tables
- `sessions`: session metadata, mode, RAG flag, status.
- `turns`: redacted user input and turn output.
- `run_states`: RunState snapshots after each turn.
- `final_reports`: FinalReport and safety check records.
- `risk_events`: rule-first risk status, rule ids and reasons.
- `rag_evidence`: retrieved and used evidence with source/chunk/hash/index metadata.
- `audit_logs`: tool/report/turn audit records.
- `eval_runs`: validation and eval summaries.
- `trace_events`: structured P7 trace records.
- `memory_snapshots`: L1/L2/L3/L4 memory snapshots.

## JSON
All JSON is UTF-8 with `ensure_ascii=False`. Sensitive values are redacted before storage. Storage failures raise exceptions and are not silently swallowed.

## RAG Evidence
Retrieved evidence and report-used evidence are distinct. `used_in_report_section` is set only for used evidence. `core_state_mutation_count_by_rag` must remain 0.
