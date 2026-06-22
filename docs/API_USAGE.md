# API Usage

## RAG Health
`GET /rag/health`

Returns RAG mode, chunk count, retriever availability, index directory, and chunks path.

## RAG Search
`POST /rag/search`

```json
{
  "query": "chest pain breathing difficulty red flag",
  "top_k": 5,
  "mode": "hybrid"
}
```

## Session RAG Search
`POST /sessions/{session_id}/rag/search`

Builds a sanitized query from current session state and retrieves evidence.

## Report Export
`POST /sessions/{session_id}/report/export`

```json
{
  "format": "markdown"
}
```

Supported formats are `json`, `markdown`, and `summary_markdown`. Exports go to `artifacts/p10m2/exports`.

## Safety Redteam
`POST /safety/redteam`

Runs deterministic local safety cases without real LLM calls.

## Final Eval
`POST /eval/final`

Runs or loads P10M2 final eval metrics.

