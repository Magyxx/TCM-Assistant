# P1-F3 Tool Audit Trace

P1-F3 connects internal tool invocation audit records to session trace evidence.

## Behavior

- `/tools/{tool_name}/invoke` generates one `trace_id` per tool call.
- The same `trace_id` is returned in the response, written into the tool `audit_log`, and persisted as a session `trace_event` when `session_id` is supplied.
- Tool audit logs also include the current request id when invoked through HTTP middleware.
- Side-effect tools such as `export_report_tool` remain blocked unless `approved=true`.
- Tool payloads in responses, audit logs, and trace events remain redacted.

## Compatibility

P1-F3 is additive. It does not add required API fields, change `/health`, require a real LLM, or introduce an external tool runtime.

## Artifact

`scripts/verify_p1_f3_tool_audit_trace.py` writes `artifacts/p1_f3_tool_audit_trace_validation.json`.
