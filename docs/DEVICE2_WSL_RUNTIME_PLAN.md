# DEVICE2_WSL_RUNTIME_PLAN

## 1. Stage

D2-P0C WSL2 Runtime Plan & Storage Stabilization

## 2. Current Status

* Windows GPU visible: yes. `nvidia-smi` reports `NVIDIA GeForce RTX 4070` with `12282 MiB` VRAM.
* Driver / CUDA shown by Windows `nvidia-smi`: driver `560.94`, CUDA `12.6`.
* WSL status: `wsl.exe` exists, but `wsl --status`, `wsl -l -v`, and `wsl --version` did not return usable readiness output in this environment.
* Ubuntu status: not confirmed.
* WSL GPU visibility: not confirmed; WSL `nvidia-smi` follows the WSL help/error path.
* Python current issue: Windows Python is Anaconda CPython `3.13.5`; this should not be used as the main training or vLLM runtime.
* Disk issue: repo lives on `C:\`, which has about `22.63 GiB` free at the D2-P0C check. D/E drives are available and should be preferred for model/cache storage.

## 3. Why WSL2 Is Required

Device2 should use Linux/WSL2 for future CUDA inference, LoRA training, vLLM, and bitsandbytes work. Those stacks are generally validated first on Linux, and mixing native Windows Python 3.13 with CUDA training and vLLM raises compatibility risk. The Windows host can remain the control plane, while the GPU runtime should be isolated in Ubuntu under WSL2.

## 4. Target Runtime

Recommended target:

```text
Windows host
-> WSL2
-> Ubuntu 22.04 or Ubuntu 24.04
-> Python 3.10/3.11/3.12 isolated environment
-> PyTorch CUDA wheel
-> transformers / datasets / accelerate
-> peft / trl / bitsandbytes
-> vLLM
-> OpenAI-compatible local API
```

## 5. Python Version Policy

* Current Windows Python `3.13.5` is not the training/inference main environment.
* Future WSL environment should use Python `3.10`, `3.11`, or `3.12`.
* The exact version should be locked before D2-P1 based on PyTorch, CUDA, vLLM, and bitsandbytes compatibility.
* Prefer Python `3.11` or `3.12`; avoid Python `3.13` for this stack until compatibility is explicitly confirmed.

## 6. Environment Isolation Policy

* Do not contaminate base conda.
* Do not contaminate the host system Python.
* Create an isolated environment such as `~/venvs/tcm-device2`.
* Keep the training/runtime environment separate from the main TCM-Assistant application environment.

## 7. Install Plan Preview

Plan only. Do not execute during D2-P0C.

1. Enable WSL2.
2. Install Ubuntu 22.04 or 24.04.
3. Confirm `nvidia-smi` works inside WSL.
4. Create model/cache directories outside the repo.
5. Create an isolated Python environment.
6. Install a compatible PyTorch CUDA build.
7. Install the training stack.
8. Install vLLM only after compatibility is confirmed.
9. Run import and CUDA checks.
10. Enter D2-P1 base model inference only after readiness is confirmed.

## 8. D2-P1 Readiness Checklist

* WSL Ubuntu available.
* WSL `nvidia-smi` available.
* Python `3.10`-`3.12` isolated environment exists.
* External disk path selected with enough free space.
* `HF_HOME`, `HUGGINGFACE_HUB_CACHE`, `TRANSFORMERS_CACHE`, `HF_DATASETS_CACHE`, `TORCH_HOME`, and `VLLM_CACHE_ROOT` planned.
* No model cache inside this repo.

## 9. Risks

* WSL not installed or not fully enabled.
* Ubuntu not installed.
* GPU not visible in WSL.
* CUDA/PyTorch/vLLM compatibility mismatch.
* C drive is too small for model/cache/checkpoint workflows.
* RTX 4070 12GB VRAM constrains 7B/8B model training and serving choices.
* Accidental commit of model weights, adapters, checkpoints, or cache files.

## 10. Acceptance

Result: `caution`

D2-P0C confirms a valid plan and storage direction, but D2-P1 should not start until Ubuntu and WSL GPU visibility are confirmed.

## D2-P0D Update

D2-P0D ran `wsl --install -d Ubuntu --no-launch`. Windows installed Virtual Machine Platform, Windows Subsystem for Linux, and Ubuntu, then reported that a reboot is required before changes take effect.

```text
REBOOT_REQUIRED=true
```

D2-P1 is still blocked until the machine reboots and the following checks pass:

* Ubuntu appears in `wsl -l -v`.
* Ubuntu is running as WSL2.
* WSL `nvidia-smi` sees the RTX 4070.
* External cache paths are created and visible through `/mnt/e`.
* Non-secret cache environment variables are configured.
* A Python 3.10-3.12 isolated environment exists.

## D2-P0D-Resume Update

Post-reboot checks found WSL version `2.7.8.0` with default WSL version `2`, but WSL2 cannot start because virtualization is not enabled or not available. Ubuntu is not registered in `wsl -l -v`.

D2-P1 remains blocked by:

* virtualization not enabled or unavailable
* no registered Ubuntu distro
* WSL GPU not verified
* WSL `/mnt/e/...` paths not created
* cache environment variables not configured
* Python venv not created

## D2-P0E Update

D2-P0E confirms partial recovery only:

* Firmware virtualization: yes, according to `systeminfo`.
* WSL runtime: installed, with WSL `2.7.8.0`.
* WSL2 readiness: still blocked by a virtualization or Virtual Machine Platform message from `wsl --status`.
* Ubuntu: not registered in `wsl -l -v`.
* WSL GPU: not verified because Ubuntu cannot launch.
* `/mnt/e`: not verified because Ubuntu cannot launch.
* Cache env vars: not configured.
* Target Python venv: `~/venvs/tcm-device2`, not created.

The next permitted stage is a recovery/readiness continuation, not D2-P1. D2-P1 remains blocked until Ubuntu is registered as WSL2, WSL `nvidia-smi` works, `/mnt/e` cache paths are visible, non-secret cache environment variables are configured, and `~/venvs/tcm-device2` exists.

## D2-P0F Update

D2-P0F confirmed that the Windows hypervisor/VMP chain is still not ready:

* `HyperVisorPresent=False`.
* Firmware virtualization, SLAT, and DEP requirements are satisfied.
* WSL and VMP optional feature states could not be confirmed because feature queries require elevation.
* DISM feature repair failed with `Error: 740`.
* `bcdedit /set hypervisorlaunchtype auto` failed with `Access is denied`.
* Ubuntu is not registered and cannot launch.

The next permitted stage is `D2-P0F-Resume` after the user runs the repair commands in a true Administrator PowerShell. D2-P0G is not allowed yet, and D2-P1 remains blocked.

## D2-P0F-Resume Update

D2-P0F-Resume validates the runtime baseline after manual Administrator repair and Ubuntu initialization:

* Ubuntu distribution name: `Ubuntu`.
* Ubuntu registration: ok.
* WSL version: `2`.
* Ubuntu launch: ok.
* `/mnt/e/ai_models` and `/mnt/e/ai_artifacts/tcm_assistant_device2`: accessible.
* Cache env block: written and verified from Ubuntu `~/.bashrc`.
* Isolated venv: `~/venvs/tcm-device2`, Python `3.14.4`, pip `25.1.1`.
* WSL GPU: `nvidia-smi` sees `NVIDIA GeForce RTX 4070`, `12282 MiB`, driver `560.94`, CUDA `12.6`.

Result: `ok`.

The next permitted stage is `D2-P0G: ML Runtime Dependency Gate`. D2-P1 remains blocked until the ML runtime dependency gate is explicitly completed.

## D2-P0G Update

D2-P0G created the dedicated ML runtime:

```text
~/venvs/tcm-device2-ml-py312
Python 3.12.13
pip cache: /mnt/e/ai_models/pip
```

The older readiness venv remains untouched for ML dependency purposes:

```text
~/venvs/tcm-device2
Python 3.14.4
```

PyTorch CUDA 12.6 was initially installed from:

```text
https://download.pytorch.org/whl/cu126
```

Initial torch CUDA smoke passed with `torch 2.12.1+cu126`, CUDA `12.6`, and `NVIDIA GeForce RTX 4070`.

vLLM installation then resolved to `vllm 0.23.0` and changed the final torch stack to `torch 2.11.0+cu130`. With the current WSL NVIDIA driver `560.94` reporting CUDA `12.6`, final torch CUDA tensor creation fails. PEFT import also fails because torch and torchaudio CUDA builds are mismatched after vLLM dependency resolution. bitsandbytes imports but its CUDA smoke fails for the same final torch CUDA blocker.

Result: `caution`.

D2-P1 remains blocked. The next permitted stage is `D2-P0G-Resume: ML Runtime Dependency Repair`.

## D2-P0G-Resume Update

D2-P0G-Resume split the runtime into two clean Python 3.12.13 environments:

```text
training: ~/venvs/tcm-device2-train-py312-cu126
serving:  ~/venvs/tcm-device2-vllm-py312-cu126
```

The training environment now passes the dependency and CUDA gate:

* `torch 2.12.1+cu126`, CUDA `12.6`.
* CUDA tensor creation works on `NVIDIA GeForce RTX 4070`.
* `transformers`, `datasets`, `accelerate`, `peft`, `trl`, and
  `bitsandbytes` import successfully.
* bitsandbytes CUDA smoke passes.

The serving environment preserves the cu126 PyTorch base:

* `torch 2.12.1+cu126`, CUDA `12.6`.
* CUDA tensor creation works.
* vLLM import does not pass because vLLM was intentionally not installed
  without a compatible wheel.

Recent vLLM GitHub releases were queried through the release API. The latest
tag was `v0.23.0`, and the recent 10 releases had no matching `cu126` Linux
`x86_64` wheel. Default `pip install vllm` was not used because the previous
D2-P0G attempt proved it can pull an incompatible cu130 torch stack on this
driver.

Result: `caution`.

The next permitted stage is `D2-P0H: vLLM CUDA-Compatible Serving Env Repair`.
D2-P1 remains blocked.

## D2-P0H Update

D2-P0H narrows the gate to the formal pre-training runtime. vLLM is no longer
treated as a training prerequisite and is deferred to a later serving gate.

Storage was also repaired before the final training runtime was rebuilt:

```text
Ubuntu WSL VHDX: E:\wsl\Ubuntu\ext4.vhdx
```

The active WSL virtual disk is not under `C:\Users\Administrator\AppData\Local\wsl`.
WSL cache and temporary paths now resolve to `/mnt/e/...`:

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

Final training runtime:

```text
~/venvs/tcm-device2-train-py312-cu126-final
Python 3.12.13
torch 2.12.1+cu126
torch CUDA 12.6
```

The following checks pass:

* `torch.cuda.is_available() == True`.
* CUDA tensor smoke.
* `transformers`, `datasets`, `accelerate`, `peft`, `trl`, and
  `bitsandbytes` imports.
* bitsandbytes CUDA smoke.
* `LoraConfig` dry-run.
* `SFTConfig` dry-run.
* vLLM absent from the training env.

Result: `ok`.

The next permitted stage is:

```text
D2-P1: Transformers-only Local Base Inference Baseline
```

vLLM remains deferred to a later serving gate after the training/evaluation
loop is complete.
