# Device2 Windows Hypervisor + VMP Repair Report

Stage: D2-P0F Windows Hypervisor + VMP Repair Gate

Result: `caution`

## 1. Branch / HEAD

* branch: `feature/device2-local-lora-extractor`
* pre-stage HEAD: `07b6707`
* repo path: `C:\Users\Administrator\Documents\TCM-Ass\TCM-Assistant`

## 2. Windows WSL Version

`wsl --version` reports:

```text
WSL version: 2.7.8.0
Kernel version: 6.18.33.1-1
Windows: 10.0.22621.6060
```

`wsl --status` still reports default WSL version `2`, but WSL2 cannot start because virtualization or Virtual Machine Platform is not enabled/available.

## 3. WSL Optional Features

These read-only feature probes were attempted:

```text
Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux
Get-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform
dism.exe /online /Get-FeatureInfo /FeatureName:Microsoft-Windows-Subsystem-Linux
dism.exe /online /Get-FeatureInfo /FeatureName:VirtualMachinePlatform
```

Observed result:

```text
The requested operation requires elevation.
Error: 740
Elevated permissions are required to run DISM.
```

Feature state conclusion:

* `Microsoft-Windows-Subsystem-Linux`: not confirmed from this shell.
* `VirtualMachinePlatform`: not confirmed from this shell.

## 4. Hypervisor State

`Get-ComputerInfo` from the diagnostic pass reported:

```text
HyperVisorPresent=False
HyperVRequirementVirtualizationFirmwareEnabled=True
HyperVRequirementSecondLevelAddressTranslation=True
HyperVRequirementDataExecutionPreventionAvailable=True
```

Interpretation:

* BIOS/UEFI firmware virtualization requirement: satisfied.
* SLAT requirement: satisfied.
* DEP requirement: satisfied.
* Windows hypervisor currently present: no.

## 5. `hypervisorlaunchtype`

`bcdedit /enum` and `bcdedit /set hypervisorlaunchtype auto` were attempted.

Observed result:

```text
The boot configuration data store could not be opened.
Access is denied.
```

Conclusion: `hypervisorlaunchtype` could not be confirmed or repaired from this shell.

## 6. Repair Attempts

The following D2-P0F repair commands were attempted:

```text
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
bcdedit /set hypervisorlaunchtype auto
wsl --shutdown
wsl --update
wsl --set-default-version 2
```

Results:

* DISM feature enable for WSL failed with `Error: 740`.
* DISM feature enable for VMP failed with `Error: 740`.
* `bcdedit /set hypervisorlaunchtype auto` failed with `Access is denied`.
* `wsl --shutdown` completed.
* `wsl --update` completed or returned no actionable error.
* `wsl --set-default-version 2` completed.

No command reported `REBOOT_REQUIRED=true` in this run because the Windows feature and BCD changes were not accepted. A reboot is still expected after the same repair commands are run from a real Administrator PowerShell.

## 7. Ubuntu Registration

`wsl -l -v` did not show a registered Ubuntu distribution.

Ubuntu status: not registered.

## 8. Ubuntu Version

Ubuntu WSL version: not available.

Requirement `VERSION=2`: not satisfied.

## 9. Ubuntu Launch

Ubuntu launch was not attempted beyond probe commands because no distribution is registered and the hypervisor/VMP chain is still blocked.

Ubuntu launch status: not confirmed.

## 10. `/mnt/e` Accessibility

Windows-side cache roots still exist:

```text
E:\ai_models\huggingface
E:\ai_models\modelscope
E:\ai_models\vllm
E:\ai_models\torch
E:\ai_models\pip
E:\ai_artifacts\tcm_assistant_device2
```

WSL-side `/mnt/e` access could not be confirmed because Ubuntu cannot launch.

## 11. Cache Environment Variables

Ubuntu `~/.bashrc` was not changed because Ubuntu is not registered.

Cache env status: not written.

## 12. Python Venv

Target venv:

```text
~/venvs/tcm-device2
```

Venv status: not created.

## 13. WSL `nvidia-smi`

WSL `nvidia-smi` did not pass because Ubuntu cannot launch.

Windows-side `nvidia-smi` remains available from the environment report and sees RTX 4070.

## 14. Blockers

* The shell used by Codex does not have a true Windows Administrator token.
* DISM feature repair is blocked by `Error: 740`.
* BCD repair is blocked by `Access is denied`.
* `HyperVisorPresent=False` from the diagnostic pass.
* WSL2 still reports a virtualization or Virtual Machine Platform blocker.
* Ubuntu is not registered.
* `/mnt/e`, cache env variables, `~/venvs/tcm-device2`, and WSL `nvidia-smi` cannot be validated until Ubuntu can launch.

## 15. Required Manual Actions

Open a real elevated Administrator PowerShell and run:

```text
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
bcdedit /set hypervisorlaunchtype auto
wsl --shutdown
wsl --update
wsl --set-default-version 2
```

If Windows reports that a restart is required, reboot and continue with `D2-P0F-Resume`.

After reboot, validate:

```text
wsl --version
wsl --status
wsl -l -v
Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux
Get-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform
bcdedit /enum "{current}"
```

Only then register Ubuntu with `wsl --install -d Ubuntu-22.04` or `wsl --install -d Ubuntu`, using the real name shown by `wsl --list --online`.

## 16. Conclusion / Next Stage

Conclusion: `caution`

D2-P0G is not allowed yet.

D2-P1 remains forbidden.

Next stage should be `D2-P0F-Resume: Windows Hypervisor + VMP Repair Gate` after the user completes the Administrator PowerShell repair and reboot if required.
