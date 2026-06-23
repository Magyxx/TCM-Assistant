# Device2 ML Runtime Dependency Report

Stage: D2-P0H: Pre-Training Runtime Finalization Gate

Result: `ok`

Generated at: `2026-06-23T01:18:52+00:00`

## 1. Branch / HEAD

* branch: `feature/device2-local-lora-extractor`
* pre-stage HEAD: `6a670e9`
* repo path: `C:\Users\Administrator\Documents\TCM-Ass\TCM-Assistant`

## 2. Scope

This stage finalized only the formal pre-training runtime for Device2.

vLLM was explicitly removed from this gate. vLLM is a later serving-stage
dependency and was not installed into the training environment.

No base model was downloaded. No `from_pretrained()` model download was run. No
training was run. No vLLM server was started. No LoRA adapter, checkpoint,
model weight, cache directory, venv, or site-packages directory was committed.
No app, API, LangGraph, schema, or business-code file was changed. No push was
performed.

## 3. Storage Baseline

Before rerunning the finalization gate, Ubuntu WSL storage was moved off the C
drive:

```text
E:\wsl\Ubuntu\ext4.vhdx
```

The active WSL virtual disk is no longer under
`C:\Users\Administrator\AppData\Local\wsl`.

WSL cache and temporary paths are configured outside the repo and outside C:

```text
HF_HOME=/mnt/e/ai_models/huggingface
HUGGINGFACE_HUB_CACHE=/mnt/e/ai_models/huggingface/hub
TRANSFORMERS_CACHE=/mnt/e/ai_models/huggingface/transformers
HF_DATASETS_CACHE=/mnt/e/ai_models/huggingface/datasets
TORCH_HOME=/mnt/e/ai_models/torch
PIP_CACHE_DIR=/mnt/e/ai_models/pip
UV_CACHE_DIR=/mnt/e/ai_models/uv
TMPDIR=/mnt/e/ai_artifacts/tcm_assistant_device2/tmp
TCM_DEVICE2_ARTIFACTS=/mnt/e/ai_artifacts/tcm_assistant_device2
```

Disk baseline from the final checker:

```text
/      1007G total, 947G available
/mnt/e  377G total, 235G available
/mnt/d  378G total, 264G available
```

The WSL venv root after finalization:

```text
/home/magyxx/venvs: 6.9G
```

## 4. Ubuntu / GPU Baseline

Ubuntu baseline:

* distribution: `Ubuntu`
* WSL VERSION: `2`
* user: `magyxx`
* WSL launch: ok

GPU baseline:

* WSL `nvidia-smi`: ok
* GPU: `NVIDIA GeForce RTX 4070`
* VRAM: `12282 MiB`
* driver: `560.94`
* CUDA shown by `nvidia-smi`: `12.6`

## 5. Training Runtime

Final training runtime:

```text
~/venvs/tcm-device2-train-py312-cu126-final
Python 3.12.13
pip cache: /mnt/e/ai_models/pip
```

PyTorch:

```text
torch_version=2.12.1+cu126
torch_cuda_version=12.6
torch_cuda_available=True
torch_device_name=NVIDIA GeForce RTX 4070
torch_cuda_tensor_ok=True
```

## 6. Package Import Results

| Package | Result | Version |
| --- | --- | --- |
| `torch` | ok | `2.12.1+cu126` |
| `transformers` | ok | `5.12.1` |
| `datasets` | ok | `5.0.0` |
| `accelerate` | ok | `1.14.0` |
| `peft` | ok | `0.19.1` |
| `trl` | ok | `1.6.0` |
| `bitsandbytes` | ok | `0.49.2` |
| `sentencepiece` | ok | `0.2.1` |
| `protobuf` | ok | `7.35.1` |
| `pyyaml` | ok | `6.0.3` |
| `rich` | ok | `15.0.0` |
| `safetensors` | ok | `0.8.0` |
| `numpy` | ok | `2.5.0` |

## 7. Smoke Tests

Training runtime smoke tests passed:

* `torch.cuda.is_available() == True`
* CUDA tensor creation passed
* PEFT import passed
* TRL import passed
* bitsandbytes import passed
* bitsandbytes CUDA smoke passed
* `LoraConfig` dry-run passed
* `SFTConfig` dry-run passed
* vLLM absent from the training env

Warnings observed during smoke:

* TRL emitted a future warning about its future default `loss_type` change.
* bitsandbytes emitted an expected warning that `Linear8bitLt` casts float32
  inputs to float16 during quantization.

Neither warning blocks D2-P0H.

## 8. Artifacts

Generated evidence:

* `reports/device2/ml_runtime_dependency_report.md`
* `reports/device2/ml_runtime_finalization_check.json`
* `reports/device2/ml_runtime_check.json`
* `scripts/device2/check_ml_runtime.py`

## 9. Acceptance

D2-P0H acceptance requires all of the following to pass at the same time:

* Python 3.12 dedicated clean training venv
* pip cache at `/mnt/e/ai_models/pip`
* WSL storage and cache paths outside C
* torch CUDA 12.6 stack
* `torch.cuda.is_available() == True`
* CUDA tensor creation
* transformers/datasets/accelerate/PEFT/TRL imports
* bitsandbytes import
* bitsandbytes CUDA smoke
* `LoraConfig` dry-run
* `SFTConfig` dry-run
* vLLM not installed in the training env
* no model download
* no training
* no vLLM server startup

Final status: `ok`.

D2-P1 is allowed as:

```text
D2-P1: Transformers-only Local Base Inference Baseline
```
