# P4 Migration Plan: From P3 Pipeline to Controlled Agentic Workflow

## Migration Principles

- Wrap before rewrite.
- Preserve API.
- Preserve response schema.
- Preserve SQLite schema.
- Preserve P3 gate.
- Preserve historical sessions.
- Preserve risk rule semantics.
- Preserve report safety boundary.
- Add observability before adding autonomy.
- Prefer deterministic nodes over free agents.

## P3 To P4 Conceptual Mapping

| P3 Component | P4 Target Component | Migration Phase | Compatibility Requirement | Risk |
| --- | --- | --- | --- | --- |
| Current user input handling | InputNormalizeNode | P4.1 | Preserve accepted request payload and error shape | Input normalization could change user-visible behavior |
| Current extractor | TurnExtractNode | P4.1 | Preserve `TurnOutput` compatibility and fallback behavior | LLM output may drift or write invalid fields |
| Pydantic validation | SchemaValidateNode | P4.1 | Validate before state write | Silent acceptance of invalid JSON |
| State merge | MemoryUpdateNode / StateMergeNode | P4.1-P4.2 | Preserve `RunState` as authoritative state | Memory could overwrite structured state |
| Risk rules | RiskRuleNode | P4.1 | Preserve rule IDs, reasons, and high-risk semantics | High-risk false negative or silent downgrade |
| Follow-up planner | QuestionPlannerNode | P4.1 | Preserve existing next-question behavior and no routine follow-up after high risk | Repeated or missing questions |
| RAG | Bounded HybridRAGNode | P4.3 | RAG is read-only for core consultation state | RAG modifies risk/core fields or invents symptoms |
| Report generation | ReportGeneratorNode | P4.1-P4.3 | Preserve `FinalReport` schema and safety disclaimer | Report becomes diagnostic or prescriptive |
| Safety check | ReportSafetyNode | P4.1-P4.5 | Safety check remains mandatory for report-like output | Unsafe language reaches final report |
| Export | ExportReportTool | P4.4 | Export uses approved tool metadata and audit log | Side effects without approval or audit |

## P4.1 Migration Plan

Future plan only.

- Build a graph-like adapter around the existing flow.
- No core logic rewrite.
- Preserve public API response.
- Add graph trace only if non-breaking.
- Keep rollback path to P3 pipeline.
- Keep P3.5 gate and API contract checks as inherited acceptance.
- Keep SQLite schema unchanged.

P4.1 should start by wrapping the current extraction, validation, merge, risk rule, follow-up, retrieval, report generation, and safety-post-check sequence behind deterministic node boundaries.

## P4.2 Migration Plan

Future plan only.

Memory layers:

- L1 recent turns
- L2 structured authoritative RunState
- L3 consultation summary
- L4 knowledge / anonymized eval experience

Rules:

- L2 is authoritative.
- L3 cannot overwrite L2.
- L4 cannot contain raw patient PII.
- LLM candidates must pass schema validation before state write.
- High-risk present cannot be silently downgraded.
- Memory is consultation safety memory, not user profile memory.
- Memory source tracking should make report fields explainable where possible.

## P4.3 Migration Plan

Future plan only.

Hybrid RAG:

- BM25 / sparse
- Dense embeddings
- Reranking
- Evidence pack
- Report explanation only

Explicit boundary:

RAG is read-only with respect to core consultation state.

RAG may provide evidence snippets and explanation context for reports, but it cannot rewrite `chief_complaint`, `duration`, `risk_status`, `risk_rule_ids`, or user-provided symptoms.

## P4.4 Migration Plan

Future plan only.

Internal tool registry:

- Tool metadata
- Permissions
- Side effects
- Human approval
- Audit log
- No MCP server in first implementation

Initial tool candidates:

- `risk_check_tool`
- `rag_search_tool`
- `report_safety_tool`
- `export_report_tool`
- `eval_case_tool`

Every tool must be schema-bound, permission-bound, and audit-logged. Tools must not bypass risk or report safety boundaries.

## P4.5 Migration Plan

Future plan only.

Gate:

- Regression suite
- Boundary tests
- Safety tests
- API contract tests
- SQLite compatibility tests
- Historical session replay if available
- P3.5 gate or strict successor
- Secret scan
- Full unit test discovery

P4.5 should block release on any regression in P3.5 contracts, risk rules, report safety, API response body shape, SQLite compatibility, or historical session readability.

## Migration Checklist

| ID | Item | Phase | Status | Evidence | Owner/Notes |
| --- | --- | --- | --- | --- | --- |
| P4_CHECK_001 | Freeze P3.5 RC baseline | P4.0 | DONE | `artifacts/p3_5_rc_gate.json` inspected; `status=ok`, `checks_passed=11`, `recommend_next=P4.0` | P4.0 documentation |
| P4_CHECK_002 | Document API/schema/SQLite non-breaking boundary | P4.0 | DONE | `docs/API_CONTRACT.md`, `docs/SQLITE_SCHEMA.md`, `docs/P4_BOUNDARY.md` | P4.0 documentation |
| P4_CHECK_003 | Document P4.1 LangGraph adapter plan | P4.0 | DONE | `docs/P4_ROADMAP.md`, this migration plan | P4.1 future only |
| P4_CHECK_004 | Implement controlled graph adapter with parity checks | P4.1 | DONE | `app/agentic/workflow_adapter.py`, `tests/test_p4_1_workflow_adapter.py`, P4 gate `p4_1_workflow_adapter=ok` | Runtime wraps existing flow |
| P4_CHECK_005 | Add MemoryManager consultation safety memory | P4.2 | DONE | `app/memory/consultation_memory.py`, `tests/test_p4_2_memory_manager.py`, P4 gate `p4_2_memory_manager=ok` | Memory is not user profile |
| P4_CHECK_006 | Add Hybrid RAG evidence boundary | P4.3 | DONE | `app/rag/evidence_boundary.py`, `tests/test_p4_3_rag_boundary.py`, P4 gate `p4_3_rag_boundary=ok` | RAG is read-only for core state |
| P4_CHECK_007 | Add internal Tool Registry and permission policy | P4.4 | DONE | `app/tools/internal_registry.py`, `tests/test_p4_4_tool_registry.py`, P4 gate `p4_4_tool_registry=ok` | Internal registry only; no MCP |
| P4_CHECK_008 | Compose P4 gate | P4.5 | DONE | `scripts/run_p4_gate.py`, `tests/test_p4_5_gate.py`, `artifacts/p4_gate_result.json`, `artifacts/p4_5_gate.json` | P4 gate passed |

## Rollback Plan

- P4.1 can disable graph adapter and use P3 pipeline.
- P4.2 can disable MemoryManager and use RunState only.
- P4.3 can disable Hybrid RAG and use existing RAG or no RAG.
- P4.4 can disable tool registry and call internal functions directly.
- P4.5 gate failure blocks release.

Rollback must preserve API response bodies, SQLite readability, and report safety behavior.

## Validation Commands

Discovered from repo:

| Command | Source | P4.0 Status | Notes |
| --- | --- | --- | --- |
| `python scripts/run_p3_gate.py --json` | `docs/P3_5_RC_GATE_REPORT.md`, `scripts/run_p3_gate.py` | not_run | Full gate writes P3 artifacts outside the P4.0 allowed output list. Existing artifact reports pass. |
| `python scripts/run_p3_gate.py --summary-only --json` | `docs/P3_FINAL_RELEASE_CANDIDATE.md`, `scripts/run_p3_gate.py` | not_run | Summary mode still writes gate artifacts unless redirected. |
| `python -m unittest discover -s tests -p "test*.py"` | P3.5 report and gate script | not_run | Existing P3.5 artifact reports 257 tests OK. |
| `python scripts/secret_scan.py --json --output artifacts/secret_scan_result.json` | P3.5 report and gate script | not_run | Writes non-P4 artifact; existing artifact reports OK. |
| `git diff --check` | P3.5 report and gate script | not_run | Existing P3.5 artifact reports exit code 0 with Windows LF/CRLF warnings. |
| `python -m json.tool artifacts/p4_baseline.json` | P4.0 validation requirement | run_after_edit | Must pass for P4.0. |
| `git diff --name-only` | P4.0 validation requirement | run_after_edit | Used for final diff inspection. |
| `python -m unittest tests.test_p4_1_workflow_adapter tests.test_p4_2_memory_manager tests.test_p4_3_rag_boundary tests.test_p4_4_tool_registry tests.test_p4_5_gate` | P4.5 validation | pass | 11 P4 tests passed. |
| `python scripts/run_p4_gate.py --json --output artifacts/p4_gate_result.json --rc-output artifacts/p4_5_gate.json` | P4.5 validation | pass | 9/9 P4 gate checks passed. |

No dependencies should be installed in P4.0. No lockfiles, runtime source, tests, prompts, API contracts, response models, or SQLite schema files should be modified by P4.0.
