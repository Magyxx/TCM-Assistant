# Device2 WSL Admin Repair Resume Report

Stage: D2-P0F-Resume: Ubuntu Readiness Verification

Result: `ok`

Generated at: `2026-06-22T15:59:25+00:00`

## 1. Branch / HEAD

* branch: `feature/device2-local-lora-extractor`
* pre-stage HEAD: `f905bf3`
* repo path: `C:\Users\Administrator\Documents\TCM-Ass\TCM-Assistant`

## 2. Scope

This resume pass validates Ubuntu readiness after the user completed Windows WSL, Virtual Machine Platform, Ubuntu registration, and Linux user initialization manually.

No base model was downloaded. No training was run. vLLM was not started. No torch, transformers, vLLM, PEFT, TRL, or bitsandbytes install was performed. No app, API, LangGraph, or business-code file was changed. No push was performed.

## 3. WSL / Ubuntu Identity

`wsl --version` reports WSL `2.7.8.0`, kernel `6.18.33.1-1`, WSLg `1.0.73.2`, and Windows `10.0.22621.6060`.

`wsl --status` reports:

```text
Default Distribution: Ubuntu
Default Version: 2
```

`wsl -l -v` reports:

```text
NAME      STATE    VERSION
* Ubuntu  Running  2
```

Recorded Ubuntu distribution name: `Ubuntu`.

Ubuntu registered: yes.

Ubuntu VERSION=2: yes.

## 4. Ubuntu Startup

`wsl -d Ubuntu -- uname -a` succeeded:

```text
Linux PC-20230721BRRG 6.18.33.1-microsoft-standard-WSL2 #1 SMP PREEMPT_DYNAMIC Fri Jun 5 01:12:21 UTC 2026 x86_64 GNU/Linux
```

`wsl -d Ubuntu -- bash -lc "pwd && whoami"` succeeded:

```text
/mnt/c/Users/Administrator/Documents/TCM-Ass/TCM-Assistant
magyxx
```

Ubuntu startup status: ok.

## 5. External Cache Mount

`/mnt/e` and the required cache/artifact roots are accessible from Ubuntu:

```text
/mnt/e
/mnt/e/ai_models
/mnt/e/ai_models/pip
/mnt/e/ai_artifacts/tcm_assistant_device2
```

`/mnt/e` cache status: ok.

## 6. Cache Environment Variables

Ubuntu `~/.bashrc` was updated idempotently with exactly one begin marker and one end marker:

```text
# >>> TCM_ASSISTANT_DEVICE2_CACHE >>>
export HF_HOME=/mnt/e/ai_models/huggingface
export HUGGINGFACE_HUB_CACHE=/mnt/e/ai_models/huggingface/hub
export TRANSFORMERS_CACHE=/mnt/e/ai_models/huggingface/transformers
export MODELSCOPE_CACHE=/mnt/e/ai_models/modelscope
export TORCH_HOME=/mnt/e/ai_models/torch
export VLLM_CACHE_ROOT=/mnt/e/ai_models/vllm
export TCM_DEVICE2_ARTIFACTS=/mnt/e/ai_artifacts/tcm_assistant_device2
export PIP_CACHE_DIR=/mnt/e/ai_models/pip
# <<< TCM_ASSISTANT_DEVICE2_CACHE <<<
```

The block is placed before Ubuntu's default non-interactive `.bashrc` return guard so the verification command can source it successfully.

Verification output:

```text
/mnt/e/ai_models/huggingface
/mnt/e/ai_models/pip
/mnt/e/ai_artifacts/tcm_assistant_device2
```

Cache env status: ok.

## 7. Python Venv

Initial `python3 -m venv ~/venvs/tcm-device2` failed because `ensurepip` was unavailable and Ubuntu requested `python3.14-venv`. After the user completed the apt install manually, the venv was recreated with `--clear`.

Verification output:

```text
Python 3.14.4
pip 25.1.1 from /home/magyxx/venvs/tcm-device2/lib/python3.14/site-packages/pip (python 3.14)
```

Venv status: ok.

## 8. WSL NVIDIA / CUDA

`wsl -d Ubuntu -- bash -lc "nvidia-smi"` succeeded and detected the RTX 4070:

```text
NVIDIA-SMI 560.35.02
Driver Version: 560.94
CUDA Version: 12.6
GPU 0: NVIDIA GeForce RTX 4070
Memory: 12282 MiB
```

Concise query output:

```text
NVIDIA GeForce RTX 4070, 12282 MiB, 560.94
```

WSL `nvidia-smi` status: ok.

## 9. Non-Blocking Observation

Some WSL commands printed a localized localhost/NAT warning, but the readiness commands above returned exit code `0` and produced the required evidence. This warning is recorded as non-blocking for D2-P0F-Resume.

## 10. Acceptance Checklist

| Item | Result |
| --- | --- |
| Ubuntu registered | ok |
| Ubuntu VERSION=2 | ok |
| Ubuntu can start | ok |
| `/mnt/e/ai_models` accessible | ok |
| `/mnt/e/ai_artifacts/tcm_assistant_device2` accessible | ok |
| cache env block written to Ubuntu `~/.bashrc` | ok |
| `~/venvs/tcm-device2` exists and python/pip work | ok |
| WSL `nvidia-smi` sees RTX 4070 | ok |

## 11. Blockers / Next Stage

Blocking items for D2-P0F-Resume: none.

Stage status: `ok`.

D2-P0G is allowed as `D2-P0G: ML Runtime Dependency Gate`.

D2-P1 remains forbidden.
