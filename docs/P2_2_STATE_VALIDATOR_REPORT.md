# P2.2 State Validator and State Consistency Report

Generated: 2026-06-17

## 1. Goal

P2.2 adds a non-mutating `RunState` validator and session consistency checks for
the existing API/SQLite workflow. It verifies that persisted session state is
JSON-safe, structurally compatible with the current `RunState`, type-safe,
versioned consistently, free of unredacted secrets, and free of out-of-bound
medical output.

P2.2 does not add diagnosis, prescription, treatment-plan, MemoryManager,
Embedding, Tool Registry, multi-agent, Web UI, user/auth, ORM, or external
service capability.

## 2. State Validator Checks

`app/api/state_validator.py` provides:

- `validate_state(state)`
- `assert_state_valid(state)`
- `validate_state_json(state_json)`
- `validate_session_consistency(store, session_id)`

`validate_state` checks:

- state is not `None`.
- state is a non-empty JSON object.
- state can be serialized as JSON.
- required fields match the current `RunState` model fields.
- field types are reasonable for optional strings, string lists, tri-state
  fields, `turn_count`, `metadata`, and `final_report`.
- `state_version` exists or can safely fall back to `turn_count`.
- `state_version` is a non-negative integer and not lower than `turn_count`.
- state contains no unredacted secret-like content.
- state contains no out-of-bound phrases such as `诊断为`, `确诊`, `处方`, or
  `治疗方案`.

The validator returns machine-readable `passed/errors/warnings/checks` and does
not modify the state.

## 3. State Version Handling

Current states are expected to include additive `state_version`. Legacy states
without `state_version` are handled with a warning and a `turn_count` fallback
when possible. Negative, non-integer, or contradictory versions fail.

Session consistency checks validate:

- session row exists.
- state row exists.
- state itself passes `validate_state_json`.
- persisted turn count matches `state.turn_count`.
- `state_version >= persisted turn count`.
- turn indexes are monotonic from `1..N`.
- report `state_version` values are valid, monotonic, and not ahead of current
  state.

## 4. Corrupted State Handling

`validate_state_json` returns a failed result with `state_json_corrupted` for
malformed JSON. `audit_session --check-state` surfaces this as
`state_validation` without a stack trace or raw state dump.

## 5. audit_session Usage

```bash
python scripts/audit_session.py --db .runtime/tcm_assistant.sqlite3 --session <session_id> --check-state
python scripts/audit_session.py --db .runtime/tcm_assistant.sqlite3 --session <session_id> --check-state --json
```

The default output remains a summary. Full state is omitted unless `--verbose`
is explicitly provided, and verbose state is redacted.

## 6. Case Corpus Eval Integration

`scripts/run_case_corpus_eval.py` now calls `validate_session_consistency` after
each case replay. Each case includes `state_validation`, and the top-level JSON
includes:

```json
{
  "state_validation": {
    "enabled": true,
    "passed": true,
    "failed": 0,
    "case_count": 10
  }
}
```

`expect.state.require_valid_state` defaults to `true` and can be set explicitly
for future compatibility.

## 7. Latest Results

- `python -m unittest tests.test_p2_2_state_validator`: `OK`, 12 tests.
- `python -m unittest tests.test_p2_1_case_corpus_eval tests.test_p2_2_state_validator`: `OK`, 26 tests.
- `python scripts/run_case_corpus_eval.py artifacts/eval_cases/ --output artifacts/p2_case_corpus_eval.json`: `ok`, 10/10 cases, state validation 10/10.
- `python scripts/run_p1_gate.py --output artifacts/p1_gate_result.json`: `ok`, 13/13 checks.
- `python -m unittest discover -s tests`: `OK`, 158 tests.
- `python scripts/secret_scan.py --json --output artifacts/secret_scan_result.json`: `ok`, findings `0`, allowed synthetic findings `14`.
- `git diff --check`: exit code `0`; LF/CRLF warnings only.
- `python scripts/audit_session.py --db .runtime/tcm_assistant.sqlite3 --session 827ed397-2cda-4c8b-9020-405a697f0657 --check-state --json`: `passed=true`, `state_validation.passed=true`.

## 8. Boundary Review

No P2.2 boundary violation is introduced:

- no MemoryManager
- no Embedding expansion
- no Tool Registry
- no multi-agent workflow
- no Web UI
- no user/auth system
- no ORM
- no diagnosis, prescription, or treatment-plan output
- no real LLM key dependency by default

## 9. Recommendation

Proceed to P2.3 if the final validation commands remain green.
