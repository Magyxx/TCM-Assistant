# Device2 Environment Check Report

Stage: D2-P0B Environment Readiness & Dependency Draft

Result: `caution`

Evidence JSON: `reports/device2/env_check.json`

## Summary

D2-P0B completed a lightweight inventory of the Device2 machine and repository
state. The repository is on `feature/device2-local-lora-extractor`, with D2-P0A
committed as `159c3cb` (`docs: add device2 repository intake baseline`).

The Windows host can see Python, conda, uv, Git, and the NVIDIA RTX 4070 GPU.
The NVIDIA driver reports CUDA `12.6`. However, WSL/Ubuntu was not confirmed,
the current Python environment does not expose `bitsandbytes`, `trl`, or `vllm`,
and the repo drive has only about `25.42 GiB` free.

## Commands Run

Representative commands:

```text
git -c safe.directory=C:/Users/Administrator/Documents/TCM-Ass/TCM-Assistant status --short
git -c safe.directory=C:/Users/Administrator/Documents/TCM-Ass/TCM-Assistant branch --show-current
git -c safe.directory=C:/Users/Administrator/Documents/TCM-Ass/TCM-Assistant log --oneline -n 5
git -c safe.directory=C:/Users/Administrator/Documents/TCM-Ass/TCM-Assistant add docs/DEVICE2_BRANCH_BASELINE.md docs/DEVICE2_REPO_INTAKE.md docs/DEVICE2_TASK_UNDERSTANDING.md reports/device2/repo_intake_report.md
git -c safe.directory=C:/Users/Administrator/Documents/TCM-Ass/TCM-Assistant -c user.name=Codex -c user.email=codex@example.com commit -m "docs: add device2 repository intake baseline"
nvidia-smi
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
cmd /c ver
wsl --status
wsl -l -v
wsl bash -lc "uname -a"
python scripts/device2/check_env.py
```

Manual Windows WMI/system inventory commands were also attempted, but
`Get-CimInstance` and `systeminfo` returned access denied in this environment.
Fallback environment APIs and `nvidia-smi` supplied the recorded host details.

## Host Findings

| Item | Result |
| --- | --- |
| Branch | `feature/device2-local-lora-extractor` |
| HEAD | `159c3cb` |
| OS | `Windows-11-10.0.22621-SP0`; `cmd /c ver` reported `10.0.22621.6060` |
| CPU | Intel Family 6 Model 183, 24 logical processors |
| Python | Anaconda CPython `3.13.5`, executable `D:\anaconda3\python.exe` |
| conda | `25.7.0` |
| uv | `0.10.11` |
| GPU | `NVIDIA GeForce RTX 4070`, `12282 MiB` |
| Driver | `560.94` |
| CUDA reported | `12.6` |
| Repo drive free | `25.42 GiB` |

## WSL Findings

WSL is a blocker for assuming Linux-side training/serving readiness:

* `wsl --status`: exit code `50`
* `wsl -l -v`: exit code `1`, help-like output
* `wsl bash -lc "uname -a"`: exit code `1`, help-like output

No Ubuntu distro, WSL2 version, or WSL GPU visibility was confirmed.

## Package Findings

The script used `importlib.util.find_spec` and did not import heavy modules.

Discoverable:

* `torch`
* `transformers`
* `datasets`
* `accelerate`
* `peft`
* `openai`
* `pydantic`
* `yaml`
* `sklearn`
* `pandas`

Missing:

* `bitsandbytes`
* `trl`
* `vllm`

## Files Added In D2-P0B

* `requirements-device2.txt`
* `scripts/device2/check_env.py`
* `reports/device2/env_check.json`
* `docs/DEVICE2_ENVIRONMENT_CHECK.md`
* `docs/DEVICE2_REQUIREMENTS_DRAFT.md`
* `reports/device2/env_check_report.md`

## Non-Actions

* business code changed: no
* tests changed: no
* API/schema/main flow changed: no
* model downloaded: no
* training run: no
* heavy dependency installed: no
* `local_lora_extractor.py` created: no
* ExtractorBackend integration changed: no
* push performed: no

## Acceptance Result

Result: `caution`

This phase is acceptable as an inventory/draft phase, but the environment is not
ready for immediate local LoRA training or vLLM serving. D2-P1 should first
prepare an isolated supported environment and storage plan, then run local
base-model smoke tests before training.
