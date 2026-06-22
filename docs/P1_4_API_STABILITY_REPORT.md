# P1.4 API Stability Report

Generated: 2026-06-17

## 1. Goal

P1.4 stabilizes the existing P1 API under invalid input, missing or corrupted
state, and repeatable replay conditions. It keeps all P1.1 success response
models unchanged and preserves P1.2/P1.3 SQLite persistence behavior.

## 2. Added Files

- `app/api/errors.py`
- `scripts/replay_api_case.py`
- `tests/test_p1_4_api_error_contract.py`
- `tests/test_p1_4_api_input_boundaries.py`
- `tests/test_p1_4_api_contract_snapshot.py`
- `artifacts/replay_cases/p1_4_basic_consultation_replay.json`
- `artifacts/p1_4_api_replay_result.json`
- `artifacts/p1_api_contract_snapshot.json`
- `docs/P1_4_API_STABILITY_REPORT.md`

## 3. Error Response Structure

All handled API errors use:

```json
{
  "error": {
    "code": "SESSION_NOT_FOUND",
    "message": "Session not found.",
    "details": {}
  }
}
```

Supported error codes:

- `INVALID_REQUEST`
- `SESSION_NOT_FOUND`
- `STATE_NOT_FOUND`
- `STORE_UNAVAILABLE`
- `STATE_CORRUPTED`
- `TURN_REJECTED`
- `INTERNAL_ERROR`

The error wrapper redacts secret-like values and removes local path / traceback
fragments from default responses.

## 4. Input Boundary Tests

P1.4 covers:

- empty `user_input`
- whitespace-only `user_input`
- missing `user_input`
- non-string `user_input`
- missing or nonexistent session path
- repeated session creation
- special characters
- Unicode / Chinese input
- long input
- synthetic secret injection
- multiple turns
- report behavior when information is insufficient
- no diagnosis / prescription / treatment-plan terms in API payloads

## 5. Replay Harness

Command:

```powershell
python scripts/replay_api_case.py artifacts/replay_cases/p1_4_basic_consultation_replay.json --output artifacts/p1_4_api_replay_result.json --json
```

The replay harness uses a temporary SQLite DB by default, creates a fake-mode
API session through `TestClient`, submits the case turns, checks `min_turns`,
checks `report_available`, checks `must_not_contain`, and fails with non-zero
exit code if any check fails.

Replay result summary:

- case: `p1_4_basic_consultation_replay`
- status: `ok`
- turn_count: 3
- report_available: true
- must_not_contain_passed: true

## 6. Contract Snapshot

Snapshot: `artifacts/p1_api_contract_snapshot.json`

It records:

- endpoint path list
- request schema summaries
- success response required fields
- exact `/health` contract
- error response shape
- error code list
- compatibility rules

The snapshot test allows backward-compatible additive fields but fails if
required fields are removed or renamed.

## 7. Regression Results

Validated commands:

```powershell
python -m unittest tests.test_p1_4_api_error_contract
python -m unittest tests.test_p1_4_api_input_boundaries
python -m unittest tests.test_p1_4_api_contract_snapshot
python -m unittest tests.test_p1_3_redaction
python -m unittest tests.test_p1_3_sqlite_schema_meta
python -m unittest tests.test_p1_3_sqlite_store_hardening
python -m unittest tests.test_p1_2_sqlite_persistence tests.test_p1_1_api_minimal
python -m unittest discover -s tests
python scripts/replay_api_case.py artifacts/replay_cases/p1_4_basic_consultation_replay.json --output artifacts/p1_4_api_replay_result.json --json
python scripts/run_api_persistence_demo.py
rg -n "sk-[A-Za-z0-9_-]{20,}" app scripts docs artifacts README.md .env.example
git diff --check
```

Results:

- P1.4 error contract tests: 6 tests OK
- P1.4 input boundary tests: 10 tests OK
- P1.4 contract snapshot tests: 4 tests OK
- P1.3 regression tests: 12 tests OK
- P1.2 + P1.1 regression tests: 17 tests OK
- Full unittest discovery: 98 tests OK
- Replay harness: passed
- Persistence demo: restored `turn_count_after_restart=1` and
  `final_report_ready_after_restart=true`
- High-entropy `sk-...` scan: no hits in app/scripts/docs/artifacts/README
- Broad secret scan: environment variable names, historical notes, and
  synthetic test secrets only
- `git diff --check`: OK, no whitespace errors; Windows LF/CRLF warnings only

## 8. Boundary Check

P1.4 does not introduce:

- ORM
- MemoryManager
- Embedding or vector-store expansion
- Tool Registry
- multi-agent workflow
- Web UI
- user or permission system
- diagnosis, prescription, or treatment-plan output

`GET /health` remains the exact P1.1 contract.

## 9. Recommendation

P1.4 is complete. Proceed to P1.5 report snapshot, auditability, and
traceability under the same explicit boundaries.
