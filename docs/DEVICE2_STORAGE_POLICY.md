# DEVICE2_STORAGE_POLICY

## 1. Purpose

This policy defines where Device2 local model files, model caches, LoRA adapters, checkpoints, and runtime artifacts may live. The goal is to keep Git clean, avoid filling the repo drive, and prevent accidental commits of large or sensitive artifacts.

## 2. Repository Storage

Allowed in Git:

* code
* config without secrets
* docs
* reports
* small JSON reports
* small sample JSONL files
* requirements drafts
* scripts

## 3. External Storage

Must stay outside the repo:

* Hugging Face cache
* ModelScope cache
* base model weights
* large LoRA adapter weights
* checkpoints
* vLLM cache
* long prediction dumps
* any `.safetensors`, `.bin`, `.pt`, `.pth`, `.ckpt`, `.gguf`, `.onnx`, `.tflite`, `.engine`, or `.plan` model/runtime file

## 4. Recommended Paths

D2-P0C detected these Windows fixed drives:

| Drive | Approx total | Approx free | Use |
| --- | ---: | ---: | --- |
| `C:\` | `199.19 GiB` | `22.63 GiB` | Repo only; do not store models here. |
| `D:\` | `377.00 GiB` | `76.75 GiB` | Usable for some artifacts after cleanup. |
| `E:\` | `376.50 GiB` | `126.92 GiB` | Best current target for model/cache storage. |

Recommended Windows paths:

```text
E:\ai_models\huggingface
E:\ai_models\modelscope
E:\ai_models\vllm
E:\ai_models\torch
E:\ai_models\pip
E:\ai_artifacts\tcm_assistant_device2
```

Equivalent WSL paths after Ubuntu is installed:

```text
/mnt/e/ai_models/huggingface
/mnt/e/ai_models/modelscope
/mnt/e/ai_models/vllm
/mnt/e/ai_models/torch
/mnt/e/ai_models/pip
/mnt/e/ai_artifacts/tcm_assistant_device2
```

## D2-P0D-Resume Update

The Windows-side torch cache directory was added:

```text
E:\ai_models\torch
```

WSL-side `/mnt/e/...` path creation is still pending because WSL2 cannot start until virtualization is enabled or available.

Fallback if E is unavailable:

```text
D:\ai_models\huggingface
D:\ai_models\modelscope
D:\ai_models\vllm
D:\ai_artifacts\tcm_assistant_device2
```

If only C is available in a future environment, treat storage readiness as `caution` and clean disk space or attach external storage before D2-P1.

## 5. Environment Variables

Future runtime setup should point cache variables outside this repo:

```text
HF_HOME
HUGGINGFACE_HUB_CACHE
TRANSFORMERS_CACHE
HF_DATASETS_CACHE
TORCH_HOME
VLLM_CACHE_ROOT
MODELSCOPE_CACHE
PIP_CACHE_DIR
```

Never write tokens, API keys, or secrets into this document or into committed environment files.

## 6. Git Ignore Policy

`.gitignore` protects general model weight extensions and now also protects Device2-specific local artifact directories:

```text
artifacts/device2/checkpoints/
artifacts/device2/adapters/
artifacts/device2/model_cache/
artifacts/device2/hf_cache/
artifacts/device2/vllm_cache/
artifacts/device2/predictions/*.jsonl
```

Small prediction samples may be committed only when explicitly named as samples:

```text
!artifacts/device2/predictions/README.md
!artifacts/device2/predictions/*_sample.jsonl
```

## 7. Safety Checklist

Before any future commit:

```text
git status --short
git diff --check
```

Confirm:

* no `.env`
* no token or secret files
* no `safetensors`, `bin`, `pt`, `pth`, `ckpt`, `gguf`, `onnx`, `tflite`, `engine`, or `plan` files
* no checkpoint, adapter, model cache, HF cache, or vLLM cache directories
* no long prediction dumps

## D2-P0D Update

D2-P0D kept the storage policy unchanged. Windows/Ubuntu bootstrap reached a reboot-required state, so WSL path creation and shell environment-variable configuration are deferred until after reboot.

Windows-side directories were created:

```text
E:\ai_models\huggingface
E:\ai_models\modelscope
E:\ai_models\vllm
E:\ai_artifacts\tcm_assistant_device2
```

Planned WSL equivalents:

```text
/mnt/e/ai_models/huggingface
/mnt/e/ai_models/modelscope
/mnt/e/ai_models/vllm
/mnt/e/ai_artifacts/tcm_assistant_device2
```

## D2-P0E Update

The Windows-side pip cache directory was added and confirmed:

```text
E:\ai_models\pip
```

Current Windows-side Device2 cache/artifact roots:

```text
E:\ai_models\huggingface
E:\ai_models\modelscope
E:\ai_models\vllm
E:\ai_models\torch
E:\ai_models\pip
E:\ai_artifacts\tcm_assistant_device2
```

WSL-side equivalents remain pending because Ubuntu is not registered and cannot launch:

```text
/mnt/e/ai_models/huggingface
/mnt/e/ai_models/modelscope
/mnt/e/ai_models/vllm
/mnt/e/ai_models/torch
/mnt/e/ai_models/pip
/mnt/e/ai_artifacts/tcm_assistant_device2
```

No model weights, adapters, checkpoints, or cache contents were placed in the repo.

## D2-P0F Update

D2-P0F did not change storage policy. Windows-side cache roots remain outside the repo:

```text
E:\ai_models\huggingface
E:\ai_models\modelscope
E:\ai_models\vllm
E:\ai_models\torch
E:\ai_models\pip
E:\ai_artifacts\tcm_assistant_device2
```

WSL-side `/mnt/e/...` paths remain unverified because Ubuntu is not registered and cannot launch. No model weights, adapters, checkpoints, venv contents, or caches were committed.

## D2-P0F-Resume Update

Ubuntu now verifies the Device2 external storage roots through WSL:

```text
/mnt/e
/mnt/e/ai_models
/mnt/e/ai_models/pip
/mnt/e/ai_artifacts/tcm_assistant_device2
```

The committed repo still contains no model weights, adapters, checkpoints, virtualenv contents, or cache directories. Runtime cache variables in Ubuntu point outside the repo:

```text
HF_HOME=/mnt/e/ai_models/huggingface
HUGGINGFACE_HUB_CACHE=/mnt/e/ai_models/huggingface/hub
TRANSFORMERS_CACHE=/mnt/e/ai_models/huggingface/transformers
MODELSCOPE_CACHE=/mnt/e/ai_models/modelscope
TORCH_HOME=/mnt/e/ai_models/torch
VLLM_CACHE_ROOT=/mnt/e/ai_models/vllm
TCM_DEVICE2_ARTIFACTS=/mnt/e/ai_artifacts/tcm_assistant_device2
PIP_CACHE_DIR=/mnt/e/ai_models/pip
```

Storage status for D2-P0F-Resume: `ok`.
