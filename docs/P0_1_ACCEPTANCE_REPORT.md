# P0.1 Acceptance Report

## 1. Summary

P0.1 closes the P0 acceptance loop for reproducibility, fallback clarity, metric semantics, and test coverage.

This project remains a TCM inquiry assistance system. It does not diagnose, prescribe, or make treatment decisions.

## 2. Files Added

- `docs/P0_1_ACCEPTANCE_GAP_REPORT.md`
- `docs/P0_1_ACCEPTANCE_REPORT.md`
- `scripts/check_p0_env.py`
- `tests/test_p0_turn_extractor.py`
- `tests/test_p0_consultation_graph.py`
- `tests/test_p0_hybrid_rag.py`
- `tests/test_p0_report_safety.py`
- `artifacts/p0_1_eval_failure_analysis.json`

## 3. Files Modified

- `requirements.txt`
- `docs/P0_STRUCTURED_EXTRACTION.md`
- `app/chains/turn_extractor.py`
- `app/graphs/consultation_state.py`
- `app/graphs/consultation_nodes.py`
- `app/graphs/consultation_graph.py`
- `app/rules/risk_rules.py`
- `app/rag/hybrid_retriever.py`
- `app/chains/rag_enhancer.py`
- `app/safety/report_safety.py`
- `app/chains/report_chain.py`
- `scripts/eval_report.py`
- `tests/test_p0_risk_rules.py`

## 4. Command Results

### Environment

`python scripts/check_p0_env.py`

- `langgraph`: missing
- `langchain_openai`: missing
- `rank_bm25`: missing
- `pydantic`: present
- `python-dotenv`: present
- `.env`: present
- `OPENAI_API_KEY`: present
- `OPENAI_BASE_URL`: present
- optional SFT: `torch` present; `transformers`, `datasets`, `peft`, `accelerate` missing
- mode: `fallback-only`

### Compile

`python -m py_compile ...`

- Passed.

### Unit Tests

- `python -m unittest tests.test_p0_risk_rules`: 13 tests OK
- `python -m unittest tests.test_p0_turn_extractor`: 5 tests OK
- `python -m unittest tests.test_p0_consultation_graph`: 6 tests OK
- `python -m unittest tests.test_p0_hybrid_rag`: 4 tests OK
- `python -m unittest tests.test_p0_report_safety`: 5 tests OK

### SFT Eval

`python scripts/eval_sft_extract.py --pred-file data\sft\processed\sft_report_turn_extract_val.jsonl`

- total: 4
- passed: 4
- failed: 0
- schema pass: 4/4
- chief complaint consistency: 4/4
- risk recognition consistency: 4/4
- negation detection: n/a for this validation split

### Graph Eval

`python scripts/eval_report.py --mode graph --failed-only`

- total cases: 20
- passed: 6
- failed: 14
- business assertion pass rate: 30.0%
- failure analysis artifact: `artifacts/p0_1_eval_failure_analysis.json`

Key metrics:

- `raw_llm_json_valid_rate`: 0.0%
- `final_schema_pass_rate`: 100.0%
- `fallback_used_rate`: 100.0%
- `risk_recognition_consistency`: 100.0%
- `risk_recall_on_redflag_cases`: 100.0%
- `negation_accuracy`: 100.0%
- `multi_turn_core_completion_rate`: 0.0%
- `rag_recall_at_3`: 50.0%
- `business_assertion_pass_rate`: 30.0%

### Diff Check

`git diff --check`

- Passed with only CRLF conversion warnings from Git on Windows.

## 5. Real LLM Path Status

The real LLM path is implemented but not verified in this environment.

Reason:

- `langchain_openai` is missing.

Although `.env`, `OPENAI_API_KEY`, and `OPENAI_BASE_URL` are present, no real structured-output or legacy ChatOpenAI request was executed.

## 6. Fallback Path Status

Fallback path is verified.

Verified fallback capabilities:

- rule fallback extractor does not crash without LLM dependencies
- graph sequential fallback works without `langgraph`
- fake structured extractor works without API keys
- final `TurnOutput` schema pass is tracked separately from raw JSON validity
- high-risk and negation rules pass the P0.1 regression suite
- report safety post-check preserves structured fields

## 7. RAG Status

Current RAG path is fallback RAG, not real BM25.

Reason:

- `rank_bm25` is missing.

Verified:

- lexical fallback returns evidence
- evidence contains `chunk_id`, `source`, `content`, `score`, `retriever_type`
- RAG enhancer can skip LLM enhancement and still attach evidence metadata
- RAG only changes `impression` and `advice` when LLM enhancement is available; core report fields are preserved

Not verified:

- real `rank_bm25.BM25Okapi`
- dense/vector retrieval
- reranker beyond no-op ordering

## 8. Current Open Issues

1. Real LLM extraction is not verified because `langchain_openai` is missing.
2. Real LangGraph runtime is not verified because `langgraph` is missing.
3. Real BM25 is not verified because `rank_bm25` is missing.
4. Graph business assertion pass rate remains 30.0% in fallback-only mode.
5. Multi-turn core completion is 0.0% in fallback-only mode because rule fallback intentionally does not do full semantic extraction.
6. Dense retriever and reranker remain P0 architecture placeholders.

## 9. Why Business Assertions Did Not Improve

The command `python scripts/eval_report.py --mode graph --failed-only` intentionally runs the graph in the current environment. Since `langchain_openai` is missing, every turn uses `rule_fallback`.

The rule fallback is designed to keep the system safe and non-crashing, not to fully extract chief complaint, duration, and symptoms. Therefore the failures are mostly classified as `fallback_limit`, not as risk-rule failures.

Risk recall and negation accuracy are both 100.0% in this fallback-only evaluation.

## 10. P1 Recommendation

Do not start implementation-heavy P1 work yet.

Recommended next step before P1:

1. Install P0 dependencies from `requirements.txt`.
2. Re-run `python scripts/check_p0_env.py`.
3. Re-run graph eval with real `langgraph`, `langchain_openai`, and `rank_bm25` available.
4. Verify at least one real LLM structured extraction path and one real BM25 retrieval path.

After those checks pass, the project is ready to enter P1 planning for FastAPI, model gateway, vector retrieval, and observability. Those P1 items are intentionally not implemented in P0.1.

## P0.2 Real Path Validation

P0.2 验收报告见 `docs/P0_2_REAL_PATH_VALIDATION_REPORT.md`。
