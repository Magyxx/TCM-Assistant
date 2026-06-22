# P3.2 Observability Report

Generated: 2026-06-18

## Goal

P3.2 adds a minimal, testable, redacted observability layer for API requests,
session/turn flow, scripts, and gates. It does not change P1/P2 API response
contracts, the exact P1.1 `/health` body, SQLite schema, or the
inquiry-information safety boundary.

## Added Files

- `app/api/observability.py`
- `scripts/check_observability.py`
- `tests/test_p3_2_observability.py`
- `tests/test_p3_2_observability_script.py`
- `docs/OBSERVABILITY.md`
- `docs/P3_2_OBSERVABILITY_REPORT.md`
- `artifacts/p3_2_observability.json`

## Modified Files

- `README.md`
- `app/api/main.py`
- `app/api/session_runtime.py`
- `scripts/run_case_corpus_eval.py`
- `scripts/run_p2_gate.py`
- `docs/API_CONTRACT.md`
- `docs/LOCAL_RUNBOOK.md`
- `docs/P3_GATE_PLAN.md`
- `docs/P3_ROADMAP.md`

## Feature Summary

- Stable structured log event shape.
- Redaction for sensitive values and sensitive key names.
- Long user text truncation.
- Request start/end/error middleware.
- `X-Request-ID` request/response header support.
- Session, turn, and persistence success/error events.
- `scripts/check_observability.py` preflight and artifact.
- `observability_check` integrated into `scripts/run_p2_gate.py`.

## Structured Event Fields

- `ts`
- `level`
- `event`
- `runtime_mode`
- `request_id`
- `session_id`
- `turn_id`
- `component`
- `status`
- `duration_ms`
- `message`
- `extra`

## Redaction Rules

P3.2 redacts `OPENAI_API_KEY`, `sk-...` style values, sensitive key names and
values for API keys, passwords, secrets, tokens, authorization, and cookies. It
also truncates long text and raw user input summaries. Secrets remain protected
even when `TCM_REDACT_LOGS=false`.

## P2 Gate Integration

`scripts/run_p2_gate.py` includes:

```bash
python scripts/check_observability.py --json --output artifacts/p3_2_observability.json
```

The current gate should report 8/8 checks when all checks pass.

## Initial Validation

- `python -m unittest tests.test_p3_2_observability tests.test_p3_2_observability_script`: `ok`, 15 tests
- `python scripts/check_observability.py --json --output artifacts/p3_2_observability.json`: `ok`

## Final Validation

- `python scripts/check_runtime_config.py`: `ok`
- `python scripts/check_observability.py`: `ok`, 9/9 checks, artifact refreshed
- `python scripts/run_p1_gate.py`: `ok`, 13/13 checks
- `python scripts/run_p2_gate.py`: `ok`, 8/8 checks, includes `observability_check`
- `python scripts/run_case_corpus_eval.py`: `ok`, 12/12 cases
- `python scripts/run_long_session_demo.py`: `ok`, 3 sessions x 50 turns
- `python scripts/secret_scan.py`: `ok`, 0 findings, 15 allowlisted synthetic findings
- `python -m unittest discover`: `ok`, 0 tests discovered by default layout
- `python -m unittest discover -s tests -p "test*.py"`: `ok`, 225 tests
- `git diff --check`: `ok`, exit code 0; Windows LF/CRLF warnings only

## Contract And Boundary

- P1/P2 API response contract changed: no
- `/health` exact P1.1 body changed: no
- Additive `X-Request-ID` header: yes
- SQLite schema changed: no
- Diagnosis output added: no
- Prescription output added: no
- Treatment-plan output added: no
- Web UI, users, permissions, ORM, MemoryManager, embeddings, Tool Registry, or
  multi-agent behavior added: no
- External monitoring/logging platform added: no
- Real LLM key required by default gates: no
- Real secret committed: no

## Known Limits

P3.2 writes local structured events only. It does not provide log retention,
metrics aggregation, dashboards, tracing backends, packaging, API versioning, or
a release-candidate gate.

## Recommendation

Proceed to P3.3 Release Packaging & Reproducibility after final validation
remains green.
