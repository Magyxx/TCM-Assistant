# P7 Release Freeze

Status date: 2026-06-22

## Freeze Summary

P7 is frozen as a functional-complete local baseline for the service, storage,
memory, tools, observability, safety, and gate layers.

Current release state:

- Phase: P7
- Gate status: `caution`
- Functional status: complete for non-Docker local validation
- Sole current caution: Docker CLI is unavailable on this machine
- Docker metrics: `docker_runtime_available=false`, `docker_smoke_pass=false`

This is not a feature failure. It is an environment limitation recorded by the
gate and preserved in artifacts.

## Completed Scope

- FastAPI P7 endpoints and additive P7 read surfaces
- SQLite persistence for sessions, turns, states, final reports, risk events,
  RAG evidence, audit logs, eval runs, trace events, and memory snapshots
- PostgreSQL schema-ready adapter
- Four-layer memory manager
- Internal tool registry with permission and audit checks
- RAG evidence persistence and report-use distinction
- Structured P7 trace schema and storage
- Report safety validation
- P7 failure analysis
- P5, P6, P6B, P6C, and code-health regression coverage

## Frozen Safety Boundary

The system remains an inquiry-information assistant. It must not diagnose,
prescribe, replace clinicians, or turn RAG/tool output into treatment decisions.

P7 evidence and trace fields are operational support data. They are not medical
judgment fields and must not change the frozen public response contract.

## Validation Baseline

Recorded baseline:

```bash
python -m unittest discover -s tests
python -m compileall -q app scripts tests
python scripts/run_p7_gate.py
```

Expected local result on the current machine:

- `unittest`: pass, 333 tests
- `compileall`: pass
- `run_p7_gate.py`: writes `artifacts/p7_gate_report.json`, exits non-zero
  because Docker smoke is unavailable
- `p7_gate_status`: `caution`

## Source-Of-Truth Artifacts

- `artifacts/p7_gate_report.json`
- `artifacts/p7_docker_smoke.json`
- `artifacts/p7_failure_analysis.json`

Supporting P7 artifacts:

- `artifacts/p7_api_validation.json`
- `artifacts/p7_storage_validation.json`
- `artifacts/p7_memory_validation.json`
- `artifacts/p7_tool_registry_validation.json`
- `artifacts/p7_observability_validation.json`
- `artifacts/p7_safety_validation.json`
- `artifacts/p7_trace_samples.json`

## Release Markers

Recommended commit:

```bash
git commit -m "freeze: P7 service storage memory tools observability gate"
```

Recommended caution tag:

```bash
git tag v0.7.0-p7-caution
```

After Docker smoke passes on a Docker-capable machine:

```bash
git tag v0.7.0-p7-ok
```

## Next Phase

The next phase should be P7.5, not broad P8 development. P7.5 should focus on
branch contract, extractor contract, and LangGraph skeleton work that preserves
the frozen P7 API and safety boundary.
