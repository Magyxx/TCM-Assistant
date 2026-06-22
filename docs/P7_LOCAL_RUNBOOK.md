# P7 Local Runbook

## Environment
Copy `.env.example` values or set:

```bash
TCM_ENV=local
TCM_DB_BACKEND=sqlite
TCM_SQLITE_PATH=data/tcm_assistant.sqlite3
TCM_RAG_INDEX_PATH=knowledge/indexes/p6_bm25_index.json
TCM_CHUNKS_PATH=knowledge/processed/p6_chunks.jsonl
TCM_LLM_MODE=fake|real_llm
TCM_TRACE_DIR=artifacts/traces
TCM_LOG_LEVEL=INFO
```

## Run API

```bash
uvicorn app.api.main:app --host 127.0.0.1 --port 8000
```

## Docker

```bash
docker compose up api
```

If Docker CLI is unavailable, `scripts/run_p7_docker_smoke.py` records that as an explicit failure/caution instead of marking runtime success.

## Validation

```bash
python scripts/run_p7_gate.py
python -m unittest discover -s tests
python -m compileall -q app scripts tests
```

Artifacts are written under `artifacts/`, including `p7_gate_report.json` and P7 validation detail files.
