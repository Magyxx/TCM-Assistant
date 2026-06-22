# P2.4 Long Session and Multi Session Reliability Report

Generated: 2026-06-17

## 1. Goal

P2.4 validates long-session and multi-session reliability for the existing
FastAPI and SQLite workflow. It checks that repeated turns, interleaved
sessions, cache clear, SQLite recovery, report snapshots, state versions,
secret redaction, and state/report validators remain stable.

P2.4 is a reliability and sanity-check phase only. It does not add performance
optimization, MemoryManager, Embedding expansion, Tool Registry, multi-agent
workflow, Web UI, user/auth, ORM, diagnosis, prescription, or treatment-plan
capability.

## 2. Long Session Demo

New script:

```bash
python scripts/run_long_session_demo.py
python scripts/run_long_session_demo.py --turns 50
python scripts/run_long_session_demo.py --sessions 3
python scripts/run_long_session_demo.py --db <temp_db>
python scripts/run_long_session_demo.py --output artifacts/p2_4_long_session_reliability.json
python scripts/run_long_session_demo.py --json
```

Defaults:

- `turns=50`
- `sessions=3`
- temporary SQLite DB unless `--db` is explicit
- fake extractor
- RAG disabled for this reliability demo to avoid turning P2.4 into a RAG
  throughput check

## 3. Multi Session Strategy

The demo creates all sessions first, then writes turns in an interleaved order:

1. session 1 turn 1
2. session 2 turn 1
3. session 3 turn 1
4. session 1 turn 2
5. ...

This validates that `turn_count`, `state_version`, report snapshots, and
recovery stay isolated per session.

## 4. Cache Clear and Recovery

After all turns are written, the runtime session cache is cleared. The demo then
loads `/sessions/{session_id}/state` and `/sessions/{session_id}/report` through
the API, forcing recovery from SQLite-backed state.

For each session it checks:

- state endpoint recovers after cache clear
- report endpoint remains ready
- `turn_count == turns`
- `state_version == turns`
- state versions are monotonic from `1..N`
- report snapshots exist and stay scoped to the session

## 5. Validator Integration

P2.4 calls:

- `validate_session_consistency(db_path, session_id)`
- `validate_report(final_report, recovered_state)`

Both must pass for every session. The demo output includes per-session
`state_validation_passed` and `report_validation_passed`.

## 6. DB Size Sanity

P2.4 records aggregate DB/WAL/SHM size in bytes. It applies only a loose sanity
ceiling of `25 MiB` for the default `3 x 50` local demo. `duration_seconds` is
recorded but is not a default fail condition.

## 7. Latest Demo Result

`python scripts/run_long_session_demo.py --turns 50 --sessions 3 --output artifacts/p2_4_long_session_reliability.json`

Result:

- status: `ok`
- sessions: `3`
- turns per session: `50`
- per-session `turn_count`: `50`
- per-session `state_version`: `50`
- per-session report snapshots: `48`
- state validation: passed for every session
- report validation: passed for every session
- recovered after cache clear: true for every session
- secret_found: `false`
- DB size: `1265664` bytes
- duration_seconds: `12.8214`

## 8. Test Coverage

`tests/test_p2_4_long_session_reliability.py` covers:

- single session with 50 turns
- multi-session interleaved writes
- per-session `turn_count` and `state_version` isolation
- per-session report snapshot isolation
- cache clear recovery
- state/report validator pass
- synthetic secret injection not leaking to DB/WAL/SHM
- temporary DB usage
- inspect script summary for long DB
- audit script summary for long session
- CLI JSON shape for `run_long_session_demo.py`
- P2.1 case corpus smoke
- P1 gate CLI compatibility smoke

## 9. Secret Scan

The long-session demo injects a synthetic secret through one turn and verifies
DB/WAL/SHM bytes do not contain the raw value or key name. Formal repository
secret scan remains part of final validation.

## 10. git diff Check

`git diff --check` is part of final validation. On Windows, LF/CRLF warnings may
appear; the exit code is the authoritative whitespace result.

## 11. Final Validation Results

- `python -m unittest tests.test_p2_4_long_session_reliability`: `OK`, 6 tests.
- `python scripts/run_long_session_demo.py --turns 50 --sessions 3 --output artifacts/p2_4_long_session_reliability.json`: `ok`.
- `python scripts/run_case_corpus_eval.py artifacts/eval_cases/ --output artifacts/p2_case_corpus_eval.json`: `ok`, 12/12 cases.
- `python scripts/run_p1_gate.py --output artifacts/p1_gate_result.json`: `ok`, 13/13 checks.
- `python -m unittest discover -s tests`: `OK`, 177 tests.
- `python scripts/secret_scan.py --json --output artifacts/secret_scan_result.json`: `ok`, findings `0`, allowed synthetic findings `15`.
- `git diff --check`: exit code `0`; LF/CRLF warnings only.

## 12. Boundary Review

No P2.4 boundary violation is introduced:

- no MemoryManager
- no Embedding expansion
- no Tool Registry
- no multi-agent workflow
- no Web UI
- no user/auth system
- no ORM
- no diagnosis, prescription, or treatment-plan output
- no real LLM key dependency by default

## 13. Recommendation

Proceed to P2.5.
