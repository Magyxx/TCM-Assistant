# D2-P6B Main Flow End-to-End Local-LoRA Validation

## 1. Branch and HEAD

- Branch: `feature/device2-local-lora-extractor`
- Validation HEAD: `5c8b123`
- Validation artifact: `artifacts/device2/d2_p6b_e2e_validation.json`
- Artifact status: `ok`

`5c8b123` is the D2-P6A baseline commit created before this D2-P6B work. The final D2-P6B commit hash is intentionally reported in the handoff output because a commit cannot contain its own final hash without changing that hash.

## 2. D2-P6A Commit Status

D2-P6A was uncommitted at the start of this round and was committed separately:

- `5c8b123 extractors: integrate local lora backend for device2`

## 3. Files Added or Modified in D2-P6B

- `app/graphs/consultation_nodes.py`
- `app/graphs/consultation_graph.py`
- `app/graphs/consultation_state.py`
- `tests/test_device2_p6b_main_flow_e2e.py`
- `scripts/device2/verify_d2_p6b_e2e.py`
- `artifacts/device2/d2_p6b_e2e_validation.json`
- `reports/device2/d2_p6b_e2e_report.md`

## 4. Main Flow Entry

The E2E validation uses the existing main consultation flow:

`app.graphs.consultation_graph.run_consultation_graph(...)`

The verifier runs it with `use_langgraph=False` for deterministic local execution and `rag_enabled=False` so the test focuses on extraction, schema validation, RunState merge, and deterministic risk rules.

## 5. Router Selection

`EXTRACTOR_BACKEND=local_lora` is set in the mocked E2E environment. `extract_turn(...)` sees that override, calls `app.extractors.router.extract_with_backend_router(...)`, and the router resolves `LocalLoraExtractorBackend`.

The artifact records:

- `router_selected_local_lora: passed`
- local_lora case `backend: local_lora`
- local_lora case `strategy: extractor_backend_router`

## 6. E2E Call Chain

`user_input -> run_consultation_graph -> extract_turn_node -> extract_turn -> router -> local_lora -> TurnOutput -> validate_turn -> merge_state -> risk_rule_check`

The mocked local_lora client returns OpenAI-compatible chat completion text. The local adapter parses JSON, validates it as `TurnOutput`, strips model-owned risk claims, and then the graph applies deterministic `risk_rule_check` after RunState merge.

## 7. Case Results

| Case | Result | Notes |
| --- | --- | --- |
| `digestive_negation_001` | passed | `chief_complaint=胃胀`, `duration=一周`; model risk claim stripped; final `risk_flags_status=none` from rules. |
| `cough_negation_001` | passed | negated fever/chest pain/dyspnea did not become present; final `risk_flags_status=none`. |
| `high_risk_chest_dyspnea_001` | passed | chest pain and dyspnea hit deterministic rules; final `risk_flags_status=present`; rule IDs include `P0_RISK_CHEST_PAIN` and `P0_RISK_DYSPNEA`. |
| `schema_fail_001` | passed | invalid JSON returned `turn_output=None`; schema failed closed; RunState core snapshot unchanged. |
| `backend_switch_local_lora_001` | passed | `EXTRACTOR_BACKEND=local_lora` path ran through the main flow and updated RunState. |
| `fake_backend_regression_001` | passed | `EXTRACTOR_BACKEND=fake` still ran and updated RunState through the existing fake path. |

## 8. Schema-Fail Blocking Behavior

When the extractor returns no valid `TurnOutput`, `validate_turn` now records `state_merge_blocked=True` and keeps `turn_output=None`.

Downstream graph nodes honor that flag and do not merge candidate fields, apply risk-rule writes, ask follow-up writes, retrieve evidence, or generate a report for the failed turn. In the schema-fail case, `chief_complaint`, `duration`, risk fields, `turn_count`, and `final_report` remained unchanged.

## 9. Risk Rule Ownership

local_lora only owns a `TurnOutput` candidate. It does not own final risk state.

In the digestive and cough negation cases, the mocked local_lora response claimed risk `present`, but final `risk_flags_status` was `none` because deterministic rules saw negated risk language. In the high-risk case, final `present` came from deterministic risk rules, not from a model-supplied risk claim.

## 10. Fake Backend Regression

The fake backend regression passed under `EXTRACTOR_BACKEND=fake`.

The artifact records `backend=fake`, `schema_pass=true`, `run_state_updated=true`, and `fake_backend_regression=passed`.

## 11. Live vLLM Smoke

Live vLLM smoke was skipped:

- `enabled: false`
- `status: skipped`
- `reason: RUN_LOCAL_VLLM_SMOKE not enabled`

This is expected for the default unit-test and verification path. Live smoke remains optional through `RUN_LOCAL_VLLM_SMOKE=1`.

## 12. Full Unittest Discover

Full unittest discover is not claimed as passed.

The D2-P6B artifact records `failed_due_preexisting_local_env_blockers` for full discover, with known blockers:

- missing `fastapi`
- import-time cloud model config
- temp permission errors
- historical fixture failures

## 13. Acceptance Commands

- `git status --short`: completed; showed the six expected D2-P6B changed files before commit.
- `git log --oneline -10`: completed; top commit was D2-P6A `5c8b123` before the D2-P6B commit.
- `python -m compileall -q app scripts tests`: passed.
- `python -m unittest tests.test_device2_p6b_main_flow_e2e`: passed, `6 tests`.
- `python scripts/device2/verify_d2_p6b_e2e.py --json --output artifacts/device2/d2_p6b_e2e_validation.json`: passed, artifact `status=ok`.
- `python scripts/secret_scan.py --json --output artifacts/secret_scan_result.json`: passed, `status=ok`, `finding_count=0`.

## 14. Model Weights

No model weights, base model files, adapter checkpoints, or checkpoint directories were added by D2-P6B.

The verifier reports:

- `weights_not_tracked: true`
- `tracked_weight_findings: []`

## 15. Next Step

Proceed to D2-P6C backend compare.
