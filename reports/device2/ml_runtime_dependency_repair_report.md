# Device2 ML Runtime Dependency Repair Report

Stage: `D2-P0G-Resume: ML Runtime Dependency Repair`

Status: `caution`

Generated evidence:

* `reports/device2/ml_runtime_repair_check.json`
* `reports/device2/ml_runtime_check.json`
* `reports/device2/env_check.json`
* `scripts/device2/check_ml_runtime.py`

## Summary

The clean training runtime is repaired and CUDA-capable on the RTX 4070. The
clean vLLM serving runtime preserves the CUDA 12.6 PyTorch stack, but vLLM was
not installed because recent vLLM GitHub releases do not expose a matching
`cu126` Linux `x86_64` wheel. This stage therefore remains `caution`.

## Required Report Fields

1. Current branch and HEAD: `feature/device2-local-lora-extractor`, `ee7bed0`.
2. Previous failure: D2-P0G default vLLM dependency resolution changed the old
   ML env to `torch 2.11.0+cu130`; CUDA then failed on driver `560.94` /
   CUDA `12.6`, PEFT import failed, and bitsandbytes CUDA smoke failed.
3. Why the old venv was not repaired: `~/venvs/tcm-device2-ml-py312` is treated
   as polluted because it contains the incompatible cu130 torch stack and vLLM
   dependency graph from the previous gate.
4. Training env path: `~/venvs/tcm-device2-train-py312-cu126`.
5. Training env Python: `3.12.13`.
6. Training env torch/CUDA: `torch 2.12.1+cu126`, CUDA `12.6`.
7. Training env torch CUDA tensor: passed on `NVIDIA GeForce RTX 4070`.
8. Training imports: `transformers 5.12.1`, `datasets 5.0.0`,
   `accelerate 1.14.0`, `peft 0.19.1`, `trl 1.6.0`.
9. bitsandbytes import: passed with `bitsandbytes 0.49.2`.
10. bitsandbytes CUDA smoke: passed with `bnb.nn.Linear8bitLt` on CUDA.
11. vLLM env path: `~/venvs/tcm-device2-vllm-py312-cu126`.
12. vLLM cu126 wheel found: no. The latest release was `v0.23.0`; the recent
    10 releases queried had zero matching `cu126` Linux `x86_64` assets.
13. vLLM import: failed because vLLM was intentionally not installed without a
    compatible cu126 wheel.
14. vLLM preserved torch cu126: yes, `torch 2.12.1+cu126`, CUDA `12.6`, CUDA
    tensor smoke passed.
15. Model downloaded: no.
16. Training run: no.
17. vLLM server started: no.
18. Stage status: `caution`.
19. D2-P1 allowed: no.

## Additional Notes

During the first vLLM env torch install attempt, Ubuntu's root filesystem became
read-only and `mount` returned an input/output error. `wsl --shutdown` recovered
Ubuntu, `/mnt/e` cache writability, and WSL `nvidia-smi`. The partially installed
vLLM env was then recreated cleanly before the final checks.

No-go confirmation:

* base model downloaded: no
* `from_pretrained()` model download: no
* training run: no
* vLLM server started: no
* LoRA adapter created: no
* model, adapter, checkpoint, venv, cache, or large file committed: no
* app/API/LangGraph/business code changed: no
* push performed: no

Next permitted stage: `D2-P0H: vLLM CUDA-Compatible Serving Env Repair`.

D2-P1 remains blocked.
