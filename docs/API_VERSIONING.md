# API Versioning

Generated: 2026-06-19

P3.4 adds a minimal API versioning and contract freeze layer for the current local prototype. It does not add medical business capability, a user system, auth, ORM, Web UI, embeddings, multi-agent behavior, or production deployment infrastructure.

## Current Version Policy

- API version: `v1`
- Contract status: `frozen`
- Stage: `P3.4`
- Source constants: `app/api/versioning.py`

The version constants are static code constants. They do not depend on environment variables, do not read secrets, and can be reused by API routes, scripts, tests, and gate checks.

## Public API Surface

The current public v1-compatible API surface is:

| Method | Path | Request model | Response model | Status | Contract |
| --- | --- | --- | --- | --- | --- |
| GET | `/health` | none | `HealthResponse` | 200 | frozen health contract |
| GET | `/version` | none | `VersionResponse` | 200 | additive P3.4 metadata endpoint |
| POST | `/sessions` | `CreateSessionRequest` | `CreateSessionResponse` | 200 | frozen P1/P2 contract |
| POST | `/sessions/{session_id}/turn` | `TurnRequest` | `TurnResponse` | 200 | frozen P1/P2 contract |
| GET | `/sessions/{session_id}/state` | none | `SessionStateResponse` | 200 | frozen P1/P2 contract |
| GET | `/sessions/{session_id}/report` | none | `SessionReportResponse` | 200 | frozen P1/P2 contract |

The source of truth for the P1/P2 body contract remains `artifacts/p1_api_contract_snapshot.json`. P3.4 adds a version-aware route snapshot at `artifacts/p3_4_api_contract_snapshot.json`.

## Unversioned Endpoint Relationship To v1

P3.4 freezes the existing unversioned endpoints as the current v1-compatible public API surface. Existing clients may continue to call `/health`, `/sessions`, `/sessions/{session_id}/turn`, `/sessions/{session_id}/state`, and `/sessions/{session_id}/report` without changing paths.

P3.4 freezes current public API as v1-compatible surface. Physical /api/v1 aliases are deferred unless needed by downstream clients.

## `/api/v1` Alias Policy

No physical `/api/v1/...` aliases are added in P3.4. Deferring aliases keeps the contract layer minimal and avoids duplicating route inventory before downstream clients require versioned paths. Future aliases are allowed only as non-breaking additive changes that retain the original unversioned endpoints and preserve response body contracts.

## `/version` Endpoint

`GET /version` is added as a read-only metadata endpoint. It returns:

```json
{
  "service": "TCM-Assistant",
  "api_version": "v1",
  "stage": "P3.4",
  "contract_status": "frozen"
}
```

This endpoint is not a diagnosis capability statement. It does not expose local paths, environment variable values, API keys, `.env` content, or private runtime data.

## Header Policy

P3.2 introduced `X-Request-ID` as an additive tracing header. P3.4 adds `X-API-Version: v1` as an additive version header.

Headers must not change response bodies. Missing or ignored headers must not make core API behavior fail. Existing response body schemas remain frozen even when headers are present.

## breaking change policy

The following are breaking changes for the frozen public contract:

- delete public endpoint
- change existing endpoint method
- change existing endpoint path
- remove existing response body field
- change response field type
- change optional field to required
- change existing error semantics
- change SQLite schema in a way that breaks historical sessions
- turn assistant intake output into diagnosis, prescription, or treatment plan output

## non-breaking additive change policy

The following are allowed as non-breaking additive changes when they preserve existing clients:

- add endpoint
- add optional response field
- add response header
- add optional request field
- add artifact
- add check script
- add documentation
- add versioned alias while retaining original endpoint and response body contract

## Response Body Freeze Policy

The existing P1/P2 response body contract is frozen. Required top-level fields from `artifacts/p1_api_contract_snapshot.json` must not be removed, renamed, or changed to incompatible types. `GET /health` remains exact. Error responses keep the top-level `error` object and nested `code`, `message`, and `details` fields.

## SQLite Schema Compatibility

P3.4 does not change the SQLite schema. A schema change is breaking if it makes historical sessions, session states, turns, schema metadata, or report snapshots unreadable by the current local API.

## Safety Boundary

The API remains an assistant intake and risk提示 helper. It is explicitly 不诊断 / 不开方 / 不替代医生 / 高风险提示线下就医. It must not output diagnosis, prescription, or treatment-plan content as an API versioning side effect.

## P3.5 RC Gate Usage

P3.5 can use `scripts/check_api_contract.py`, `artifacts/p3_4_api_contract_snapshot.json`, and `artifacts/p3_4_api_contract_check.json` as the baseline for release-candidate contract validation. Any future route addition must be compared against this snapshot and classified as breaking or non-breaking additive before it enters an RC gate.