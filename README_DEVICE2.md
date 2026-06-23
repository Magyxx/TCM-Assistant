# Device2 Local-LoRA Extractor

Device2 is the Local-LoRA Extractor branch for TCM-Assistant. It packages a local LoRA-backed structured extraction backend, served through a local vLLM OpenAI-compatible API, and connects that backend to the existing main consultation flow through the project extractor router.

## Scope

Device2 produces a `TurnOutput` candidate for one consultation turn. It is an engineering branch for structured extraction, schema guarding, backend comparison, and handoff readiness.

Device2 does not:

- provide diagnosis
- prescribe formulas, medication, dosage, or treatment plans
- train a complete multi-turn Agent
- replace main-system risk rules
- commit base model weights
- commit `adapter_model.safetensors`
- save real patient private data

## Architecture

```text
user_input
  -> main graph / run_consultation_graph
  -> extractor router
  -> local_lora_extractor
  -> local vLLM OpenAI-compatible API
  -> TurnOutput JSON
  -> Pydantic validation
  -> RunState
  -> RiskRuleEngine
```

The LoRA path only proposes extraction fields. `TurnOutput.model_validate(...)` is the schema gate, failed schema candidates do not write to `RunState`, and final risk status remains owned by `RiskRuleEngine`.

## Backend Switching

Set `EXTRACTOR_BACKEND` to choose the extractor implementation:

```powershell
$env:EXTRACTOR_BACKEND="fake"
$env:EXTRACTOR_BACKEND="cloud_llm"
$env:EXTRACTOR_BACKEND="local_base"
$env:EXTRACTOR_BACKEND="local_lora"
```

Device2 local runtime variables:

```powershell
$env:LOCAL_LLM_BASE_URL="http://127.0.0.1:8000/v1"
$env:LOCAL_LLM_MODEL="tcm-extractor-lora"
$env:LOCAL_LLM_API_KEY="EMPTY"
$env:RUN_LOCAL_VLLM_SMOKE="1"
```

`RUN_LOCAL_VLLM_SMOKE=1` is optional. Without it, live vLLM smoke tests are skipped by design.

## Stage Results

| Stage | Core commits | Outputs | Artifacts | Status |
| --- | --- | --- | --- | --- |
| D2-P0 repo and runtime intake | `159c3cb`, `37e0cee`, `1b4ef27`, `f6c5d0f`, `9b2547e` | Device2 branch baseline, WSL/runtime/storage readiness plan, ML runtime gates | `reports/device2/repo_intake_report.md`, `reports/device2/env_check_report.md`, `reports/device2/ml_runtime_dependency_report.md` | complete |
| D2-P1 local base inference baseline | `77364b4` | local base inference and baseline prediction path | `artifacts/device2/predictions/local_base_sample.jsonl`, `reports/device2/d2t1_evaluation_report.md` | complete |
| D2-P2 synthetic data and eval sets | `a539feb` | risk-repair training, validation, and eval JSONL sets | `data/sft/processed/train_sft_risk_repair.jsonl`, `data/sft/eval/eval_risk_repair.jsonl`, `data/sft/eval/eval_negation_repair.jsonl` | complete |
| D2-P3 QLoRA/SFT training | `77364b4`, `f57e2d2`, `3fb8e31` | D2-T1 adapter run, D2-T1R2 risk-repair continuation, external adapter outputs | `reports/device2/d2t1_training_report.md`, `reports/device2/d2t1r2_training_report.md`, `artifacts/device2/metrics/d2t1r2_training_metrics.json` | complete; weights external |
| D2-P4 local evaluation | `1235ba5`, `3fb8e31` | extraction, negation, risk, repair metrics and badcase analysis | `reports/device2/d2t1r2_evaluation_report.md`, `reports/device2/d2t1r2_badcase_analysis.md`, `artifacts/device2/metrics/d2t1r2_compare_to_d2t1.json` | complete |
| D2-P5 vLLM serving and backend realpath | `77364b4`, `3fb8e31` | vLLM serving attempt, local_lora realpath smoke, backend comparison | `reports/device2/DEVICE2_VLLM_SERVING_REPORT.md`, `reports/device2/local_lora_realpath_report.md`, `reports/device2/backend_compare_report.md` | complete with live serving caveats |
| D2-P6A integration | `5c8b123` | `local_lora` as `ExtractorBackend`, router modes, schema and fallback guards | `artifacts/device2/d2_p6_integration_validation.json`, `reports/device2/d2_p6_integration_report.md` | verifier ok |
| D2-P6B main-flow E2E | `547bd24` | `run_consultation_graph(...)` E2E with local_lora, fake regression, schema-fail no-write check | `artifacts/device2/d2_p6b_e2e_validation.json`, `reports/device2/d2_p6b_e2e_report.md` | verifier ok |
| D2-P6C backend compare | `c56fbb0` | `fake`, `local_base`, `local_lora`, `cloud_llm` comparison, metrics, samples, badcases | `artifacts/device2/d2_p6c_backend_metrics.json`, `artifacts/device2/d2_p6c_backend_predictions.sample.jsonl`, `artifacts/device2/d2_p6c_backend_badcases.sample.jsonl`, `reports/device2/d2_p6c_backend_compare_report.md` | verifier ok |

## Current Validation State

- `python -m compileall -q app scripts tests`: passed
- Focused D2-P6C tests: passed
- D2-P6A verifier: status ok
- D2-P6B verifier: status ok
- D2-P6C verifier: status ok
- Secret scan: passed, `finding_count=0`
- Full unittest discover: `failed_due_preexisting_local_env_blockers`
- Live vLLM smoke: live vLLM skipped unless RUN_LOCAL_VLLM_SMOKE=1

## D2-P6C Caveats

- D2-P6C used a 7-case minimal eval: `builtin_d2_p6c_minimal`
- Requested `data/sft/eval/eval_extract.jsonl`, `data/sft/eval/eval_negation.jsonl`, and `data/sft/eval/eval_risk.jsonl` are not present
- `cloud_llm skipped` because the default local verification path has no API key and avoids external calls
- live vLLM skipped unless RUN_LOCAL_VLLM_SMOKE=1
- full unittest discover pre-existing blockers remain documented as `failed_due_preexisting_local_env_blockers`
- These results are engineering regression evidence, not a large-scale medical evaluation

## Weight Management

Do not commit:

- base model files
- `adapter_model.safetensors`
- checkpoints
- large prediction files
- local cache directories
- `.env`

The repository `.gitignore` covers:

```text
artifacts/device2/checkpoints/
artifacts/device2/adapters/
artifacts/device2/model_cache/
artifacts/device2/hf_cache/
artifacts/device2/vllm_cache/
artifacts/device2/predictions/*.jsonl
!artifacts/device2/predictions/*_sample.jsonl
*.safetensors
*.bin
*.ckpt
*.pt
*.pth
*.gguf
*.onnx
```

## Acceptance Commands

Focused tests:

```powershell
python -m compileall -q app scripts tests
python -m unittest tests.test_device2_p6c_backend_compare
python -m unittest tests.test_device2_p6c_metrics
python -m unittest tests.test_device2_p6c_backend_skip
```

Verifiers:

```powershell
python scripts/device2/verify_d2_p6b_e2e.py --json --output artifacts/device2/d2_p6b_e2e_validation.json
python scripts/device2/verify_d2_p6c_backend_compare.py --json --output artifacts/device2/d2_p6c_backend_compare_validation.json
python scripts/device2/verify_d2_p7_final.py --json --output artifacts/device2/d2_p7_final_validation.json
```

Secret scan:

```powershell
python scripts/secret_scan.py --json --output artifacts/secret_scan_result.json
```

Optional live smoke:

```powershell
$env:RUN_LOCAL_VLLM_SMOKE="1"
python scripts/device2/test_local_lora_backend.py --json
```

