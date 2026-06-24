# P1-F0 Productization Foundation Plan

P1-F0 turns the verified P8/P10 engineering path into a productization foundation without binding the project to external services.

## Scope

- Add safe runtime settings and `.env.example` defaults.
- Provide a minimal FastAPI foundation app for `/health`, `/sessions`, `/turn`, `/reports/{session_id}`, and `/eval/smoke`.
- Provide a local SQLite demo repository using the standard library.
- Keep internal tools in an audited registry rather than creating an MCP server.
- Define a small RAG EvidencePack contract with a BM25 stub and disabled/skipped behavior.
- Define a deterministic report skeleton and report safety checker.
- Add JSON observability events that avoid raw sensitive text by default.
- Write `artifacts/p1_foundation_validation.json`.

## Why No Real Model Metrics Here

This stage proves contracts, storage, safety boundaries, artifacts, and fallback behavior. It does not require a live LLM, local LoRA service, embedding model, vector database, PostgreSQL, or deployment target. Those systems can be enabled later behind explicit config and validation gates.

## Next Step

After the release candidate audit passes, the package is ready for an explicit user-approved git stage/commit/push workflow. It should continue to use the P8-to-P1 route, not the older P1.1-P1.6 gate line that treated MemoryManager and Tool Registry as non-goals.

## P1-F1 Progress

P1-F1 now records the P1 EvidencePack contract in graph metadata/export paths using the existing BM25 realpath. It also attaches a deterministic report skeleton to the graph/report path and validates the result in `artifacts/p1_f1_graph_integration_validation.json`.

## P1-F2 Progress

P1-F2 exposes the P1-F1 evidence pack and deterministic report skeleton through `ConsultationService`, `app.api.main:app`, and the P1 productization wrapper in `app.api.app:app`. The additive HTTP fields are validated by `artifacts/p1_f2_api_exposure_validation.json`.

## P1-F3 Progress

P1-F3 connects internal tool invocation audit records to trace evidence. Tool calls now share one trace id across the response, persisted audit log, and session trace event, while preserving approval gates and payload redaction. Validation is recorded in `artifacts/p1_f3_tool_audit_trace_validation.json`.

## P1-F4 Progress

P1-F4 adds a post-P8 productization gate for P1-F0 through P1-F3 and the inherited P8 memory/graph/extractor baselines. It records command results, artifact status checks, and explicit boundary decisions in `artifacts/p1_f4_productization_gate.json`.

## P1-F5 Progress

P1-F5 adds report safety, redaction, and audit envelopes to the productized API paths. Main API turn/report responses, the P1 wrapper report response, and persisted P7 final report safety checks can now expose `p1_f5_report_audit` evidence without raw report text. Validation is recorded in `artifacts/p1_f5_report_audit_validation.json`.

## P1-F6 Progress

P1-F6 closes the post-P8 productization follow-up by aggregating P1-F0 through P1-F5, the inherited P8 baselines, secret scan, focused regression, and boundary decisions into `artifacts/p1_f6_post_p8_productization_final.json`. It records the older P1.1-P1.6 gate as historical rather than authoritative for this route and recommends P2/P10 release hardening and packaging as the next slice.

## P2/P10 Release Hardening Progress

P2/P10 release hardening composes P1-F6, P10M2 core validation, P10M3 local LoRA backend validation, P10-M4A extractor contract validation, release packaging checks, focused regression, secret scan, and `git diff --check` into `artifacts/p2_p10_release_hardening.json`. It keeps the package as a local engineering release candidate and recommends release candidate audit and commit packaging as the next slice.

## Release Candidate Audit Progress

The release candidate audit validates the P2/P10 hardened package, records the pending worktree package inventory, checks for forbidden model/adapter/checkpoint/private-data paths, and writes `artifacts/release_candidate_audit.json`. It intentionally does not perform git stage, commit, push, or PR creation without explicit user approval.
