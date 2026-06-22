# P4.6.5 Deprecation & Compatibility Plan

Generated/refreshed: 2026-06-20

This phase is inventory and planning only. No legacy, gate, SFT, RAG,
demo, eval, artifact, API, schema, SQLite, risk-rule, fake, real, or fallback
entrypoint was deleted or behaviorally changed.

## Policy

- Keep public API behavior frozen.
- Keep SQLite schema and historical session readability frozen.
- Keep `TurnOutput`, `RunState`, and `FinalReport` fields and meanings frozen.
- Keep risk rule IDs, keyword semantics, negation handling, and high-risk sticky
  behavior frozen.
- Keep fake, fallback, and real runtime paths explicit and separate.
- Keep RAG read-only for core consultation state.
- Do not remove files referenced by README, docs, tests, scripts, FastAPI
  routes, workflow graph, tool registry, or acceptance artifacts.
- Future deletion requires a separate approved cleanup phase with replacement
  docs, passing gates, and human confirmation.

## entrypoint_inventory

| ID | Scope | Entrypoints | Status | Reason |
| --- | --- | --- | --- | --- |
| api_runtime | FastAPI/API | `app/api/main.py`, `app/api/models.py`, `app/api/session_runtime.py`, `app/api/sqlite_store.py`, `app/api/runtime_config.py`, validators, redaction, errors, versioning | risky_do_not_touch | FastAPI routes, response models, SQLite compatibility, runtime config, redaction, and validation are contract-sensitive. |
| p4_workflow | Workflow graph | `app/agentic/workflow_adapter.py`, `app/graphs/*`, `app/memory/*`, `app/tools/internal_registry.py`, `app/safety/report_safety.py` | keep | Referenced by API, P4 gate, docs, and tests. |
| rules_and_schema | Core rules/schema | `app/rules/*`, `app/schemas/report_schemas.py`, `app/schemas/consultation.py` | risky_do_not_touch | Risk semantics and schema fields are frozen. |
| current_rag_boundary | Bounded RAG path | `app/rag/bm25_retriever.py`, `app/rag/hybrid_retriever.py`, `app/rag/evidence_boundary.py`, `app/rag/document_store.py`, `app/rag/embedding_retriever.py`, `app/rag/reranker.py`, `app/rag/base.py`, `app/chains/rag_enhancer.py`, `app/prompts/rag_prompt.py`, `app/rag/knowledge_base.txt` | keep_with_reason | P4 tests and docs verify RAG can provide evidence but cannot modify core state fields. |
| legacy_rag_retriever | Legacy RAG module | `app/rag/rag_retriever.py` | compatibility_shim | README/docs still list it; ranking behavior must be snapshotted before replacement. |
| vector_store_experiment | Dense/vector utility | `app/rag/build_vector_store.py` | archive_candidate | Manual/experimental utility with optional vector deps; not part of current P4 gate path. |
| sft_lora_manual | SFT/LoRA manual path | `app/chains/sft_infer_chain.py`, `app/prompts/sft_prompt.py`, `app/schemas/sft_schemas.py`, `app/utils/sft_postprocess.py`, `scripts/run_sft.py`, `scripts/build_sft_dataset.py`, `scripts/convert_sft_dataset.py`, `scripts/filter_sft_manual_only.py`, `scripts/train_sft_lora.py`, `scripts/test_sft_chain.py`, `scripts/test_sft_lora_infer.py`, `scripts/eval_sft_extract.py` | keep_with_reason | README, SFT docs, historical artifacts, and optional `mode="sft"` path reference these. |
| gate_runners | Historical and current gates | `scripts/run_p1_gate.py`, `scripts/run_p2_gate.py`, `scripts/run_p3_gate.py`, `scripts/run_p4_gate.py`, `scripts/run_code_health_gate.py`, `scripts/gate_utils.py`, `scripts/check_api_contract.py`, `scripts/check_runtime_config.py`, `scripts/check_observability.py`, `scripts/check_release_packaging.py`, `scripts/secret_scan.py`, `scripts/validate_p1_api_contract.py` | keep | README/docs/tests/artifacts reference these; gate artifact schemas remain acceptance evidence. |
| eval_and_case_corpus | Eval/reliability scripts and fixtures | `scripts/eval_report.py`, `scripts/run_case_corpus_eval.py`, `scripts/run_long_session_demo.py`, `artifacts/eval_cases/*`, `tests/report_test_cases.json`, `tests/sft_tests_cases.json` | keep_with_reason | Used by docs, gates, reliability tests, and acceptance artifacts. |
| api_demo_and_audit | Demo/audit/debug utilities | `scripts/run_api_demo.py`, `scripts/run_api_persistence_demo.py`, `scripts/replay_api_case.py`, `scripts/audit_session.py`, `scripts/inspect_sqlite_store.py`, `scripts/run_graph_demo.py`, `scripts/validate_real_extractor.py`, `scripts/validate_real_bm25.py`, `scripts/test_env.py` | keep_with_reason | Useful for local validation and referenced by docs/artifacts; may be reorganized only after docs migrate. |
| legacy_mvp_cli | Legacy MVP path | `scripts/run_mvp.py`, `app/chains/mvp_chain.py`, `app/prompts/mvp_prompt.py` | deprecated | Legacy CLI path remains available; no deletion in P4. |
| legacy_stateful_cli | Legacy stateful path | `scripts/run_state.py`, `scripts/run_state1.py`, `app/chains/stateful_chain.py`, `app/chains/stateful1_chain.py`, `app/prompts/stateful_prompt.py`, `app/prompts/stateful1_prompt.py`, `app/schemas/stateful1_schemas.py` | deprecated | Legacy CLI path remains available; no deletion in P4. |
| legacy_report_cli | Legacy report CLI/eval mode | `scripts/run_report.py`, `scripts/eval_report.py --mode legacy` | deprecated | Kept for historical comparison. `app/chains/report_chain.py` itself is not deprecated because graph fallback and tests still use its helpers. |
| artifacts_evidence | Acceptance artifacts | `artifacts/p*`, `artifacts/code_health_*`, `artifacts/secret_scan_result.json`, `artifacts/replay_cases/*` | risky_do_not_touch | These are validation evidence and gate baselines; do not remove in P4. |

## keep_list

- API runtime and public response models.
- P4 workflow adapter, graph nodes, memory manager, tool registry, and report
  safety boundary.
- Risk rules and public schema models.
- Current bounded RAG evidence path.
- Gate runners and check scripts.
- Eval corpus, long-session reliability path, and acceptance fixtures.
- SFT/LoRA manual path, while clearly separated from real runtime.
- Existing validation artifacts.

## compatibility_shims

| Entrypoint | Status | Reason |
| --- | --- | --- |
| `app/rag/rag_retriever.py` | compatibility_shim | README/docs still list the legacy module; remove only after ranking snapshots and docs migration. |
| `app/api/sqlite_store.py::DEFAULT_DB_PATH` | compatibility_shim | `scripts/run_case_corpus_eval.py` imports this re-export. |
| `scripts/run_p2_gate.py`, `scripts/run_p3_gate.py`, `scripts/run_p4_gate.py` `_redact_preserving_schema` alias | compatibility_shim | P4.6.4 consolidated the helper but preserved local call names. |
| `scripts/eval_report.py --mode legacy` | compatibility_shim | Preserves old report-chain comparison path while graph mode is the preferred validation path. |

## deprecated_candidates

| Entrypoint | Currently referenced | Affects gate | Affects tests | Affects API/schema | Suggested deletion condition | Suggested phase |
| --- | --- | --- | --- | --- | --- | --- |
| `scripts/run_mvp.py`, `app/chains/mvp_chain.py`, `app/prompts/mvp_prompt.py` | yes: README/docs/code-health audit | no direct P4 gate path; compileall covers syntax | no direct unittest dependency found | no | README/docs remove MVP CLI instructions; replacement demo path exists; one release passes without references. | P5 legacy CLI cleanup |
| `scripts/run_state.py`, `scripts/run_state1.py`, `app/chains/stateful_chain.py`, `app/chains/stateful1_chain.py`, `app/prompts/stateful_prompt.py`, `app/prompts/stateful1_prompt.py`, `app/schemas/stateful1_schemas.py` | yes: README/docs and scripts | no direct P4 gate path; compileall covers syntax | no direct unittest dependency found | no | README/docs migrate to graph/API flow; stateful schemas proven unused outside legacy scripts; human approval. | P5 legacy CLI cleanup |
| `scripts/run_report.py`, `scripts/eval_report.py --mode legacy` | yes: README/docs and eval script | eval script remains used by historical artifacts; compileall covers syntax | graph tests use `report_chain` helpers, not this CLI | no | Graph/API eval fully replaces legacy comparison; docs and historical reports stop instructing legacy mode. | P5 eval cleanup |

No deprecated candidate is removed in P4.6.5.

## archive_candidates

| Entrypoint | Currently referenced | Affects gate | Affects tests | Affects API/schema | Archive condition | Suggested phase |
| --- | --- | --- | --- | --- | --- | --- |
| `app/rag/build_vector_store.py` | yes: README/docs/audit references | no current P4 gate path | no direct unittest dependency found | no | Decide optional vector deps and move to documented experimental/tooling area with import-safe tests. | P5 RAG tooling cleanup |
| Demo/audit utilities group | yes: docs/artifacts reference several scripts | some are invoked by docs or historical gates | some covered indirectly by script tests | no | Create `scripts/demo/` or docs-only runbook and keep backward-compatible shims for one release. | P5 tooling organization |

## remove_later_candidates

| Entrypoint | Currently referenced | Affects gate | Affects tests | Affects API/schema | Suggested deletion condition | Suggested phase |
| --- | --- | --- | --- | --- | --- | --- |
| `app/rag/rag_retriever.py` | yes: README/docs/audit | no current P4 gate path, but RAG behavior is acceptance-sensitive | no direct current unittest import found; RAG tests cover newer path | no | Snapshot current legacy ranking, migrate docs to `bm25_retriever`/`hybrid_retriever`, prove no artifact or README reference remains. | P5 RAG compatibility cleanup |
| Legacy MVP CLI group | yes | no direct P4 gate path | no direct unittest dependency found | no | Same as deprecated condition plus one full gate cycle after docs migration. | P5 legacy CLI cleanup |
| Legacy stateful CLI group | yes | no direct P4 gate path | no direct unittest dependency found | no | Same as deprecated condition plus one full gate cycle after docs migration. | P5 legacy CLI cleanup |

No remove-later candidate has deletion approval.

## risky_do_not_touch

- `TurnOutput`, `RunState`, and `FinalReport` fields and semantics.
- FastAPI routes and response models in `app/api/main.py` and
  `app/api/models.py`.
- SQLite schema, schema metadata, and historical persistence compatibility.
- Risk rule IDs, keyword matching, negation behavior, and high-risk sticky
  behavior.
- P4 workflow adapter and graph behavior used by API and P4 gate.
- RAG evidence boundary fields: `chief_complaint`, `duration`, `risk_status`,
  `risk_rule_ids`.
- Tool registry names: `risk_check_tool`, `rag_search_tool`,
  `report_safety_tool`, `export_report_tool`, `eval_case_tool`.
- Gate runners and generated acceptance artifacts.
- Synthetic eval cases and replay artifacts under `artifacts/`.

## deletion_preconditions

Before any future deletion:

1. Show zero references in README, docs, tests, scripts, app code, and
   acceptance artifacts.
2. Prove the item is absent from gate runners or provide a replacement gate
   assertion.
3. Prove full unittest, compileall, code-health gate, and P4 gate still pass.
4. Confirm no API/schema/SQLite/risk-rule behavior changes.
5. Preserve fake, fallback, real, SFT, and RAG path separation.
6. For RAG cleanup, provide deterministic retrieval/ranking snapshots.
7. For legacy CLI cleanup, provide replacement runbook/docs and one release of
   compatibility notice.
8. Obtain explicit human approval in a later cleanup phase.

## validation_results

| Command | Status | Notes |
| --- | --- | --- |
| `python scripts/run_code_health_gate.py` | pass | hard=`ok`, soft=`caution`, 4/4 hard checks passed. |
| `python scripts/run_p4_gate.py` | pass | Existing Transformers/PyTorch warning remains advisory. |
| `python -m unittest discover -s tests` | pass | 270 tests passed. |
| `python -m compileall -q app scripts tests` | pass | Compile check passed. |
| `python -m json.tool artifacts/deprecation_compatibility_plan.json` | pass | P4.6.5 JSON artifact is valid. |

## unchanged_contracts

- No API response schema changes.
- No SQLite schema changes.
- No risk rule semantic changes.
- No `TurnOutput`, `RunState`, or `FinalReport` changes.
- No deletion of legacy/gate/SFT/RAG compatibility entrypoints.
- No fake/real/fallback behavior changes.
- No artifact deletion.

## next_recommended_phase

P4.6.6 Encoding / Chinese Literal Stability:

- Inventory user-visible Chinese literals and known mojibake candidates.
- Freeze output-sensitive strings through manifest and snapshot guidance.
- Avoid broad text repair until product copy review and snapshot tests approve it.
