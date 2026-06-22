# Device2 ML Runtime Dependency Report

Stage: D2-P0G: ML Runtime Dependency Gate

Result: `caution`

Generated at: `2026-06-22T18:25:32+00:00`

## 1. Branch / HEAD

* branch: `feature/device2-local-lora-extractor`
* pre-stage HEAD: `f00198a`
* repo path: `C:\Users\Administrator\Documents\TCM-Ass\TCM-Assistant`

## 2. Scope

This stage created a dedicated Python 3.12 ML runtime in Ubuntu WSL2 and installed/import-tested PyTorch, transformers, datasets, accelerate, PEFT, TRL, bitsandbytes, and vLLM.

No base model was downloaded. No `from_pretrained()` model download was run. No training was run. No vLLM server was started. No LoRA adapter, checkpoint, model weight, cache directory, venv, or site-packages directory was committed. No app, API, LangGraph, or business-code file was changed. No push was performed.

## 3. Ubuntu / WSL / GPU Baseline

Ubuntu baseline remained available:

* distribution: `Ubuntu`
* WSL VERSION: `2`
* user: `magyxx`
* kernel: `6.18.33.1-microsoft-standard-WSL2`
* cache env: `HF_HOME`, `PIP_CACHE_DIR`, and `TCM_DEVICE2_ARTIFACTS` sourced from Ubuntu `~/.bashrc`

GPU baseline:

* WSL `nvidia-smi`: ok
* GPU: `NVIDIA GeForce RTX 4070`
* VRAM: `12282 MiB`
* driver: `560.94`
* CUDA shown by `nvidia-smi`: `12.6`

## 4. Python Runtime Choice

The previous readiness venv remains:

```text
~/venvs/tcm-device2
Python 3.14.4
pip 25.1.1
```

It was not used as the ML runtime because Python 3.14 is too new for the current PyTorch/vLLM/PEFT/TRL/bitsandbytes ecosystem and carries high compatibility risk.

The new ML runtime is:

```text
~/venvs/tcm-device2-ml-py312
Python 3.12.13
pip 26.1.2
```

`uv` is installed in a separate tool venv:

```text
~/venvs/tcm-device2-tools
uv 0.11.23
```

`uv` was not installed through the remote shell installer because that execution path was rejected by the sandbox review. Instead, `uv` was installed via pip inside the separate tools venv, then used to install managed Python `3.12.13` and create the ML venv.

## 5. Cache Paths

pip cache:

```text
/mnt/e/ai_models/pip
```

uv cache used for Python/runtime tooling:

```text
/mnt/e/ai_models/uv
```

No model/cache/venv content was committed to the repository.

## 6. PyTorch Install and CUDA Smoke

PyTorch was first installed from the PyTorch CUDA 12.6 wheel index:

```text
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126
```

Initial smoke result before vLLM install:

```text
torch_version= 2.12.1+cu126
cuda_available= True
cuda_version= 12.6
device_count= 1
device_name= NVIDIA GeForce RTX 4070
cuda_tensor_ok= True
```

After `pip install vllm`, vLLM replaced the torch stack:

```text
torch: 2.11.0+cu130
torchvision: 0.26.0
torchaudio: 2.11.0+cu126 retained
```

Final torch CUDA result:

```text
torch_version= 2.11.0+cu130
cuda_version= 13.0
cuda_tensor_ok= False
```

Final blocker:

```text
RuntimeError: The NVIDIA driver on your system is too old (found version 12060).
```

Interpretation: the final vLLM-resolved torch stack targets CUDA 13.0, while the current WSL driver reports CUDA 12.6. CUDA is therefore not usable in the final environment.

## 7. Package Import Results

Final import results after vLLM install:

| Package | Result | Version / Detail |
| --- | --- | --- |
| `torch` | import ok, CUDA tensor failed | `2.11.0+cu130` |
| `transformers` | ok | `5.12.1` |
| `datasets` | ok | `5.0.0` |
| `accelerate` | ok | `1.14.0` |
| `peft` | failed | torch/torchaudio CUDA mismatch through transformers import path |
| `trl` | ok | `1.6.0` |
| `bitsandbytes` | import ok | `0.49.2` |
| `vllm` | import ok | `0.23.0` |

PEFT import failure detail:

```text
RuntimeError: Detected that PyTorch and TorchAudio were compiled with different CUDA versions.
PyTorch has CUDA version 13.0 whereas TorchAudio has CUDA version 12.6.
```

## 8. bitsandbytes Smoke

Before vLLM install, bitsandbytes CUDA smoke passed:

```text
bnb_version= 0.49.2
torch_cuda_available= True
bnb_linear8bit_cuda_ok= True (1, 2)
```

Final result after vLLM install:

```text
bnb_version= 0.49.2
torch_cuda_available= False
bitsandbytes CUDA smoke: failed
```

Failure is caused by the final torch CUDA 13.0 stack being incompatible with the current NVIDIA driver.

## 9. vLLM Import

vLLM installed and imports successfully:

```text
vllm 0.23.0
```

No vLLM server was started, and no model was downloaded.

## 10. Artifacts

Generated evidence:

* `reports/device2/ml_runtime_dependency_report.md`
* `reports/device2/ml_runtime_check.json`
* `reports/device2/env_check.json`
* `scripts/device2/check_ml_runtime.py`

## 11. Acceptance

D2-P0G acceptance requires all of the following to pass at the same time:

* Python 3.12 dedicated ML venv
* pip cache at `/mnt/e/ai_models/pip`
* torch install
* `torch.cuda.is_available() == True`
* CUDA tensor creation
* transformers/datasets/accelerate/PEFT/TRL imports
* bitsandbytes import
* bitsandbytes CUDA smoke
* vLLM import
* no model download
* no training
* no vLLM server startup

Final status: `caution`.

Blocking reasons:

* final torch CUDA tensor creation failed after vLLM changed torch to `2.11.0+cu130`
* PEFT import failed because torch and torchaudio CUDA builds are mismatched
* bitsandbytes CUDA smoke failed because torch CUDA initialization fails

D2-P1 is not allowed.

Recommended next stage: `D2-P0G-Resume: ML Runtime Dependency Repair`.

Recommended repair direction: use an isolated vLLM-compatible environment and resolve one of these paths explicitly before D2-P1:

* update the NVIDIA driver to support the CUDA 13.0 stack selected by current vLLM, then repair torchaudio alignment; or
* pin/rebuild a CUDA 12.6-compatible torch/vLLM combination in a fresh venv without repeated uninstall/reinstall churn in this environment.
