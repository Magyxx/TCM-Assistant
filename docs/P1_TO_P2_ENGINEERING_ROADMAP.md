# P1 To P2 Engineering Roadmap

Generated: 2026-06-17

## Current Baseline

Completed:

- P0: LangGraph workflow, risk rules, BM25 RAG baseline, real LLM extraction
  validation, report safety checks.
- P1.1: Minimal FastAPI service around the existing graph.
- P1.2: Local SQLite persistence for sessions, latest state, and turns.
- P1.3: SQLite schema metadata, idempotent initialization, redaction utility,
  inspect script, and persistence hardening tests.
- P1.4: API stability, error response contract, input-boundary tests, replay
  harness, and API contract snapshot.

The `/health` endpoint remains a P1.1 contract:

```json
{
  "status": "ok",
  "service": "TCM-Assistant",
  "stage": "P1.1",
  "mode": "agentic_workflow",
  "diagnosis_system": false
}
```

## Non-Negotiable Boundaries

Until explicitly approved, P1 to P2 work must not introduce:

- diagnosis, prescription, or treatment-plan output
- MemoryManager
- Embedding or vector-store expansion
- Tool Registry
- multi-agent workflow
- Web UI
- user or permission system
- ORM or framework migration

P2.0 is an engineering landing target, not a license to expand medical scope.

## Milestone Plan

### P1.5 Report Snapshot, Auditability, Traceability

Goal: make the path from consultation turns to `RunState` and final report
traceable without changing existing success response contracts.

Expected deliverables:

- report snapshot persistence
- report/state version metadata
- session audit script
- report safety audit artifact
- tests proving old sessions and reports remain readable

Primary evidence:

- P1.1-P1.4 tests remain green
- replay harness passes
- report audit command passes
- inspect/audit scripts avoid secrets and raw turn dumps by default
- `git diff --check` passes

### P1.6 Local Gate Automation And Secret Scan

Goal: make P1 acceptance repeatable through one local gate command.

Expected deliverables:

- `scripts/run_p1_gate.py`
- `scripts/secret_scan.py`
- `artifacts/p1_gate_result.json`
- `artifacts/secret_scan_result.json`
- README gate command documentation

Primary evidence:

- P1 gate runner covers unittest discovery, replay, persistence demo, inspect,
  audit, secret scan, and `git diff --check`
- secret scan fails on real high-entropy secrets
- test synthetic secrets remain whitelisted

### P1 Final Gate

Goal: summarize P1 and decide whether the system may enter P2.0 baseline.

Expected deliverables:

- `docs/P1_FINAL_GATE_REPORT.md`
- `artifacts/p1_final_gate.json`
- full P1 gate run
- documented known limits and recommendation

Primary evidence:

- all P1.1-P1.6 gates pass
- no P1 contract drift
- no boundary violations

### P2.0 Engineering Landing

Goal: declare the current assistant service an engineering-complete baseline for
local/API use.

P2.0 requires:

- all P1.1-P1.6 gates plus P1 Final Gate passing
- no unverified expansion of medical behavior
- no secret leakage in tracked files, responses, runtime DB, or logs produced by
  acceptance scripts
- current API contract documented and gated
- persistence behavior documented and gated
- operational commands documented and reproducible

P2.0 does not automatically include:

- Web UI
- auth/users/permissions
- production deployment
- vector-store or embedding expansion
- multi-agent orchestration

Those require separate scope decisions after P2.0.

## Gate Rule

Every milestone must add:

- a report in `docs/`
- a machine-readable artifact in `artifacts/`
- focused tests or an executable validation script
- a short boundary statement

Every milestone must preserve:

- P1.1 `/health` contract
- P1.2 session/state/turn recovery behavior
- P1.3 SQLite schema metadata behavior
- P1.4 API stability, replay, and contract snapshot behavior
