"""Device2 Windows hypervisor/VMP and WSL2/Ubuntu readiness gate.

This script is intentionally stdlib-only and mostly read-only. It does not
install WSL, Ubuntu, Python packages, model weights, vLLM, or training
dependencies. It checks the current repo branch, Windows virtualization and
hypervisor signals, WSL/Ubuntu/GPU status, external cache paths, environment
variables, and the planned WSL Python venv, then writes a JSON report.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
from pathlib import Path


STAGE = "D2-P0F"
EXPECTED_BRANCH = "feature/device2-local-lora-extractor"
REPORT_PATH = Path("reports") / "device2" / "wsl_bootstrap_check.json"
WINDOWS_CACHE_PATHS = [
    Path("E:/ai_models/huggingface"),
    Path("E:/ai_models/modelscope"),
    Path("E:/ai_models/vllm"),
    Path("E:/ai_models/torch"),
    Path("E:/ai_models/pip"),
    Path("E:/ai_artifacts/tcm_assistant_device2"),
]
WSL_CACHE_PATHS = [
    "/mnt/e/ai_models/huggingface",
    "/mnt/e/ai_models/modelscope",
    "/mnt/e/ai_models/vllm",
    "/mnt/e/ai_models/torch",
    "/mnt/e/ai_models/pip",
    "/mnt/e/ai_artifacts/tcm_assistant_device2",
]
WSL_VENV_PATH = "~/venvs/tcm-device2"
REQUIRED_ENV_VARS = [
    "HF_HOME",
    "HUGGINGFACE_HUB_CACHE",
    "TRANSFORMERS_CACHE",
    "HF_DATASETS_CACHE",
    "MODELSCOPE_CACHE",
    "TORCH_HOME",
    "VLLM_CACHE_ROOT",
    "TCM_DEVICE2_ARTIFACTS",
    "PIP_CACHE_DIR",
]


def decode_output(data: bytes) -> str:
    if not data:
        return ""

    candidates: list[str] = []
    for encoding in ("utf-8", "utf-16-le", "gb18030", "mbcs"):
        try:
            candidates.append(data.decode(encoding, errors="replace"))
        except LookupError:
            continue

    def score(text: str) -> tuple[int, int]:
        return (text.count("\ufffd") + text.count("\x00"), -len(text.strip()))

    best = min(candidates, key=score)
    return best.replace("\r\n", "\n").strip()


def truncate(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[truncated]"


def format_command(args: list[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(args)
    return " ".join(args)


def run_command(args: list[str], timeout: int = 20) -> dict[str, object]:
    command = format_command(args)
    if shutil.which(args[0]) is None:
        return {
            "command": command,
            "available": False,
            "returncode": None,
            "stdout": "",
            "stderr": f"{args[0]} not found",
        }

    try:
        proc = subprocess.run(args, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {
            "command": command,
            "available": True,
            "returncode": None,
            "stdout": "",
            "stderr": f"timed out after {timeout}s",
        }
    except OSError as exc:
        return {
            "command": command,
            "available": True,
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
        }

    return {
        "command": command,
        "available": True,
        "returncode": proc.returncode,
        "stdout": truncate(decode_output(proc.stdout)),
        "stderr": truncate(decode_output(proc.stderr)),
    }


def command_ok(result: dict[str, object]) -> bool:
    return bool(result["available"]) and result["returncode"] == 0


def safe_dir() -> str:
    return str(Path.cwd()).replace("\\", "/")


def git_command(args: list[str]) -> dict[str, object]:
    return run_command(["git", "-c", f"safe.directory={safe_dir()}"] + args)


def wsl_shell(command: str, timeout: int = 20) -> dict[str, object]:
    return run_command(["wsl", "bash", "-lc", command], timeout=timeout)


def windows_feature_command(feature_name: str) -> dict[str, object]:
    return run_command(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            f"Get-WindowsOptionalFeature -Online -FeatureName {feature_name}",
        ],
        timeout=40,
    )


def computer_info_command() -> dict[str, object]:
    return run_command(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            (
                "$ci=Get-ComputerInfo; "
                '"HyperVisorPresent=$($ci.HyperVisorPresent)"; '
                '"HyperVRequirementVirtualizationFirmwareEnabled='
                '$($ci.HyperVRequirementVirtualizationFirmwareEnabled)"; '
                '"HyperVRequirementSecondLevelAddressTranslation='
                '$($ci.HyperVRequirementSecondLevelAddressTranslation)"; '
                '"HyperVRequirementDataExecutionPreventionAvailable='
                '$($ci.HyperVRequirementDataExecutionPreventionAvailable)"'
            ),
        ],
        timeout=120,
    )


def bcdedit_command() -> dict[str, object]:
    return run_command(["bcdedit", "/enum"], timeout=40)


def parse_distro_lines(result: dict[str, object]) -> list[str]:
    if not command_ok(result):
        return []
    lines: list[str] = []
    for raw_line in str(result["stdout"]).splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if "NAME" in line and "STATE" in line:
            continue
        lines.append(line)
    return lines


def parse_default_distro(lines: list[str]) -> str | None:
    for line in lines:
        if line.startswith("*"):
            return line.lstrip("*").strip().split()[0]
    return None


def has_ubuntu(lines: list[str]) -> bool:
    return any("ubuntu" in line.lower() for line in lines)


def parse_wsl2(lines: list[str]) -> bool:
    for line in lines:
        parts = line.split()
        if "ubuntu" in line.lower() and parts and parts[-1] == "2":
            return True
    return False


def parse_gpu(stdout: str) -> dict[str, str] | None:
    for line in stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) >= 2:
            return {"name": parts[0], "memory_total": parts[1]}
    return None


def extract_systeminfo_value(stdout: str, key: str) -> str | None:
    for line in stdout.splitlines():
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        if name.strip().lower() == key.lower():
            return value.strip()
    return None


def parse_firmware_virtualization(systeminfo: dict[str, object]) -> bool | None:
    if not command_ok(systeminfo):
        return None
    value = extract_systeminfo_value(
        str(systeminfo["stdout"]),
        "Virtualization Enabled In Firmware",
    )
    if value is None:
        return None
    lowered = value.lower()
    if lowered.startswith("yes"):
        return True
    if lowered.startswith("no"):
        return False
    return None


def parse_key_value_lines(stdout: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def parse_bool_signal(values: dict[str, str], key: str) -> bool | None:
    value = values.get(key)
    if value == "True":
        return True
    if value == "False":
        return False
    return None


def parse_optional_feature_state(result: dict[str, object]) -> str | None:
    if not command_ok(result):
        return None
    for line in str(result["stdout"]).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        if key.strip().lower() == "state":
            return value.strip()
    return None


def parse_hypervisorlaunchtype(result: dict[str, object]) -> str | None:
    if not command_ok(result):
        return None
    for line in str(result["stdout"]).splitlines():
        parts = line.split()
        if parts and parts[0].lower() == "hypervisorlaunchtype" and len(parts) >= 2:
            return parts[-1]
    return None


def has_virtualization_blocker(*results: dict[str, object]) -> bool:
    combined = "\n".join(
        str(result.get("stdout", "")) + "\n" + str(result.get("stderr", ""))
        for result in results
    ).lower()
    markers = [
        "virtualization",
        "enablevirtualization",
        "virtual machine platform",
        "wsl2",
    ]
    return any(marker in combined for marker in markers)


def has_access_denied(*results: dict[str, object]) -> bool:
    combined = "\n".join(
        str(result.get("stdout", "")) + "\n" + str(result.get("stderr", ""))
        for result in results
    ).lower()
    markers = ["access denied", "e_accessdenied", "拒绝访问"]
    return any(marker in combined for marker in markers)


def manual_recovery_actions() -> list[str]:
    return [
        "Open an elevated Administrator PowerShell.",
        "Run: dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart",
        "Run: dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart",
        "Run: bcdedit /set hypervisorlaunchtype auto",
        "Run: wsl.exe --shutdown",
        "Run: wsl.exe --update",
        "Run: wsl.exe --set-default-version 2",
        "Reboot Windows if any command reports that a restart is required.",
        "After reboot, run: wsl.exe --install -d Ubuntu-22.04 or wsl.exe --install -d Ubuntu.",
        "Initialize Ubuntu, then rerun the Device2 readiness gate.",
    ]


def build_report() -> dict[str, object]:
    branch = git_command(["branch", "--show-current"])
    head = git_command(["rev-parse", "--short", "HEAD"])
    repo_markers = {name: Path(name).exists() for name in [".git", "app", "docs", "scripts"]}
    repo_ok = all(repo_markers.values())
    branch_name = str(branch["stdout"]).strip() if command_ok(branch) else None

    systeminfo = run_command(["systeminfo"], timeout=60)
    firmware_virtualization = parse_firmware_virtualization(systeminfo)
    computer_info = computer_info_command()
    hypervisor_info = parse_key_value_lines(str(computer_info["stdout"]))
    feature_wsl = windows_feature_command("Microsoft-Windows-Subsystem-Linux")
    feature_vmp = windows_feature_command("VirtualMachinePlatform")
    feature_wsl_state = parse_optional_feature_state(feature_wsl)
    feature_vmp_state = parse_optional_feature_state(feature_vmp)
    bcdedit = bcdedit_command()
    hypervisorlaunchtype = parse_hypervisorlaunchtype(bcdedit)

    wsl_status = run_command(["wsl", "--status"])
    wsl_version = run_command(["wsl", "--version"])
    wsl_list = run_command(["wsl", "-l", "-v"])
    wsl_list_verbose = run_command(["wsl", "--list", "--verbose"])
    where_wsl = run_command(["where", "wsl"]) if os.name == "nt" else run_command(["which", "wsl"])

    distro_lines = parse_distro_lines(wsl_list) or parse_distro_lines(wsl_list_verbose)
    ubuntu_available = has_ubuntu(distro_lines)
    default_distro = parse_default_distro(distro_lines)
    wsl2_available = parse_wsl2(distro_lines)

    ubuntu_launch = wsl_shell("true")
    mnt_e_check = wsl_shell("test -d /mnt/e && echo /mnt/e accessible")
    gpu_query = wsl_shell("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader")
    gpu_visible = command_ok(gpu_query)
    wsl_python = wsl_shell("python3 --version")
    wsl_pip = wsl_shell("pip3 --version")
    wsl_cache_check = wsl_shell(
        "for p in "
        + " ".join(WSL_CACHE_PATHS)
        + '; do [ -e "$p" ] && echo "$p exists" || echo "$p missing"; done'
    )
    wsl_venv_check = wsl_shell(
        f"test -x {WSL_VENV_PATH}/bin/python && {WSL_VENV_PATH}/bin/python --version"
    )
    env_check = wsl_shell(
        "source ~/.bashrc >/dev/null 2>&1 || true; "
        + "for k in "
        + " ".join(REQUIRED_ENV_VARS)
        + '; do v=$(printenv "$k"); [ -n "$v" ] && echo "$k=$v" || echo "$k=missing"; done'
    )

    windows_cache = {str(path): path.exists() for path in WINDOWS_CACHE_PATHS}
    wsl_cache_exists = command_ok(wsl_cache_check) and " missing" not in str(wsl_cache_check["stdout"])
    mnt_e_accessible = command_ok(mnt_e_check)
    venv_exists = command_ok(wsl_venv_check)
    env_vars_configured = command_ok(env_check) and "=missing" not in str(env_check["stdout"])
    virtualization_blocker = has_virtualization_blocker(
        wsl_status,
        wsl_list,
        wsl_list_verbose,
        gpu_query,
    )
    hypervisor_present = parse_bool_signal(hypervisor_info, "HyperVisorPresent")
    firmware_ok = parse_bool_signal(
        hypervisor_info,
        "HyperVRequirementVirtualizationFirmwareEnabled",
    )
    slat_ok = parse_bool_signal(
        hypervisor_info,
        "HyperVRequirementSecondLevelAddressTranslation",
    )
    dep_ok = parse_bool_signal(
        hypervisor_info,
        "HyperVRequirementDataExecutionPreventionAvailable",
    )
    wsl_feature_enabled = feature_wsl_state == "Enabled"
    vmp_feature_enabled = feature_vmp_state == "Enabled"
    hypervisor_auto = (
        hypervisorlaunchtype is not None
        and hypervisorlaunchtype.lower() == "auto"
    )

    failures: list[str] = []
    cautions: list[str] = []
    if not repo_ok:
        failures.append("Current directory is not the expected TCM-Assistant repo root.")
    if branch_name != EXPECTED_BRANCH:
        failures.append(f"Current branch is {branch_name!r}, expected {EXPECTED_BRANCH!r}.")
    if not command_ok(where_wsl):
        cautions.append("wsl.exe is not available.")
    if firmware_virtualization is False:
        cautions.append("Firmware virtualization is still disabled according to systeminfo.")
    if firmware_virtualization is None:
        cautions.append("Firmware virtualization could not be parsed from systeminfo.")
    wsl_access_denied = has_access_denied(
        wsl_status,
        wsl_list,
        wsl_list_verbose,
        ubuntu_launch,
        gpu_query,
    )

    if firmware_ok is not True:
        cautions.append("Firmware virtualization requirement is not confirmed by Get-ComputerInfo.")
    if slat_ok is not True:
        cautions.append("Second Level Address Translation is not confirmed by Get-ComputerInfo.")
    if dep_ok is not True:
        cautions.append("Data Execution Prevention is not confirmed by Get-ComputerInfo.")
    if hypervisor_present is False:
        cautions.append("HyperVisorPresent is false; the Windows hypervisor is not active.")
    if hypervisor_present is None:
        cautions.append("HyperVisorPresent could not be confirmed by Get-ComputerInfo.")
    if feature_wsl_state is None:
        cautions.append("Microsoft-Windows-Subsystem-Linux feature state could not be confirmed.")
    elif not wsl_feature_enabled:
        cautions.append("Microsoft-Windows-Subsystem-Linux is not Enabled.")
    if feature_vmp_state is None:
        cautions.append("VirtualMachinePlatform feature state could not be confirmed.")
    elif not vmp_feature_enabled:
        cautions.append("VirtualMachinePlatform is not Enabled.")
    if hypervisorlaunchtype is None:
        cautions.append("hypervisorlaunchtype could not be confirmed from bcdedit.")
    elif not hypervisor_auto:
        cautions.append("hypervisorlaunchtype is not Auto.")
    if virtualization_blocker:
        cautions.append(
            "WSL2 still reports a virtualization or Virtual Machine Platform blocker."
        )
    if wsl_access_denied:
        cautions.append("WSL service returned access denied from this shell.")
    if not command_ok(feature_wsl) or not command_ok(feature_vmp):
        cautions.append(
            "Windows optional feature state could not be confirmed from this shell."
        )
    if not ubuntu_available:
        cautions.append("Ubuntu is not confirmed in the WSL distro list.")
    if not command_ok(ubuntu_launch):
        cautions.append("Ubuntu launch is not confirmed.")
    if not wsl2_available:
        cautions.append("Ubuntu WSL version 2 is not confirmed.")
    if not mnt_e_accessible:
        cautions.append("/mnt/e is not accessible from WSL.")
    if not gpu_visible:
        cautions.append("WSL nvidia-smi is not available.")
    if not all(windows_cache.values()):
        cautions.append("One or more Windows external cache paths are missing.")
    if not wsl_cache_exists:
        cautions.append("One or more WSL cache paths are missing or WSL could not check them.")
    if not command_ok(wsl_python):
        cautions.append("WSL python3 is not confirmed.")
    if not command_ok(wsl_pip):
        cautions.append("WSL pip3 is not confirmed.")
    if not env_vars_configured:
        cautions.append("Required non-secret WSL cache environment variables are not configured.")
    if not venv_exists:
        cautions.append("Planned WSL Python venv is not present.")

    status = "failed" if failures else ("caution" if cautions else "ok")
    base_ready_without_gpu = all(
        [
            wsl_feature_enabled,
            vmp_feature_enabled,
            hypervisor_auto,
            not virtualization_blocker,
            ubuntu_available,
            wsl2_available,
            command_ok(ubuntu_launch),
            mnt_e_accessible,
            wsl_cache_exists,
            env_vars_configured,
            venv_exists,
        ]
    )
    d2_p0g_allowed = base_ready_without_gpu
    if base_ready_without_gpu and not gpu_visible:
        next_gate = "D2-P0G: WSL NVIDIA Driver CUDA Readiness Gate"
    elif base_ready_without_gpu and gpu_visible:
        next_gate = "D2-P0G: ML Runtime Dependency Gate"
    else:
        next_gate = "D2-P0F-Resume: Windows Hypervisor + VMP Repair Gate"
    return {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "stage": STAGE,
        "status": status,
        "expected_branch": EXPECTED_BRANCH,
        "repo": {
            "path": str(Path.cwd()),
            "markers": repo_markers,
            "is_repo_root": repo_ok,
        },
        "git": {
            "branch": branch,
            "current_branch": branch_name,
            "head": head,
            "head_short": str(head["stdout"]).strip() if command_ok(head) else None,
        },
        "windows": {
            "systeminfo": systeminfo,
            "firmware_virtualization_enabled": firmware_virtualization,
            "computer_info": computer_info,
            "hypervisor": {
                "info": hypervisor_info,
                "present": hypervisor_present,
                "firmware_virtualization_requirement": firmware_ok,
                "second_level_address_translation": slat_ok,
                "data_execution_prevention": dep_ok,
            },
            "optional_features": {
                "Microsoft-Windows-Subsystem-Linux": {
                    "state": feature_wsl_state,
                    "enabled": wsl_feature_enabled,
                    "command": feature_wsl,
                },
                "VirtualMachinePlatform": {
                    "state": feature_vmp_state,
                    "enabled": vmp_feature_enabled,
                    "command": feature_vmp,
                },
            },
            "bcdedit": {
                "command": bcdedit,
                "hypervisorlaunchtype": hypervisorlaunchtype,
                "hypervisorlaunchtype_auto": hypervisor_auto,
            },
        },
        "wsl": {
            "where": where_wsl,
            "status": wsl_status,
            "version": wsl_version,
            "list": wsl_list,
            "list_verbose": wsl_list_verbose,
            "distro_lines": distro_lines,
            "default_distro": default_distro,
            "ubuntu_available": ubuntu_available,
            "ubuntu_launch": ubuntu_launch,
            "ubuntu_launch_confirmed": command_ok(ubuntu_launch),
            "wsl2_available": wsl2_available,
            "virtualization_blocker": virtualization_blocker,
            "access_denied": wsl_access_denied,
        },
        "gpu": {
            "query": gpu_query,
            "visible": gpu_visible,
            "parsed": parse_gpu(str(gpu_query["stdout"])) if gpu_visible else None,
        },
        "storage": {
            "windows_cache_paths": windows_cache,
            "wsl_cache_paths": WSL_CACHE_PATHS,
            "wsl_mnt_e_check": mnt_e_check,
            "wsl_mnt_e_accessible": mnt_e_accessible,
            "wsl_cache_check": wsl_cache_check,
            "wsl_cache_exists": wsl_cache_exists,
        },
        "python": {
            "wsl_python3": wsl_python,
            "wsl_pip3": wsl_pip,
            "venv_path": WSL_VENV_PATH,
            "venv_check": wsl_venv_check,
            "venv_exists": venv_exists,
        },
        "environment": {
            "required_vars": REQUIRED_ENV_VARS,
            "check": env_check,
            "configured": env_vars_configured,
        },
        "policy": {
            "model_downloaded": False,
            "training_started": False,
            "vllm_started": False,
            "torch_installed": False,
            "transformers_installed": False,
            "peft_installed": False,
            "trl_installed": False,
            "bitsandbytes_installed": False,
            "business_code_changed": False,
        },
        "manual_recovery_actions": manual_recovery_actions(),
        "reboot": {
            "required_by_executed_repair": False,
            "manual_admin_repair_may_require_reboot": True,
        },
        "next_stage": {
            "d2_p0g_allowed": d2_p0g_allowed,
            "name": next_gate,
            "d2_p1_allowed": False,
        },
        "summary": {
            "failures": failures,
            "cautions": cautions,
        },
    }


def main() -> int:
    try:
        report = build_report()
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(
            json.dumps(report, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        print("Device2 WSL2/Ubuntu readiness gate status: failed")
        print(f"Could not write report: {exc}")
        return 1

    print(f"Device2 Windows hypervisor/VMP gate status: {report['status']}")
    print(f"Report written: {REPORT_PATH}")
    print(f"Branch: {report['git']['current_branch']}")
    print(
        "Firmware virtualization enabled: "
        f"{report['windows']['firmware_virtualization_enabled']}"
    )
    print(f"HyperVisorPresent: {report['windows']['hypervisor']['present']}")
    print(
        "Microsoft-Windows-Subsystem-Linux enabled: "
        f"{report['windows']['optional_features']['Microsoft-Windows-Subsystem-Linux']['enabled']}"
    )
    print(
        "VirtualMachinePlatform enabled: "
        f"{report['windows']['optional_features']['VirtualMachinePlatform']['enabled']}"
    )
    print(
        "hypervisorlaunchtype: "
        f"{report['windows']['bcdedit']['hypervisorlaunchtype']}"
    )
    print(f"Ubuntu available: {report['wsl']['ubuntu_available']}")
    print(f"Ubuntu launch confirmed: {report['wsl']['ubuntu_launch_confirmed']}")
    print(f"WSL2 confirmed: {report['wsl']['wsl2_available']}")
    print(f"Virtualization blocker: {report['wsl']['virtualization_blocker']}")
    print(f"/mnt/e accessible: {report['storage']['wsl_mnt_e_accessible']}")
    print(f"WSL GPU visible: {report['gpu']['visible']}")
    print(f"WSL cache paths exist: {report['storage']['wsl_cache_exists']}")
    print(f"Cache env configured: {report['environment']['configured']}")
    print(f"Python venv exists: {report['python']['venv_exists']}")
    print(f"D2-P0G allowed: {report['next_stage']['d2_p0g_allowed']}")
    print(f"D2-P1 allowed: {report['next_stage']['d2_p1_allowed']}")
    if report["summary"]["cautions"]:
        print("Cautions:")
        for item in report["summary"]["cautions"]:
            print(f"- {item}")
    if report["summary"]["failures"]:
        print("Failures:")
        for item in report["summary"]["failures"]:
            print(f"- {item}")

    return 1 if report["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
