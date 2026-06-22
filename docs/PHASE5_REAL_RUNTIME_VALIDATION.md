# Phase 5 Real Runtime Validation

## P5 Scope

P5 proves that the consultation assistant can run through the real LangGraph runtime chain instead of only passing fake, fallback, or gate-only paths. It validates extractor modes, Pydantic schemas, accumulated `RunState`, risk rules, BM25 RAG, report generation, report safety, final report schema, multi-turn behavior, trace fields, and P5 metrics.

The product boundary is unchanged: this is a TCM consultation assistance system for information organization, risk reminders, and structured summaries. It is not a diagnostic system and does not prescribe.

## Changed Files

- `app/chains/turn_extractor.py`
- `app/chains/report_chain.py`
- `scripts/run_p5_real_runtime_validation.py`
- `scripts/run_p5_demo_cases.py`
- `docs/P5_REAL_RUNTIME_DESIGN.md`
- `docs/PHASE5_REAL_RUNTIME_VALIDATION.md`
- `tests/test_p5_real_runtime_validation.py`
- `tests/test_p5_rag_boundary.py`
- `tests/test_p5_extractor_modes.py`
- `tests/test_p5_multiturn_runtime.py`
- `artifacts/p5_real_runtime_validation.json`
- `artifacts/p5_demo_results.json`
- `artifacts/p5_trace_samples.json`
- `artifacts/p5_failure_analysis.json`

## Real LangGraph Runtime Status

`scripts/run_p5_real_runtime_validation.py` calls `build_consultation_graph()` and invokes `run_consultation_graph(..., use_langgraph=True)`. The required P5 runtime cases require `graph_runtime == "langgraph"` and at least five passing graph cases.

## Extractor Mode Status

The P5 artifact separates:

- `fake`: deterministic structured extraction, no fallback counted.
- `rule_fallback`: explicit fallback, counted separately and never reported as LLM success.
- `real_llm`: subprocess probe with timeout. If unavailable, the artifact records caution.

## Real LLM Availability

Real LLM availability is environment-dependent. When it is reachable, P5 records `raw_llm_json_valid_rate`, `schema_pass_rate`, and `fallback_used_rate`. When it is unavailable, P5 marks `real_llm` as caution and does not spoof success.

## BM25 RAG Smoke-Test Status

The smoke test builds an evidence pack with `mode="bm25_only"` and asserts evidence is returned. It also verifies RAG metadata forbids writes to `chief_complaint`, `duration`, `risk_status`, and `risk_rule_ids`.

## Multiturn Demo Results

`scripts/run_p5_demo_cases.py` covers eight required demo cases:

1. Digestive complaint follow-up.
2. Duration update without repeated duration question.
3. Sleep, appetite, stool/urine accumulation.
4. Negated fever/chest pain/blood-in-stool not present.
5. Chest pain, chest tightness, dyspnea high-risk trigger.
6. Blood in stool high-risk trigger and retained rule ids.
7. FinalReport generation after enough fields.
8. Prompt injection boundary.

## Risk Rule Validation

Risk status remains rule-governed. P5 checks high-risk false negatives are zero and negated risk phrases do not become `present`.

## RAG Boundary Validation

RAG cannot rewrite core state. It can only enrich evidence/report metadata and support `impression` or `advice` context. P5 verifies both state snapshots and report contract fields stay unchanged.

## Report Safety Validation

P5 validates `FinalReport` schema and audits reports for diagnosis, prescription, treatment-plan, substitute-medical-advice, drug-dose-like, and secret-like violations. Required counts are zero.

## Metrics Table

Authoritative values are written to `artifacts/p5_real_runtime_validation.json` and `artifacts/p5_demo_results.json`. Required P5 metrics include:

| Metric | Expected |
| --- | --- |
| graph_runtime_case_pass_count | at least 5 |
| demo_cases_passed | at least 8 |
| report_safety_violation_count | 0 |
| diagnosis_or_prescription_violation_count | 0 |
| high_risk_false_negative_count | 0 |
| state_loss_rate | 0 |
| trace_field_completeness_pass | true |
| BM25 evidence count | greater than 0 |

## Failure Analysis

`artifacts/p5_failure_analysis.json` records blockers and cautions. A failed hard gate, failed graph runtime case, failed RAG boundary, nonzero safety violation, nonzero high-risk false negative, or nonzero state loss marks P5 as failed. Real LLM unavailability is caution, not success.

## Known Cautions

- Real LLM availability depends on reachable provider configuration and network access.
- Existing dependency warnings from transformers/PyTorch can appear during import and are not P5 hard failures.
- P5 does not expand the knowledge base beyond the existing BM25 smoke corpus.

## P5 Conclusion

P5 is `ok` when all hard gates and P5 runtime checks pass and the real LLM probe succeeds. P5 is `caution` when deterministic runtime checks pass but real LLM is unavailable. P5 is `failed` when any hard gate, runtime case, boundary, risk, safety, trace, or JSON artifact check fails.

The exact current conclusion is the `status` field in `artifacts/p5_real_runtime_validation.json`.

## P6 Entry Criteria

- P5 artifacts exist and pass `python -m json.tool`.
- P4 gate and code health hard gate pass.
- LangGraph runtime cases and multi-turn demo cases pass.
- RAG boundary, risk rules, report safety, and FinalReport schema pass.
- Any real LLM caution is explicitly accepted or resolved by rerunning in a reachable provider environment.
