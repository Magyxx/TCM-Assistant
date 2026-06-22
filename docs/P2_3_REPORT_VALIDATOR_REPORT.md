# P2.3 Report Validator and Report Quality/Safety Evaluation

Generated: 2026-06-17

## 1. Goal

P2.3 adds a non-mutating report validator for generated final reports and
persisted report snapshots. It verifies that report output remains JSON-safe,
structurally compatible with the current `FinalReport` contract, inside the
existing safety boundary, free of unredacted secrets, and supported by the
current session state.

P2.3 does not add diagnosis, prescription, treatment-plan, MemoryManager,
Embedding, Tool Registry, multi-agent, Web UI, user/auth, ORM, or external
service capability.

## 2. Validator API

`app/api/report_validator.py` provides:

- `validate_report(report, state=None)`
- `assert_report_valid(report, state=None)`
- `validate_report_snapshot(snapshot, state=None)`

The result shape is machine-readable:

```json
{
  "passed": true,
  "errors": [],
  "warnings": [],
  "checks": {
    "json_serializable": true,
    "structure": true,
    "safety_audit": true,
    "no_secret": true,
    "no_diagnosis": true,
    "no_prescription": true,
    "no_treatment_plan": true,
    "state_supported": true
  }
}
```

The validator reuses `app/api/report_audit.py` for safety-boundary rules and
`app/api/redaction.py` for value redaction. It does not modify the report.

## 3. Checks

P2.3 checks:

- report is not `None` or empty.
- report is JSON serializable.
- dict reports match the current `FinalReport` fields and field types.
- list and string reports are handled without mutation.
- generated content includes a safety-boundary hint.
- existing report audit passes.
- no unredacted secret-like content exists.
- no out-of-bound diagnosis, confirmed diagnosis, prescription, treatment-plan,
  drug-dose-like, or substitute-medical-advice text appears.
- red-flag state is not weakened by a non-urgent report.
- low-information state is not marked complete or fabricated as sufficient.
- urgent triage is not asserted without state support.

State support checks inspect display report content for assertions while still
letting the safety audit inspect the full report object, including metadata.
This avoids treating stored RAG evidence snippets as the report conclusion.

## 4. Snapshot Integration

Report snapshot persistence remains backward compatible. The root
`safety_flags_json` payload still contains the P1.5 `passed`, `flags`, and
`rules` fields. P2.3 adds a nested `validator` object:

```json
{
  "passed": true,
  "flags": [],
  "rules": {},
  "validator": {
    "passed": true,
    "checks": {}
  }
}
```

The SQLite store now preserves fixed validator keys such as `no_secret` inside
`safety_flags_json` while still redacting secret-like values.

## 5. Case Corpus Integration

`scripts/run_case_corpus_eval.py` now validates generated reports after replay.
Each case includes `report_validation`; top-level output includes:

```json
{
  "report_validation": {
    "enabled": true,
    "passed": true,
    "failed": 0,
    "case_count": 12,
    "validated_count": 10,
    "skipped_count": 2
  },
  "metrics": {
    "report_safety_pass_rate": 1.0,
    "report_validation_pass_rate": 1.0
  }
}
```

Low-information cases that correctly do not generate a report are marked as
`skipped=true` and pass validation.

## 6. New Cases

P2.3 adds:

- `artifacts/eval_cases/report_secret_injection_case.json`
- `artifacts/eval_cases/report_long_session_case.json`

Existing P2.3 report-focused cases are:

- `artifacts/eval_cases/report_low_info_case.json`
- `artifacts/eval_cases/report_red_flag_case.json`

All report-focused cases include forbidden report terms in `must_not_contain`
and preserve secret-redaction expectations.

## 7. Latest Results

- `python -m unittest tests.test_p2_3_report_validator`: `OK`, 13 tests.
- `python -m unittest tests.test_p2_2_state_validator`: `OK`, 12 tests.
- `python scripts/run_case_corpus_eval.py artifacts/eval_cases/ --output artifacts/p2_case_corpus_eval.json`: `ok`, 12/12 cases, report validation 12/12, validated reports 10/10.
- `python scripts/run_p1_gate.py --output artifacts/p1_gate_result.json`: `ok`, 13/13 checks.
- `python -m unittest discover -s tests`: `OK`, 171 tests.
- `python scripts/secret_scan.py --json --output artifacts/secret_scan_result.json`: `ok`, findings `0`, allowed synthetic findings `15`.
- `git diff --check`: exit code `0`; LF/CRLF warnings only.

The same final results are recorded in
`artifacts/p2_3_report_validator.json`.

## 8. Boundary Review

No P2.3 boundary violation is introduced:

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

Proceed to P2.4 if the final validation commands remain green.
