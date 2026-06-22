# P1.4 API Contract Gate Report

Generated: 2026-06-17

## 1. What P1.4 Implemented

P1.4 adds a machine-readable API contract gate for the existing P1 API surface.
It does not add a new API endpoint or product capability.

Added:

- `scripts/validate_p1_api_contract.py`
- `tests/test_p1_4_api_contract_gate.py`

The gate uses an isolated SQLite database by default, creates fake-mode API
sessions through `TestClient`, and validates:

- exact P1.1 `/health` contract
- session creation response shape
- turn response shape and required metadata
- state recovery after clearing runtime cache
- report endpoint response shape after recovery
- missing-session 404 behavior
- P1.3 `schema_meta` presence
- response and SQLite redaction for synthetic secret-like input

## 2. Safety Boundary

P1.4 remains an engineering gate only.

Not introduced:

- ORM
- MemoryManager
- Embedding or vector storage
- Tool Registry
- multi-agent workflow
- Web UI
- user or permission system
- diagnosis, prescription, or treatment-plan output

The gate explicitly checks `diagnosis_system=false` in `/health` and records
the boundary flags in its JSON output.

## 3. Command

Default isolated run:

```powershell
python scripts/validate_p1_api_contract.py --json
```

Explicit DB run:

```powershell
python scripts/validate_p1_api_contract.py --db .runtime/p1_4_contract.sqlite3 --allow-clear --json
```

`--db` requires `--allow-clear` because the gate resets sessions in the
selected SQLite database.

## 4. Output Summary

Successful JSON output includes:

- `stage = P1.4`
- `feature = API contract gate`
- `passed = true`
- per-check `ok` booleans
- `/health` stage and `diagnosis_system`
- restart recovery turn count
- P1.3 schema metadata
- final table counts
- boundary flags

The script does not print user turn text, state JSON, final report content, or
SQLite row contents.

## 5. Validation Results

Validated commands in this environment:

```powershell
python -m py_compile scripts\validate_p1_api_contract.py tests\test_p1_4_api_contract_gate.py
python -m unittest tests.test_p1_4_api_contract_gate
python scripts\validate_p1_api_contract.py --json
python -m unittest tests.test_p1_3_redaction tests.test_p1_3_sqlite_schema_meta tests.test_p1_3_sqlite_store_hardening
python -m unittest tests.test_p1_2_sqlite_persistence tests.test_p1_1_api_minimal
python -m unittest discover -s tests
python scripts\run_api_persistence_demo.py
python scripts\inspect_sqlite_store.py --db .runtime\tcm_assistant.sqlite3 --json
rg -n "sk-[A-Za-z0-9_-]{20,}" app scripts docs artifacts README.md .env.example
git diff --check
```

Results:

- P1.4 API contract gate tests: 2 tests OK
- P1.4 contract script: passed
- P1.3 regression tests: 12 tests OK
- P1.2 + P1.1 regression tests: 17 tests OK
- Full unittest discovery: 78 tests OK
- Persistence demo: restored `turn_count_after_restart=1` and
  `final_report_ready_after_restart=true`
- Inspect script: returned `schema_stage=P1.3`, `schema_version=1`,
  `schema_meta=3`, `sessions=1`, `session_states=1`, `turns=1`
- High-entropy `sk-...` scan: no hits in app/scripts/docs/artifacts/README
- `git diff --check`: OK, no whitespace errors; Windows LF/CRLF warnings only

## 6. Relationship To P2.0

P1.4 turns the API contract, SQLite persistence assumptions, and boundary
checks into a repeatable gate. This is a prerequisite for P2.0 engineering
landing because future changes can be judged against a stable contract instead
of ad hoc manual inspection.

## 7. Next Step Recommendation

Proceed to P1.5: operational readiness checks around local configuration,
runtime startup, inspectability, and documented acceptance commands, while
continuing to avoid new medical, auth, UI, Memory, Embedding, or multi-agent
scope unless explicitly approved.
