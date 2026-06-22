# DEVICE2_WSL_BOOTSTRAP

## 1. Stage

D2-P0D WSL2/Ubuntu Runtime Bootstrap

## 2. Purpose

D2-P0D prepares Device2 for the later D2-P1 local base-model inference stage by installing or repairing WSL/Ubuntu, planning external cache paths, and defining the Python isolation target. It does not download model weights, start vLLM, install training/inference heavy dependencies, or modify business code.

## 3. Pre-Stage Status

D2-P0C ended as `caution`:

* Windows could see `NVIDIA GeForce RTX 4070` with driver `560.94` and CUDA `12.6`.
* `C:\` had only about `22.63 GiB` free.
* WSL command existed, but WSL status/list/version did not return usable readiness output.
* Ubuntu, WSL GPU visibility, and WSL Python were not confirmed.
* Model download, training, vLLM startup, business-code changes, and push were not performed.

## 4. WSL Installation / Repair Actions

Actual install command run:

```text
wsl --install -d Ubuntu --no-launch
```

The command installed Windows optional components for Virtual Machine Platform and Windows Subsystem for Linux, then installed `Ubuntu`. Windows reported that the requested operation succeeded, but the changes will not take effect until the system is restarted.

```text
REBOOT_REQUIRED=true
```

Because reboot is required, D2-P0D stopped before WSL shell initialization, GPU passthrough validation, apt package installation, shell environment-variable edits, or Python venv creation.

## 5. Ubuntu Status

Ubuntu install was requested through `wsl --install -d Ubuntu --no-launch`.

Current status before reboot:

* distro name: pending confirmation after reboot
* distro version: pending confirmation after reboot
* WSL version: pending confirmation after reboot
* user initialization: pending after reboot

## 6. GPU Passthrough Status

WSL-side GPU passthrough was not validated after the install because Windows requires a reboot first.

Pending command after reboot:

```text
wsl bash -lc "nvidia-smi"
```

## 7. External Storage Status

Planned Windows cache paths:

```text
E:\ai_models\huggingface
E:\ai_models\modelscope
E:\ai_models\vllm
E:\ai_artifacts\tcm_assistant_device2
```

Planned WSL cache paths:

```text
/mnt/e/ai_models/huggingface
/mnt/e/ai_models/modelscope
/mnt/e/ai_models/vllm
/mnt/e/ai_artifacts/tcm_assistant_device2
```

Directory creation was deferred until after reboot so WSL path checks and shell configuration can be verified in one pass.
Windows-side directory creation was completed during D2-P0D:

```text
E:\ai_models\huggingface
E:\ai_models\modelscope
E:\ai_models\vllm
E:\ai_artifacts\tcm_assistant_device2
```

WSL-side path checks and shell configuration are deferred until after reboot.

## 8. Environment Variables

Planned non-secret variables:

```text
HF_HOME=/mnt/e/ai_models/huggingface
HUGGINGFACE_HUB_CACHE=/mnt/e/ai_models/huggingface/hub
TRANSFORMERS_CACHE=/mnt/e/ai_models/huggingface/transformers
HF_DATASETS_CACHE=/mnt/e/ai_models/huggingface/datasets
TORCH_HOME=/mnt/e/ai_models/torch
VLLM_CACHE_ROOT=/mnt/e/ai_models/vllm
TCM_DEVICE2_ARTIFACTS=/mnt/e/ai_artifacts/tcm_assistant_device2
```

No token or API key should be written into shell configuration.

## 9. Python Environment

Target environment:

```text
/mnt/e/ai_artifacts/tcm_assistant_device2/venvs/tcm-lora
```

Current status before reboot:

* venv created: no
* Python version: pending WSL confirmation
* pip version: pending WSL confirmation

## 10. What Was Not Installed

* torch not installed
* transformers not installed
* peft not installed
* trl not installed
* bitsandbytes not installed
* vLLM not installed

## 11. D2-P1 Readiness Checklist

| Item | Status |
| --- | --- |
| Ubuntu available | pending after reboot |
| WSL version 2 | pending after reboot |
| WSL nvidia-smi works | pending after reboot |
| external cache dirs exist | pending |
| Python env exists | no |
| no model in repo | yes |
| no training started | yes |

## 12. Acceptance

Result: `caution`

The WSL/Ubuntu install path made progress, but reboot is required before runtime readiness can be validated.
