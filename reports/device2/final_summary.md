# Device2 Final Summary

## Branch and Baseline HEAD

- Branch: `feature/device2-local-lora-extractor`
- D2-P7 baseline HEAD: `c56fbb0 eval: add device2 backend comparison metrics`
- Final D2-P7 commit: reported after commit creation

## Stage Table

| Stage | Core commits | Main outputs | Artifact paths | Status |
| --- | --- | --- | --- | --- |
| D2-P0 repo/runtime readiness | `159c3cb`, `37e0cee`, `1b4ef27`, `f6c5d0f`, `9b2547e` | branch baseline, WSL/runtime/storage plan, dependency gates | `reports/device2/repo_intake_report.md`, `reports/device2/env_check_report.md`, `reports/device2/ml_runtime_dependency_report.md` | complete |
| D2-P1 local base inference | `77364b4` | local base prediction baseline | `artifacts/device2/predictions/local_base_sample.jsonl`, `reports/device2/d2t1_evaluation_report.md` | complete |
| D2-P2 data preparation | `a539feb` | risk-repair datasets and configs | `data/sft/processed/train_sft_risk_repair.jsonl`, `data/sft/eval/eval_risk_repair.jsonl`, `configs/device2/lora_risk_repair.yaml` | complete |
| D2-P3 QLoRA/SFT training | `77364b4`, `f57e2d2`, `3fb8e31` | D2-T1 and D2-T1R2 adapter runs, external adapter storage | `reports/device2/d2t1_training_report.md`, `reports/device2/d2t1r2_training_report.md`, `artifacts/device2/metrics/d2t1r2_training_metrics.json` | complete |
| D2-P4 local evaluation | `1235ba5`, `3fb8e31` | extraction/risk/negation metrics and badcase review | `reports/device2/d2t1r2_evaluation_report.md`, `reports/device2/d2t1r2_badcase_analysis.md`, `artifacts/device2/metrics/d2t1r2_compare_to_d2t1.json` | complete |
| D2-P5 vLLM serving and realpath | `77364b4`, `3fb8e31` | vLLM serving report, local_lora realpath, backend compare | `reports/device2/DEVICE2_VLLM_SERVING_REPORT.md`, `reports/device2/local_lora_realpath_report.md`, `reports/device2/backend_compare_report.md` | complete with serving caveats |
| D2-P6A backend integration | `5c8b123` | `local_lora` as `ExtractorBackend`, router support, schema guards | `artifacts/device2/d2_p6_integration_validation.json`, `reports/device2/d2_p6_integration_report.md` | ok |
| D2-P6B main-flow E2E | `547bd24` | main graph E2E, schema-fail no-write behavior, fake regression | `artifacts/device2/d2_p6b_e2e_validation.json`, `reports/device2/d2_p6b_e2e_report.md` | ok |
| D2-P6C backend comparison | `c56fbb0` | backend metrics, prediction samples, badcase samples | `artifacts/device2/d2_p6c_backend_metrics.json`, `artifacts/device2/d2_p6c_backend_predictions.sample.jsonl`, `artifacts/device2/d2_p6c_backend_badcases.sample.jsonl`, `reports/device2/d2_p6c_backend_compare_report.md` | ok |

## Current Branch Capability

The branch can run the main consultation graph with `EXTRACTOR_BACKEND=local_lora`, route through the local LoRA extractor, parse JSON from an OpenAI-compatible local endpoint, validate it as `TurnOutput`, block invalid candidates from writing `RunState`, and keep final risk status owned by deterministic rules.

It also provides focused regression tests, P6B/P6C/P7 verifier scripts, backend comparison metrics, sample predictions, badcase summaries, and handoff documentation.

## Current Branch Limits

- The LoRA extractor is single-turn structured extraction only.
- It does not own final risk status.
- It does not generate treatment plans or prescriptions.
- Live vLLM smoke is skipped unless `RUN_LOCAL_VLLM_SMOKE=1`.
- `cloud_llm` is skipped in default local backend comparison.
- The D2-P6C set is a seven-case engineering regression set.
- The broader requested `eval_extract`, `eval_negation`, and `eval_risk` JSONL files are absent.
- Full unittest discover remains blocked by pre-existing local environment issues.

## D2-P6C Metrics Summary

| Backend | Status | Cases | JSON valid | Schema pass | Chief match | Duration match | Risk accuracy | Structured error | Avg ms | P95 ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `fake` | passed | 7 | 1.0 | 1.0 | 0.666667 | 0.857143 | 1.0 | 0.0 | 0.102 | 0.272 |
| `local_base` | passed_with_badcases | 7 | 0.857143 | 0.857143 | 0.666667 | 0.571429 | 1.0 | 0.142857 | 0.111 | 0.212 |
| `local_lora` | passed | 7 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 | 0.089 | 0.107 |
| `cloud_llm` | skipped | 0 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |

`local_lora` improved over `local_base` on JSON validity, schema pass rate, chief complaint match rate, duration match rate, structured error rate, average latency, and p95 latency in the mocked default comparison.

## Badcase Summary

The D2-P6C badcase sample contains eight entries:

- `local_base`: one `invalid_json` case, `schema_fail_mock_001`
- `cloud_llm`: seven `backend_skipped` cases because default verification avoids external API calls
- `local_lora`: no badcases in the D2-P6C sample
- hallucination rate: `0.0`
- risk false positives: `0`
- risk false negatives: `0`

## Environment Blockers

Full unittest discover is not claimed as passed. Prior reports consistently label it:

```text
failed_due_preexisting_local_env_blockers
```

Known blockers include missing `fastapi` in the local Windows test environment, import-time cloud model config, temp permission errors, and historical fixture failures.

## Merge Discussion Status

The branch is ready for review and handoff discussion, not blind mainline merge.

Recommended merge scope:

- adapter interface additions
- extractor router updates
- local extractor code
- configuration examples
- scripts
- focused tests
- docs
- reports
- small validation artifacts

Do not merge:

- base model files
- adapter weights
- checkpoints
- large prediction files
- local caches
- `.env`

## Next Step

Wait for Device1 mainline P8-M3 structured extractor adapter work or P8-M5 integrated validation to stabilize the mainline interface. Then perform PR review or cherry-pick handoff for the reviewed Device2 pieces.
