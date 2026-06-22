# P0 Repository Audit

## Current Entry Points

- CLI entry: `scripts/run_report.py`
- Main turn function: `app.chains.report_chain.run_turn(state, user_input, mode="api")`
- API extraction path: `ChatOpenAI` + prompt-only JSON output in `app/chains/report_chain.py`
- SFT extraction path: `mode="sft"` delegates to `app.chains.sft_infer_chain.run_sft_turn()`

The current CLI should remain runnable. P0 changes should add graph mode or demo entry points instead of deleting the legacy flow.

## Current Schemas

`TurnOutput` fields:

- `chief_complaint`
- `duration`
- `symptoms`
- `symptoms_status`
- `sleep`
- `appetite`
- `stool_urine`
- `risk_flags`
- `risk_flags_status`
- `next_question`
- `summary`

`RunState` fields:

- `chief_complaint`
- `duration`
- `symptoms`
- `symptoms_status`
- `sleep`
- `appetite`
- `stool_urine`
- `risk_flags`
- `risk_flags_status`
- `next_question`
- `summary`
- `final_report`
- `turn_count`

`FinalReport` fields:

- `summary`
- `impression`
- `advice`
- `triage_level`
- `info_complete`
- `missing_core_fields`
- `followup_needed`

## Current Rule Fallbacks

Rule fallbacks are currently implemented inside `app/chains/report_chain.py`:

- vague chief complaint filtering: `clean_chief_complaint()`
- normal fever vs high fever filtering: `filter_false_high_fever()`
- risk negation heuristic: `infer_risk_status_from_user_input()`
- state merge and no-regression rules: `merge_state()`
- next question order: `decide_next_question()`
- report generation rules: `generate_final_report()`

These are suitable for extraction into explicit rule modules and graph nodes. The legacy functions should remain available to avoid breaking existing scripts.

## Current RAG Flow

- `app/rag/rag_retriever.py` loads `app/rag/knowledge_base.txt`
- knowledge is split by blank lines into chunks
- BM25 is built with `rank_bm25.BM25Okapi`
- lightweight Chinese keyword tokenization and rule score boosts are used
- `app/chains/rag_enhancer.py` builds a query from `RunState` + `FinalReport`
- retrieved chunks are passed to an LLM that may only enhance `impression` and `advice`

BM25 should remain the default retriever. Dense retrieval can be introduced as a pluggable interface with fallback.

## Current Evaluation

- `scripts/eval_report.py` loads `tests/report_test_cases.json`, runs `run_turn()` across turns, and checks final state/report assertions.
- `scripts/eval_sft_extract.py` compares predicted SFT outputs against processed validation JSONL for core fields.

P0 should add aggregate metrics without requiring external APIs when only local metrics are available.

## Good LangGraph Migration Targets

The current `report_chain.py` can be split into explicit graph nodes:

- input normalization
- turn extraction
- schema validation
- state merge
- risk rule check
- next-question decision
- optional knowledge retrieval
- final report generation
- safety post-check

The graph should use the existing `RunState`, `TurnOutput`, and `FinalReport` models so the old and new flows can coexist.

## Areas To Avoid Changing In P0

- Do not remove `report_chain.py` or `scripts/run_report.py`.
- Do not change the SFT/LoRA training data format.
- Do not add FastAPI, web frontend, vLLM deployment, MCP, knowledge graph, or permission systems.
- Do not replace BM25 with a mandatory embedding model.
- Do not expand the medical scope into diagnosis, prescription, or treatment planning.
