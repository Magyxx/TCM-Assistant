# Tool Registry

P1-F0 uses an internal Python tool registry, not an MCP server.

## Tool Spec

Each tool records:

- `name`
- `description`
- `input_schema`
- `output_schema`
- `permission_level`
- `side_effect`
- `requires_human_approval`

## Registered Tools

- `risk_check_tool`: read-only deterministic risk rules, no LLM.
- `rag_search_tool`: read-only BM25/static evidence path, returns an EvidencePack and cannot mutate core RunState fields.
- `report_safety_tool`: read-only report boundary checks.
- `export_report_tool`: medium permission; file writes are approval-gated and default behavior returns a redacted payload.

Unknown tools return `tool_not_found`. Side-effect tools must expose `requires_human_approval`.

## P1-F3 Audit Trace

Tool invocation responses include an audit log with the same `trace_id` as the response. When a `session_id` is supplied, the audit record is persisted and a matching `tool.invoke` trace event is available through `/sessions/{session_id}/trace`. Payloads remain redacted.
