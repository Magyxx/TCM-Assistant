# API Contract Freeze

## Contract Rule

The legacy v1 API contract is frozen. P7 and P8 work must preserve the existing
top-level response body shape for the stable public endpoints:

- `POST /sessions`
- `POST /sessions/{session_id}/turn`
- `GET /sessions/{session_id}/state`
- `GET /sessions/{session_id}/report`
- `POST /sessions/{session_id}/report`
- `GET /health`
- `GET /version`

The source of truth for the original body contract remains:

- `docs/API_CONTRACT.md`
- `docs/API_VERSIONING.md`
- `artifacts/p1_api_contract_snapshot.json`
- `artifacts/p3_4_api_contract_snapshot.json`

## Pollution Guard

P7/P8 fields must not be added casually to legacy top-level response bodies.
This specifically includes:

- trace internals
- storage status internals
- tool-call internals
- RAG evidence internals
- memory layer internals
- agent workflow planning fields
- experimental extractor diagnostics

Allowed carriers for new operational data:

- existing `metadata` fields where backward compatible
- additive endpoints such as `/sessions/{session_id}/trace`
- additive endpoints such as `/sessions/{session_id}/evidence`
- persisted trace/evidence storage
- validation artifacts under `artifacts/`
- logs with redaction

## Additive P7 Endpoints

P7 may expose additive endpoints for operational inspection:

- `GET /sessions/{session_id}`
- `GET /sessions/{session_id}/trace`
- `GET /sessions/{session_id}/evidence`
- `GET /tools`
- `POST /tools/{tool_name}/invoke`
- `POST /eval/p7`

These endpoints must not change the stable P1/P3 response body contract.

## Safety Contract

The API remains an inquiry assistant. No API version may convert the product
into a diagnosis, prescription, treatment-planning, or clinician-replacement
system as an implementation side effect.

## Breaking Changes

The following are breaking changes:

- removing a stable endpoint
- changing a stable endpoint path or method
- removing, renaming, or changing type of required response fields
- changing the exact `GET /health` body
- changing handled error shape away from top-level `error`
- requiring a real LLM key for local gate validation
- making historical persisted sessions unreadable
- adding diagnosis, prescription, or treatment-plan content to stable outputs

## P7.5 Requirement

P7.5 branch contract, extractor contract, and LangGraph skeleton work must use
this document as a gate input. New branch/skeleton fields should be designed as
internal or additive surfaces until explicitly promoted through a future
contract review.
