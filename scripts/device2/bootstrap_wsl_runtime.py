"""Device2 WSL runtime bootstrap readiness check.

This script is intentionally stdlib-only and read-only. It does not install WSL,
Ubuntu, Python packages, model weights, vLLM, or training dependencies. It
checks the current repo branch, WSL/Ubuntu/GPU signals, external cache paths,
and the planned WSL Python venv, then writes a JSON report.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
from pathlib import Path


EXPECTED_BRANCH = "feature/device2-local-lora-extractor"
REPORT_PATH = Path("reports") / "device2" / "wsl_bootstrap_check.json"
WINDOWS_CACHE_PATHS = [
    Path("E:/ai_models/huggingface"),
    Path("E:/ai_models/modelscope"),
    Path("E:/ai_models/vllm"),
    Path("E:/ai_artifacts/tcm_assistant_device2"),
]
WSL_CACHE_PATHS = [
    "/mnt/e/ai_models/huggingface",
    "/mnt/e/ai_models/modelscope",
    "/mnt/e/ai_models/vllm",
    "/mnt/e/ai_artifacts/tcm_assistant_device2",
]
WSL_VENV_PATH = "/mnt/e/ai_artifacts/tcm_assistant_device2/venvs/tcm-lora"


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


def run_command(args: list[str], timeout: int = 20) -> dict[str, object]:
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
        if "ubuntu" in line.lower() and line.split()[-1] == "2":
            return True
    return False


def parse_gpu(stdout: str) -> dict[str, str] | None:
    for line in stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) >= 2:
            return {"name": parts[0], "memory_total": parts[1]}
    return None


def build_report() -> dict[str, object]:
    branch = git_command(["branch", "--show-current"])
    repo_markers = {name: Path(name).exists() for name in [".git", "app", "docs", "scripts"]}
    repo_ok = all(repo_markers.values())
    branch_name = str(branch["stdout"]).strip() if command_ok(branch) else None

    wsl_status = run_command(["wsl", "--status"])
    wsl_version = run_command(["wsl", "--version"])
    wsl_list = run_command(["wsl", "-l", "-v"])
    wsl_list_verbose = run_command(["wsl", "--list", "--verbose"])
    where_wsl = run_command(["where", "wsl"]) if os.name == "nt" else run_command(["which", "wsl"])

    distro_lines = parse_distro_lines(wsl_list) or parse_distro_lines(wsl_list_verbose)
    ubuntu_available = has_ubuntu(distro_lines)
    default_distro = parse_default_distro(distro_lines)
    wsl2_available = parse_wsl2(distro_lines)

    gpu_query = wsl_shell("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader")
    gpu_visible = command_ok(gpu_query)
    wsl_python = wsl_shell("python3 --version || true")
    wsl_pip = wsl_shell("pip3 --version || true")
    wsl_cache_check = wsl_shell(
        "for p in "
        + " ".join(WSL_CACHE_PATHS)
        + f" {WSL_VENV_PATH}; do [ -e \"$p\" ] && echo \"$p exists\" || echo \"$p missing\"; done"
    )
    wsl_venv_check = wsl_shell(f"test -x {WSL_VENV_PATH}/bin/python && {WSL_VENV_PATH}/bin/python --version")

    windows_cache = {str(path): path.exists() for path in WINDOWS_CACHE_PATHS}
    wsl_cache_exists = command_ok(wsl_cache_check) and " missing" not in str(wsl_cache_check["stdout"])
    venv_exists = command_ok(wsl_venv_check)

    failures: list[str] = []
    cautions: list[str] = []
    if not repo_ok:
        failures.append("Current directory is not the expected TCM-Assistant repo root.")
    if branch_name != EXPECTED_BRANCH:
        failures.append(f"Current branch is {branch_name!r}, expected {EXPECTED_BRANCH!r}.")
    if not command_ok(where_wsl):
        cautions.append("wsl.exe is not available.")
    if not ubuntu_available:
        cautions.append("Ubuntu is not confirmed in the WSL distro list.")
    if not wsl2_available:
        cautions.append("Ubuntu WSL version 2 is not confirmed.")
    if not gpu_visible:
        cautions.append("WSL nvidia-smi is not available.")
    if not all(windows_cache.values()):
        cautions.append("One or more Windows external cache paths are missing.")
    if not wsl_cache_exists:
        cautions.append("One or more WSL cache paths are missing or WSL could not check them.")
    if not command_ok(wsl_python):
        cautions.append("WSL python3 is not confirmed.")
    if not venv_exists:
        cautions.append("Planned WSL Python venv is not present.")

    status = "failed" if failures else ("caution" if cautions else "ok")
    return {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "stage": "D2-P0D",
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
            "wsl2_available": wsl2_available,
        },
        "gpu": {
            "query": gpu_query,
            "visible": gpu_visible,
            "parsed": parse_gpu(str(gpu_query["stdout"])) if gpu_visible else None,
        },
        "storage": {
            "windows_cache_paths": windows_cache,
            "wsl_cache_paths": WSL_CACHE_PATHS,
            "wsl_cache_check": wsl_cache_check,
        },
        "python": {
            "wsl_python3": wsl_python,
            "wsl_pip3": wsl_pip,
            "venv_path": WSL_VENV_PATH,
            "venv_check": wsl_venv_check,
            "venv_exists": venv_exists,
        },
        "policy": {
            "model_downloaded": False,
            "training_started": False,
            "vllm_started": False,
            "torch_installed": False,
            "transformers_installed": False,
            "business_code_changed": False,
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
        print("Device2 WSL bootstrap check status: failed")
        print(f"Could not write report: {exc}")
        return 1

    print(f"Device2 WSL bootstrap check status: {report['status']}")
    print(f"Report written: {REPORT_PATH}")
    print(f"Branch: {report['git']['current_branch']}")
    print(f"Ubuntu available: {report['wsl']['ubuntu_available']}")
    print(f"WSL2 confirmed: {report['wsl']['wsl2_available']}")
    print(f"WSL GPU visible: {report['gpu']['visible']}")
    print(f"Python venv exists: {report['python']['venv_exists']}")
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
