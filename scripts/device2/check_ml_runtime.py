"""Device2 ML runtime dependency gate check.

This script is intended to run inside the Device2 WSL ML venv. It performs
import and tiny CUDA smoke checks only. It does not download models, call
from_pretrained, start vLLM, run inference, or train.
"""

from __future__ import annotations

import datetime as dt
import importlib
import json
import os
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Any


STAGE = "D2-P0G_ML_RUNTIME_DEPENDENCY_GATE"
EXPECTED_VENV = "~/venvs/tcm-device2-ml-py312"
REPORT_PATH = Path("reports") / "device2" / "ml_runtime_check.json"
PACKAGE_IMPORTS = {
    "torch": "torch",
    "transformers": "transformers",
    "datasets": "datasets",
    "accelerate": "accelerate",
    "peft": "peft",
    "trl": "trl",
    "bitsandbytes": "bitsandbytes",
    "vllm": "vllm",
}


def run_command(args: list[str], timeout: int = 30) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except FileNotFoundError:
        return {
            "command": " ".join(args),
            "returncode": None,
            "stdout": "",
            "stderr": f"{args[0]} not found",
        }
    except subprocess.TimeoutExpired:
        return {
            "command": " ".join(args),
            "returncode": None,
            "stdout": "",
            "stderr": f"timed out after {timeout}s",
        }

    return {
        "command": " ".join(args),
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def import_package(import_name: str) -> dict[str, Any]:
    try:
        module = importlib.import_module(import_name)
    except Exception as exc:  # noqa: BLE001 - report smoke-test failure details.
        return {
            "ok": False,
            "version": None,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback_tail": traceback.format_exc().splitlines()[-12:],
        }

    return {
        "ok": True,
        "version": getattr(module, "__version__", "version_unknown"),
        "error": None,
    }


def parse_gpu_query(stdout: str) -> dict[str, Any]:
    line = stdout.splitlines()[0] if stdout.splitlines() else ""
    parts = [part.strip() for part in line.split(",")]
    if len(parts) < 3:
        return {
            "name": None,
            "vram_mib": None,
            "driver": None,
        }

    vram_text = parts[1]
    vram_mib: int | None = None
    if vram_text.lower().endswith("mib"):
        try:
            vram_mib = int(vram_text.split()[0])
        except ValueError:
            vram_mib = None

    return {
        "name": parts[0],
        "vram_mib": vram_mib,
        "driver": parts[2],
    }


def parse_cuda_from_nvidia_smi(stdout: str) -> str | None:
    for line in stdout.splitlines():
        marker = "CUDA Version:"
        if marker not in line:
            continue
        return line.split(marker, 1)[1].strip().split()[0].strip("|")
    return None


def check_gpu() -> dict[str, Any]:
    query = run_command(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,driver_version",
            "--format=csv,noheader",
        ]
    )
    summary = run_command(["nvidia-smi"])
    parsed = parse_gpu_query(query["stdout"]) if query["returncode"] == 0 else {}
    return {
        "nvidia_smi": "ok" if query["returncode"] == 0 else "failed",
        "name": parsed.get("name"),
        "vram_mib": parsed.get("vram_mib"),
        "driver": parsed.get("driver"),
        "cuda_from_nvidia_smi": parse_cuda_from_nvidia_smi(summary["stdout"]),
        "query": query,
        "summary_returncode": summary["returncode"],
    }


def check_pip_cache() -> str | None:
    result = run_command([sys.executable, "-m", "pip", "cache", "dir"])
    if result["returncode"] != 0:
        return None
    return result["stdout"].strip()


def check_torch() -> dict[str, Any]:
    result: dict[str, Any] = {
        "import": False,
        "version": None,
        "cuda_available": False,
        "cuda_version": None,
        "device_count": None,
        "device_name": None,
        "cuda_tensor": False,
        "error": None,
    }
    try:
        import torch

        result["import"] = True
        result["version"] = getattr(torch, "__version__", "version_unknown")
        result["cuda_available"] = bool(torch.cuda.is_available())
        result["cuda_version"] = torch.version.cuda
        result["device_count"] = torch.cuda.device_count()
        if result["cuda_available"]:
            result["device_name"] = torch.cuda.get_device_name(0)
            tensor = torch.randn(2, 2, device="cuda")
            result["cuda_tensor"] = tensor.device.type == "cuda"
    except Exception as exc:  # noqa: BLE001 - report smoke-test failure details.
        result["cuda_available"] = False
        result["cuda_tensor"] = False
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["traceback_tail"] = traceback.format_exc().splitlines()[-12:]
    return result


def check_bitsandbytes_cuda() -> dict[str, Any]:
    result: dict[str, Any] = {
        "import": False,
        "version": None,
        "cuda_smoke": False,
        "error": None,
    }
    try:
        import bitsandbytes as bnb
        import torch

        result["import"] = True
        result["version"] = getattr(bnb, "__version__", "version_unknown")
        lin = bnb.nn.Linear8bitLt(4, 2).cuda()
        x = torch.randn(1, 4, device="cuda")
        y = lin(x)
        result["cuda_smoke"] = y.device.type == "cuda" and tuple(y.shape) == (1, 2)
    except Exception as exc:  # noqa: BLE001 - report smoke-test failure details.
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["traceback_tail"] = traceback.format_exc().splitlines()[-12:]
    return result


def summarize(report: dict[str, Any]) -> tuple[str, str | None]:
    checks = report["checks"]
    package_imports = report["package_imports"]
    failures: list[str] = []

    if not report["python"]["version"].startswith("3.12."):
        failures.append("ML venv is not Python 3.12.")
    if report["python"]["pip_cache_dir"] != "/mnt/e/ai_models/pip":
        failures.append("pip cache is not /mnt/e/ai_models/pip.")
    if not checks["torch_cuda_available"]:
        failures.append("torch.cuda.is_available() is not true.")
    if not checks["torch_cuda_tensor"]:
        failures.append("torch cannot create a CUDA tensor.")
    for name in ["transformers", "datasets", "accelerate", "peft", "trl"]:
        if not package_imports[name]["ok"]:
            failures.append(f"{name} import failed.")
    if not checks["bitsandbytes_import"]:
        failures.append("bitsandbytes import failed.")
    if not checks["bitsandbytes_cuda_smoke"]:
        failures.append("bitsandbytes CUDA smoke failed.")
    if not checks["vllm_import"]:
        failures.append("vLLM import failed.")
    if report["policy"]["model_downloaded"]:
        failures.append("model download occurred.")
    if report["policy"]["training_run"]:
        failures.append("training occurred.")
    if report["policy"]["vllm_server_started"]:
        failures.append("vLLM server was started.")

    status = "ok" if not failures else "caution"
    return status, "; ".join(failures) if failures else None


def build_report() -> dict[str, Any]:
    package_results = {
        name: import_package(import_name)
        for name, import_name in PACKAGE_IMPORTS.items()
    }
    torch_result = check_torch()
    bnb_result = check_bitsandbytes_cuda()
    version = sys.version.split()[0]
    report: dict[str, Any] = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "stage": STAGE,
        "python": {
            "path": sys.executable,
            "version": version,
            "venv": EXPECTED_VENV,
            "prefix": sys.prefix,
            "pip_cache_dir": check_pip_cache(),
        },
        "gpu": check_gpu(),
        "packages": {
            name: result["version"] if result["ok"] else None
            for name, result in package_results.items()
        },
        "package_imports": package_results,
        "checks": {
            "torch_import": torch_result["import"],
            "torch_cuda_available": torch_result["cuda_available"],
            "torch_cuda_tensor": torch_result["cuda_tensor"],
            "bitsandbytes_import": bnb_result["import"],
            "bitsandbytes_cuda_smoke": bnb_result["cuda_smoke"],
            "vllm_import": package_results["vllm"]["ok"],
        },
        "details": {
            "torch": torch_result,
            "bitsandbytes": bnb_result,
        },
        "policy": {
            "model_downloaded": False,
            "training_run": False,
            "vllm_server_started": False,
            "business_code_changed": False,
        },
    }
    status, blocked_reason = summarize(report)
    report["status"] = status
    report["blocked_reason"] = blocked_reason
    report["next_stage"] = {
        "d2_p1_allowed": status == "ok",
        "name": (
            "D2-P1: Local Base Inference Baseline"
            if status == "ok"
            else "D2-P0G-Resume: ML Runtime Dependency Repair"
        ),
    }
    return report


def main() -> int:
    report = build_report()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
