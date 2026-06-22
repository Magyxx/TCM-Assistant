# P0.1 Acceptance Gap Report

## Evidence Used

This report is based on code review of the P0 files and local command output from:

- `python scripts/check_p0_env.py`
- `python -m py_compile ...`
- `python -m unittest tests.test_p0_risk_rules`
- `python -m unittest tests.test_p0_turn_extractor`
- `python -m unittest tests.test_p0_consultation_graph`
- `python -m unittest tests.test_p0_hybrid_rag`
- `python -m unittest tests.test_p0_report_safety`
- `python scripts/eval_sft_extract.py --pred-file data\sft\processed\sft_report_turn_extract_val.jsonl`
- `python scripts\eval_report.py --mode graph --failed-only`

No real LLM call was verified in this environment because `langchain_openai` is missing.

## Completed P0 Capabilities

- Legacy CLI remains available through `scripts/run_report.py` and `app/chains/report_chain.py`.
- Unified extraction layer exists in `app/chains/turn_extractor.py`.
- Deterministic fake structured extractor exists for tests and graph validation.
- Rule fallback extractor remains available without external API dependencies.
- Graph workflow exists in `app/graphs/consultation_graph.py` with sequential fallback when `langgraph` is missing.
- ID-based risk rules exist in `app/rules/risk_rules.py`.
- Risk rule IDs and reasons are stored in `RunState` and final report metadata.
- Hybrid RAG architecture exists with BM25, lexical fallback, dense placeholder, and reranker placeholder.
- RAG evidence uses `chunk_id`, `source`, `content`, `score`, and `retriever_type`.
- Report safety post-check exists and preserves structured fields.
- P0 eval metrics now distinguish raw JSON validity, final schema pass, and fallback usage.
- Failure analysis artifact is generated at `artifacts/p0_1_eval_failure_analysis.json`.

## Current Environment Status

`python scripts/check_p0_env.py` reported:

- `langgraph`: missing
- `langchain_openai`: missing
- `rank_bm25`: missing
- `pydantic`: present
- `python-dotenv`: present
- `.env`: present
- `OPENAI_API_KEY`: present
- `OPENAI_BASE_URL`: present
- optional SFT deps: `torch` present; `transformers`, `datasets`, `peft`, `accelerate` missing
- mode: `fallback-only`

## Open Gaps

| Issue | Severity | Evidence | Fix Strategy |
| --- | --- | --- | --- |
| Real LLM structured extraction not verified | major | `langchain_openai: missing`; graph eval used `rule_fallback` | Install P0 dependencies and run legacy/graph LLM path with real provider; keep fake/fallback tests as non-network CI checks. |
| Real LangGraph runtime not verified | major | `langgraph: missing`; graph used sequential fallback | Install `langgraph` and run graph tests with `use_langgraph=True`; sequential fallback remains required. |
| Real BM25 not verified | major | `rank_bm25: missing`; RAG tests used `bm25_lexical_fallback` | Install `rank-bm25` and run HybridRetriever tests again; lexical fallback remains required. |
| Graph business assertions are low in fallback-only mode | major | `eval_report.py --mode graph --failed-only`: 6/20 passed, business assertion pass rate 30.0% | This is expected in fallback-only mode because rule fallback only handles risk status, not full semantic extraction. Use real LLM or fake extractor for full structured-path validation; do not hardcode test cases into fallback. |
| Raw LLM JSON valid rate is 0% in fallback-only mode | minor | `raw_llm_json_valid_rate: 0.0%`, `fallback_used_rate: 100.0%` | Metric is now correctly separated; no code fix needed unless LLM path is enabled. |
| Dense retriever is only an interface placeholder | minor | `EmbeddingRetriever` returns empty when unavailable | Keep as P0 placeholder; P1 can add embeddings/vector DB. |
| SFT full training path not verified | minor | optional deps missing except `torch` | Keep SFT eval format tests; install SFT deps only when training/inference is in scope. |

## Real, Fallback, And Placeholder Paths

### Real Paths Implemented But Not Verified Locally

- `app/chains/turn_extractor.py`: LangChain `with_structured_output(TurnOutput)` path.
- `app/chains/report_chain.py`: legacy `ChatOpenAI` JSON prompt path.
- `app/graphs/consultation_graph.py`: real LangGraph runtime path.
- `app/rag/bm25_retriever.py`: real `rank_bm25.BM25Okapi` path.

### Verified Fallback Paths

- `rule_fallback` extraction path.
- deterministic fake structured extractor.
- graph sequential fallback.
- BM25 lexical fallback.
- RAG enhancer no-LLM fallback.
- report safety post-check.

### Architecture Placeholders

- `EmbeddingRetriever`: dense/vector retrieval placeholder.
- `NoopReranker`: reranker placeholder.
- SFT/LoRA training path remains script-level and dependency-dependent.

## Acceptance Interpretation

P0.1 is locally reproducible in fallback-only mode. It is not yet a verified real-LLM or real-BM25 acceptance because required packages are missing from the current environment.
