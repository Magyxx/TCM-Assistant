"""Device2 WSL/CUDA readiness check.

This script is intentionally stdlib-only. It probes WSL, Ubuntu, GPU
visibility, Python tooling, disk, and memory signals, then writes
reports/device2/wsl_cuda_check.json. It does not install dependencies, download
models, start vLLM, or run training.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import string
import subprocess
from pathlib import Path


STAGE = "D2-P0F"
REPORT_PATH = Path("reports") / "device2" / "wsl_cuda_check.json"
TIMEOUT_SECONDS = 15


def bytes_to_gib(value: int) -> float:
    return round(value / (1024**3), 2)


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


def run_command(args: list[str], timeout: int = TIMEOUT_SECONDS) -> dict[str, object]:
    command = " ".join(args)
    if shutil.which(args[0]) is None:
        return {
            "command": command,
            "available": False,
            "returncode": None,
            "stdout": "",
            "stderr": f"{args[0]} not found",
        }

    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            timeout=timeout,
        )
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


def run_wsl_shell(command: str) -> dict[str, object]:
    return run_command(["wsl", "bash", "-lc", command])


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


def parse_gpu_query(stdout: str) -> dict[str, str] | None:
    for line in stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) >= 2:
            return {
                "name": parts[0],
                "memory_total": parts[1],
            }
    return None


def windows_drive_inventory() -> list[dict[str, object]]:
    if os.name != "nt":
        usage = shutil.disk_usage(Path.cwd())
        return [
            {
                "name": str(Path.cwd().anchor or Path.cwd()),
                "ready": True,
                "total_gib": bytes_to_gib(usage.total),
                "free_gib": bytes_to_gib(usage.free),
            }
        ]

    drives: list[dict[str, object]] = []
    for letter in string.ascii_uppercase:
        root = Path(f"{letter}:\\")
        try:
            if not root.exists():
                continue
            usage = shutil.disk_usage(root)
        except OSError:
            drives.append({"name": str(root), "ready": False})
            continue
        drives.append(
            {
                "name": str(root),
                "ready": True,
                "total_gib": bytes_to_gib(usage.total),
                "free_gib": bytes_to_gib(usage.free),
            }
        )
    return drives


def build_report() -> dict[str, object]:
    status = run_command(["wsl", "--status"])
    list_verbose = run_command(["wsl", "--list", "--verbose"])
    list_short = run_command(["wsl", "-l", "-v"])
    version = run_command(["wsl", "--version"])
    where_wsl = (
        run_command(["where", "wsl"]) if os.name == "nt" else run_command(["which", "wsl"])
    )

    distro_lines = parse_distro_lines(list_verbose) or parse_distro_lines(list_short)
    default_distro = parse_default_distro(distro_lines)
    ubuntu_available = has_ubuntu(distro_lines)
    wsl_available = (
        command_ok(status)
        or command_ok(list_verbose)
        or command_ok(list_short)
        or command_ok(where_wsl)
    )

    shell_commands = {
        "os_release": run_wsl_shell("cat /etc/os-release"),
        "uname": run_wsl_shell("uname -a"),
        "nvidia_smi_query": run_wsl_shell(
            "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader"
        ),
        "nvidia_smi": run_wsl_shell("nvidia-smi"),
        "python3_path": run_wsl_shell("which python3 || true"),
        "python3_version": run_wsl_shell("python3 --version || true"),
        "pip3_path": run_wsl_shell("which pip3 || true"),
        "pip3_version": run_wsl_shell("pip3 --version || true"),
        "conda_path": run_wsl_shell("which conda || true"),
        "uv_path": run_wsl_shell("which uv || true"),
        "disk": run_wsl_shell("df -h"),
        "memory": run_wsl_shell("free -h"),
    }

    gpu_query = shell_commands["nvidia_smi_query"]
    gpu_visible = command_ok(gpu_query)
    gpu = parse_gpu_query(str(gpu_query["stdout"])) if gpu_visible else None

    cautions: list[str] = []
    failures: list[str] = []
    if not wsl_available:
        cautions.append("wsl.exe was not available or did not return a usable status.")
    if not ubuntu_available:
        cautions.append("Ubuntu was not confirmed in the WSL distro list.")
    if not gpu_visible:
        cautions.append("NVIDIA GPU was not visible from WSL nvidia-smi.")
    if not command_ok(shell_commands["python3_version"]):
        cautions.append("WSL python3 version was not confirmed.")
    if not command_ok(shell_commands["pip3_version"]):
        cautions.append("WSL pip3 version was not confirmed.")

    stage_status = "failed" if failures else ("caution" if cautions else "ok")
    return {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "stage": STAGE,
        "status": stage_status,
        "summary": {
            "wsl_available": wsl_available,
            "ubuntu_available": ubuntu_available,
            "default_distro": default_distro,
            "distro_lines": distro_lines,
            "gpu_visible_in_wsl": gpu_visible,
            "wsl_gpu": gpu,
            "cautions": cautions,
            "failures": failures,
        },
        "commands": {
            "where_wsl": where_wsl,
            "wsl_status": status,
            "wsl_list_verbose": list_verbose,
            "wsl_list_short": list_short,
            "wsl_version": version,
            "wsl_shell": shell_commands,
        },
        "windows_drives": windows_drive_inventory(),
        "policy": {
            "model_downloaded": False,
            "training_started": False,
            "vllm_started": False,
            "business_code_changed": False,
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
        print("Device2 WSL/CUDA check status: failed")
        print(f"Could not write report: {exc}")
        return 1

    summary = report["summary"]
    print(f"Device2 WSL/CUDA check status: {report['status']}")
    print(f"Report written: {REPORT_PATH}")
    print(f"WSL available: {summary['wsl_available']}")
    print(f"Ubuntu available: {summary['ubuntu_available']}")
    print(f"WSL GPU visible: {summary['gpu_visible_in_wsl']}")
    if summary["wsl_gpu"]:
        gpu = summary["wsl_gpu"]
        print(f"WSL GPU: {gpu['name']} ({gpu['memory_total']})")
    if summary["cautions"]:
        print("Cautions:")
        for item in summary["cautions"]:
            print(f"- {item}")
    if summary["failures"]:
        print("Failures:")
        for item in summary["failures"]:
            print(f"- {item}")

    return 1 if report["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
