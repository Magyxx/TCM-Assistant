# P7 API Reference

## Existing Stable Endpoints
- `GET /health`
- `GET /version`
- `POST /sessions`
- `POST /sessions/{session_id}/turn`
- `GET /sessions/{session_id}/state`
- `GET /sessions/{session_id}/report`
- `POST /sessions/{session_id}/report`

## P7 Additive Endpoints
- `GET /sessions/{session_id}` returns session metadata.
- `GET /sessions/{session_id}/trace` returns persisted P7 trace events.
- `GET /sessions/{session_id}/evidence` returns retrieved and used RAG evidence.
- `GET /tools` returns internal tool metadata.
- `POST /tools/{tool_name}/invoke` invokes an approved internal tool surface.
- `POST /eval/p7` records a P7 eval run.

## Response Contract
The legacy v1 response bodies remain frozen. P7 trace/status data must not
pollute the stable top-level bodies for `/sessions`, `/turn`, `/state`, or
`/report`.

P7 operational data is allowed only through backward-compatible carriers:

- existing `metadata` fields where compatible
- additive P7 endpoints such as `/sessions/{session_id}/trace`
- additive P7 endpoints such as `/sessions/{session_id}/evidence`
- persisted trace/evidence storage
- validation artifacts

`/health` and `/version` keep the frozen v1 response body unchanged for
backward compatibility.

## Safety
Responses are redacted for secrets and do not expose internal P6/P7 metadata that could be confused with user-facing diagnosis or prescription content.
