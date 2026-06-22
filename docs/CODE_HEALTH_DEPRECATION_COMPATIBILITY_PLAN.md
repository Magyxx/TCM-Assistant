# P4.6.5 Deprecation & Compatibility Plan

Generated: 2026-06-20

This phase records the compatibility entrypoints that must stay available after
Phase 4. It is a documentation and planning phase only: no legacy, gate, SFT,
or RAG entrypoint is deleted, moved, or reinterpreted.

## Compatibility Policy

- P4 keeps all existing public API behavior frozen.
- P4 keeps SQLite schema and historical session readability frozen.
- P4 keeps `TurnOutput`, `RunState`, and `FinalReport` fields and meanings
  frozen.
- P4 keeps risk rule IDs, keyword semantics, negation handling, and high-risk
  sticky behavior frozen.
- P4 keeps fake/fallback/real runtime separation explicit.
- P4 keeps RAG read-only for core consultation state.
- Any future removal requires a separate approved deprecation PR, replacement
  docs, compatibility tests, and human confirmation.

## Compatibility Inventory

| Area | Entrypoints | P4 decision | Future rule |
| --- | --- | --- | --- |
| Legacy MVP CLI | `scripts/run_mvp.py`, `app/chains/mvp_chain.py`, `app/prompts/mvp_prompt.py` | keep | Candidate for future deprecation notice only. |
| Legacy stateful CLI | `scripts/run_state.py`, `scripts/run_state1.py`, `app/chains/stateful_chain.py`, `app/chains/stateful1_chain.py`, `app/prompts/stateful_prompt.py`, `app/prompts/stateful1_prompt.py` | keep | Do not remove until docs/tests migrate. |
| Report chain compatibility | `app/chains/report_chain.py::run_turn`, `scripts/run_report.py`, `scripts/eval_report.py --mode legacy` | keep | Preserve legacy comparison path. |
| SFT / LoRA manual path | `app/chains/sft_infer_chain.py`, `scripts/run_sft.py`, `scripts/build_sft_dataset.py`, `scripts/convert_sft_dataset.py`, `scripts/filter_sft_manual_only.py`, `scripts/train_sft_lora.py`, `scripts/test_sft_chain.py`, `scripts/test_sft_lora_infer.py`, `scripts/eval_sft_extract.py`, `app/prompts/sft_prompt.py`, `app/schemas/sft_schemas.py`, `app/utils/sft_postprocess.py` | keep | Optional/manual path; do not mix with real runtime path. |
| RAG compatibility | `app/chains/rag_enhancer.py`, `app/rag/rag_retriever.py`, `app/rag/bm25_retriever.py`, `app/rag/hybrid_retriever.py`, `app/rag/evidence_boundary.py`, `app/rag/document_store.py`, `app/rag/embedding_retriever.py`, `app/rag/reranker.py`, `app/rag/base.py`, `app/prompts/rag_prompt.py` | keep | No RAG writes to core state; ranking refactors require snapshots. |
| Gate runners | `scripts/run_p1_gate.py`, `scripts/run_p2_gate.py`, `scripts/run_p3_gate.py`, `scripts/run_p4_gate.py`, `scripts/run_code_health_gate.py`, `scripts/gate_utils.py` | keep | Artifact schemas must remain compatible. |
| SQLite/runtime re-export | `app/api/sqlite_store.py::DEFAULT_DB_PATH`, `app/api/runtime_config.py::DEFAULT_DB_PATH` | keep | Re-export remains until callers migrate with approval. |
| API compatibility modes | `ExtractorMode = real_llm/fake/fallback` | keep | Removing or changing modes is an API contract change. |

## Deprecation Ladder

| Level | Meaning | Allowed in P4 |
| --- | --- | --- |
| active | Current supported runtime path. | yes |
| compatibility | Kept for older scripts, tests, docs, or manual workflows. | yes |
| deprecated_documented | Marked as future removal candidate, still available. | docs only |
| removal_candidate | Replacement exists and tests prove no compatibility break. | no removal in P4 |
| removed | File or API deleted. | not allowed in P4 |

P4.6.5 only assigns `active` or `compatibility`. It does not move anything to
`removed`.

## changed_files

| File | Change | Risk |
| --- | --- | --- |
| `docs/CODE_HEALTH_DEPRECATION_COMPATIBILITY_PLAN.md` | Added P4.6.5 compatibility inventory and deprecation ladder. | safe |
| `artifacts/code_health_deprecation_compatibility_plan.json` | Added machine-readable P4.6.5 plan. | safe |

## validation_results

| Command | Status | Notes |
| --- | --- | --- |
| `python scripts/run_code_health_gate.py` | pass | hard=`ok`, soft=`caution`, 4/4 hard checks passed. |
| `python scripts/run_p4_gate.py` | pass | Existing Transformers/PyTorch warning remains advisory. |
| `python -m unittest discover -s tests` | pass | 269 tests passed. |
| `python -m compileall -q app scripts tests` | pass | Compile check passed. |
| `python -m json.tool artifacts/code_health_deprecation_compatibility_plan.json` | pass | P4.6.5 JSON artifact is valid. |

## unchanged_contracts

- `TurnOutput`, `RunState`, and `FinalReport` fields and semantics unchanged.
- FastAPI API contract unchanged.
- SQLite schema unchanged.
- Risk rule semantics unchanged.
- Legacy, gate, SFT, and RAG compatibility entrypoints kept.
- Fake/test path and real runtime path remain separated.
- RAG remains read-only with respect to core consultation state.
- Runtime `requirements.txt` unchanged.

## known_cautions

- Several compatibility entrypoints are old or manual, but still referenced by
  docs, scripts, tests, or historical baselines.
- SFT dependencies remain version-sensitive and optional/manual.
- RAG helper consolidation remains blocked on deterministic ranking snapshots.
- `DEFAULT_DB_PATH` remains a compatibility re-export.
- Future cleanup must not treat this plan as removal approval.

## risky_items_not_touched

- Legacy MVP/stateful CLI files.
- Gate runner entrypoints and artifact schemas.
- SFT and LoRA scripts, prompts, schemas, and postprocessing helpers.
- RAG retrievers, evidence boundary, and knowledge files.
- Public API extractor modes.
- SQLite runtime path constants and schema metadata.
- User-visible Chinese literals.

## next_recommended_phase

P4.6.6 Encoding / Chinese Literal Stability:

- Inventory user-visible Chinese literals and known mojibake candidates.
- Freeze output-sensitive strings through manifest and snapshot guidance.
- Avoid broad text repair until product copy review and snapshot tests approve it.
