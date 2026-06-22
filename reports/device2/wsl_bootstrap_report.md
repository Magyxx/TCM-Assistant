# D2-P0D WSL BOOTSTRAP REPORT

## 1. Summary

Result: `caution`

D2-P0C was committed, and `wsl --install -d Ubuntu --no-launch` completed successfully. Windows reported that changes will not take effect until reboot, so D2-P0D stopped before WSL shell initialization, GPU passthrough checks, apt installs, environment-variable edits, and Python venv creation.

```text
REBOOT_REQUIRED=true
```

## 2. D2-P0C Commit Status

D2-P0C was committed locally before bootstrap work.

Commit: `1b4ef27` (`chore: add device2 wsl runtime and storage policy`)

## 3. Commands Run

```text
git -c safe.directory=C:/Users/Administrator/Documents/TCM-Ass/TCM-Assistant status --short
git -c safe.directory=C:/Users/Administrator/Documents/TCM-Ass/TCM-Assistant branch --show-current
git -c safe.directory=C:/Users/Administrator/Documents/TCM-Ass/TCM-Assistant log --oneline -n 10
git -c safe.directory=C:/Users/Administrator/Documents/TCM-Ass/TCM-Assistant add .gitignore scripts/device2/check_wsl_cuda.py docs/DEVICE2_WSL_RUNTIME_PLAN.md docs/DEVICE2_STORAGE_POLICY.md docs/DEVICE2_ENVIRONMENT_CHECK.md reports/device2/wsl_runtime_report.md reports/device2/wsl_cuda_check.json reports/device2/env_check.json
git -c safe.directory=C:/Users/Administrator/Documents/TCM-Ass/TCM-Assistant -c user.name=Codex -c user.email=codex@example.com commit -m "chore: add device2 wsl runtime and storage policy"
systeminfo
where.exe wsl
wsl --status
wsl --状态
wsl -l -v
wsl --list --verbose
[System.Environment]::OSVersion.Version
Get-ItemProperty -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion'
dism.exe /online /get-featureinfo /featurename:Microsoft-Windows-Subsystem-Linux
dism.exe /online /get-featureinfo /featurename:VirtualMachinePlatform
wsl --list --online
wsl --install -d Ubuntu --no-launch
New-Item -ItemType Directory -Force 'E:\ai_models\huggingface','E:\ai_models\modelscope','E:\ai_models\vllm','E:\ai_artifacts\tcm_assistant_device2'
python scripts/device2/bootstrap_wsl_runtime.py
python scripts/device2/check_wsl_cuda.py
python scripts/device2/check_env.py
python -m py_compile scripts/device2/bootstrap_wsl_runtime.py
python -m py_compile scripts/device2/bootstrap_wsl_runtime.py scripts/device2/check_wsl_cuda.py
git -c safe.directory=C:/Users/Administrator/Documents/TCM-Ass/TCM-Assistant diff --check
git -c safe.directory=C:/Users/Administrator/Documents/TCM-Ass/TCM-Assistant status --short
```

## 4. WSL / Ubuntu Results

* Windows version: Windows 10 Pro, DisplayVersion `22H2`, build `22621`, UBR `6060`.
* `systeminfo`: access denied in this environment.
* `where.exe wsl`: `C:\Windows\System32\wsl.exe`.
* `wsl --list --online`: succeeded and listed `Ubuntu` as the default online distro.
* `dism.exe /online /get-featureinfo ...`: blocked by elevation requirement (`Error: 740`).
* `wsl --install -d Ubuntu --no-launch`: installed Virtual Machine Platform, Windows Subsystem for Linux, and Ubuntu.
* Reboot required: yes.

## 5. GPU Results

WSL GPU validation was not run after install because reboot is required.

Current status:

* WSL `nvidia-smi`: pending after reboot
* WSL GPU name: pending after reboot
* WSL VRAM: pending after reboot

## 6. Storage Results

Created Windows external cache paths:

```text
E:\ai_models\huggingface
E:\ai_models\modelscope
E:\ai_models\vllm
E:\ai_artifacts\tcm_assistant_device2
```

Planned WSL paths:

```text
/mnt/e/ai_models/huggingface
/mnt/e/ai_models/modelscope
/mnt/e/ai_models/vllm
/mnt/e/ai_artifacts/tcm_assistant_device2
```

WSL path creation/configuration is deferred until after reboot.

## 7. Python Env Results

Python isolation target:

```text
/mnt/e/ai_artifacts/tcm_assistant_device2/venvs/tcm-lora
```

Status:

* venv created: no
* Python version: pending after reboot
* pip version: pending after reboot

## 8. Files Changed

* `scripts/device2/bootstrap_wsl_runtime.py`
* `docs/DEVICE2_WSL_BOOTSTRAP.md`
* `docs/DEVICE2_WSL_RUNTIME_PLAN.md`
* `docs/DEVICE2_STORAGE_POLICY.md`
* `docs/DEVICE2_ENVIRONMENT_CHECK.md`
* `reports/device2/wsl_bootstrap_report.md`
* `reports/device2/wsl_bootstrap_check.json`
* `reports/device2/wsl_cuda_check.json`
* `reports/device2/env_check.json`

## 9. No-Go Confirmation

* Model downloaded: no
* Training started: no
* vLLM server started: no
* torch installed: no
* transformers installed: no
* Business code changed: no
* API contract changed: no
* Schema changed: no
* Push performed: no

## 10. D2-P1 Readiness

Can enter D2-P1 now: no

Blocking items:

* Windows reboot is required before WSL/Ubuntu changes take effect.
* Ubuntu user initialization is pending.
* Ubuntu WSL version 2 is pending confirmation.
* WSL `nvidia-smi` is pending confirmation.
* External cache directories are planned but not configured.
* WSL shell cache variables are not configured.
* Python isolated environment is not created.

## 11. Validation Results

* `python scripts/device2/bootstrap_wsl_runtime.py`: ran successfully and generated `reports/device2/wsl_bootstrap_check.json`; result `caution`.
* `python scripts/device2/check_wsl_cuda.py`: ran successfully and regenerated `reports/device2/wsl_cuda_check.json`; result `caution`.
* `python scripts/device2/check_env.py`: ran successfully and regenerated `reports/device2/env_check.json`; result `caution`.
* `python -m py_compile scripts/device2/bootstrap_wsl_runtime.py scripts/device2/check_wsl_cuda.py`: exit code `0`.
* `git diff --check`: exit code `0`; Git reported only CRLF normalization warnings for Markdown files.
