# Local Runbook

Generated: 2026-06-17

This runbook is the local operator entrypoint for P1 and P2 validation. Default
tests use temporary SQLite databases and do not require a real LLM key.

## Environment

Use Python's built-in `unittest`; do not require pytest for the local gates.

Optional SQLite override on PowerShell:

```powershell
$env:TCM_API_DB_PATH=".runtime\tcm_assistant.sqlite3"
```

Optional SQLite override on bash:

```bash
export TCM_API_DB_PATH=./.runtime/tcm_assistant.sqlite3
```

If `TCM_API_DB_PATH` is not set, the API uses `.runtime/tcm_assistant.sqlite3`.

P3.1 runtime config defaults:

```text
TCM_RUNTIME_MODE=local
TCM_RUNTIME_DIR=.runtime
TCM_ARTIFACTS_DIR=artifacts
TCM_ALLOW_REAL_LLM=false
TCM_LOG_LEVEL=INFO
TCM_REDACT_LOGS=true
TCM_CONFIG_STRICT=false
```

`OPENAI_API_KEY` is checked only as present or absent. The value is never
printed in runtime config summaries.

## Operational Modes

- `local`: default local API mode. Uses `.runtime/tcm_assistant.sqlite3` unless
  `TCM_API_DB_PATH` is set.
- `test`: test mode. Use a temporary DB path through `TCM_API_DB_PATH` or a
  test helper.
- `demo`: controlled local demo mode. Demo outputs must remain redacted.
- `eval`: case corpus, long-session, and gate evaluation mode. Prefer temporary
  DBs or explicit `--db` paths.

Check config before running a local handoff:

```bash
python scripts/check_runtime_config.py --json --output artifacts/p3_1_runtime_config.json
```

CLI `--db` takes priority over `TCM_API_DB_PATH`; `TCM_API_DB_PATH` takes
priority over `.runtime/tcm_assistant.sqlite3`.

## Observability

P3.2 structured log events are emitted through `app/api/observability.py`.
Events are JSON-compatible and redacted. The API reads or generates
`X-Request-ID` and returns it as a response header without changing response
bodies.

Check observability before a local handoff:

```bash
python scripts/check_observability.py --json --output artifacts/p3_2_observability.json
```

Do not log full raw request bodies, full raw user input, real secrets, or
external credentials.

## Start The API

```bash
uvicorn app.api.main:app --reload
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

`GET /health` must keep the exact P1.1 success response documented in
`docs/API_CONTRACT.md`.

## Gates

Run the P1 gate:

```bash
python scripts/run_p1_gate.py --output artifacts/p1_gate_result.json
```

Run the P2 delivery gate:

```bash
python scripts/run_p2_gate.py --output artifacts/p2_gate_result.json
```

Fast local P2 gate without the long-session demo:

```bash
python scripts/run_p2_gate.py --skip-long-session --output artifacts/p2_gate_result.json
```

The P2 gate wraps `runtime_config_check`, `observability_check`, the P1 gate,
`python -m unittest discover -s tests`, case corpus evaluation, long-session
reliability, secret scan, and `git diff --check`.

## Individual Commands

Run all tests:

```bash
python -m unittest discover -s tests
```

Run the case corpus:

```bash
python scripts/run_case_corpus_eval.py artifacts/eval_cases/ --output artifacts/p2_case_corpus_eval.json
```

Run the long-session demo:

```bash
python scripts/run_long_session_demo.py --turns 50 --sessions 3 --output artifacts/p2_4_long_session_reliability.json
```

Run the secret scan:

```bash
python scripts/secret_scan.py --json --output artifacts/secret_scan_result.json
```

Run whitespace checks:

```bash
git diff --check
```

On Windows, `git diff --check` may print LF/CRLF warnings. Treat the command
exit code as the gate result.

## Persistence Demo

```bash
python scripts/run_api_persistence_demo.py
```

## Replay

```bash
python scripts/replay_api_case.py artifacts/replay_cases/p1_4_basic_consultation_replay.json --json
```

## Inspect SQLite

```bash
python scripts/inspect_sqlite_store.py --db .runtime/tcm_assistant.sqlite3 --json
```

The inspect script summarizes session count, turn count, report count, and the
latest update time. It does not print full turns by default.

## Audit Session

```bash
python scripts/audit_session.py --db .runtime/tcm_assistant.sqlite3 --session <session_id> --check-state --json
```

The audit script summarizes long sessions and can include P2.2 state validation
and P2.3 report validation data without leaking secret-like input.

## Cleanup

Remove local runtime files when a clean slate is needed:

```powershell
Remove-Item -Recurse -Force .runtime
```

Do not commit SQLite database, WAL, SHM, log, or local environment files.

## Boundary

Local validation confirms persistence, replay, state consistency, report safety,
and delivery automation only. It does not introduce MemoryManager, embeddings,
tool registry, multi-agent workflow, Web UI, users, permissions, ORM, diagnosis,
prescription, or treatment-plan behavior.
