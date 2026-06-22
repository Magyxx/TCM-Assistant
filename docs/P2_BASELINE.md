# P2.0 Baseline

Generated: 2026-06-17

## 1. Goal

P2.0 freezes the P1 baseline and defines the starting point for future P2 work.
It does not implement P2.1/P2.2/P2.3/P2.4/P2.5 capabilities.

## 2. Based On

- P1 Final Gate: passed
- P1 gate runner: passed, 13/13 checks
- API contract snapshot: `artifacts/p1_api_contract_snapshot.json`
- SQLite schema: `docs/SQLITE_SCHEMA.md`
- safety boundary: `docs/SAFETY_BOUNDARY.md`
- secret scan: passed, findings `0`

## 3. Current Capabilities

- stable minimal FastAPI wrapper
- local SQLite session/state/turn persistence
- schema metadata and idempotent initialization
- restart recovery from SQLite
- stable API error contract
- replay harness
- report snapshots
- report auditability
- session audit script
- formal secret scan
- local one-command P1 gate

## 4. P2 May Do Later

Future P2 phases may separately consider:

- P2.1 case corpus evaluation
- P2.2 state validator
- P2.3 report validator
- P2.4 long-session reliability
- P2.5 delivery documentation

Those are not part of P2.0.

## 4.1 P2.1 Addendum

P2.1 now adds the first P2 evaluation layer:

- case corpus directory: `artifacts/eval_cases/`
- eval runner: `scripts/run_case_corpus_eval.py`
- unit tests: `tests/test_p2_1_case_corpus_eval.py`
- report: `docs/P2_1_CASE_CORPUS_EVAL_REPORT.md`
- artifact: `artifacts/p2_case_corpus_eval.json`

This addendum does not change the P2.0 API, SQLite, safety, or gate baseline.
It remains a replay/evaluation harness only.

## 4.2 P2.2 Addendum

P2.2 adds state validation and session consistency checks:

- validator module: `app/api/state_validator.py`
- audit integration: `scripts/audit_session.py --check-state`
- case corpus integration: `scripts/run_case_corpus_eval.py`
- unit tests: `tests/test_p2_2_state_validator.py`
- report: `docs/P2_2_STATE_VALIDATOR_REPORT.md`
- artifact: `artifacts/p2_2_state_validator.json`

This addendum validates the existing state contract without changing API
success responses, SQLite schema, or business behavior.

## 4.3 P2.3 Addendum

P2.3 adds report validation and report quality/safety evaluation:

- validator module: `app/api/report_validator.py`
- snapshot integration: nested `validator` summary in `safety_flags_json`
- case corpus integration: `report_validation` and report safety metrics
- unit tests: `tests/test_p2_3_report_validator.py`
- report: `docs/P2_3_REPORT_VALIDATOR_REPORT.md`
- artifact: `artifacts/p2_3_report_validator.json`

This addendum validates existing final reports without changing API success
responses, SQLite schema, or business capability.

## 4.4 P2.4 Addendum

P2.4 adds long-session and multi-session reliability checks:

- demo script: `scripts/run_long_session_demo.py`
- unit tests: `tests/test_p2_4_long_session_reliability.py`
- inspect/audit summary enhancements for long DBs
- report: `docs/P2_4_LONG_SESSION_RELIABILITY_REPORT.md`
- artifact: `artifacts/p2_4_long_session_reliability.json`

This addendum validates existing API/SQLite behavior under repeated turns and
interleaved sessions without changing endpoint contracts, SQLite schema, or
business capability.

## 4.5 P2.5 Addendum

P2.5 adds local delivery documentation and one-command P2 gate automation:

- gate runner: `scripts/run_p2_gate.py`
- delivery manifest: `artifacts/p2_delivery_manifest.json`
- delivery report: `docs/P2_DELIVERY_REPORT.md`
- local runbook: `docs/LOCAL_RUNBOOK.md`
- unit tests: `tests/test_p2_5_delivery_docs.py` and
  `tests/test_p2_5_p2_gate_runner.py`

This addendum packages the existing P2 validation surface without changing API
success responses, SQLite schema, or business capability.

## 4.6 P2 Final Gate Addendum

P2 Final Gate verifies the complete P2 baseline:

- final report: `docs/P2_FINAL_REPORT.md`
- final artifact: `artifacts/p2_final_gate.json`
- P2 gate: `status=ok`, 6/6 checks
- P1 gate: `status=ok`, 13/13 checks
- full unittest discovery: 191 tests OK
- case corpus: 12/12 cases passed
- long-session reliability: 3 sessions x 50 turns passed
- replay/inspect/audit: passed against `.runtime/tcm_assistant.sqlite3`
- secret scan: findings `0`
- `git diff --check`: exit code `0`, Windows LF/CRLF warnings only

This final gate recommends P3.0 and keeps all P2 boundaries frozen.

## 5. P2 Must Not Do By Default

P2.0 does not introduce:

- MemoryManager
- Embedding or vector-store expansion
- Tool Registry
- multi-agent workflow
- Web UI
- user or permission system
- ORM
- diagnosis output
- prescription output
- treatment-plan output
- a real LLM key as a default gate requirement

## 6. Known Limits

- SQLite persistence is local and not a production multi-user data layer.
- Runtime memory remains only a short-lived cache.
- Report audit is a lightweight boundary check.
- Report validator is a lightweight report quality/safety gate, not a medical
  validator.
- Existing RAG remains inside the prior constrained report-enhancement scope.

## 7. Validation

P2.0 baseline validation uses:

```bash
python scripts/run_p1_gate.py --output artifacts/p1_gate_result.json
python -m unittest discover -s tests
python scripts/secret_scan.py --json --output artifacts/secret_scan_result.json
git diff --check
```

Recommended supporting checks:

```bash
python scripts/run_api_persistence_demo.py
python scripts/replay_api_case.py artifacts/replay_cases/p1_4_basic_consultation_replay.json --output artifacts/p1_4_api_replay_result.json
python scripts/inspect_sqlite_store.py --db .runtime/tcm_assistant.sqlite3 --json
python scripts/audit_session.py --db .runtime/tcm_assistant.sqlite3 --session <session_id> --json
python scripts/audit_session.py --db .runtime/tcm_assistant.sqlite3 --session <session_id> --check-state --json
python scripts/run_case_corpus_eval.py artifacts/eval_cases/ --output artifacts/p2_case_corpus_eval.json
python -m unittest tests.test_p2_3_report_validator
python -m unittest tests.test_p2_4_long_session_reliability
python scripts/run_long_session_demo.py --turns 50 --sessions 3 --output artifacts/p2_4_long_session_reliability.json
python scripts/run_p2_gate.py --output artifacts/p2_gate_result.json
python scripts/audit_session.py --db .runtime/tcm_assistant.sqlite3 --session <session_id> --check-state --json
```

## 8. Recommendation

P2 Final Gate passed. The current recommended next phase is P3.0, while keeping
the existing P2 boundaries: no diagnosis, prescription, treatment-plan output,
MemoryManager, new embedding capability, tool registry, multi-agent workflow,
Web UI, user or permission system, ORM, or default dependency on a real LLM key.
