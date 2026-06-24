FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV EXTRACTOR_BACKEND=fake
ENV ENABLE_REAL_LLM=false
ENV SESSION_STORE_BACKEND=sqlite
ENV SESSION_SQLITE_PATH=/app/artifacts/p10m2/p10m2_sessions.sqlite3
ENV API_LOG_PATH=/app/artifacts/p10m2/api_events.jsonl
ENV RAG_MODE=hybrid
ENV RAG_CHUNKS_PATH=/app/knowledge/processed/chunks.jsonl
ENV REPORT_EXPORT_DIR=/app/artifacts/p10m2/exports

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health?extended=true', timeout=3).read()"
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
