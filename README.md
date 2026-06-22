# TCM-Assistant

TCM-Assistant is a structured inquiry assistant for traditional Chinese
medicine intake workflows. It helps collect and organize chief complaint,
timeline, accompanying symptoms, sleep, diet, stool/urine, risk signals, and
missing follow-up information. It is not a diagnosis system, does not replace
a clinician, and does not prescribe treatment.

The long-term target is a controlled agentic workflow built with LangGraph,
Pydantic, hybrid RAG, layered memory, an internal tool registry, safety rules,
evaluation gates, FastAPI, and Docker.

## Current Status

Current phase: P7 release freeze.

P7 is functional complete for the non-Docker local baseline. The current gate
status is `caution`, not a feature failure. The only current caution is that the
local machine does not provide a Docker CLI, so Docker runtime smoke cannot be
executed:

- `docker_runtime_available=false`
- `docker_smoke_pass=false`
- `artifacts/p7_docker_smoke.json` records `docker CLI not found`

All non-Docker P7 validation is complete:

- FastAPI P7 endpoints
- SQLite persistence
- PostgreSQL schema-ready adapter
- Four-layer `MemoryManager`
- Internal tool registry
- RAG evidence persistence
- Structured trace persistence
- Report safety checks
- P5/P6/P6B/code-health regression path
- API/storage/memory/tool/observability/safety/failure-analysis validations

Latest recorded local baseline:

```text
python -m unittest discover -s tests       # 333 tests passed
python -m compileall -q app scripts tests  # passed
python scripts/run_p7_gate.py              # status caution, Docker-only smoke pending
```

The P7 source-of-truth artifacts are:

- `artifacts/p7_gate_report.json`
- `artifacts/p7_docker_smoke.json`
- `artifacts/p7_failure_analysis.json`

## Safety Boundary

TCM-Assistant is limited to inquiry assistance and structured summarization.
It must not:

- output a definitive diagnosis
- replace a doctor or offline medical evaluation
- prescribe medication, formulas, dosage, or treatment plans
- use RAG evidence to mutate core inquiry state such as chief complaint,
  duration, or risk status
- expose secrets, private runtime paths, raw private patient data, or model
  training caches

High-risk signals should be surfaced as safety/risk guidance and appropriate
offline-care prompts, not as diagnosis or treatment decisions.

## API Contract Freeze

The historical P1/P3 v1 API contract is frozen. Existing top-level response
bodies for `/sessions`, `/turn`, `/state`, and `/report` must not be polluted by
P7/P8 implementation fields. New trace/status data must be carried through
`metadata`, additive endpoints, persisted trace/evidence queries, or artifacts.

The exact P1.1 `/health` body remains part of the frozen compatibility surface.
Historical delivery gates are still documented and kept runnable for regression
checks:

```bash
python scripts/run_p1_gate.py
python scripts/run_p2_gate.py --output artifacts/p2_gate_result.json
```

See:

- `docs/API_CONTRACT.md`
- `docs/API_VERSIONING.md`
- `docs/API_CONTRACT_FREEZE.md`
- `docs/P7_API_REFERENCE.md`
- `docs/LOCAL_RUNBOOK.md`
- `docs/EVAL_CASES.md`
- `docs/P2_DELIVERY_REPORT.md`

## P7 Release Docs

- `docs/P7_RELEASE_FREEZE.md`
- `docs/P7_GITHUB_UPLOAD_CHECKLIST.md`
- `docs/API_CONTRACT_FREEZE.md`
- `docs/ARTIFACTS_POLICY.md`
- `docs/BRANCHING_POLICY.md`
- `docs/P7_LOCAL_RUNBOOK.md`
- `docs/P7_SERVICE_MEMORY_PERSISTENCE_DESIGN.md`
- `docs/P7_STORAGE_SCHEMA.md`
- `docs/P7_MEMORY_MANAGER.md`
- `docs/P7_TOOL_REGISTRY.md`

## Local Validation

Install dependencies, then run:

```bash
python -m unittest discover -s tests
python -m compileall -q app scripts tests
python scripts/run_p7_gate.py
```

`run_p7_gate.py` returns a non-zero exit code while Docker smoke is unavailable.
On a machine with Docker installed, run the same gate again and verify
`docker_smoke_pass=true` before tagging a fully Docker-verified release.

## Runtime

Run the FastAPI service locally:

```bash
uvicorn app.api.main:app --host 127.0.0.1 --port 8000
```

Useful local environment variables:

```text
TCM_ENV=local
TCM_DB_BACKEND=sqlite
TCM_SQLITE_PATH=data/tcm_assistant.sqlite3
TCM_RAG_INDEX_PATH=knowledge/indexes/p6_bm25_index.json
TCM_CHUNKS_PATH=knowledge/processed/p6_chunks.jsonl
TCM_LLM_MODE=fake
TCM_TRACE_DIR=artifacts/traces
TCM_LOG_LEVEL=INFO
```

Docker entrypoints are present, but this local P7 freeze has not run Docker
smoke because Docker CLI is unavailable on the current machine.

## Data And Artifact Policy

Keep release evidence JSON artifacts. Do not commit real patient private data,
`.env` files, local SQLite databases, model weights, LoRA adapters,
checkpoints, training outputs, `wandb`, `mlruns`, or cache directories.

See `docs/ARTIFACTS_POLICY.md` for the freeze policy.

## Branching

Recommended release sequence:

```text
P7 freeze
  -> upload GitHub
  -> P7.5 branch contract / extractor contract / LangGraph skeleton
  -> tag: v0.7.5-branch-contract
      -> dev/p8-agentic-workflow
      -> exp/sft-lora-extractor
```

Recommended P7 freeze git markers:

```bash
git commit -m "freeze: P7 service storage memory tools observability gate"
git tag v0.7.0-p7-caution
```

After Docker smoke passes on a Docker-capable machine:

```bash
git tag v0.7.0-p7-ok
```
