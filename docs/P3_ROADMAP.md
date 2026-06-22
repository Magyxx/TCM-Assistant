# P3 Roadmap

Generated: 2026-06-18

## Purpose

This roadmap defines the recommended P3 production-readiness path after the
passed P2 Final Gate. P3.1 runtime config and P3.2 observability are now
implemented; later P3 phases remain separately scoped.

## Global P3 Boundaries

P3 must preserve:

- P1.1 endpoint paths and success response contracts
- `/health` exact P1.1 contract
- P1.2-P1.6 behavior
- P2.0-P2.5 behavior
- P2 Final Gate status
- default validation without a real LLM key
- secret redaction
- inquiry-information safety boundary

P3 must not add by default:

- diagnosis output
- prescription output
- treatment-plan output
- ORM
- MemoryManager
- new embedding capability
- Tool Registry
- multi-agent system
- Web UI
- user or permission system
- committed real secrets

## P3.1 Runtime Config & Operational Modes

Status: implemented in P3.1.

Goal: make runtime behavior explicit and preflightable without changing API
contracts.

Allowed work:

- configuration governance
- environment variable validation
- startup preflight checks
- local/test/demo/eval operational modes
- documented config defaults
- clear failure messages for missing optional dependencies

Boundaries:

- no user system
- no permission system
- no API success contract change
- no real LLM key as a default gate dependency
- no new diagnosis, prescription, or treatment-plan behavior

Suggested outputs:

- `docs/RUNTIME_CONFIG.md`
- `scripts/check_runtime_config.py`
- runtime config unit and script tests
- `docs/P3_1_RUNTIME_CONFIG_REPORT.md`
- `artifacts/p3_1_runtime_config.json`

P3.1 does not implement P3.3 packaging, P3.4 API versioning, or P3.5
release-candidate gate composition.

## P3.2 Observability & Redacted Logging

Status: implemented in P3.2.

Goal: add auditable local operational traces without storing sensitive raw
inputs by default.

Allowed work:

- structured logs
- request/session/report audit events
- redacted logs
- error trace summaries
- correlation IDs where they do not alter contracts
- local-only log examples

Boundaries:

- do not log complete sensitive input by default
- do not introduce an external logging platform as a default dependency
- do not store secrets
- do not alter API success contracts

Suggested outputs:

- `docs/OBSERVABILITY.md`
- `scripts/check_observability.py`
- observability unit and script tests
- `docs/P3_2_OBSERVABILITY_REPORT.md`
- `artifacts/p3_2_observability.json`

P3.2 does not implement P3.3 packaging, P3.4 API versioning, or P3.5
release-candidate gate composition.

## P3.3 Release Packaging & Reproducibility

Goal: make local delivery repeatable and reviewable.

Allowed work:

- release manifest
- dependency list
- local reproducible run instructions
- artifact package definition
- offline acceptance guide
- checksums or file inventory where useful

Boundaries:

- no large deployment system as a default dependency
- no external secret requirement for acceptance
- no Web UI
- no user or permission system

Suggested outputs:

- release manifest
- packaging guide
- offline acceptance guide
- P3.3 report and artifact

## P3.4 API Versioning & Compatibility

Goal: define how API compatibility is preserved as future additions arrive.

Allowed work:

- API version policy
- contract compatibility check
- deprecated field policy
- backward-compatible addition rules
- compatibility report

Boundaries:

- do not break P1.1 contract
- do not remove existing required fields
- do not change `/health` exact P1.1 response
- do not introduce incompatible success response changes

Suggested outputs:

- API version policy doc
- compatibility test or gate extension
- P3.4 report and artifact

## P3.5 Release Candidate Gate

Goal: compose P1/P2/P3 checks into a release-candidate validation baseline.

Allowed work:

- P3 gate composition
- P1/P2/P3 checks
- delivery bundle validation
- final RC report
- UAT-ready backend baseline

Boundaries:

- do not bypass P1/P2 gates
- do not require real LLM keys by default
- do not include real secrets
- do not add unscoped product capability

Suggested outputs:

- P3 gate runner, only after real P3.1-P3.4 checks exist
- RC report
- RC artifact
- delivery bundle manifest

## Sequencing

Recommended sequence:

1. P3.1 Runtime Config & Operational Modes
2. P3.2 Observability & Redacted Logging
3. P3.3 Release Packaging & Reproducibility
4. P3.4 API Versioning & Compatibility
5. P3.5 Release Candidate Gate

Each phase should include its own report, artifact, boundary check, and
validation result before proceeding.
