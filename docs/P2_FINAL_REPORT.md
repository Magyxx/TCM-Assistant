# P2 Final Gate Report

Generated: 2026-06-17

## Goal

P2 Final Gate verifies that the TCM-Assistant backend has a stable, evaluable,
replayable, auditable, verifiable, and locally deliverable P2 foundation. It
does not add product capability. The system remains an inquiry-information
assistant and does not provide diagnosis, prescription, or treatment-plan
output.

## P2.0-P2.5 Summary

- P2.0 froze the P1 API, SQLite, safety, gate, and secret-scan baseline.
- P2.1 added deterministic case corpus evaluation.
- P2.2 added a non-mutating state validator and session consistency checks.
- P2.3 added a non-mutating report validator and report safety metrics.
- P2.4 added long-session and multi-session reliability validation.
- P2.5 added delivery documentation, delivery manifest, and P2 gate automation.

## Gate Coverage

The command below passed and produced `artifacts/p2_gate_result.json`:

```bash
python scripts/run_p2_gate.py --output artifacts/p2_gate_result.json
```

The P2 gate covers:

- P1 gate
- unittest discovery
- case corpus eval
- long-session demo
- secret scan
- `git diff --check`

P2 Final Gate also ran the supporting checks below and recorded them in
`artifacts/p2_final_gate.json`:

```bash
python scripts/run_api_persistence_demo.py
python scripts/replay_api_case.py artifacts/replay_cases/p1_4_basic_consultation_replay.json --db .runtime/tcm_assistant.sqlite3 --output artifacts/p1_4_api_replay_result.json --json
python scripts/inspect_sqlite_store.py --db .runtime/tcm_assistant.sqlite3 --json
python scripts/audit_session.py --db .runtime/tcm_assistant.sqlite3 --session 091c1c17-667a-4cac-a15e-a7c7ef8a6777 --check-state --json
```

State validator coverage comes from case corpus eval, long-session demo,
`audit_session --check-state`, and unit tests. Report validator coverage comes
from case corpus eval, long-session demo, report snapshots, audit output, and
unit tests.

## API Contract

P2 Final Gate confirms API compatibility:

- endpoint paths are unchanged
- required success response fields are unchanged
- stable error response shape remains `{ "error": { "code", "message", "details" } }`
- contract snapshot matches the current implementation
- `GET /health` remains the exact P1.1 contract:

```json
{
  "status": "ok",
  "service": "TCM-Assistant",
  "stage": "P1.1",
  "mode": "agentic_workflow",
  "diagnosis_system": false
}
```

## SQLite Schema

Current local SQLite tables:

- `schema_meta`
- `sessions`
- `session_states`
- `turns`
- `reports`

Schema metadata:

- `schema_version=1`
- `schema_stage=P1.3`
- `store_name=tcm_assistant_sqlite_store`

Migration status:

- empty databases initialize idempotently
- legacy P1.2/P1.3 databases gain missing metadata and tables without data loss
- future schema versions are rejected explicitly
- no ORM or external migration framework is introduced

Final inspect result:

- `sessions=1`
- `session_states=1`
- `turns=3`
- `reports=3`
- `schema_meta=3`

## Evaluation

Case corpus eval:

- command: `python scripts/run_case_corpus_eval.py artifacts/eval_cases/ --output artifacts/p2_case_corpus_eval.json`
- status: `ok`
- cases: `12`
- passed: `12`
- failed: `0`
- state validation: enabled and passed
- report validation: enabled, `10` reports validated, `2` skipped unavailable reports, `0` failed
- secret injection outputs and SQLite checks did not expose the synthetic secret
- red-flag and low-information cases remained inside the existing boundary

## Validators

State validator:

- `app/api/state_validator.py` exists and is covered by tests
- case corpus state validation passed for `12/12` cases
- `audit_session --check-state` passed for replay session `091c1c17-667a-4cac-a15e-a7c7ef8a6777`
- long-session state validation passed
- validator does not require a real LLM key

Report validator:

- `app/api/report_validator.py` exists and is covered by tests
- case corpus report validation passed: `10` validated, `0` failed
- long-session report validation passed
- `report_audit.py` remains usable through persisted report snapshots
- validator does not require a real LLM key

## Reliability

Long-session reliability:

- command: `python scripts/run_long_session_demo.py --turns 50 --sessions 3 --output artifacts/p2_4_long_session_reliability.json`
- status: `ok`
- sessions: `3`
- turns per session: `50`
- state recovery after cache clear: passed
- session isolation: passed
- state version monotonicity: passed
- report snapshots: passed
- DB size: `1,265,664` bytes
- DB/WAL/SHM secret marker count: `0`

Persistence/replay/inspect/audit:

- persistence demo: `turn_count_after_restart=1`, final report ready after restart
- replay: `status=ok`, `turn_count=3`, `report_snapshot_count=3`
- inspect: all expected tables present, `reports=3`
- audit with state validation: `passed=true`, `current_state_version=3`, `secret_found=false`

## Gate Results

P1 gate:

- command: `python scripts/run_p1_gate.py --output artifacts/p1_gate_result.json`
- status: `ok`
- total checks: `13`
- passed: `13`
- failed: `0`

P2 gate:

- command: `python scripts/run_p2_gate.py --output artifacts/p2_gate_result.json`
- status: `ok`
- total checks: `6`
- passed: `6`
- failed: `0`
- recommendation: `P2 Final Gate`

Unittest discovery:

- command: `python -m unittest discover -s tests`
- status: `ok`
- tests: `191`

Secret scan:

- command: `python scripts/secret_scan.py --json --output artifacts/secret_scan_result.json`
- status: `ok`
- findings: `0`
- allowed synthetic findings: `15`
- scanned files: `191`

`git diff --check`:

- status: `ok`
- exit code: `0`
- Windows LF/CRLF warnings only

## Gate Adjustment

During Final Gate, the first full P2 gate run exposed a P1 gate wrapper timeout:
the P1 gate's full unittest discovery had a 300-second timeout, while the same
test command passed inside the P2 gate when allowed 600 seconds. The P1 gate
runner timeout was raised to 600 seconds. No test assertion or API behavior was
relaxed.

## Known Limits

- Local gates do not require a real LLM key by default.
- SQLite persistence remains local runtime persistence, not a production
  multi-user data layer.
- Validators are deterministic consistency and safety checks, not medical
  validators.
- Long-session validation is a reliability sanity check, not a performance
  benchmark.
- Existing RAG remains inside the prior constrained report-enhancement scope.

## Boundary Statement

P2 Final Gate did not introduce:

- MemoryManager
- new embedding capability
- tool registry
- multi-agent workflow
- Web UI
- user or permission system
- ORM
- diagnosis output
- prescription output
- treatment-plan output
- real secret values

The P1.1 endpoint paths and success response contracts remain unchanged. The
`/health` response remains the exact P1.1 contract.

## Recommendation

P2 Final Gate passed. Recommend proceeding to P3.0, with the same explicit
boundary: P3.0 work should not add diagnosis, prescription, treatment-plan
output, real-secret defaults, or P3.1+ capabilities unless separately scoped and
gated.
