# Observability

## P1-F0 Event Contract

P1-F0 events use a single-line JSON structure:

```json
{
  "trace_id": "trace-...",
  "session_id": "...",
  "turn_id": "...",
  "event_type": "...",
  "component": "...",
  "status": "ok",
  "latency_ms": 0,
  "metadata": {}
}
```

Default logs should not include raw sensitive text. Use redacted text, hashes, `fallback_used`, `risk_rule_ids`, and `evidence_count` style metadata instead.

Generated: 2026-06-18

## P3.2 Goal

P3.2 adds a minimal, local, redacted observability layer. It gives API runs,
demos, evals, and gates stable structured events for request/session/turn
tracing without changing API response bodies, SQLite schema, or the
inquiry-information safety boundary.

This is not a monitoring platform. P3.2 does not add Prometheus, Grafana,
OpenTelemetry, Sentry, ELK, LangSmith, Langfuse, or an external log service.

## Module

Observability lives in:

```text
app/api/observability.py
```

Primary helpers:

- `make_log_event(...)`
- `emit_log_event(...)`
- `log_event(...)`
- `redact_observable_value(...)`
- `generate_request_id()`
- `normalize_request_id(...)`

## Event Structure

Every structured event is a JSON-compatible dict with stable fields:

- `ts`
- `level`
- `event`
- `runtime_mode`
- `request_id`
- `session_id`
- `turn_id`
- `component`
- `status`
- `duration_ms`
- `message`
- `extra`

`RuntimeConfig.log_level` controls whether an event is emitted. Events default
to stderr/stdout-style local output and are not written to a persistent log file
by default.

## Redaction Rules

P3.2 redacts:

- `OPENAI_API_KEY`
- `sk-...` key-like values
- sensitive key names and values containing `api_key`, `password`, `secret`,
  `token`, `authorization`, or `cookie`
- nested dict/list values
- long text fields
- raw user input, which is truncated and redacted rather than logged in full

When `TCM_REDACT_LOGS=true`, redaction is mandatory. When
`TCM_REDACT_LOGS=false`, secret-like values and sensitive key names are still
redacted. Key presence booleans such as `openai_api_key_present=true/false` may
be recorded.

## Tracing IDs

The API middleware reads `X-Request-ID` when present or generates a request id.
It returns `X-Request-ID` as a response header without modifying response
bodies.

Event usage:

- `request_id`: correlates one HTTP request and internal events.
- `session_id`: correlates API session lifecycle and persistence events.
- `turn_id`: correlates persisted turn writes and turn completion.

P1-F3 extends the same correlation rule to internal tool calls: `/tools/{tool_name}/invoke` returns a `trace_id`, stores that id in the tool audit log, and persists a `tool.invoke` trace event when `session_id` is provided.

## Allowed Logging

Allowed:

- method, path, status code, duration
- request/session/turn ids
- status strings and error type names
- turn count, state version, report-ready boolean
- runtime mode and component names
- redacted/truncated diagnostic summaries

Forbidden:

- full raw request body by default
- full raw user input by default
- real API keys, tokens, cookies, passwords, or secrets
- diagnosis, prescription, or treatment-plan output
- local secrets in artifacts

## RuntimeConfig Relationship

P3.2 builds on P3.1 RuntimeConfig:

- `runtime_mode` is included in every event.
- `log_level` controls event emission.
- `redact_logs` controls redaction strictness, while secrets remain protected
  even when it is false.

## Checks

Run:

```bash
python scripts/check_observability.py --json --output artifacts/p3_2_observability.json
```

The current gate also runs this as `observability_check`.

## Future Extensions

P3.3 may package these artifacts for reproducible delivery. P3.4 may define
compatibility policy around headers such as `X-Request-ID`. P3.5 may compose a
release-candidate gate. P3.2 does not implement those later phases.
