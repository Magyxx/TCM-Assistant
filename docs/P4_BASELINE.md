# P4 Baseline: P3.5 RC Frozen Starting Point

## Baseline Summary

- Source phase: P3.5 RC
- Target phase: P4.0
- Baseline date: 2026-06-20
- Repository branch: `sft-local-pipeline`
- Repository commit: `613424415acc3747e4497b50528474c860a184ba`
- Runtime change status: No runtime changes in P4.0
- Dirty worktree before P4.0 documentation changes: true. The repository already contained modified and untracked files before this P4.0 update.

P4.0 is a migration design phase only. It records the P3.5 RC baseline, the P4 roadmap, the migration plan, the P4 safety and compatibility boundaries, and a machine-readable baseline artifact. It does not implement P4.1-P4.5 runtime behavior.

## Current System Positioning

The current system is a TCM consultation assistant for structured consultation information collection, risk signal identification, report summary, and safety advice.

It may:

- organize user-provided consultation information
- collect structured consultation fields
- identify rule-based risk signals
- ask bounded follow-up questions
- generate report summaries and cautious safety advice
- advise offline medical care when high-risk signals are present

It must remain:

- not diagnosis
- not prescription
- not treatment plan
- not doctor replacement

## P3.5 RC Capabilities To Freeze

| Area | Status | Evidence | Notes |
| --- | --- | --- | --- |
| CLI entrypoints | present | `scripts/run_p1_gate.py`, `scripts/run_p2_gate.py`, `scripts/run_p3_gate.py`, `scripts/run_graph_demo.py`, `scripts/run_api_demo.py`, `scripts/eval_report.py` | Existing scripts remain unchanged in P4.0. |
| API entrypoints | present | `app/api/main.py`; `docs/API_CONTRACT.md`; `artifacts/p3_4_api_contract_check.json` | Public endpoint count is 6 in the P3.5 artifact. |
| Public API endpoints | present | `GET /health`, `GET /version`, `POST /sessions`, `POST /sessions/{session_id}/turn`, `GET /sessions/{session_id}/state`, `GET /sessions/{session_id}/report` | P3.4 adds version metadata without changing existing response bodies. |
| Pydantic models | present | `app/schemas/report_schemas.py`, `app/api/models.py`, `app/schemas/sft_schemas.py` | Runtime schemas are not changed by P4.0. |
| `TurnOutput` schema | present | `app/schemas/report_schemas.py` | Used for per-turn extraction output. |
| `RunState` schema | present | `app/schemas/report_schemas.py` | Stores authoritative consultation state fields such as `chief_complaint`, `duration`, risk status, and final report. |
| `FinalReport` schema | present | `app/schemas/report_schemas.py` | Stores summary, impression, advice, triage level, completeness, and metadata. |
| API response schemas | present | `app/api/models.py` | `TurnResponse`, `SessionStateResponse`, and `SessionReportResponse` include risk fields and safety disclaimer. |
| Graph-like consultation flow | present | `app/graphs/consultation_graph.py`, `app/graphs/consultation_nodes.py` | Existing optional LangGraph path and sequential fallback are baseline facts; P4.0 does not modify them. |
| Risk rule engine | present | `app/rules/risk_rules.py`; `tests/test_p0_risk_rules.py` | Risk rules evaluate high-risk signals and negation, then write rule IDs and reasons into state metadata. |
| Rule-first high-risk persistence | present | `apply_risk_evaluation_to_state` in `app/rules/risk_rules.py` | A present high-risk state is not silently downgraded by a later `none` evaluation. |
| RAG / BM25 retrieval | present | `app/rag/bm25_retriever.py`, `app/rag/hybrid_retriever.py`, `app/chains/rag_enhancer.py` | BM25 and hybrid interfaces exist. P4.0 does not add embeddings or a new RAG runtime. |
| Dense retrieval | present as placeholder | `app/rag/embedding_retriever.py` | Existing placeholder returns no configured dense retrieval unless later implemented. |
| SQLite persistence | present | `app/api/sqlite_store.py`, `docs/SQLITE_SCHEMA.md` | `schema_version=1`, `schema_stage=P1.3`, tables: `schema_meta`, `sessions`, `session_states`, `turns`, `reports`. |
| Historical session handling | present | `tests/test_p1_5_report_snapshot.py`, `docs/SQLITE_SCHEMA.md` | Legacy-session compatibility is part of the inherited boundary. |
| Evaluation scripts | present | `scripts/run_case_corpus_eval.py`, `scripts/eval_report.py`, `scripts/eval_sft_extract.py`, `scripts/run_long_session_demo.py` | P3.5 gate aggregates eval and reliability checks. |
| Artifacts | present | `artifacts/p3_5_rc_gate.json`, `artifacts/p3_gate_result.json`, `artifacts/p3_4_api_contract_check.json`, `artifacts/p2_case_corpus_eval.json` | P4.0 adds only `artifacts/p4_baseline.json`. |
| Existing tests | present | `tests/test*.py`; P3.5 artifact reports 257 unittest tests | P4.0 does not add or modify tests. |
| Report safety boundary logic | present | `app/safety/report_safety.py`, `app/api/report_validator.py`, `docs/SAFETY_BOUNDARY.md` | Report safety sanitizes forbidden diagnosis/prescription/treatment-plan language and appends safety boundary text. |
| API contract gate | present | `scripts/check_api_contract.py`, `artifacts/p3_4_api_contract_check.json` | P3.5 artifact reports `api_contract_status=frozen`. |
| Secret scanning and redaction | present | `scripts/secret_scan.py`, `app/api/redaction.py`, `artifacts/secret_scan_result.json` | P3.5 artifact reports secret scan ok. |

## Frozen Contracts

| Contract | P4.0 Status | Evidence Checked | Notes |
| --- | --- | --- | --- |
| API contract frozen | true | `docs/API_CONTRACT.md`, `scripts/check_api_contract.py`, `artifacts/p3_4_api_contract_check.json`, `artifacts/p3_5_rc_gate.json` | P3.5 artifact reports `api_contract_status=frozen`. |
| Response body schema frozen | true | `app/api/models.py`, `docs/API_CONTRACT.md`, `artifacts/p3_5_rc_gate.json` | P3.5 artifact reports `api_response_body_changed=false`. |
| SQLite schema frozen | true | `app/api/sqlite_store.py`, `docs/SQLITE_SCHEMA.md`, `artifacts/p3_5_rc_gate.json` | P3.5 artifact reports `sqlite_schema_changed=false`. |
| Pydantic schema compatibility frozen | true | `app/schemas/report_schemas.py`, `app/api/models.py` | P4.0 does not change runtime models. |
| Historical session compatibility required | true | `docs/SQLITE_SCHEMA.md`, `tests/test_p1_5_report_snapshot.py` | Future P4 changes must keep existing sessions readable. |
| Risk rule semantics frozen | true | `app/rules/risk_rules.py`, `tests/test_p0_risk_rules.py` | High-risk rule results remain authoritative. |
| Report safety boundary frozen | true | `app/safety/report_safety.py`, `docs/SAFETY_BOUNDARY.md` | Reports remain non-diagnostic and non-prescriptive. |
| Runtime prompt behavior frozen | true | `app/prompts/*`, `app/chains/*` inspected by path inventory only | P4.0 does not edit prompts or runtime chains. |

No inspected contract is marked UNKNOWN for P4.0. Some README status text is older than the P3.5 documents and artifacts, so P4.0 uses the P3.5 report, gate script, and gate artifacts as stronger evidence.

## P3 Gate / P3.5 Gate Evidence

Discovered P3.5 gate commands:

- `python scripts/run_p3_gate.py --json`
- `python scripts/run_p3_gate.py --summary-only --json`
- `python -m unittest discover -s tests -p "test*.py"`
- `python scripts/secret_scan.py --json --output artifacts/secret_scan_result.json`
- `git diff --check`

P4.0 command policy:

- Full P3.5 gate was not rerun during P4.0 because `scripts/run_p3_gate.py --json` rewrites multiple existing gate artifacts outside the P4.0 allowed output list.
- Existing P3.5 evidence was inspected from `docs/P3_5_RC_GATE_REPORT.md`, `docs/P3_FINAL_RELEASE_CANDIDATE.md`, and `artifacts/p3_5_rc_gate.json`.
- P4.0 validation runs are limited to JSON validation and final diff/status inspection.

| Command / Evidence | Run In P4.0 | Status | Output Summary | Known Failures |
| --- | --- | --- | --- | --- |
| Existing `artifacts/p3_5_rc_gate.json` | inspected | pass | `status=ok`, `checks_passed=11`, `checks_total=11`, `recommend_next=P4.0` | none recorded in artifact |
| Existing P3.5 gate command record | inspected | pass | P1 gate, P2 gate, runtime config, observability, release packaging, API contract, corpus eval, long session, secret scan, git diff check, and unittest discovery all recorded `ok` | none recorded in artifact |
| `python scripts/run_p3_gate.py --json` | not_run | not_run | Not run in P4.0 to avoid writing non-P4 artifacts | not applicable |
| `python -m unittest discover -s tests -p "test*.py"` | not_run | not_run | Existing P3.5 artifact reports 257 tests OK | not applicable |
| `python scripts/secret_scan.py --json --output artifacts/secret_scan_result.json` | not_run | not_run | Existing P3.5 artifact reports secret scan OK | not applicable |
| `git diff --check` | not_run as P3 gate | not_run | Existing P3.5 artifact reports exit code 0 with Windows LF/CRLF warnings only | not applicable |

Do not fix runtime failures in P4.0. If a future rerun fails, record the failure and handle it in the appropriate runtime phase.

## P4 Entry Assumptions

- P4 starts only after P3.5 RC is frozen.
- P4.0 only creates baseline and migration design.
- P4.0 does not change runtime behavior, public API response bodies, SQLite schema, Pydantic runtime models, risk rules, prompts, or tests.
- P4.1 is the earliest phase allowed to introduce or normalize a controlled LangGraph skeleton/adapter for the P4 workflow.
- P4.1 must wrap existing flow first and preserve P3.5 public contracts.
- RAG, memory, tools, and LLM output must not overwrite core consultation state.
- High-risk signals remain rule-prioritized and auditable.

## Baseline Decision

| Area | Status | Evidence | P4 Migration Impact |
| --- | --- | --- | --- |
| P3.5 RC gate | present / pass | `artifacts/p3_5_rc_gate.json` reports `status=ok`, 11/11 checks | P4.1+ must preserve this gate or document a gated successor. |
| API contract | frozen | `docs/API_CONTRACT.md`; `artifacts/p3_4_api_contract_check.json`; P3.5 artifact | P4 adapters must keep response bodies compatible. |
| Response body schemas | frozen | `app/api/models.py`; P3.5 artifact reports unchanged | P4 internals cannot leak new required response fields. |
| SQLite schema | frozen | `app/api/sqlite_store.py`; `docs/SQLITE_SCHEMA.md`; P3.5 artifact | P4.0/P4.1 no SQLite schema change; P4.2+ requires migration and rollback plan. |
| Pydantic runtime models | frozen | `app/schemas/report_schemas.py`; `app/api/models.py` | LLM candidates must validate before state writes in future phases. |
| Risk rules | frozen | `app/rules/risk_rules.py`; risk tests | Future LLM/RAG/memory/tool outputs cannot downgrade high risk. |
| RAG | present / bounded baseline | `app/rag/*`, `app/chains/rag_enhancer.py`, RAG tests | P4.3 can enhance evidence, but RAG remains read-only for core state. |
| Memory | not_found as P4 MemoryManager | No `MemoryManager` implementation found in inspected files | P4.2 must define consultation safety memory before runtime implementation. |
| Tool registry | not_found | No internal Tool Registry implementation found in inspected files | P4.4 must define schema, permission, side-effect, approval, and audit fields. |
| MCP server | not_found | No MCP server implementation found in inspected files | Explicitly deferred beyond P4.0. |
| Multi-agent architecture | not_found | No multi-agent runtime found in inspected files | Explicitly deferred. |
| Web UI | not_found | No Web UI surface found in inspected file inventory | Explicitly deferred. |
| Safety/report boundary | present / frozen | `app/safety/report_safety.py`, `docs/SAFETY_BOUNDARY.md`, report validator tests | P4 output remains consultation summary and safety advice only. |

## P4 Risk Register

| ID | Description | Severity | Mitigation | Target Phase For Verification |
| --- | --- | --- | --- | --- |
| P4_RISK_001 | P3.5 gate broken by P4 migration | high | P4.5 must rerun the P3.5 gate or a strict successor and block release on failure. | P4.5 |
| P4_RISK_002 | API contract drift | high | Keep API contract frozen and add compatibility checks before releasing P4 runtime phases. | P4.1, P4.5 |
| P4_RISK_003 | Response body schema drift | high | Require response body snapshot comparison and forbid new required fields. | P4.1, P4.5 |
| P4_RISK_004 | SQLite schema incompatibility | high | No SQLite schema change in P4.0/P4.1; future changes require migration, rollback, and replay tests. | P4.2, P4.5 |
| P4_RISK_005 | Historical session incompatibility | high | Replay or inspect historical sessions after persistence changes. | P4.2, P4.5 |
| P4_RISK_006 | LLM overwrites `risk_status` | critical | Rule engine remains authoritative; LLM output validates as candidate only before controlled merge. | P4.1, P4.5 |
| P4_RISK_007 | RAG overwrites `risk_status` or `risk_rule_ids` | critical | RAG is read-only for core state and cannot write risk status or rule IDs. | P4.3, P4.5 |
| P4_RISK_008 | RAG modifies `chief_complaint` or `duration` | high | Core user-provided fields are owned by validated extraction/state merge only. | P4.3, P4.5 |
| P4_RISK_009 | Memory stores raw patient PII | high | L4 memory stores only knowledge or anonymized evaluation experience; raw patient PII is forbidden. | P4.2, P4.5 |
| P4_RISK_010 | Memory becomes a user profile instead of consultation safety memory | high | Scope memory to consultation safety: avoid repeated questions, preserve fields, track sources. | P4.2 |
| P4_RISK_011 | Tool side effects occur without human approval | high | Tool Registry requires `side_effect` and `requires_human_approval` metadata. | P4.4, P4.5 |
| P4_RISK_012 | Missing audit logs for tools | high | Tool calls require redacted audit logs before P4.4 acceptance. | P4.4, P4.5 |
| P4_RISK_013 | Report outputs diagnosis | critical | Report safety gate blocks diagnostic claims and regression tests cover forbidden phrases. | P4.5 |
| P4_RISK_014 | Report outputs prescription | critical | Report safety gate blocks prescription language and dosing instructions. | P4.5 |
| P4_RISK_015 | Report outputs treatment plan or treatment recommendation | critical | Report safety boundary keeps advice cautious and refers high-risk cases offline. | P4.5 |
| P4_RISK_016 | High-risk false negative | critical | Rule-first triage, high-risk regression cases, and no silent downgrade policy. | P4.1-P4.5 |
| P4_RISK_017 | Negation misclassification | high | Preserve explicit negation handling and add targeted regression cases. | P4.1-P4.5 |
| P4_RISK_018 | Scope creep into multi-agent, MCP, GraphRAG, or Web UI | medium | Keep deferred capabilities out of P4.0 and require separate scope approval. | Every P4 phase |
