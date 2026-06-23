"""Device2 pre-training runtime finalization gate check.

This check validates only the formal training runtime. It intentionally does
not install or import vLLM as a serving requirement, does not download models,
does not call from_pretrained, does not train, and does not create adapters.
"""

from __future__ import annotations

import datetime as dt
import json
import subprocess
import textwrap
from pathlib import Path
from typing import Any


STAGE = "D2-P0H: Pre-Training Runtime Finalization Gate"
TRAINING_ENV = "~/venvs/tcm-device2-train-py312-cu126-final"
REPORT_PATH = Path("reports") / "device2" / "ml_runtime_finalization_check.json"
LEGACY_REPORT_PATH = Path("reports") / "device2" / "ml_runtime_check.json"
REQUIRED_IMPORTS = [
    "transformers",
    "datasets",
    "accelerate",
    "peft",
    "trl",
    "bitsandbytes",
    "sentencepiece",
    "google.protobuf",
    "yaml",
    "rich",
    "safetensors",
    "numpy",
]


def run_command(args: list[str], timeout: int = 60) -> dict[str, Any]:
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


def env_python(env_path: str) -> str:
    return str(Path.home() / env_path.removeprefix("~/") / "bin" / "python")


def run_env_probe(env_path: str, code: str, timeout: int = 240) -> dict[str, Any]:
    python = env_python(env_path)
    proc = run_command([python, "-c", textwrap.dedent(code)], timeout=timeout)
    if proc["returncode"] != 0:
        return {
            "ok": False,
            "python": python,
            "probe_error": proc,
        }

    try:
        payload = json.loads(proc["stdout"])
    except json.JSONDecodeError as exc:
        return {
            "ok": False,
            "python": python,
            "probe_error": {
                "error": f"JSONDecodeError: {exc}",
                "raw": proc,
            },
        }

    payload["ok"] = True
    payload["python"] = python
    payload["stderr"] = proc["stderr"]
    return payload


def check_gpu() -> dict[str, Any]:
    query = run_command(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,driver_version",
            "--format=csv,noheader",
        ]
    )
    parsed: dict[str, str | None] = {
        "name": None,
        "memory_total": None,
        "driver_version": None,
    }
    if query["returncode"] == 0 and query["stdout"]:
        parts = [part.strip() for part in query["stdout"].splitlines()[0].split(",")]
        if len(parts) >= 3:
            parsed = {
                "name": parts[0],
                "memory_total": parts[1],
                "driver_version": parts[2],
            }

    summary = run_command(["nvidia-smi"])
    cuda_version = None
    for line in summary["stdout"].splitlines():
        marker = "CUDA Version:"
        if marker in line:
            cuda_version = line.split(marker, 1)[1].strip().split()[0].strip("|")
            break

    return {
        "nvidia_smi": "ok" if query["returncode"] == 0 else "failed",
        "name": parsed["name"],
        "memory_total": parsed["memory_total"],
        "driver_version": parsed["driver_version"],
        "cuda_from_nvidia_smi": cuda_version,
        "query": query,
        "summary_returncode": summary["returncode"],
    }


def check_storage() -> dict[str, Any]:
    return {
        "df": run_command(["df", "-h", "/", "/mnt/e", "/mnt/d"], timeout=30),
        "venvs": run_command(["du", "-sh", str(Path.home() / "venvs")], timeout=30),
    }


TRAINING_PROBE = r"""
import importlib
import importlib.metadata as metadata
import importlib.util
import json
import os
import subprocess
import sys
import traceback

result = {
    "path": "__ENV_PATH__",
    "python_version": sys.version.split()[0],
    "prefix": sys.prefix,
    "pip_cache_dir": None,
    "cache_env": {
        "HF_HOME": os.environ.get("HF_HOME"),
        "HUGGINGFACE_HUB_CACHE": os.environ.get("HUGGINGFACE_HUB_CACHE"),
        "TRANSFORMERS_CACHE": os.environ.get("TRANSFORMERS_CACHE"),
        "HF_DATASETS_CACHE": os.environ.get("HF_DATASETS_CACHE"),
        "TORCH_HOME": os.environ.get("TORCH_HOME"),
        "PIP_CACHE_DIR": os.environ.get("PIP_CACHE_DIR"),
        "UV_CACHE_DIR": os.environ.get("UV_CACHE_DIR"),
        "TMPDIR": os.environ.get("TMPDIR"),
        "TCM_DEVICE2_ARTIFACTS": os.environ.get("TCM_DEVICE2_ARTIFACTS"),
    },
    "packages": {},
    "imports": {},
    "torch": {
        "import": False,
        "version": None,
        "cuda_version": None,
        "cuda_available": False,
        "device_count": None,
        "device_name": None,
        "cuda_tensor": False,
        "error": None,
    },
    "bitsandbytes": {
        "import": False,
        "version": None,
        "cuda_smoke": False,
        "error": None,
    },
    "dry_runs": {
        "lora_config": False,
        "sft_config": False,
        "error": None,
    },
    "vllm_absent": False,
}

pip_cache = subprocess.run(
    [sys.executable, "-m", "pip", "cache", "dir"],
    capture_output=True,
    text=True,
)
if pip_cache.returncode == 0:
    result["pip_cache_dir"] = pip_cache.stdout.strip()

try:
    import torch

    result["torch"]["import"] = True
    result["torch"]["version"] = getattr(torch, "__version__", "version_unknown")
    result["torch"]["cuda_version"] = torch.version.cuda
    result["torch"]["cuda_available"] = bool(torch.cuda.is_available())
    result["torch"]["device_count"] = torch.cuda.device_count()
    if result["torch"]["cuda_available"]:
        result["torch"]["device_name"] = torch.cuda.get_device_name(0)
        tensor = torch.ones(2, device="cuda")
        result["torch"]["cuda_tensor"] = tensor.device.type == "cuda" and float(tensor.sum().item()) == 2.0
except Exception as exc:
    result["torch"]["error"] = f"{type(exc).__name__}: {exc}"
    result["torch"]["traceback_tail"] = traceback.format_exc().splitlines()[-12:]

for name in __IMPORTS__:
    try:
        module = importlib.import_module(name)
        version = getattr(module, "__version__", "version_unknown")
        if version == "version_unknown":
            package_name = {
                "google.protobuf": "protobuf",
                "yaml": "pyyaml",
            }.get(name, name)
            try:
                version = metadata.version(package_name)
            except metadata.PackageNotFoundError:
                version = "version_unknown"
        result["imports"][name] = {"ok": True, "version": version, "error": None}
        result["packages"][name] = version
    except Exception as exc:
        result["imports"][name] = {
            "ok": False,
            "version": None,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback_tail": traceback.format_exc().splitlines()[-12:],
        }
        result["packages"][name] = None

try:
    from peft import LoraConfig
    from trl import SFTConfig

    LoraConfig(
        r=8,
        lora_alpha=16,
        target_modules=["q_proj", "v_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    result["dry_runs"]["lora_config"] = True

    SFTConfig(
        output_dir="/tmp/tcm-device2-sft-dry-run",
        dataset_text_field="text",
        max_steps=1,
        per_device_train_batch_size=1,
    )
    result["dry_runs"]["sft_config"] = True
except Exception as exc:
    result["dry_runs"]["error"] = f"{type(exc).__name__}: {exc}"
    result["dry_runs"]["traceback_tail"] = traceback.format_exc().splitlines()[-12:]

try:
    import bitsandbytes as bnb
    import torch

    result["bitsandbytes"]["import"] = True
    result["bitsandbytes"]["version"] = getattr(bnb, "__version__", "version_unknown")
    lin = bnb.nn.Linear8bitLt(4, 2).cuda()
    x = torch.randn(1, 4, device="cuda")
    y = lin(x)
    result["bitsandbytes"]["cuda_smoke"] = y.device.type == "cuda" and tuple(y.shape) == (1, 2)
except Exception as exc:
    result["bitsandbytes"]["error"] = f"{type(exc).__name__}: {exc}"
    result["bitsandbytes"]["traceback_tail"] = traceback.format_exc().splitlines()[-12:]

result["vllm_absent"] = importlib.util.find_spec("vllm") is None

print(json.dumps(result, ensure_ascii=True))
"""


def build_training_probe() -> str:
    return TRAINING_PROBE.replace("__ENV_PATH__", TRAINING_ENV).replace(
        "__IMPORTS__",
        repr(REQUIRED_IMPORTS),
    )


def summarize(report: dict[str, Any]) -> tuple[str, str | None]:
    failures: list[str] = []
    training = report["training_env"]

    if report["gpu"]["nvidia_smi"] != "ok":
        failures.append("WSL nvidia-smi failed")

    if not training.get("ok"):
        failures.append("training env probe failed")
    else:
        if not training["python_version"].startswith("3.12."):
            failures.append("training env is not Python 3.12")
        if training.get("pip_cache_dir") != "/mnt/e/ai_models/pip":
            failures.append("training env pip cache is not /mnt/e/ai_models/pip")
        if training["cache_env"].get("TMPDIR") != "/mnt/e/ai_artifacts/tcm_assistant_device2/tmp":
            failures.append("training env TMPDIR is not on /mnt/e")
        if not training["torch"]["import"]:
            failures.append("training env torch import failed")
        if training["torch"]["version"] != "2.12.1+cu126":
            failures.append("training env torch is not 2.12.1+cu126")
        if training["torch"]["cuda_version"] != "12.6":
            failures.append("training env torch CUDA is not 12.6")
        if not training["torch"]["cuda_available"]:
            failures.append("training env torch CUDA is unavailable")
        if not training["torch"]["cuda_tensor"]:
            failures.append("training env torch CUDA tensor smoke failed")
        for name in ["transformers", "datasets", "accelerate", "peft", "trl", "bitsandbytes"]:
            if not training["imports"].get(name, {}).get("ok"):
                failures.append(f"training env {name} import failed")
        if not training["bitsandbytes"]["import"]:
            failures.append("training env bitsandbytes import failed")
        if not training["bitsandbytes"]["cuda_smoke"]:
            failures.append("training env bitsandbytes CUDA smoke failed")
        if not training["dry_runs"]["lora_config"]:
            failures.append("LoraConfig dry-run failed")
        if not training["dry_runs"]["sft_config"]:
            failures.append("SFTConfig dry-run failed")
        if not training["vllm_absent"]:
            failures.append("vLLM is installed in the training env")

    for key in [
        "model_downloaded",
        "from_pretrained_model_download",
        "training_run",
        "vllm_server_started",
        "lora_adapter_created",
        "business_code_changed",
        "api_changed",
        "langgraph_changed",
        "pushed",
    ]:
        if report["policy"][key]:
            failures.append(f"policy violation: {key}")

    status = "ok" if not failures else "blocked_no_commit"
    return status, "; ".join(failures) if failures else None


def build_report() -> dict[str, Any]:
    report: dict[str, Any] = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "stage": STAGE,
        "gpu": check_gpu(),
        "storage": check_storage(),
        "training_env": run_env_probe(TRAINING_ENV, build_training_probe()),
        "policy": {
            "model_downloaded": False,
            "from_pretrained_model_download": False,
            "training_run": False,
            "vllm_server_started": False,
            "lora_adapter_created": False,
            "business_code_changed": False,
            "api_changed": False,
            "langgraph_changed": False,
            "pushed": False,
        },
    }
    status, blocked_reason = summarize(report)
    report["status"] = status
    report["blocked_reason"] = blocked_reason
    report["acceptance"] = {
        "result": status,
        "d2_p1_allowed": status == "ok",
        "next_stage": (
            "D2-P1: Transformers-only Local Base Inference Baseline"
            if status == "ok"
            else "D2-P0H: Pre-Training Runtime Finalization Gate"
        ),
    }
    return report


def main() -> int:
    report = build_report()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, indent=2, ensure_ascii=True) + "\n"
    REPORT_PATH.write_text(payload, encoding="utf-8")
    LEGACY_REPORT_PATH.write_text(payload, encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
