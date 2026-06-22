# Runtime Config

Generated: 2026-06-17

## P3.1 Goal

P3.1 establishes one runtime configuration layer for local operation, tests,
demo scripts, eval scripts, and gates. It makes config sources explicit,
preflightable, JSON-serializable, and redacted. P3.1 does not change API
contracts, the exact P1.1 `/health` response, the SQLite schema, or the safety
boundary.

## Module

Runtime config lives in:

```text
app/api/runtime_config.py
```

Public helpers:

- `RuntimeConfig`
- `load_runtime_config(env=None)`
- `get_runtime_config()`
- `reset_runtime_config_cache()`
- `validate_runtime_config(config)`
- `runtime_config_summary(config, redacted=True)`

`RuntimeConfig` is a dataclass. It does not use Pydantic and has no import-time
filesystem side effects.

## Fields

- `runtime_mode`: one of `local`, `test`, `demo`, or `eval`
- `db_path`: SQLite path used by the API runtime
- `db_path_source`: `default`, `env:TCM_API_DB_PATH`, or `cli:--db`
- `runtime_dir`: local runtime directory
- `artifacts_dir`: artifact output directory
- `allow_real_llm`: whether real LLM use was explicitly enabled
- `openai_api_key_present`: boolean presence only; the key value is never
  printed
- `log_level`: one of `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- `redact_logs`: whether runtime redaction is enabled
- `config_strict`: whether warnings are promoted to errors
- `loaded_at`: config load timestamp
- `warnings`: redacted warning strings
- `errors`: redacted error strings

## Modes

`local` is the default local development mode. It uses
`.runtime/tcm_assistant.sqlite3` unless `TCM_API_DB_PATH` is set, does not
require a real LLM key, and keeps redaction enabled by default.

`test` is for unit and integration tests. Tests should use temporary database
paths and should not make a real LLM key a required condition.

`demo` is for controlled local demos. Demo scripts may use files under
`.runtime/`, but their output must remain redacted.

`eval` is for case corpus, long-session, and gate evaluation. Eval commands
should use temporary DBs by default or an explicit `--db`; outputs should be
machine-readable artifacts.

## Environment Variables

Defaults:

```text
TCM_RUNTIME_MODE=local
TCM_API_DB_PATH=.runtime/tcm_assistant.sqlite3
TCM_RUNTIME_DIR=.runtime
TCM_ARTIFACTS_DIR=artifacts
TCM_ALLOW_REAL_LLM=false
TCM_LOG_LEVEL=INFO
TCM_REDACT_LOGS=true
TCM_CONFIG_STRICT=false
OPENAI_API_KEY absent
```

`OPENAI_API_KEY` is recorded only as `openai_api_key_present=true/false`.
Runtime summaries and gate artifacts must not contain the value.

Boolean values accept `true/false`, `yes/no`, `on/off`, and `1/0`. Invalid
runtime modes, boolean values, log levels, or paths are reported as errors.

## DB Path Priority

The priority is:

1. CLI `--db` for scripts that expose it.
2. `TCM_API_DB_PATH`.
3. `.runtime/tcm_assistant.sqlite3`.

Scripts with explicit `--db` keep that CLI path ahead of the environment. The
runtime API default still honors `TCM_API_DB_PATH` before the default path.

## Preflight

Run the P3.1 config check:

```bash
python scripts/check_runtime_config.py
python scripts/check_runtime_config.py --json
python scripts/check_runtime_config.py --json --output artifacts/p3_1_runtime_config.json
python scripts/check_runtime_config.py --mode local
python scripts/check_runtime_config.py --mode test --db /tmp/tcm_test.sqlite3
python scripts/check_runtime_config.py --mode demo
python scripts/check_runtime_config.py --mode eval --db /tmp/tcm_eval.sqlite3
```

The script validates mode, DB path parent, runtime directory, artifact
directory, log level, redaction, key presence, and explicit real-LLM enablement.
It exits nonzero when errors are present and does not require a real LLM key.

## Test And Eval Isolation

Tests should set `TCM_API_DB_PATH` to a temporary SQLite file or pass a temporary
path through helper APIs. Eval scripts default to temporary DBs unless `--db` is
explicit. This avoids writing business data to `.runtime/` during normal gate
runs.

## Redaction

`runtime_config_summary(..., redacted=True)` redacts secret-like values and
prints only `openai_api_key_present` for `OPENAI_API_KEY`. Gate subprocess
stdout/stderr tails are also redacted.

## Boundary

P3.1 does not introduce Web UI, users, permissions, ORM, MemoryManager,
embedding capability, Tool Registry, multi-agent behavior, diagnosis,
prescription, or treatment-plan output.
