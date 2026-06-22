"""Device2 environment readiness check.

This script is intentionally stdlib-only. It checks command availability,
basic versions, optional Python module discoverability, GPU/WSL signals, and
disk space, then writes reports/device2/env_check.json.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


ROOT_MARKERS = [".git", "app", "docs", "scripts"]
STAGE = "D2-P0E"
REPORT_PATH = Path("reports") / "device2" / "env_check.json"

OPTIONAL_MODULES = [
    "torch",
    "transformers",
    "datasets",
    "accelerate",
    "peft",
    "trl",
    "bitsandbytes",
    "vllm",
    "openai",
    "pydantic",
    "yaml",
    "sklearn",
    "pandas",
]


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


def run_command(args: list[str], timeout: int = 15) -> dict[str, object]:
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


def parse_cuda_version(stdout: str) -> str | None:
    for line in stdout.splitlines():
        if "CUDA Version:" not in line:
            continue
        after = line.split("CUDA Version:", 1)[1].strip()
        return after.split()[0].strip("|")
    return None


def parse_gpu_csv(stdout: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for line in stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 3:
            continue
        records.append(
            {
                "name": parts[0],
                "memory_total": parts[1],
                "driver_version": parts[2],
            }
        )
    return records


def check_repo_root(root: Path) -> dict[str, object]:
    markers = {marker: (root / marker).exists() for marker in ROOT_MARKERS}
    return {
        "path": str(root),
        "markers": markers,
        "is_repo_root": all(markers.values()),
    }


def check_git() -> dict[str, object]:
    safe_dir = str(Path.cwd()).replace("\\", "/")
    git = ["git", "-c", f"safe.directory={safe_dir}"]
    version = run_command(["git", "--version"])
    branch = run_command(git + ["branch", "--show-current"])
    head = run_command(git + ["rev-parse", "--short", "HEAD"])
    status = run_command(git + ["status", "--short"])
    return {
        "version": version,
        "branch": branch,
        "head": head,
        "status_short": status,
        "available": command_ok(version),
        "current_branch": branch["stdout"] if command_ok(branch) else None,
        "head_short": head["stdout"] if command_ok(head) else None,
    }


def check_python() -> dict[str, object]:
    where_python = (
        run_command(["where", "python"])
        if os.name == "nt"
        else run_command(["which", "python"])
    )
    conda = run_command(["conda", "--version"])
    uv = run_command(["uv", "--version"])
    pip = run_command([sys.executable, "-m", "pip", "--version"])
    modules = {
        name: importlib.util.find_spec(name) is not None
        for name in OPTIONAL_MODULES
    }
    return {
        "executable": sys.executable,
        "version": sys.version.replace("\n", " "),
        "implementation": platform.python_implementation(),
        "where_python": where_python,
        "conda": conda,
        "uv": uv,
        "pip": pip,
        "optional_modules": modules,
    }


def check_system(root: Path) -> dict[str, object]:
    usage = shutil.disk_usage(root)
    return {
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "disk": {
            "path": str(root.anchor or root),
            "total_gib": bytes_to_gib(usage.total),
            "free_gib": bytes_to_gib(usage.free),
            "used_gib": bytes_to_gib(usage.used),
        },
    }


def check_nvidia() -> dict[str, object]:
    query = run_command(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,driver_version",
            "--format=csv,noheader",
        ]
    )
    summary = run_command(["nvidia-smi"])
    return {
        "query": query,
        "summary": summary,
        "available": command_ok(query),
        "gpus": parse_gpu_csv(str(query["stdout"])) if command_ok(query) else [],
        "cuda_version": (
            parse_cuda_version(str(summary["stdout"])) if command_ok(summary) else None
        ),
    }


def check_wsl() -> dict[str, object]:
    if os.name != "nt":
        return {
            "applicable": False,
            "available": False,
            "status": None,
            "list": None,
            "uname": None,
        }

    status = run_command(["wsl", "--status"])
    distros = run_command(["wsl", "-l", "-v"])
    uname = run_command(["wsl", "bash", "-lc", "uname -a"])
    return {
        "applicable": True,
        "available": command_ok(status) or command_ok(distros) or command_ok(uname),
        "status": status,
        "list": distros,
        "uname": uname,
    }


def wsl_runtime_blocked(wsl: dict[str, object]) -> bool:
    combined = "\n".join(
        str(result.get("stdout", "")) + "\n" + str(result.get("stderr", ""))
        for result in [wsl["status"], wsl["list"], wsl["uname"]]
        if isinstance(result, dict)
    ).lower()
    markers = [
        "wsl2",
        "virtualization",
        "enablevirtualization",
        "virtual machine platform",
        "no installed distributions",
    ]
    return any(marker in combined for marker in markers)


def build_summary(report: dict[str, object]) -> dict[str, object]:
    failures: list[str] = []
    cautions: list[str] = []

    repo = report["repo"]
    git = report["git"]
    nvidia = report["nvidia"]
    wsl = report["wsl"]
    python = report["python"]

    if not repo["is_repo_root"]:
        failures.append("Current working directory is not the expected repo root.")
    if not git["available"]:
        failures.append("git is unavailable.")
    if not nvidia["available"]:
        cautions.append("nvidia-smi is unavailable or returned a non-zero result.")
    if not nvidia["cuda_version"]:
        cautions.append("CUDA version could not be parsed from nvidia-smi.")
    if wsl["applicable"] and not wsl["available"]:
        cautions.append("WSL did not return a successful status/list/uname result.")
    if wsl["applicable"] and wsl_runtime_blocked(wsl):
        cautions.append("WSL2/Ubuntu runtime is still blocked or not registered.")

    modules = python["optional_modules"]
    missing_modules = sorted(name for name, present in modules.items() if not present)
    if missing_modules:
        cautions.append(
            "Optional Python modules are not discoverable: "
            + ", ".join(missing_modules)
        )

    disk = report["system"]["disk"]
    if disk["free_gib"] < 80:
        cautions.append(
            f"Free disk space on the repo drive is {disk['free_gib']} GiB; "
            "model caches and checkpoints need a separate storage plan."
        )

    status = "failed" if failures else ("caution" if cautions else "ok")
    return {
        "status": status,
        "failures": failures,
        "cautions": cautions,
        "missing_optional_modules": missing_modules,
    }


def main() -> int:
    root = Path.cwd()
    report: dict[str, object] = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "stage": STAGE,
        "repo": check_repo_root(root),
        "system": check_system(root),
        "git": check_git(),
        "python": check_python(),
        "nvidia": check_nvidia(),
        "wsl": check_wsl(),
        "policy": {
            "model_downloaded": False,
            "training_run": False,
            "heavy_dependency_install": False,
            "business_code_changed": False,
        },
    }
    report["summary"] = build_summary(report)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )

    summary = report["summary"]
    print(f"Device2 env check status: {summary['status']}")
    print(f"Report written: {REPORT_PATH}")
    if summary["failures"]:
        print("Failures:")
        for item in summary["failures"]:
            print(f"- {item}")
    if summary["cautions"]:
        print("Cautions:")
        for item in summary["cautions"]:
            print(f"- {item}")

    return 1 if summary["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
