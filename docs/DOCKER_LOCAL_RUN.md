# Docker Local Run

## Start
```bash
docker compose build
docker compose up -d
```

The compose file starts only the FastAPI app. It uses SQLite, fake extractor, local artifacts, local knowledge, and no real LLM key.

## Smoke
```bash
python scripts/docker_smoke_p10m2.py
```

The smoke checks `/health?extended=true`, `/sessions`, `/turn`, `/rag/health`, `/rag/search`, and `/eval/final`.

## Stop
```bash
docker compose down
```

No PostgreSQL, Redis, Qdrant, Milvus, vLLM, GPU, model download, LoRA adapter, or checkpoint is required for P10M2.

