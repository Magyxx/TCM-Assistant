# P3.4 API Versioning Report

Generated: 2026-06-19

## Added Files

- `app/api/versioning.py`
- `scripts/check_api_contract.py`
- `tests/test_p3_4_api_versioning.py`
- `tests/test_p3_4_api_contract_script.py`
- `docs/API_VERSIONING.md`
- `docs/P3_4_API_VERSIONING_REPORT.md`
- `artifacts/p3_4_api_versioning.json`
- `artifacts/p3_4_api_contract_snapshot.json`
- `artifacts/p3_4_api_contract_check.json`

## Modified Files

- `app/api/main.py`
- `app/api/models.py`
- `scripts/run_p2_gate.py`
- `tests/test_p2_5_p2_gate_runner.py`
- `tests/test_p3_2_observability_script.py`
- `tests/test_p3_3_release_packaging.py`

## P3.4 API Versioning Summary

P3.4 freezes the current P1/P2 public API as a v1-compatible surface. It adds static version constants, an additive `X-API-Version` response header, an additive read-only `/version` endpoint, a route/body contract snapshot, a contract check script, tests, docs, and P2 gate integration.

## API Version Policy Summary

`app/api/versioning.py` defines `API_VERSION = "v1"`, `API_CONTRACT_STATUS = "frozen"`, and `API_STAGE = "P3.4"`. These values are static and do not require environment variables or secrets.

## Public Endpoint Snapshot Summary

`artifacts/p3_4_api_contract_snapshot.json` records 6 public endpoints: `GET /health`, `GET /version`, `POST /sessions`, `POST /sessions/{session_id}/turn`, `GET /sessions/{session_id}/state`, and `GET /sessions/{session_id}/report`.

## Contract Freeze Rules Summary

Breaking changes include deleting public endpoints, changing existing methods or paths, removing response fields, changing field types, making optional fields required, changing error semantics, breaking SQLite historical session compatibility, or changing assistant intake output into diagnosis/prescription/treatment-plan output.

Non-breaking additive changes include new endpoints, optional response/request fields, response headers, artifacts, check scripts, docs, and future versioned aliases that keep original endpoints.

## Header Policy Summary

P3.2 `X-Request-ID` remains supported. P3.4 adds `X-API-Version: v1`. Both are additive headers and do not change response bodies.

## `/version` Endpoint Summary

`GET /version` returns service metadata only: service name, API version, stage, and contract status. It does not expose paths, secrets, `.env` content, environment values, or medical capability claims.

## `/api/v1` Alias Summary

No physical `/api/v1/...` aliases are added in P3.4. The unversioned endpoints are frozen as v1-compatible, and aliases are deferred until downstream clients need them.

## `check_api_contract.py` Output Summary

Final P3.4 check output: `status=ok`, `api_version=v1`, `contract_status=frozen`, `checks_passed=16/16`, `public_endpoint_count=6`, `recommend_next=P3.5`.

## `run_p2_gate.py` Integration Summary

`api_contract_check` is integrated into `scripts/run_p2_gate.py` after `release_packaging_check`. The gate phase is updated to P3.4, reports 10/10 checks, and recommends P3.5 on success. A dedicated `run_p3_gate.py` remains deferred to the P3.5 RC gate.

## `p3_4_api_versioning.json` Summary

The manifest records P3.4 status, API version, contract status, endpoint count, supported version headers, `/version` support, deferred versioned aliases, contract snapshot creation, P2 gate integration, validation summaries, and boundary flags.

## `p3_4_api_contract_snapshot.json` Summary

The snapshot records route metadata, request/response model names, response top-level fields, status codes, headers, breaking/non-breaking rules, and the frozen P1/P2 contract metadata. It uses relative metadata only and contains no local absolute paths or secrets.

## Validation Results

- `python scripts/check_runtime_config.py`: ok, P3.1, 0 warnings, 0 errors
- `python scripts/check_observability.py`: ok, P3.2, 9 checks, structured logging and redaction enabled
- `python scripts/check_release_packaging.py`: ok, P3.3, 12/12 checks
- `python scripts/check_api_contract.py`: ok, P3.4, 16/16 checks
- `python scripts/run_p1_gate.py`: ok, 13/13 checks
- `python scripts/run_p2_gate.py`: ok, current gate phase P3.4, 10/10 checks, recommends P3.5
- `python scripts/run_case_corpus_eval.py`: ok, 12/12 cases
- `python scripts/run_long_session_demo.py`: ok, 3 sessions x 50 turns, `secret_found=false`
- `python scripts/secret_scan.py`: ok, 0 findings, 15 allowlisted synthetic findings, 225 files scanned
- `python -m unittest discover -s tests -p "test*.py"`: ok, 246 tests
- `python -m unittest discover`: ok, 0 tests discovered; this is not treated as full discovery
- `git diff --check`: ok, exit code 0; Windows LF/CRLF warnings only

## Contract And Schema

- P1/P2 contract changed: no
- API response body schema changed: no
- SQLite schema changed: no
- Boundary violated: no

## Known Limitations

P3.4 does not add `/api/v1` physical aliases, authentication, user management, Web UI, production monitoring, CI/CD, or a P3.5 RC gate. It freezes and documents the current local API contract only.

## Recommendation

Recommend entering P3.5 RC gate preparation with `artifacts/p3_4_api_contract_snapshot.json` and `scripts/check_api_contract.py` as the contract baseline.