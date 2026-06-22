# P2 Delivery Report

Generated: 2026-06-17

## Goal

P2.5 packages the completed P2 baseline into local delivery documentation and a
single P2 gate command. It keeps the existing P1.1 API contract and P1/P2 safety
boundaries intact.

## P2 Summary

- P2.0 froze the P1 API, SQLite, safety, gate, and secret-scan baseline.
- P2.1 added deterministic case corpus evaluation.
- P2.2 added a non-mutating state validator.
- P2.3 added a non-mutating report validator.
- P2.4 added long-session and multi-session reliability validation.
- P2.5 adds delivery docs, manifest, and P2 gate automation.

## Delivery Docs

- `docs/API_CONTRACT.md`
- `docs/SQLITE_SCHEMA.md`
- `docs/SAFETY_BOUNDARY.md`
- `docs/EVAL_CASES.md`
- `docs/LOCAL_RUNBOOK.md`
- `docs/P2_DELIVERY_REPORT.md`
- `docs/P2_FINAL_REPORT.md`

## P2 Gate

Run:

```bash
python scripts/run_p2_gate.py --output artifacts/p2_gate_result.json
```

The gate runs:

- `python scripts/run_p1_gate.py --output artifacts/p1_gate_result.json`
- `python -m unittest discover -s tests`
- `python scripts/run_case_corpus_eval.py artifacts/eval_cases/ --output artifacts/p2_case_corpus_eval.json`
- `python scripts/run_long_session_demo.py --turns 50 --sessions 3 --output artifacts/p2_4_long_session_reliability.json`
- `python scripts/secret_scan.py --json --output artifacts/secret_scan_result.json`
- `git diff --check`

Use `--skip-long-session` only for fast local iteration. The full P2 delivery
gate should include the long-session demo.

Latest result:

- `artifacts/p2_gate_result.json`: `status=ok`, `passed=6`, `failed=0`
- P2 gate check durations recorded in artifact: P1 gate `272.032s`,
  unittest discovery `196.044s`, case corpus `14.557s`, long-session demo
  `19.779s`, secret scan `0.186s`, `git diff --check` `0.064s`

P2 Final Gate rerun result:

- `artifacts/p2_gate_result.json`: `status=ok`, `passed=6`, `failed=0`
- P2 gate check durations recorded in artifact: P1 gate `303.831s`,
  unittest discovery `219.764s`, case corpus `12.319s`, long-session demo
  `16.302s`, secret scan `0.218s`, `git diff --check` `0.075s`
- The P1 gate wrapper timeout for full unittest discovery was raised from 300
  seconds to 600 seconds after the first final run exposed a timeout-only gate
  failure. The same unittest command passed; no test assertion was relaxed.

## P2 Final Gate

Final report and artifact:

- `docs/P2_FINAL_REPORT.md`
- `artifacts/p2_final_gate.json`

Additional Final Gate commands:

```bash
python scripts/run_api_persistence_demo.py
python scripts/replay_api_case.py artifacts/replay_cases/p1_4_basic_consultation_replay.json --db .runtime/tcm_assistant.sqlite3 --output artifacts/p1_4_api_replay_result.json --json
python scripts/inspect_sqlite_store.py --db .runtime/tcm_assistant.sqlite3 --json
python scripts/audit_session.py --db .runtime/tcm_assistant.sqlite3 --session 091c1c17-667a-4cac-a15e-a7c7ef8a6777 --check-state --json
```

Observed Final Gate result:

- status: `ok`
- P1 gate: `ok`, 13/13 checks
- P2 gate: `ok`, 6/6 checks
- full unittest discovery: `ok`, 191 tests
- replay: `ok`, `turn_count=3`, `report_snapshot_count=3`
- inspect: expected tables present, `reports=3`
- audit with state validation: `passed=true`, `state_version=3`
- secret scan: `ok`, findings `0`
- `git diff --check`: exit code `0`, Windows LF/CRLF warnings only
- recommendation: proceed to `P3.0`

## API Contract

`GET /health` remains the exact P1.1 contract:

```json
{
  "status": "ok",
  "service": "TCM-Assistant",
  "stage": "P1.1",
  "mode": "agentic_workflow",
  "diagnosis_system": false
}
```

P2.5 does not add or remove API endpoints.

## SQLite Schema

The SQLite schema remains the P1/P2 local persistence schema documented in
`docs/SQLITE_SCHEMA.md`: `sessions`, `session_states`, `turns`, `schema_meta`,
and `reports`. No ORM or migration framework is introduced.

## Evaluation Corpus

The case corpus lives in `artifacts/eval_cases/` and is documented in
`docs/EVAL_CASES.md`. It covers deterministic replay, state validation, report
validation, low-information input, red-flag behavior, and secret-injection
redaction.

Latest result:

- `artifacts/p2_case_corpus_eval.json`: `status=ok`, `passed=12`, `failed=0`
- state validation: enabled, passed
- report validation: enabled, validated 10 reports, skipped 2 unavailable
  reports, failed 0

## Validators

The P2.2 state validator and P2.3 report validator are integrated into case
corpus evaluation, session audit, report snapshots, and the P2.4 long-session
demo. Validators are non-mutating and JSON-serializable.

## Long-Session Reliability

P2.4 validates 3 sessions x 50 turns, cache clear, SQLite recovery, independent
session state versions, independent report snapshots, DB size sanity, and
secret scan checks against DB/WAL/SHM bytes.

Latest result:

- `artifacts/p2_4_long_session_reliability.json`: `status=ok`
- sessions: 3
- turns per session: 50
- DB size: 1,265,664 bytes
- DB size sanity: passed
- secret found: false

## Secret Scan

The formal secret scan command is:

```bash
python scripts/secret_scan.py --json --output artifacts/secret_scan_result.json
```

Allowed synthetic fixtures remain limited to test and eval-corpus redaction
coverage.

Latest result:

- `artifacts/secret_scan_result.json`: `status=ok`
- findings: 0
- allowed synthetic findings: 15
- scanned files: 191

## Test Results

- `python -m unittest tests.test_p2_5_delivery_docs`: 7 tests, OK
- `python -m unittest tests.test_p2_5_p2_gate_runner`: 6 tests, OK
- `python -m unittest discover -s tests`: 191 tests, OK
- `python scripts/run_p1_gate.py --output artifacts/p1_gate_result.json`:
  `status=ok`, `passed=13`, `failed=0`
- `git diff --check`: exit code 0; Windows LF/CRLF warnings only

## Known Limits

- Local gates do not require a real LLM key.
- Long-session checks are reliability sanity checks, not performance benchmarks.
- P2.5 does not add MemoryManager, embeddings, tool registry, multi-agent
  workflow, Web UI, users, permissions, or ORM.
- The assistant remains inquiry-information only and must not provide diagnosis,
  prescription, or treatment-plan behavior.

## Boundary Check

No P2.5 task violates the frozen P0/P1/P2.0-P2.4 boundaries. P1.1 `/health`
stays exact, default tests use temporary databases, outputs are redacted, and no
real LLM key is required.

## Recommendation

P2 Final Gate passed. Proceed to P3.0 while preserving the current boundary:
no diagnosis, prescription, treatment-plan output, real-secret defaults, Web UI,
users, permissions, ORM, MemoryManager, embeddings, tool registry, or
multi-agent workflow unless separately scoped and gated.
