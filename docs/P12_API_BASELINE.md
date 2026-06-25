# P12 API Baseline

The current FastAPI app is imported from `app.api.main:app`. The baseline already
contains the minimum service loop required by P12:

| Surface | Route |
| --- | --- |
| Health | `GET /health`, including `extended=true` readiness details |
| Version | `GET /version` |
| Create session | `POST /sessions` |
| Session detail | `GET /sessions/{session_id}` |
| Submit turn | `POST /sessions/{session_id}/turn` |
| State read | `GET /sessions/{session_id}/state` |
| Turn list | `GET /sessions/{session_id}/turns` |
| Report read | `GET /sessions/{session_id}/report` |
| Report snapshot | `POST /sessions/{session_id}/report` |
| Report export | `POST /sessions/{session_id}/report/export` |
| Replay | `POST /sessions/{session_id}/replay` |
| Eval | `POST /eval/p7`, `POST /eval/p9m2-multiturn`, `POST /eval/final` |
| RAG | `GET /rag/health`, `POST /rag/search`, `POST /sessions/{session_id}/rag/search` |
| Tools and audit | `GET /tools`, `POST /tools/{tool_name}/invoke` |

The service layer already includes consultation, report, eval, export, and P7
runtime helpers. The storage layer includes:

- `app.api.sqlite_store` for the public API session/state/turn/report store.
- `app.storage.sqlite_store` for P7 service, memory, audit, evidence, eval, and trace persistence.
- `app.session.sqlite_store` for replayable graph/session state.
- `app.storage.postgres_store` as a schema-ready PostgreSQL placeholder without a required runtime dependency.

P12 keeps these surfaces and adds explicit regression artifacts around them rather
than replacing the existing modules.
