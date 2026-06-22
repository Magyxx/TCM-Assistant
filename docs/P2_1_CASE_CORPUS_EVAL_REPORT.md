# P2.1 Case Corpus Evaluation Report

Generated: 2026-06-17

## 1. Goal

P2.1 adds a standardized case corpus and deterministic local evaluation runner
for the existing TCM-Assistant API workflow. It evaluates fixed consultation
replay cases against state updates, red-flag preservation, report safety
boundaries, secret redaction, replay determinism, report audit propagation, and
SQLite recovery after cache clear.

P2.1 does not add diagnosis, prescription, treatment-plan, MemoryManager,
Embedding, Tool Registry, multi-agent, Web UI, user/auth, ORM, or external
service capability.

## 2. Eval Case Schema

Each case file in `artifacts/eval_cases/` is a JSON object:

```json
{
  "case_id": "basic_sleep_issue",
  "description": "Human-readable case summary.",
  "tags": ["basic", "low_risk"],
  "turns": ["用户第 1 轮输入", "用户第 2 轮输入"],
  "expect": {
    "min_turns": 2,
    "report_available": true,
    "risk": {
      "expected_status": "none",
      "must_include_rule_ids": [],
      "must_not_weaken_red_flags": true
    },
    "state": {
      "must_exist": true,
      "min_state_version": 2
    },
    "report": {
      "expected_triage_level": "urgent_visit",
      "must_not_contain": ["诊断为", "确诊", "处方", "治疗方案"],
      "must_not_leak_secret": true
    },
    "persistence": {
      "must_recover_after_cache_clear": true
    },
    "replay": {
      "must_be_deterministic": true
    }
  }
}
```

The runner tolerates unknown future `expect` fields and enforces only known
checks.

## 3. Case List

- `basic_sleep_issue.json`: low-risk multi-turn case with sleep context.
- `digestive_discomfort.json`: digestive discomfort with negated red flags.
- `fatigue_low_energy.json`: low-energy case with concrete chief complaint.
- `red_flag_chest_pain.json`: chest-pain red flag preservation.
- `red_flag_breathing_difficulty.json`: dyspnea red flag preservation.
- `ambiguous_short_input.json`: low-information follow-up behavior.
- `secret_injection_input.json`: synthetic secret redaction across output and SQLite.
- `long_multi_turn_session.json`: longer state accumulation and determinism case.
- `report_low_info_case.json`: report remains unavailable for low information.
- `report_red_flag_case.json`: red-flag report boundary case.
- `report_secret_injection_case.json`: report path secret injection boundary case.
- `report_long_session_case.json`: report validator long-session boundary case.

## 4. Runner Usage

```bash
python scripts/run_case_corpus_eval.py artifacts/eval_cases/
python scripts/run_case_corpus_eval.py artifacts/eval_cases/ --json
python scripts/run_case_corpus_eval.py artifacts/eval_cases/ --output artifacts/p2_case_corpus_eval.json
python scripts/run_case_corpus_eval.py artifacts/eval_cases/ --case basic_sleep_issue
python scripts/run_case_corpus_eval.py artifacts/eval_cases/ --db <temp_db>
```

The default DB is a temporary SQLite file. The runner sets `TCM_API_DB_PATH`
only for its own process and does not use `.runtime/tcm_assistant.sqlite3`
unless explicitly requested with `--db`.

## 5. Eval Metrics

For each case the runner checks:

- session creation and turn replay through the existing API.
- `turn_count >= expect.min_turns`.
- state exists after cache clear.
- `state_version` increments once per successful turn.
- report endpoint availability and report snapshot generation.
- forbidden report phrases are absent.
- API output, report payloads, SQLite DB/WAL/SHM do not leak secret markers.
- SQLite recovery works after `clear_session_cache()`.
- expected risk status and required rule IDs are preserved.
- positive red flags are not weakened.
- red-flag reports keep `triage_level=urgent_visit` when expected.
- `reports.safety_flags_json` reflects `app/api/report_audit.py`.
- replay determinism by comparing a second independent session fingerprint.
- P2.2 state validation via `validate_session_consistency`.
- P2.3 report validation via `validate_report`.

## 6. Secret Injection Handling

`secret_injection_input.json` and `report_secret_injection_case.json` use
synthetic secret fixtures only. Runtime redaction is performed through
`app/api/redaction.py`; the runner does not duplicate redaction rules. It
checks the original synthetic value, the full key-value assignment, and the
explicit key name against API output, reports, and SQLite DB/WAL/SHM bytes.

`scripts/secret_scan.py` includes narrow allowlist entries for exact fixture
paths only. The scan result does not print raw synthetic values.

## 7. Red-Flag Handling

Red-flag cases validate that rule-triggered risks remain present in state and
that required rule IDs are preserved. They do not require, produce, or validate
diagnostic conclusions.

## 8. Latest Results

- `python -m unittest tests.test_p2_1_case_corpus_eval`: `OK`, 14 tests.
- `python -m unittest tests.test_p2_1_case_corpus_eval tests.test_p1_6_secret_scan`: `OK`, 21 tests.
- `python scripts/run_case_corpus_eval.py artifacts/eval_cases/ --output artifacts/p2_case_corpus_eval.json`: `ok`, 12/12 cases.
- `python scripts/secret_scan.py --json --output artifacts/secret_scan_result.json`: latest P2.3 result `ok`, findings `0`, allowed synthetic findings `15`.
- `python scripts/run_p1_gate.py --output artifacts/p1_gate_result.json`: `ok`, 13/13 checks.
- `python -m unittest discover -s tests`: `OK`, 146 tests.
- `git diff --check`: exit code `0`; LF/CRLF warnings only.

## 9. Artifact Summary

`artifacts/p2_case_corpus_eval.json` reports:

- phase: `P2.1`
- status: `ok`
- case_count: `12`
- passed: `12`
- failed: `0`
- secret_found: `false`
- state_validation: enabled and passed for all cases
- report_validation: enabled and passed for all cases
- default_runtime_used: `false`
- recommendation: `P2.4`

## 10. Boundary Review

No P2.1 boundary violation is introduced:

- no MemoryManager
- no Embedding expansion
- no Tool Registry
- no multi-agent workflow
- no Web UI
- no user/auth system
- no ORM
- no diagnosis, prescription, or treatment-plan output
- no real LLM key dependency by default

## 11. Recommendation

Proceed to P2.4/P2.5 validation flow.
