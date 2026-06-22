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

## D2-P0C Update

Stage: D2-P0C WSL2 Runtime Plan & Storage Stabilization

Result: `caution`

* D2-P0B commit status: committed locally as `37e0cee` (`chore: add device2 environment readiness checks`).
* WSL2 status: `wsl.exe` is present, but `wsl --status`, `wsl -l -v`, and `wsl --version` did not return usable readiness output.
* Ubuntu status: not confirmed.
* WSL CUDA status: not confirmed; WSL `nvidia-smi` follows the WSL help/error path.
* Storage strategy: keep model weights, adapters, checkpoints, Hugging Face cache, ModelScope cache, and vLLM cache outside this repo. Prefer `E:\ai_models\...` and `/mnt/e/ai_models/...`; use `D:\ai_models\...` only as fallback.
* Python recommendation: do not use Windows Anaconda CPython `3.13.5` as the training/inference runtime. Prepare an isolated WSL Python `3.10`, `3.11`, or `3.12` environment before D2-P1.
* D2-P1 ready: no. Blocked by unconfirmed Ubuntu, unconfirmed WSL GPU visibility, no locked WSL Python environment, and no exported external cache paths.

No-go confirmation for D2-P0C:

* model downloaded: no
* training run: no
* vLLM server started: no
* business code changed: no
* API contract changed: no
* schema changed: no
* push performed: no

## D2-P0G Update

Stage: D2-P0G: ML Runtime Dependency Gate

Result: `caution`

Generated evidence:

* `reports/device2/ml_runtime_dependency_report.md`
* `reports/device2/ml_runtime_check.json`
* `reports/device2/env_check.json`
* `scripts/device2/check_ml_runtime.py`

Key findings:

* Branch: `feature/device2-local-lora-extractor`.
* Pre-stage HEAD: `f00198a`.
* Ubuntu distribution name: `Ubuntu`.
* Ubuntu VERSION: `2`.
* GPU baseline: `NVIDIA GeForce RTX 4070`, `12282 MiB`, driver `560.94`, CUDA `12.6` from `nvidia-smi`.
* Existing readiness venv `~/venvs/tcm-device2` remains Python `3.14.4` and was not used for ML dependencies.
* New ML venv: `~/venvs/tcm-device2-ml-py312`.
* ML Python: `3.12.13`.
* pip cache: `/mnt/e/ai_models/pip`.
* PyTorch CUDA 12.6 wheel install initially passed with `torch 2.12.1+cu126` and CUDA tensor creation.
* `pip install vllm` installed `vllm 0.23.0`, but changed the final torch stack to `torch 2.11.0+cu130`.
* Final torch CUDA tensor creation failed because the current driver reports CUDA `12.6` / driver `560.94`, while final torch expects CUDA `13.0`.
* `transformers`, `datasets`, `accelerate`, `trl`, `bitsandbytes`, and `vllm` imports succeeded.
* `peft` import failed because torch and torchaudio CUDA builds are mismatched after vLLM dependency resolution.
* bitsandbytes import succeeded, but bitsandbytes CUDA smoke failed because final torch CUDA initialization fails.
* D2-P1: not allowed.

No-go confirmation for D2-P0G:

* model downloaded: no
* transformers `from_pretrained()` model download: no
* training run: no
* vLLM server started: no
* LoRA adapter created: no
* business code changed: no
* API contract changed: no
* LangGraph changed: no
* schema changed: no
* push performed: no

Recommended next stage: `D2-P0G-Resume: ML Runtime Dependency Repair`.

## D2-P0F-Resume Update

Stage: D2-P0F-Resume: Ubuntu Readiness Verification

Result: `ok`

Generated evidence:

* `reports/device2/wsl_admin_repair_resume_report.md`
* `reports/device2/windows_hypervisor_vmp_repair_report.md`
* `reports/device2/wsl_bootstrap_check.json`
* `reports/device2/wsl_cuda_check.json`
* `reports/device2/env_check.json`

Key findings:

* Branch: `feature/device2-local-lora-extractor`.
* Pre-stage HEAD: `f905bf3`.
* Ubuntu distribution name: `Ubuntu`.
* Ubuntu registered: yes.
* Ubuntu VERSION=2: yes.
* Ubuntu launch: ok.
* `/mnt/e/ai_models` and `/mnt/e/ai_artifacts/tcm_assistant_device2`: accessible.
* Cache env vars: written to Ubuntu `~/.bashrc` with one begin marker and one end marker, then verified.
* Target venv: `~/venvs/tcm-device2`, created and verified.
* Venv Python: `Python 3.14.4`.
* Venv pip: `pip 25.1.1`.
* WSL `nvidia-smi`: ok; sees `NVIDIA GeForce RTX 4070`, `12282 MiB`, driver `560.94`, CUDA `12.6`.
* D2-P0G: allowed as `D2-P0G: ML Runtime Dependency Gate`.
* D2-P1: not allowed.

No-go confirmation for D2-P0F-Resume:

* model downloaded: no
* training run: no
* vLLM server started: no
* torch installed: no
* transformers installed: no
* peft installed: no
* trl installed: no
* bitsandbytes installed: no
* business code changed: no
* API contract changed: no
* LangGraph changed: no
* schema changed: no
* push performed: no

## D2-P0D-Resume Update

Stage: D2-P0D-Resume Post-Reboot WSL2/Ubuntu Runtime Completion

Result: `caution`

* D2-P0D commit status: committed locally as `f6c5d0f` (`chore: bootstrap device2 wsl runtime`).
* WSL version: `2.7.8.0` available.
* Default WSL version: `2`.
* WSL2 runtime status: blocked because virtualization is not enabled or not available.
* Ubuntu status: not registered in `wsl -l -v`; not initialized.
* WSL CUDA status: not checked successfully because WSL2/Ubuntu cannot start.
* Windows cache directories: `E:\ai_models\huggingface`, `E:\ai_models\modelscope`, `E:\ai_models\vllm`, `E:\ai_models\torch`, and `E:\ai_artifacts\tcm_assistant_device2` exist.
* WSL cache env: not configured.
* Python venv: not created.
* D2-P1 ready: no.

No-go confirmation for D2-P0D-Resume:

* model downloaded: no
* training run: no
* vLLM server started: no
* torch installed: no
* transformers installed: no
* peft installed: no
* trl installed: no
* bitsandbytes installed: no
* business code changed: no
* API contract changed: no
* schema changed: no
* push performed: no

## D2-P0D Update

Stage: D2-P0D WSL2/Ubuntu Runtime Bootstrap

Result: `caution`

* D2-P0C commit status: committed locally as `1b4ef27` (`chore: add device2 wsl runtime and storage policy`).
* Windows version: Windows 10 Pro 22H2, build `22621.6060`.
* WSL install action: `wsl --install -d Ubuntu --no-launch` completed.
* Reboot required: `true`.
* Ubuntu status: installed/requested, but pending confirmation after reboot.
* WSL CUDA status: pending after reboot.
* Storage strategy: unchanged; Windows-side `E:\ai_models\...` and `E:\ai_artifacts\...` directories were created. WSL `/mnt/e/...` checks are pending after reboot.
* Python environment: not created yet because reboot is required first.
* D2-P1 ready: no.

No-go confirmation for D2-P0D:

* model downloaded: no
* training run: no
* vLLM server started: no
* torch installed: no
* transformers installed: no
* business code changed: no
* API contract changed: no
* schema changed: no
* push performed: no

## D2-P0E Update

Stage: D2-P0E Virtualization Recovery + WSL2 Ubuntu Readiness Gate

Result: `caution`

Generated evidence:

* `reports/device2/wsl_virtualization_recovery_report.md`
* `reports/device2/wsl_bootstrap_check.json`
* `reports/device2/wsl_cuda_check.json`
* `reports/device2/env_check.json`

Key findings:

* Branch: `feature/device2-local-lora-extractor`.
* Pre-stage HEAD: `4abe1d0`.
* Firmware virtualization: `Yes` according to `systeminfo`.
* WSL version: `2.7.8.0`.
* WSL status: still reports a virtualization or Virtual Machine Platform blocker.
* Optional feature state: not confirmed because `Get-WindowsOptionalFeature` requires elevation from this shell.
* Ubuntu: not registered in `wsl -l -v`.
* WSL `nvidia-smi`: not available because Ubuntu cannot launch.
* `/mnt/e`: not confirmed from WSL.
* Windows cache roots: present, including `E:\ai_models\pip`.
* Cache env vars: not configured.
* Target venv: `~/venvs/tcm-device2`, not created.
* D2-P0F: allowed only as recovery/readiness continuation after manual Windows feature and Ubuntu registration work.
* D2-P1: not allowed.

No-go confirmation for D2-P0E:

* model downloaded: no
* training run: no
* vLLM server started: no
* torch installed: no
* transformers installed: no
* peft installed: no
* trl installed: no
* bitsandbytes installed: no
* business code changed: no
* API contract changed: no
* schema changed: no
* push performed: no

## D2-P0F Update

Stage: D2-P0F Windows Hypervisor + VMP Repair Gate

Result: `caution`

Generated evidence:

* `reports/device2/windows_hypervisor_vmp_repair_report.md`
* `reports/device2/wsl_bootstrap_check.json`
* `reports/device2/wsl_cuda_check.json`
* `reports/device2/env_check.json`

Key findings:

* Branch: `feature/device2-local-lora-extractor`.
* Pre-stage HEAD: `07b6707`.
* WSL version: `2.7.8.0`.
* HyperVisorPresent: `False` from the diagnostic pass.
* Firmware virtualization requirement: `True`.
* SLAT requirement: `True`.
* DEP requirement: `True`.
* WSL optional feature state: not confirmed; queries require elevation.
* VMP optional feature state: not confirmed; queries require elevation.
* `hypervisorlaunchtype`: not confirmed; `bcdedit` returned `Access is denied`.
* Repair attempt: DISM feature enables failed with `Error: 740`; `bcdedit /set hypervisorlaunchtype auto` failed with `Access is denied`.
* Ubuntu: not registered.
* Ubuntu VERSION: not available.
* Ubuntu launch: not confirmed.
* `/mnt/e`: not confirmed from WSL.
* Cache env vars: not written.
* Target venv: `~/venvs/tcm-device2`, not created.
* WSL `nvidia-smi`: not available.
* D2-P0G: not allowed yet.
* D2-P1: not allowed.

No-go confirmation for D2-P0F:

* model downloaded: no
* training run: no
* vLLM server started: no
* torch installed: no
* transformers installed: no
* peft installed: no
* trl installed: no
* bitsandbytes installed: no
* business code changed: no
* API contract changed: no
* schema changed: no
* push performed: no
