# P1.5 Report Auditability Report

Generated: 2026-06-17

## 1. Goal

P1.5 adds persisted final-report snapshots and a lightweight audit path on top
of the P1.2/P1.3 SQLite store. It preserves the P1.1 API success contracts and
the P1.4 stable error shape.

## 2. Added Files

- `app/api/report_audit.py`
- `scripts/audit_session.py`
- `tests/test_p1_5_report_audit.py`
- `tests/test_p1_5_report_snapshot.py`
- `docs/P1_5_REPORT_AUDITABILITY_REPORT.md`
- `artifacts/p1_5_report_auditability.json`

## 3. Modified Files

- `app/api/sqlite_store.py`
- `app/api/session_runtime.py`
- `app/api/main.py`
- `scripts/inspect_sqlite_store.py`
- `scripts/replay_api_case.py`
- `README.md`
- `docs/P1_GATE_REPORT.md`

## 4. SQLite Schema And Migration

P1.5 keeps `schema_version=1` and `schema_stage=P1.3` for compatibility with
the existing P1.4 gate. The new capability is detected by the `reports` table.

New table:

```sql
CREATE TABLE IF NOT EXISTS reports (
    report_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    state_version INTEGER NOT NULL,
    report_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    safety_flags_json TEXT,
    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
);
```

Migration behavior:

- empty databases create all P1 tables plus `reports`
- legacy P1.2/P1.3 databases gain `reports` during idempotent initialization
- existing session/state/turn rows are preserved
- initialization remains safe to run repeatedly
- future `schema_version` rejection remains unchanged

## 5. State Version

`state_version` is stored as an additive field inside `session_states.state_json`.

Rules:

- new sessions start at `state_version=0`
- each successful `/turn` increments `state_version` by 1
- cache clear / process restart recovers `state_version` from SQLite
- old rows without `state_version` fall back to the persisted `turn_count`
- top-level API response fields are unchanged; `state.state_version` is additive

## 6. Report Snapshot

When a turn produces `final_report`, the runtime audits the report and writes a
snapshot in the same SQLite transaction as the turn/state update.

Snapshot fields:

- `report_id`
- `session_id`
- `state_version`
- redacted `report_json`
- `created_at`
- redacted `safety_flags_json`

Repeated report generation writes multiple snapshots, one per successful turn
that produces a report. Snapshot write failures are explicit because the same
transaction rolls back instead of silently ignoring the failure.

## 7. Report Audit

`app/api/report_audit.py` provides:

- `audit_report(report, state=None) -> dict`
- `assert_report_safe(report, state=None) -> None`

The audit returns a JSON-serializable payload:

```json
{
  "passed": true,
  "flags": [],
  "checked_at": "2026-06-16T18:59:53.866387+00:00",
  "rules": {
    "forbidden_phrases_checked": [
      "confirmed_diagnosis_phrase",
      "diagnosis_phrase",
      "prescription_phrase",
      "treatment_plan_phrase"
    ],
    "drug_dose_pattern_checked": true,
    "credential_pattern_checked": true,
    "substitute_medical_advice_checked": true,
    "safety_boundary_hint_present": true,
    "urgent_state_has_report_context": true
  }
}
```

Failure flags cover explicit diagnosis, prescription, treatment-plan wording,
drug-dose-like text, secret-like content, empty reports, and text that claims it
can substitute for clinician judgment.

## 8. Inspect And Audit Scripts

Inspect command:

```powershell
python scripts/inspect_sqlite_store.py --db .runtime/tcm_assistant.sqlite3 --json
```

Observed summary after replay:

- `reports=3`
- `schema_meta=3`
- `sessions=1`
- `session_states=1`
- `turns=3`

Audit command:

```powershell
python scripts/audit_session.py --db .runtime/tcm_assistant.sqlite3 --session 42d7185a-c2f0-4357-88fd-fd0ce39062ff --json
```

Observed summary:

- `passed=true`
- `turn_count=3`
- `current_state_version=3`
- `report_count=3`
- latest report audit `passed=true`
- `secret_found=false`
- `raw_user_text_included=false`

## 9. Validation Results

Validated commands:

```powershell
python -m unittest tests.test_p1_5_report_snapshot
python -m unittest tests.test_p1_5_report_audit
python -m unittest tests.test_p1_4_api_error_contract
python -m unittest tests.test_p1_4_api_input_boundaries
python -m unittest tests.test_p1_4_api_contract_snapshot
python -m unittest tests.test_p1_3_redaction
python -m unittest tests.test_p1_3_sqlite_schema_meta
python -m unittest tests.test_p1_3_sqlite_store_hardening
python -m unittest tests.test_p1_2_sqlite_persistence
python -m unittest tests.test_p1_1_api_minimal
python -m unittest discover -s tests
python scripts/replay_api_case.py artifacts/replay_cases/p1_4_basic_consultation_replay.json --output artifacts/p1_4_api_replay_result.json --json
python scripts/run_api_persistence_demo.py
python scripts/inspect_sqlite_store.py --db .runtime/tcm_assistant.sqlite3 --json
python scripts/audit_session.py --db .runtime/tcm_assistant.sqlite3 --session 42d7185a-c2f0-4357-88fd-fd0ce39062ff --json
rg -n "sk-[A-Za-z0-9_-]{20,}" app scripts docs artifacts README.md .env.example
git diff --check
```

Results:

- P1.5 report snapshot tests: 10 tests OK
- P1.5 report audit tests: 10 tests OK
- P1.4 regression tests: 20 tests OK
- P1.3 regression tests: 12 tests OK
- P1.2 SQLite persistence tests: 8 tests OK
- P1.1 API minimal tests: 9 tests OK
- Full unittest discovery: 118 tests OK
- Replay harness: passed, `report_snapshot_count=3`
- Persistence demo: restored `turn_count_after_restart=1` and
  `final_report_ready_after_restart=true`
- High-entropy `sk-...` scan: no hits
- Broad secret scan: environment variable names, historical notes, scanner
  patterns, and synthetic test secrets only
- `git diff --check`: OK, no whitespace errors; Windows LF/CRLF warnings only

## 10. Boundary Check

P1.5 does not introduce:

- ORM
- MemoryManager
- Embedding or vector-store expansion
- Tool Registry
- multi-agent workflow
- Web UI
- user or permission system
- diagnosis, prescription, or treatment-plan output

`GET /health` remains the exact P1.1 contract.

## 11. Recommendation

P1.5 is complete. Proceed to P1.6 local gate automation and secret scan under
the same explicit P1 boundaries.
