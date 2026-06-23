# D2-P5A vLLM Repair Report

Stage: `D2-P5A: vLLM Environment Repair & LoRA Serving Smoke`

Generated at: `2026-06-23T19:12:00+08:00`

Status: `ok`

## Git Freeze

* repository: `C:\Users\Administrator\Documents\TCM-Ass\TCM-Assistant`
* WSL repository path: `/mnt/c/Users/Administrator/Documents/TCM-Ass/TCM-Assistant`
* branch: `feature/device2-local-lora-extractor`
* HEAD: `3fb8e31 reports: add device2 risk repair light training results`
* recent stack:
  * `3fb8e31 reports: add device2 risk repair light training results`
  * `f57e2d2 training: support device2 risk repair light training`
  * `683a1e6 chore: document device2 git recovery manifest`
  * `a539feb data: add device2 risk repair datasets and configs`
  * `980b02e extractor: add deterministic risk projection for device2`
  * `1235ba5 eval: add device2 risk failure and metric audit`
  * `77364b4 feat: complete device2 train eval and vllm serving attempt`
  * `9b2547e chore: finalize device2 training runtime gate`
  * `6a670e9 chore: repair device2 ml runtime dependency gate`
  * `ee7bed0 chore: add device2 ml runtime dependency gate`

Windows Git status is used as the authoritative worktree status. WSL Git status
under `/mnt/c` can show unrelated line-ending noise from the Windows-mounted
filesystem and is not used to infer repository changes.

## Training Artifact Reference

* D2-T1R2 status: `ok`
* base model: `/mnt/e/models/Qwen2.5-1.5B-Instruct`
* output adapter: `/mnt/e/ai_artifacts/tcm_assistant_device2/d2t1r2/risk_repair_20260623T060605Z/adapter/final_adapter`
* training: `4 epochs / 16 steps`
* train loss: `0.190773`
* eval loss: `0.213176`
* peak GPU memory: `4.6056 GiB`

The adapter, base model, checkpoints, and model weights remain outside Git.

## Root Cause and Fixes

The first latest-vLLM install route was not adopted as the final fix because the
unconstrained resolver path timed out and was stopped. The working repair uses an
isolated WSL serving environment, separate from the training environment:

`/home/magyxx/venvs/tcm-vllm`

Observed and fixed issues:

* `transformers==5.12.1` was incompatible with the working vLLM route for Qwen
  tokenizer loading. Fixed by pinning `transformers==4.45.2` and
  `tokenizers==0.20.3`.
* `--generation-config vllm` attempted an online Hugging Face lookup in the
  offline WSL path. The serving scripts now support `GENERATION_CONFIG`, and
  offline smoke uses `GENERATION_CONFIG=/mnt/e/models/Qwen2.5-1.5B-Instruct`.
* LoRA startup failed before a C compiler was available for the vLLM/Triton
  runtime path. Fixed by installing WSL `build-essential` as root. No Windows
  driver or CUDA Toolkit reinstall was performed.
* LoRA chat initially failed without an explicit chat template. The LoRA serving
  script now automatically uses `chat_template.jinja` from the adapter directory
  when present.
* `response_format={"type":"json_object"}` hit an xgrammar compatibility issue
  in this vLLM stack. The smoke test now uses prompt-constrained JSON plus
  Pydantic schema validation instead of guided JSON.

The training environment
`/home/magyxx/venvs/tcm-device2-train-py312-cu126-final` was inspected as
baseline only and was not modified by the vLLM repair.

## Runtime Matrix

Source: `reports/device2/vllm_repair_check.json`

| Item | Value |
| --- | --- |
| WSL distro | Ubuntu 26.04 LTS |
| Python | `3.12.13` |
| Python executable | `/home/magyxx/venvs/tcm-vllm/bin/python` |
| GPU | `NVIDIA GeForce RTX 4070` |
| NVIDIA driver | `560.94` |
| torch | `2.5.1+cu124` |
| torch CUDA | `12.4` |
| torch CUDA available | `true` |
| vLLM | `0.6.6.post1` |
| transformers | `4.45.2` |
| openai | `2.43.0` |
| adapter exists | `true` |
| adapter weights exist | `true` |
| base model path exists | `true` |
| LoRA rank / alpha | `16 / 32` |
| runtime check status | `ok` |

## Serving Commands

Base-only server:

```bash
source /home/magyxx/venvs/tcm-vllm/bin/activate
BASE_MODEL=/mnt/e/models/Qwen2.5-1.5B-Instruct \
GENERATION_CONFIG=/mnt/e/models/Qwen2.5-1.5B-Instruct \
HOST=127.0.0.1 PORT=8000 \
scripts/device2/serve_vllm_base.sh
```

LoRA server:

```bash
source /home/magyxx/venvs/tcm-vllm/bin/activate
GENERATION_CONFIG=/mnt/e/models/Qwen2.5-1.5B-Instruct \
HOST=127.0.0.1 PORT=8000 \
scripts/device2/serve_vllm_lora.sh
```

The LoRA server infers `BASE_MODEL` from `adapter_config.json` and serves the
adapter as `tcm-extractor-lora`.

## API Smoke Results

Source files:

* base-only smoke: `reports/device2/vllm_base_api_smoke.json`
* LoRA smoke: `reports/device2/vllm_api_smoke.json`

| Check | Base-only | LoRA |
| --- | --- | --- |
| `/v1/models` | `ok` | `ok` |
| model listed | `/mnt/e/models/Qwen2.5-1.5B-Instruct` | base + `tcm-extractor-lora` |
| `/v1/chat/completions` | `ok` | `ok` |
| Python OpenAI client | `ok` | `ok` |
| JSON parse | `ok` | `ok` |
| `TurnOutput` schema | `ok` | `ok` |
| smoke status | `ok` | `ok` |

## Repository Changes

Added or updated:

* `.env.example`
* `app/extractors/__init__.py`
* `app/extractors/local_vllm_extractor.py`
* `app/extractors/local_lora_extractor.py`
* `docs/DEVICE2_VLLM_REPAIR_GUIDE.md`
* `scripts/device2/check_vllm_runtime.py`
* `scripts/device2/serve_vllm_base.sh`
* `scripts/device2/serve_vllm_lora.sh`
* `scripts/device2/test_vllm_api.py`
* `tests/test_device2_vllm_config.py`
* `tests/test_device2_vllm_scripts.py`
* `tests/test_local_vllm_extractor.py`
* `reports/device2/vllm_repair_check.json`
* `reports/device2/vllm_api_smoke.json`
* `reports/device2/vllm_base_api_smoke.json`

## Validation Commands

| Command | Result | Notes |
| --- | --- | --- |
| `python -m compileall -q app scripts tests` | `ok` | Syntax check passed. |
| `python -m unittest tests.test_device2_vllm_config tests.test_device2_vllm_scripts tests.test_local_vllm_extractor` | `ok` | `9` D2-P5A tests passed. |
| `python scripts/secret_scan.py --json --output artifacts/secret_scan_result.json` | `ok` | No unallowlisted findings; synthetic fixtures remain allowlisted. |
| `python scripts/device2/check_vllm_runtime.py ... --output reports/device2/vllm_repair_check.json` | `ok` | Run inside `/home/magyxx/venvs/tcm-vllm`. |
| `python scripts/device2/test_vllm_api.py --base-url http://127.0.0.1:8000/v1 --model tcm-extractor-lora ...` | `ok` | LoRA `/models`, chat, JSON parse, schema all passed. |
| `python scripts/device2/test_vllm_api.py --base-url http://127.0.0.1:8001/v1 --model /mnt/e/models/Qwen2.5-1.5B-Instruct ...` | `ok` | Base-only `/models`, chat, JSON parse, schema all passed. |
| `python -m unittest discover -s tests` | `failed` | Current Windows Python test env lacks unrelated dependencies such as `fastapi`; several historical tests also fail from system temp directory write/cleanup permissions and existing artifact expectations. This does not block D2-P5A-specific acceptance, which passed above. |

## Safety Notes

* No retraining was performed in this stage.
* No base model weights, adapter weights, checkpoints, Hugging Face cache, venv,
  wandb, or tensorboard outputs were added to Git.
* Existing training artifacts under `/mnt/e/ai_artifacts/tcm_assistant_device2/`
  were not deleted or modified.
* The local extractor path does not silently fall back to fake mode when vLLM is
  unavailable; it returns a clear error and `fallback_used=false`.
* The local extractor applies the existing risk-rule guard after schema
  validation.

## Residual Notes

* Offline WSL sessions should set `GENERATION_CONFIG` to the local base-model
  directory. The default `vllm` generation config can trigger a network lookup.
* Do not enable dynamic LoRA loading by default.
* Keep `response_format=json_object` disabled on this vLLM/xgrammar combination
  unless that dependency path is upgraded and retested.

## Next Step

Proceed to `D2-P5B`: main-system `local_lora` backend real-path integration and
comparison evaluation.
