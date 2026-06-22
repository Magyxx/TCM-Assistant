# P4 Roadmap: Agentic Workflow Upgrade

## P4 Long-Term Goal

The system will migrate from a P3 structured consultation pipeline into a controlled Agentic Workflow without breaking P3 contracts.

The target remains a structured TCM consultation assistant, not a diagnosis system, prescription system, treatment-plan system, or doctor replacement. P4 must add orchestration, validation, memory, RAG, and tooling in bounded phases with deterministic state and regression gates.

## Implementation Status

P4.0 through P4.5 are implemented in this repository as a controlled workflow upgrade:

- P4.0 documented the baseline and migration boundaries.
- P4.1 adds `P4WorkflowAdapter` around the existing consultation flow.
- P4.2 adds consultation safety memory metadata and high-risk sticky protection.
- P4.3 adds a bounded RAG evidence pack boundary.
- P4.4 adds an internal tool registry with schema, permission, approval, and audit metadata.
- P4.5 adds `scripts/run_p4_gate.py` and P4-specific regression tests.

The public API response models and SQLite schema remain unchanged by P4.

## P4 Phase Table

| Phase | Goal | Scope | Deliverables | Forbidden Changes | Acceptance Criteria | Rollback Criteria |
| --- | --- | --- | --- | --- | --- | --- |
| P4.0: P4 baseline & migration plan | Freeze the P3.5 RC starting point and define P4 migration boundaries. | Docs and artifact only. | `docs/P4_BASELINE.md`, `docs/P4_ROADMAP.md`, `docs/P4_MIGRATION_PLAN.md`, `docs/P4_BOUNDARY.md`, `artifacts/p4_baseline.json` | Runtime refactor in P4.0, API/schema/SQLite changes, Web UI, auth, ORM, MCP, multi-agent, GraphRAG | Required docs exist, JSON validates, no runtime/API/schema/SQLite changes introduced by P4.0 | Revert P4.0 docs/artifact only |
| P4.1: LangGraph workflow skeleton / adapter | Introduce a controlled workflow skeleton/adapter around the existing flow. | Wrap existing flow first; add internal trace and boundary metadata. | `app/agentic/workflow_adapter.py`, `tests/test_p4_1_workflow_adapter.py`, `docs/P4_1_WORKFLOW_ADAPTER_REPORT.md`, `artifacts/p4_1_workflow_adapter.json` | Core logic rewrite, API contract change, response body schema change, SQLite schema change, diagnosis/prescription/treatment output | P4 workflow tests pass; P4 gate reports API body unchanged and SQLite unchanged | Switch API call back to existing `run_consultation_graph` |
| P4.2: MemoryManager / consultation safety memory | Add bounded consultation safety memory that protects state continuity. | Memory metadata for recent turns, authoritative RunState, source tracking, negation, and high-risk sticky protection. | `app/memory/consultation_memory.py`, `tests/test_p4_2_memory_manager.py`, `docs/P4_2_MEMORY_MANAGER_REPORT.md`, `artifacts/p4_2_memory_manager.json` | User profile memory, raw PII in vector memory, hidden cross-user memory, unvalidated state writes, silent high-risk downgrade | L2 structured state remains authoritative; high-risk present cannot be silently downgraded | Disable P4 memory metadata and use RunState only |
| P4.3: Hybrid RAG / evidence boundary | Add bounded RAG evidence support, not state authority. | Evidence pack, allowed uses, forbidden state writes, report metadata only. | `app/rag/evidence_boundary.py`, graph metadata integration, `tests/test_p4_3_rag_boundary.py`, `docs/P4_3_RAG_BOUNDARY_REPORT.md`, `artifacts/p4_3_rag_boundary.json` | RAG modifying `chief_complaint`, `duration`, `risk_status`, `risk_rule_ids`, diagnosis, prescription, treatment plan, GraphRAG | RAG evidence pack is read-only for core state; high-risk remains rule-first | Disable P4 evidence pack and use existing RAG/no RAG |
| P4.4: Internal Tool Registry / permission policy | Add reviewed internal tools with schemas, permissions, side-effect metadata, approvals, and audit logs. | Internal registry only; no MCP server. | `app/tools/internal_registry.py`, `tests/test_p4_4_tool_registry.py`, `docs/P4_4_TOOL_REGISTRY_REPORT.md`, `artifacts/p4_4_tool_registry.json` | Arbitrary tool execution, MCP server, user tools, tools bypassing risk/report boundaries | Every tool defines schema, permission, side effect, human approval, and audit log | Do not call registry; use existing internal functions directly |
| P4.5: P4 gate / regression and boundary check | Compose a P4 acceptance gate across P3.5 baseline and P4 additions. | Regression, boundary, safety, API contract, SQLite compatibility, P4 tests. | `scripts/run_p4_gate.py`, `tests/test_p4_5_gate.py`, `docs/P4_5_GATE_REPORT.md`, `artifacts/p4_gate_result.json`, `artifacts/p4_5_gate.json` | Releasing with failed P3 gate, schema drift, SQLite breakage, overwritten risk rules, unsafe reports | P4 gate passes with boundary violations empty | Gate failure blocks release |

## Phase Detail: P4.0

P4.0 is docs and artifact only.

It has no runtime refactor. It has no API changes, no response body schema changes, and no SQLite changes.

P4.0 produces:

- `docs/P4_BASELINE.md`
- `docs/P4_ROADMAP.md`
- `docs/P4_MIGRATION_PLAN.md`
- `docs/P4_BOUNDARY.md`
- `artifacts/p4_baseline.json`

P4.0 records the existing P3.5 RC evidence, but it does not rerun gate commands that write artifacts outside the P4.0 allowed file list.

## Phase Detail: P4.1

P4.1 defines a LangGraph workflow skeleton/adapter. It must wrap the existing flow first and must not rewrite core logic.

P4.1 must not change:

- API contract
- response body schema
- SQLite schema
- existing Pydantic runtime schemas
- risk rule semantics
- report safety boundary

Implementation note: `P4WorkflowAdapter` wraps the current `run_consultation_graph` flow and records P4 trace/boundary metadata inside internal state metadata. It does not add new public response model fields.

## Phase Detail: P4.2

P4.2 defines MemoryManager as consultation safety memory, not user profile.

Goals:

- Do not repeat questions.
- Do not lose fields.
- Do not misread negation.
- Do not forget high-risk signals.
- Do not let RAG overwrite core state.
- Explain field sources in reports.

Implementation note: `ConsultationMemoryManager` records bounded memory metadata and enforces high-risk sticky behavior. L2 structured `RunState` remains the authoritative state layer.

## Phase Detail: P4.3

P4.3 defines Hybrid RAG.

Rules:

- RAG can enhance impression.
- RAG can enhance advice.
- RAG can enhance report explanation.
- RAG can provide evidence snippets.
- RAG cannot rewrite `chief_complaint`.
- RAG cannot rewrite `duration`.
- RAG cannot rewrite `risk_status`.
- RAG cannot rewrite `risk_rule_ids`.
- High-risk judgment remains rule-first.

Implementation note: `EvidencePack` records allowed report uses and forbidden state writes. RAG evidence is read-only with respect to core consultation state.

## Phase Detail: P4.4

P4.4 defines an internal tool registry, not full MCP.

Initial tools:

- `risk_check_tool`
- `rag_search_tool`
- `report_safety_tool`
- `export_report_tool`
- `eval_case_tool`

Every tool must define:

- `input_schema`
- `output_schema`
- `permission_level`
- `side_effect`
- `requires_human_approval`
- `audit_log`

Tools cannot bypass risk rules, report safety checks, schema validation, or the no-diagnosis/no-prescription/no-treatment-plan boundary.

## Phase Detail: P4.5

P4.5 defines the P4 gate:

- P3.5 gate still passes.
- API contract still frozen.
- SQLite schema compatible.
- Historical sessions compatible.
- Risk rules not overwritten by LLM/RAG.
- Reports still do not diagnose or prescribe.
- LangGraph/Memory/RAG/Tool additions are regression-tested.

Implementation note: `scripts/run_p4_gate.py` validates the existing P3.5 artifact, API contract invariants, SQLite schema invariants, P4 workflow/memory/RAG/tool boundaries, report safety, and P4 unit tests.

## Deferred Capabilities

These capabilities are explicitly deferred:

- MCP Server
- GraphRAG
- Multi-agent system
- Web UI
- User/permission system
- ORM migration
- Doctor dashboard
- External medical APIs
- Auto diagnosis
- Auto prescription
- Treatment plan generation

## Roadmap Control Notes

- Each P4 runtime phase must be separately reviewable.
- P4.1-P4.4 must preserve the P3.5 public contract until a future migration explicitly gates a versioned change.
- P4.5 is the first phase that can recommend a P4 release candidate.
