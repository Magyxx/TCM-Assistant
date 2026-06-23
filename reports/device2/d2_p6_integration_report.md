# D2-P6A Main ExtractorBackend Integration Report

## 1. Branch and HEAD

- Branch: `feature/device2-local-lora-extractor`
- HEAD: `3fb8e31`
- Recent commits:
  - `3fb8e31 reports: add device2 risk repair light training results`
  - `f57e2d2 training: support device2 risk repair light training`
  - `683a1e6 chore: document device2 git recovery manifest`
  - `a539feb data: add device2 risk repair datasets and configs`
  - `980b02e extractor: add deterministic risk projection for device2`

## 2. Files Added or Modified in This Round

- Updated local backend contract/config:
  - `.env.example`
  - `app/extractors/local_vllm_extractor.py`
  - `app/utils/json_repair.py`
- Reused existing D2 extractor scaffold:
  - `app/extractors/base.py`
  - `app/extractors/fake_extractor.py`
  - `app/extractors/cloud_llm_extractor.py`
  - `app/extractors/local_lora_extractor.py`
  - `app/extractors/router.py`
- Updated local smoke/helper defaults to `LOCAL_LLM_API_KEY=EMPTY`:
  - `scripts/device2/test_vllm_api.py`
  - `scripts/device2/run_local_lora_realpath.py`
  - `scripts/device2/eval_backend_compare.py`
  - `scripts/device2/check_extractor_backend.py`
  - `docs/DEVICE2_LOCAL_LORA_BACKEND.md`
  - `docs/DEVICE2_VLLM_REPAIR_GUIDE.md`
- Added D2-P6 validation and smoke:
  - `scripts/device2/test_local_lora_backend.py`
  - `scripts/device2/verify_d2_p6_integration.py`
  - `artifacts/device2/d2_p6_integration_validation.json`
  - `reports/device2/d2_p6_integration_report.md`
- Added/updated tests:
  - `tests/test_extractor_router.py`
  - `tests/test_local_lora_extractor.py`
  - `tests/test_local_lora_schema_guard.py`
  - `tests/test_local_lora_realpath_config.py`
  - `tests/test_local_vllm_extractor.py`
  - `tests/test_device2_vllm_config.py`
  - `tests/test_device2_backend_compare.py`

## 3. ExtractorBackend Interface

The existing project-oriented protocol is reused in `app/extractors/base.py`:

```python
class ExtractorBackend(Protocol):
    name: str

    def extract_turn(self, state: RunState, user_input: str) -> BackendResult:
        ...
```

`BackendResult` carries the validated `TurnOutput` candidate plus audit metadata: `raw_output`, `parsed_json`, `json_valid`, `schema_pass`, `fallback_used`, `latency_ms`, `model_name`, `base_url`, `error_type`, and schema error preview.

## 4. Backend Switching

`EXTRACTOR_BACKEND` supports:

- `fake`
- `cloud_llm`
- `local_base`
- `local_lora`

Aliases such as `real_llm -> cloud_llm`, `local_vllm -> local_base`, and `local-lora -> local_lora` are normalized by `app/extractors/router.py`.

## 5. local_lora Call Chain

`EXTRACTOR_BACKEND=local_lora` resolves through:

`turn_extractor.extract_turn(..., extractor_mode="auto")`
-> `extract_with_backend_router`
-> `LocalLoraExtractorBackend`
-> `extract_with_local_lora`
-> `extract_with_local_vllm`
-> OpenAI-compatible `chat.completions.create`
-> `TurnOutput.model_validate`
-> rule-owned risk projection
-> `BackendResult`.

## 6. Schema Validation Path

The local vLLM adapter extracts the first JSON object, applies light JSON repair through `app/utils/json_repair.py`, parses into a dict, then validates via `TurnOutput.model_validate()`.

Invalid JSON returns a structured `json_invalid` result. Schema mismatch returns `schema_mismatch` with `turn_output=None`. No schema-failed result is merged into `RunState` by the local backend.

## 7. Fallback and Error Handling

By default, `local_lora` does not silently fallback. Explicit fallback is only enabled through `ALLOW_EXTRACTOR_FALLBACK=true` or `allow_fallback=True`, and records `fallback_used=True`.

The live smoke script `scripts/device2/test_local_lora_backend.py` does not call the real vLLM endpoint unless `RUN_LOCAL_VLLM_SMOKE=1`.

## 8. Risk Rule Ownership

The LoRA output is treated as a `TurnOutput` candidate only. Model-supplied `risk_flags` and `risk_flags_status` are cleared in the local vLLM adapter, then re-projected only from deterministic `evaluate_risk_rules()` output. This prevents the local LoRA model from owning final risk status.

## 9. Test Results

- `git status --short`: completed.
- `python -m compileall -q app scripts tests`: passed.
- Focused D2-P6 suite: `25 tests` passed.
- `python scripts/device2/verify_d2_p6_integration.py --json --output artifacts/device2/d2_p6_integration_validation.json`: passed, status `ok`.
- `python scripts/secret_scan.py --json --output artifacts/secret_scan_result.json`: passed, status `ok`, finding_count `0`.
- `python -m unittest discover -s tests`: failed in this Windows Python environment with `226 tests`, `9 failures`, and `70 errors`.

Full-suite blockers observed:

- Missing runtime dependency: `fastapi`.
- Older `report_chain` tests import a cloud `ChatOpenAI` model at module import time without `OPENAI_MODEL`.
- Several temp-directory writes/cleanups failed under `C:\Users\ADMINI~1\AppData\Local\Temp`.
- Existing P6/P6C fixture validations failed after the full-suite runner invoked historical artifact-generation paths.

The unrelated artifact churn from the failed full-suite run was restored before this report was written.

## 10. Live vLLM Smoke

Live smoke was skipped because `RUN_LOCAL_VLLM_SMOKE` was not enabled.

Dry skip check:

```text
python scripts/device2/test_local_lora_backend.py --json
status: skipped
enabled: false
base_url: http://127.0.0.1:8000/v1
model: tcm-extractor-lora
```

## 11. Weight and Checkpoint Tracking

No model weights, base model files, adapter checkpoints, or large prediction files were added by D2-P6A. The verifier confirmed:

- `weights_not_tracked: true`
- no tracked `artifacts/device2/checkpoints/`
- no tracked `artifacts/device2/adapters/`
- `.gitignore` covers Device2 checkpoint and adapter directories

## 12. Next Step

Proceed to D2-P6B: main-flow end-to-end validation with `fake`, `cloud_llm`, `local_base`, and `local_lora`, followed by D2-P6C backend comparison.
