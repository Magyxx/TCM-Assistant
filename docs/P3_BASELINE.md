# P3.0 Baseline

Generated: 2026-06-17

## Goal

P3.0 freezes the passed P2 Final Gate and establishes the P3 baseline,
roadmap, validation entrypoints, and boundaries. P3.0 does not implement P3.1+
capabilities and does not change P1/P2 API, SQLite, safety, or gate contracts.

The system remains an inquiry-information assistant. It does not provide
diagnosis, prescription, or treatment-plan output.

## Based On P2 Final Gate

Primary inputs:

- `docs/P2_FINAL_REPORT.md`
- `artifacts/p2_final_gate.json`
- `artifacts/p2_gate_result.json`
- `artifacts/p2_case_corpus_eval.json`
- `artifacts/p2_4_long_session_reliability.json`
- `artifacts/secret_scan_result.json`

Frozen P2 Final Gate summary:

- P2 Final Gate: `ok`
- P2 gate: `ok`, 6/6 checks
- P1 gate: `ok`, 13/13 checks
- unittest discovery: `ok`, 191 tests
- case corpus eval: `ok`, 12/12 cases
- state validator: passed through case corpus, long session, audit, and tests
- report validator: passed through case corpus, long session, audit, and tests
- long-session reliability: `ok`, 3 sessions x 50 turns
- secret scan: `ok`, 0 findings
- `git diff --check`: exit code `0`, Windows LF/CRLF warnings only
- recommendation from P2 Final Gate: proceed to P3.0

## Current System Capability Baseline

### API Contract

- Minimal FastAPI service is available.
- Endpoint paths are unchanged:
  - `GET /health`
  - `POST /sessions`
  - `POST /sessions/{session_id}/turn`
  - `GET /sessions/{session_id}/state`
  - `GET /sessions/{session_id}/report`
- Success response contract remains compatible with P1/P2.
- Error response shape remains `{ "error": { "code", "message", "details" } }`.
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

### SQLite Persistence

- Local SQLite session, state, turn, and report persistence is available.
- Runtime DB path defaults to `.runtime/tcm_assistant.sqlite3`.
- `TCM_API_DB_PATH` override is available.
- Runtime DB/WAL/SHM files remain local-only and ignored by Git.

### Schema Migration

- `schema_version=1`
- `schema_stage=P1.3`
- `store_name=tcm_assistant_sqlite_store`
- Empty databases initialize idempotently.
- Legacy P1.2/P1.3 databases gain missing metadata and tables without data loss.
- Future schema versions are rejected explicitly.
- No ORM or external migration framework is introduced.

### Report Snapshot And Audit

- Report snapshots persist in the `reports` table.
- Snapshots include `state_version`, redacted `report_json`, and redacted
  `safety_flags_json`.
- `scripts/audit_session.py` remains the local audit entrypoint.
- `report_audit.py` remains available for safety-boundary checks.

### Validators

- `app/api/state_validator.py` validates session state and consistency.
- `app/api/report_validator.py` validates report structure and safety boundary.
- Validators are deterministic, non-mutating, JSON-serializable checks.
- Validators do not require a real LLM key.

### Evaluation And Reliability

- Case corpus eval is available through
  `python scripts/run_case_corpus_eval.py artifacts/eval_cases/ --output artifacts/p2_case_corpus_eval.json`.
- Long-session reliability is available through
  `python scripts/run_long_session_demo.py --turns 50 --sessions 3 --output artifacts/p2_4_long_session_reliability.json`.
- P1 and P2 gate runners are available.
- Formal secret scan is available through
  `python scripts/secret_scan.py --json --output artifacts/secret_scan_result.json`.

## P3 Allowed Scope

P3 may add production-readiness and delivery hardening in separately gated
steps:

- runtime config hardening
- environment variable validation
- startup preflight checks
- local/test/demo operational modes
- redacted structured logging
- request/session/report audit event summaries
- release manifest and reproducibility documentation
- artifact package definition
- API compatibility policy
- release-candidate gate composition

P3 work should remain incremental and backward compatible.

## P3 Forbidden Scope

P3.0 and later P3 work must not introduce these by default unless a later task
explicitly scopes and gates them:

- diagnosis output
- prescription output
- treatment-plan output
- ORM
- MemoryManager
- new embedding capability
- Tool Registry
- multi-agent system
- Web UI
- user or permission system
- default dependency on a real LLM key
- committed real secrets
- breaking P1.1 endpoint paths or success response contracts
- breaking `/health` exact P1.1 contract
- breaking P1.2-P1.6 or P2.0-P2.5 behavior

## Suggested P3 Roadmap

The proposed P3 roadmap is documented in `docs/P3_ROADMAP.md`:

- P3.1 Runtime Config & Operational Modes
- P3.2 Observability & Redacted Logging
- P3.3 Release Packaging & Reproducibility
- P3.4 API Versioning & Compatibility
- P3.5 Release Candidate Gate

## P3 Gate Inheritance

P3 gate planning is documented in `docs/P3_GATE_PLAN.md`.

P3.0 does not add `scripts/run_p3_gate.py`. Until P3.1+ adds actual P3 checks,
the recommended acceptance entrypoint remains:

```bash
python scripts/run_p2_gate.py --output artifacts/p2_gate_result.json
```

Supporting commands:

```bash
python scripts/run_p1_gate.py --output artifacts/p1_gate_result.json
python -m unittest discover -s tests
python scripts/secret_scan.py --json --output artifacts/secret_scan_result.json
git diff --check
```

Recommended supporting checks:

```bash
python scripts/run_case_corpus_eval.py artifacts/eval_cases/ --output artifacts/p2_case_corpus_eval.json
python scripts/run_long_session_demo.py --turns 50 --sessions 3 --output artifacts/p2_4_long_session_reliability.json
```

When pytest is unavailable, local validation uses `unittest`, as in the P1/P2
gates.

## P3.1 Follow-On

P3.1 implements the first P3 check without changing the P3.0 baseline contract:

- `app/api/runtime_config.py`
- `scripts/check_runtime_config.py`
- `docs/RUNTIME_CONFIG.md`
- `docs/P3_1_RUNTIME_CONFIG_REPORT.md`
- `artifacts/p3_1_runtime_config.json`

The current `scripts/run_p2_gate.py` entrypoint now includes
`runtime_config_check` before the inherited P1/P2 checks. This preserves the
P1/P2 API contract, exact `/health` response, SQLite schema, and default
no-real-LLM-key validation behavior.

## P3.2 Follow-On

P3.2 adds minimal structured observability and redacted logging without changing
the P3.0 baseline contract:

- `app/api/observability.py`
- `scripts/check_observability.py`
- `docs/OBSERVABILITY.md`
- `docs/P3_2_OBSERVABILITY_REPORT.md`
- `artifacts/p3_2_observability.json`

The current `scripts/run_p2_gate.py` entrypoint now also includes
`observability_check`. P3.2 adds only an additive `X-Request-ID` header and does
not change API response bodies, `/health`, SQLite schema, or default
no-real-LLM-key validation behavior.

## P3.0 Validation Result

P3.0 baseline validation was run after adding the P3 baseline documents and
artifact.

Required commands:

- `python scripts/run_p2_gate.py --output artifacts/p2_gate_result.json`: `ok`, 6/6 checks
- `python scripts/run_p1_gate.py --output artifacts/p1_gate_result.json`: `ok`, 13/13 checks
- `python -m unittest discover -s tests`: `ok`, 191 tests
- `python scripts/secret_scan.py --json --output artifacts/secret_scan_result.json`: `ok`, findings `0`, scanned files `195`
- `git diff --check`: exit code `0`, Windows LF/CRLF warnings only

Recommended supporting commands:

- `python scripts/run_case_corpus_eval.py artifacts/eval_cases/ --output artifacts/p2_case_corpus_eval.json`: `ok`, 12/12 cases
- `python scripts/run_long_session_demo.py --turns 50 --sessions 3 --output artifacts/p2_4_long_session_reliability.json`: `ok`, 3 sessions x 50 turns

No P1/P2 contract change was introduced. No P3.1+ capability was implemented.

## P3.0 Contract Statement

P3.0 does not change:

- P1/P2 API endpoint paths
- P1/P2 API success response contracts
- `/health` exact P1.1 response
- SQLite schema
- safety boundary
- P1/P2 gate semantics
- default no-real-LLM-key validation behavior

## P3.0 Result

P3.0 baseline is established and passed:

- `artifacts/p3_baseline.json` reports `status=ok`
- P2 Final Gate remains `ok`
- P2 gate remains `ok`
- P1 gate remains `ok`
- unittest discovery remains green
- secret scan reports 0 findings
- `git diff --check` exits 0
- no P3.1+ capability is implemented in P3.0

## Recommendation

P3.0 recommends proceeding to P3.1 Runtime Config & Operational Modes while
preserving P1/P2 contracts and the existing safety boundary.
