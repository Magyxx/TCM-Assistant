# P3.1 Runtime Config Report

Generated: 2026-06-17

## Goal

P3.1 establishes a unified runtime config layer and operational modes for
local, test, demo, eval, and gate usage. The work is limited to configuration
governance, environment validation, redacted summaries, and preflight checks.
It does not change API contracts, the exact P1.1 `/health` response, SQLite
schema, or the inquiry-information safety boundary.

## Added Files

- `app/api/runtime_config.py`
- `scripts/check_runtime_config.py`
- `tests/test_p3_1_runtime_config.py`
- `tests/test_p3_1_runtime_config_script.py`
- `docs/RUNTIME_CONFIG.md`
- `docs/P3_1_RUNTIME_CONFIG_REPORT.md`
- `artifacts/p3_1_runtime_config.json`

## Modified Files

- `README.md`
- `app/api/sqlite_store.py`
- `scripts/run_api_persistence_demo.py`
- `scripts/replay_api_case.py`
- `scripts/run_case_corpus_eval.py`
- `scripts/run_long_session_demo.py`
- `scripts/run_p1_gate.py`
- `scripts/run_p2_gate.py`
- `docs/API_CONTRACT.md`
- `docs/LOCAL_RUNBOOK.md`
- `docs/P3_BASELINE.md`
- `docs/P3_GATE_PLAN.md`
- `docs/P3_ROADMAP.md`
- `docs/SQLITE_SCHEMA.md`

## RuntimeConfig Fields

- `runtime_mode`
- `db_path`
- `db_path_source`
- `runtime_dir`
- `artifacts_dir`
- `allow_real_llm`
- `openai_api_key_present`
- `log_level`
- `redact_logs`
- `config_strict`
- `loaded_at`
- `warnings`
- `errors`

## Environment Variables

- `TCM_RUNTIME_MODE`
- `TCM_API_DB_PATH`
- `TCM_RUNTIME_DIR`
- `TCM_ARTIFACTS_DIR`
- `TCM_ALLOW_REAL_LLM`
- `TCM_LOG_LEVEL`
- `TCM_REDACT_LOGS`
- `TCM_CONFIG_STRICT`
- `OPENAI_API_KEY`

Defaults are `local`, `.runtime/tcm_assistant.sqlite3`, `.runtime`,
`artifacts`, `false`, `INFO`, `true`, and `false`. `OPENAI_API_KEY` is recorded
only as present or absent.

## Operational Modes

- `local`: default local development mode.
- `test`: test mode, expected to use temporary DBs.
- `demo`: controlled demo script mode with redacted output.
- `eval`: case corpus, long-session, and gate eval mode with temporary or
  explicit DBs.

## DB Path Priority

1. CLI `--db`
2. `TCM_API_DB_PATH`
3. `.runtime/tcm_assistant.sqlite3`

`db_path_source` records `default`, `env:TCM_API_DB_PATH`, or `cli:--db`.

## Preflight Script

`scripts/check_runtime_config.py` supports:

```bash
python scripts/check_runtime_config.py
python scripts/check_runtime_config.py --json
python scripts/check_runtime_config.py --output artifacts/p3_1_runtime_config.json
python scripts/check_runtime_config.py --mode local
python scripts/check_runtime_config.py --mode test
python scripts/check_runtime_config.py --mode demo
python scripts/check_runtime_config.py --mode eval
python scripts/check_runtime_config.py --db <path>
```

The script validates mode, DB parent, runtime directory, artifacts directory,
log level, redaction, key presence, and explicit real-LLM enablement. It exits
nonzero on errors and does not require a real LLM key.

## P2 Gate Integration

`scripts/run_p2_gate.py` now includes `runtime_config_check` before the existing
P1/P2 checks. The check runs:

```bash
python scripts/check_runtime_config.py --json --output artifacts/p3_1_runtime_config.json
```

The current gate may report 7/7 checks when all checks pass.

## Validation Results

Initial P3.1 checks:

- `python -m unittest tests.test_p3_1_runtime_config`: `ok`, 10 tests
- `python -m unittest tests.test_p3_1_runtime_config_script`: `ok`, 9 tests
- `python scripts/check_runtime_config.py --json --output artifacts/p3_1_runtime_config.json`: `ok`

Full acceptance commands are recorded below.

## Final Validation

- `python -m unittest tests.test_p3_1_runtime_config`: `ok`, 10 tests
- `python -m unittest tests.test_p3_1_runtime_config_script`: `ok`, 9 tests
- `python scripts/check_runtime_config.py --json --output artifacts/p3_1_runtime_config.json`: `ok`
- `python scripts/run_p2_gate.py --output artifacts/p2_gate_result.json`: `ok`, 7/7 checks
- `python scripts/run_p1_gate.py --output artifacts/p1_gate_result.json`: `ok`, 13/13 checks
- `python -m unittest discover -s tests`: `ok`, 210 tests
- `python scripts/run_case_corpus_eval.py artifacts/eval_cases/ --output artifacts/p2_case_corpus_eval.json`: `ok`, 12/12 cases
- `python scripts/run_long_session_demo.py --turns 50 --sessions 3 --output artifacts/p2_4_long_session_reliability.json`: `ok`, 3 sessions x 50 turns
- `python scripts/secret_scan.py --json --output artifacts/secret_scan_result.json`: `ok`, 0 findings, 202 files scanned
- `git diff --check`: exit code 0, Windows LF/CRLF warnings only

`runtime_config_check` status in `artifacts/p2_gate_result.json`: `ok`,
`runtime_mode=local`, `db_path_source=default`, `warnings=0`, `errors=0`.

## Contract And Boundary

- P1/P2 API contract changed: no
- `/health` exact P1.1 contract changed: no
- SQLite schema changed: no
- Diagnosis output added: no
- Prescription output added: no
- Treatment-plan output added: no
- Web UI, users, permissions, ORM, MemoryManager, embeddings, Tool Registry, or
  multi-agent behavior added: no
- Real LLM key required by default gates: no
- Real secret committed: no

## Recommendation

Proceed to P3.2 Observability & Redacted Logging after final validation remains
green.
