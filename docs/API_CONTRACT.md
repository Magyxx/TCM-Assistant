# API Contract

Generated: 2026-06-17

This document freezes the P1 API contract for the P2.0 baseline. The source of
truth is `artifacts/p1_api_contract_snapshot.json`.

## P1-F0 Additive Foundation API

P1-F0 adds a productization foundation app at `app.api.app:app`. This does not replace the frozen P1.1/P1.4 contract in `app.api.main:app`.

Routes:

- `GET /health`: returns `status`, `app`, `mode`, and `external_dependencies_required=false`.
- `POST /sessions`: creates a local fake/fallback session.
- `POST /turn`: runs fake/fallback extraction and returns schema/risk/missing-field summary.
- `GET /sessions/{session_id}`: returns a session summary.
- `GET /reports/{session_id}`: returns `report_status=not_ready` or a deterministic skeleton.
- `POST /eval/smoke`: runs one local fake/fallback smoke sample.

No route requires uvicorn, real LLM keys, a local LoRA service, embeddings, vectorstore, PostgreSQL, or deployment.

P1-F2 adds optional `evidence_pack` and `report_skeleton` fields to the P1-F0 wrapper turn/report responses. Ready report responses prefer the deterministic P1 report skeleton as `skeleton` when it is available.

P1-F5 adds an optional `report_audit` envelope to productized turn/report responses. This is additive and does not change the frozen legacy success fields.

## Contract Version

- `p1_api_v1`

## Endpoints

### GET /health

Success response is exact and must not change:

```json
{
  "status": "ok",
  "service": "TCM-Assistant",
  "stage": "P1.1",
  "mode": "agentic_workflow",
  "diagnosis_system": false
}
```

### POST /sessions

Request:

```json
{
  "extractor_mode": "real_llm",
  "rag_enabled": true
}
```

`extractor_mode` may be `real_llm`, `fake`, or `fallback`.

Required success fields:

- `session_id`
- `extractor_mode`
- `rag_enabled`
- `created_at`
- `turn_count`

### POST /sessions/{session_id}/turn

Request:

```json
{
  "user_input": "string"
}
```

Required success fields:

- `session_id`
- `turn_id`
- `turn_count`
- `next_question`
- `state`
- `risk_flags_status`
- `risk_rule_ids`
- `risk_reasons`
- `final_report`
- `p1_evidence_pack` (optional, P1-F2 additive)
- `p1_report_skeleton` (optional, P1-F2 additive)
- `report_audit` (optional, P1-F5 additive)
- `metadata`
- `safety_disclaimer`

P1.5 adds `state.state_version` as an additive nested field.

### GET /sessions/{session_id}/state

Required success fields:

- `session_id`
- `turn_count`
- `state`
- `risk_flags_status`
- `risk_rule_ids`
- `missing_core_fields`
- `next_question`
- `metadata`
- `safety_disclaimer`

### GET /sessions/{session_id}/report

Required success fields:

- `session_id`
- `ready`
- `final_report`
- `p1_evidence_pack` (optional, P1-F2 additive)
- `p1_report_skeleton` (optional, P1-F2 additive)
- `report_audit` (optional, P1-F5 additive)
- `missing_core_fields`
- `next_question`
- `safety_disclaimer`

When `ready=false`, `final_report` is `null` and the response may include
missing fields / next question. When `ready=true`, `final_report` is present.

## Error Shape

All handled API errors use:

```json
{
  "error": {
    "code": "SESSION_NOT_FOUND",
    "message": "Session not found.",
    "details": {}
  }
}
```

Known error codes:

- `INVALID_REQUEST`
- `SESSION_NOT_FOUND`
- `STATE_NOT_FOUND`
- `STORE_UNAVAILABLE`
- `STATE_CORRUPTED`
- `TURN_REJECTED`
- `INTERNAL_ERROR`

Error details must be redacted and must not include raw secrets, local absolute
paths, or tracebacks.

## Compatibility Rules For P2

- Required success fields may not be removed or renamed.
- `GET /health` must remain exact.
- New success fields must be backward-compatible and additive.
- Error response must keep the top-level `error` object and nested
  `code/message/details`.
- P2 work must not make a real LLM key required for local gate validation.

## P3.1 Runtime Config Contract Statement

P3.1 adds runtime config loading and preflight checks only. It does not change:

- endpoint paths
- required success fields
- error shape
- exact `GET /health` response
- default no-real-LLM-key gate behavior

## P3.2 Observability Contract Statement

P3.2 adds internal structured logging and request tracing only. It does not
change response bodies or required success fields. The API may return an
`X-Request-ID` response header, generated or copied from the request header, as
an additive tracing header.

P3.2 logs must not contain full raw request bodies, full raw user input, real
API keys, tokens, cookies, passwords, or secrets.

## P2.5 Delivery Gate

`scripts/run_p2_gate.py` treats this contract as frozen delivery input. The
current P3.2-era gate runs runtime config preflight, observability preflight,
the P1 gate, full `unittest` discovery, case corpus evaluation, long-session
reliability, secret scan, and `git diff --check` without changing endpoint paths
or the exact `GET /health` response.

## P7 Freeze Contract Statement

P7 keeps the legacy v1 response bodies frozen. P7 service, storage, memory,
tool registry, RAG evidence, and observability data must not add new operational
fields to the stable top-level bodies for `/sessions`, `/turn`, `/state`, or
`/report`.

New trace/status/evidence data must be carried through compatible `metadata`,
additive endpoints, persisted trace/evidence queries, or artifacts. See
`docs/API_CONTRACT_FREEZE.md` for the P7/P7.5 policy.
