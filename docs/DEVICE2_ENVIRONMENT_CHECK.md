# DEVICE2_ENVIRONMENT_CHECK

Stage: D2-P0B Environment Readiness & Dependency Draft

Result: `caution`

Generated evidence:

* `reports/device2/env_check.json`
* `reports/device2/env_check_report.md`

## 1. Scope

This check inventories Device2 readiness for a future local base/local LoRA
extractor path. It does not install dependencies, download models, run training,
create training data, change application code, change tests, change API schema,
or integrate `local_lora_extractor.py`.

## 2. Git Baseline

* current branch: `feature/device2-local-lora-extractor`
* current HEAD after D2-P0A commit: `159c3cb`
* D2-P0A commit message: `docs: add device2 repository intake baseline`
* git binary: `git version 2.45.1.windows.1`
* global git config was not modified; local commands use a temporary
  `safe.directory` override when needed.

## 3. Host Summary

Detected by `scripts/device2/check_env.py` and manual local checks:

| Area | Result |
| --- | --- |
| OS | Detected platform: `Windows-11-10.0.22621-SP0`; `cmd /c ver` reported `Microsoft Windows [Version 10.0.22621.6060]`. |
| CPU | `Intel64 Family 6 Model 183 Stepping 1, GenuineIntel`; 24 logical processors. |
| Python | `D:\anaconda3\python.exe`; CPython `3.13.5` from Anaconda. |
| pip | `pip 25.1` for Python 3.13. |
| conda | `conda 25.7.0` available. |
| uv | `uv 0.10.11` available. |
| Repo drive | `C:\`; total `199.19 GiB`, free `25.42 GiB` at the latest check. |
| NVIDIA GPU | `NVIDIA GeForce RTX 4070`, `12282 MiB` VRAM. |
| NVIDIA driver | `560.94`. |
| CUDA reported by driver | `12.6`. |

The user-provided hardware profile mentioned Windows 10 Pro, i7-13700KF,
RTX 4070 12GB, and a 1TB disk. The direct OS probe reports the Windows 11 /
10.0.22621 family, and the current repo drive is a roughly 199 GiB `C:\`
volume with limited free space. Future model caches and checkpoints should use
a planned non-repo storage location.

## 4. WSL Status

WSL is currently a caution:

* `wsl.exe` is present.
* `wsl --status` returned exit code `50`.
* `wsl -l -v` returned exit code `1` and printed help-like text instead of a
  distro list.
* `wsl bash -lc "uname -a"` returned exit code `1`.

Conclusion: Ubuntu/WSL2 was not confirmed from this environment, and GPU
visibility inside WSL was not verified. D2-P1 should not assume WSL training or
vLLM serving is ready until a Linux environment is explicitly prepared and
checked.

## 5. Python Package Probe

The script used `importlib.util.find_spec` only. It did not import heavy
libraries or validate runtime compatibility.

| Package | Discoverable |
| --- | --- |
| `torch` | yes |
| `transformers` | yes |
| `datasets` | yes |
| `accelerate` | yes |
| `peft` | yes |
| `trl` | no |
| `bitsandbytes` | no |
| `vllm` | no |
| `openai` | yes |
| `pydantic` | yes |
| `yaml` | yes |
| `sklearn` | yes |
| `pandas` | yes |

This is enough for an inventory result only. It is not proof that CUDA kernels,
PyTorch CUDA support, quantization, vLLM, or LoRA training will work.

## 6. Readiness Assessment

Result: `caution`

Reasons:

* WSL/Ubuntu is not confirmed.
* GPU visibility inside WSL is not confirmed.
* `bitsandbytes`, `trl`, and `vllm` are not discoverable in the current Python
  environment.
* The repo drive has only about `25.42 GiB` free, which is not enough for an
  unconstrained model cache/checkpoint workflow.
* Python is `3.13.5`; future D2-P1 dependency resolution should confirm support
  for PyTorch, vLLM, bitsandbytes, and training libraries before installing.

Positive signals:

* Git is available.
* Python, pip, conda, and uv are available.
* NVIDIA driver and GPU are visible from Windows.
* Driver-reported CUDA version is `12.6`.
* Many model/data packages are already discoverable.

## 7. D2-P0B Non-Actions

* business code changed: no
* tests changed: no
* API contract changed: no
* P7 freeze semantics changed: no
* model downloaded: no
* training run: no
* heavy dependency install: no
* push performed: no

## 8. Recommended D2-P1 Entry

Do not start training yet. Recommended next step is a dedicated environment
preparation phase:

1. Choose the execution target: WSL2/Ubuntu or native Windows.
2. Choose a Python version compatible with the target PyTorch/vLLM/bitsandbytes
   stack.
3. Decide a model/cache/checkpoint directory outside the repo and preferably
   outside the nearly full `C:\` volume.
4. Install only the minimal runtime dependencies after explicit approval.
5. Run a 5-10 sample local base-model structured extraction smoke test.
6. Measure JSON valid rate and schema pass rate before any LoRA training.
