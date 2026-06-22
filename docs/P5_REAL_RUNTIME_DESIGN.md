# P5 Real Runtime Design

## Scope

P5 validates the real runtime chain for the TCM consultation assistant without changing the frozen public boundaries:

- Real LangGraph compile and invoke.
- Extractor mode separation: `fake`, `rule_fallback`, and `real_llm`.
- Pydantic validation for `TurnOutput`, `RunState`, and `FinalReport`.
- Multi-turn `RunState` accumulation.
- Risk-rule authority over `risk_flags_status`, `triggered_rule_ids`, and `risk_reasons`.
- BM25 RAG smoke test and RAG write boundary.
- Report generation, safety post-check, and report audit.
- P5 trace and metric artifacts.

The product boundary remains unchanged: the system organizes consultation information, highlights risks, and prepares structured summaries. It does not diagnose, prescribe, replace clinicians, or provide deterministic medical conclusions.

## Non-Goals

P5 deliberately does not add multi-agent orchestration, MCP servers, model gateways, GraphRAG, large medical-book ingestion, Docker/deployment, or SFT/LoRA training. It also does not change the FastAPI contract, SQLite schema, `TurnOutput`, `RunState`, `FinalReport`, or risk-rule semantics.

## Runtime Path

The validation path uses `app.graphs.consultation_graph.build_consultation_graph()` and `run_consultation_graph(..., use_langgraph=True)`. The graph is considered real runtime only when the compiled LangGraph exists and invoked cases report `graph_runtime == "langgraph"`.

P5 graph cases cover:

- Incomplete digestive complaint follow-up.
- Complete low-risk digestive case with BM25 evidence.
- High-risk chest pain and dyspnea.
- Negated red-flag sentence.
- GI bleeding high-risk rule.

## Extractor Modes

The artifact records each mode separately:

- `fake`: deterministic structured extractor for local validation.
- `rule_fallback`: rule-only fallback path; it must not be counted as real LLM success.
- `real_llm`: subprocess probe with timeout. If provider/network/config is unavailable, P5 records `caution` and never spoofs success.

The implementation also records `raw_llm_json_valid_rate`, `schema_pass_rate`, and `fallback_used_rate` for real LLM attempts. When the real LLM is not probed or unavailable, those values remain `null` or `0.0` as appropriate instead of being inflated.

## State and Risk Authority

LLM output cannot be the final authority for risk status. The graph applies `evaluate_risk_rules()` and `apply_risk_evaluation_to_state()` after extraction. P5 checks:

- High-risk chest pain/dyspnea and GI bleeding are present.
- Negated fever/chest pain/blood-in-stool stays non-present.
- High-risk false negative count is zero.
- Existing state is not lost across demo turns.

P5 includes a small extractor hygiene fix so negated weak-chief phrases such as "不胸痛" do not overwrite an existing chief complaint. This protects accumulated state and does not change risk-rule semantics.

## RAG Boundary

RAG is limited to evidence and report enrichment. P5 checks that BM25 retrieval can execute and that RAG metadata declares:

- `core_state_readonly == true`
- forbidden writes include `chief_complaint`, `duration`, `risk_status`, and `risk_rule_ids`
- `can_diagnose == false`
- `can_prescribe == false`

RAG may enhance `impression`, `advice`, and evidence metadata; it must not rewrite core state.

## Trace Contract

Each trace sample contains:

`trace_id`, `session_id`, `turn_id`, `case_id`, `graph_runtime`, `extractor_mode`, `raw_llm_json_valid`, `schema_pass`, `fallback_used`, `fallback_reason`, `risk_status`, `risk_rule_ids`, `risk_reasons`, `retrieved_evidence_count`, `retrieved_chunk_ids`, `rag_boundary_pass`, `final_report_schema_pass`, `safety_rewrite_used`, `diagnosis_or_prescription_violation`, `state_loss_detected`, `repeated_question_detected`, `latency_ms`, and `error`.

## Artifacts

P5 writes:

- `artifacts/p5_real_runtime_validation.json`
- `artifacts/p5_demo_results.json`
- `artifacts/p5_trace_samples.json`
- `artifacts/p5_failure_analysis.json`

These files are intended to be validated with `python -m json.tool`.
