# Device2 Final Usage

This guide is for local verification and handoff review of the Device2 Local-LoRA Extractor branch.

## Default Local Verification

Run from the repository root:

```powershell
python -m compileall -q app scripts tests
python -m unittest tests.test_device2_p6c_backend_compare
python -m unittest tests.test_device2_p6c_metrics
python -m unittest tests.test_device2_p6c_backend_skip
python scripts/device2/verify_d2_p6b_e2e.py --json --output artifacts/device2/d2_p6b_e2e_validation.json
python scripts/device2/verify_d2_p6c_backend_compare.py --json --output artifacts/device2/d2_p6c_backend_compare_validation.json
python scripts/device2/verify_d2_p7_final.py --json --output artifacts/device2/d2_p7_final_validation.json
python scripts/secret_scan.py --json --output artifacts/secret_scan_result.json
```

## Backend Selection

```powershell
$env:EXTRACTOR_BACKEND="fake"
$env:EXTRACTOR_BACKEND="cloud_llm"
$env:EXTRACTOR_BACKEND="local_base"
$env:EXTRACTOR_BACKEND="local_lora"
```

## Local vLLM Variables

```powershell
$env:LOCAL_LLM_BASE_URL="http://127.0.0.1:8000/v1"
$env:LOCAL_LLM_MODEL="tcm-extractor-lora"
$env:LOCAL_LLM_API_KEY="EMPTY"
```

## Optional Live Smoke

Live vLLM smoke is off by default:

```powershell
$env:RUN_LOCAL_VLLM_SMOKE="1"
python scripts/device2/test_local_lora_backend.py --json
```

Keep the base model, LoRA adapter, checkpoints, and cache directories outside the Git repository.

## Interpreting Results

- `status=ok` in P6B means main-flow E2E extraction, no-write schema failure, fake regression, and rule-owned risk projection passed.
- `status=ok` in P6C means backend comparison artifacts were generated and local_lora passed the built-in seven-case regression set.
- `status=ok` in P7 means final docs, caveats, prior artifacts, secret scan, and tracked-weight hygiene are in place.
- Full unittest discover is not claimed as passed in this local environment; keep it labeled `failed_due_preexisting_local_env_blockers` unless those blockers are actually fixed.

