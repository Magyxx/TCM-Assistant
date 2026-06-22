# Device2 WSL Virtualization Recovery Report

Stage: D2-P0E Virtualization Recovery + WSL2 Ubuntu Readiness Gate

Result: `caution`

## 1. Branch / HEAD

* branch: `feature/device2-local-lora-extractor`
* pre-stage HEAD: `4abe1d0`
* repo path: `C:\Users\Administrator\Documents\TCM-Ass\TCM-Assistant`

## 2. Windows WSL Status

`wsl.exe` is present, and `wsl --version` reports WSL `2.7.8.0`, kernel `6.18.33.1-1`, and Windows `10.0.22621.6060`.

`systeminfo` reports:

```text
Virtualization Enabled In Firmware: Yes
```

This means BIOS/UEFI CPU virtualization appears enabled after the user reboot.

However, `wsl --status` still reports that WSL2 cannot start because virtualization is not enabled or not available, and it recommends enabling Virtual Machine Platform through:

```text
wsl.exe --install --no-distribution
```

The optional feature probes were attempted:

```text
Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux
Get-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform
```

Both returned `The requested operation requires elevation`, so the exact Windows optional feature state could not be confirmed from this shell.

## 3. Ubuntu Registration

`wsl -l -v` and `wsl --list --verbose` returned no registered Linux distributions.

Ubuntu status: not registered.

## 4. Ubuntu Launch

`wsl bash -lc true` did not launch Ubuntu because no Linux distribution is registered.

Ubuntu launch status: not confirmed.

## 5. WSL Version 2

The default WSL version is reported as `2`, but no Ubuntu distro is registered as WSL version 2.

Ubuntu WSL2 status: not confirmed.

## 6. `/mnt/e` Accessibility

Windows-side cache directories exist:

```text
E:\ai_models\huggingface
E:\ai_models\modelscope
E:\ai_models\vllm
E:\ai_models\torch
E:\ai_models\pip
E:\ai_artifacts\tcm_assistant_device2
```

WSL-side `/mnt/e` accessibility could not be confirmed because Ubuntu cannot launch.

## 7. Environment Variables

The required non-secret WSL variables are not configured because `~/.bashrc` cannot be edited until Ubuntu exists:

```text
HF_HOME
HUGGINGFACE_HUB_CACHE
TRANSFORMERS_CACHE
HF_DATASETS_CACHE
MODELSCOPE_CACHE
TORCH_HOME
VLLM_CACHE_ROOT
TCM_DEVICE2_ARTIFACTS
PIP_CACHE_DIR
```

No token, secret, or API key was written.

## 8. Python Venv

Target venv:

```text
~/venvs/tcm-device2
```

Venv status: not created, because Ubuntu cannot launch.

## 9. WSL `nvidia-smi`

Windows `nvidia-smi` still sees:

```text
NVIDIA GeForce RTX 4070, 12282 MiB, driver 560.94
```

WSL `nvidia-smi` did not run because no Ubuntu distro is registered.

## 10. Blockers

* WSL2 still reports a virtualization or Virtual Machine Platform blocker.
* Windows optional feature state could not be confirmed because the feature query requires elevation.
* No Ubuntu distro is registered.
* Ubuntu cannot launch.
* `/mnt/e` cannot be checked from WSL.
* WSL GPU visibility is not confirmed.
* WSL cache environment variables are not configured.
* `~/venvs/tcm-device2` does not exist.

## 11. Manual Recovery Actions

Run these from an elevated Administrator PowerShell, then reboot when prompted:

```text
wsl.exe --install --no-distribution
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
```

After reboot:

```text
wsl.exe --install -d Ubuntu
wsl.exe -l -v
```

Then initialize Ubuntu and rerun the Device2 readiness gate.

## 12. Conclusion / Next Stage

Conclusion: `caution`

D2-P0F is allowed only as a recovery/readiness continuation after the manual Windows feature and Ubuntu registration steps.

D2-P1 remains forbidden. Do not install ML dependencies, download models, start vLLM, or run LoRA training until WSL2 Ubuntu, `/mnt/e`, WSL `nvidia-smi`, cache environment variables, and `~/venvs/tcm-device2` are all confirmed.
