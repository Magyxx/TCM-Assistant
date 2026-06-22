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
* Create an isolated environment such as `tcm-lora`.
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
