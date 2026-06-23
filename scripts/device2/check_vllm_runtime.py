from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_ADAPTER_PATH = Path(
    "/mnt/e/ai_artifacts/tcm_assistant_device2/"
    "d2t1r2/risk_repair_20260623T060605Z/adapter/final_adapter"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def import_module_version(name: str) -> tuple[bool, str | None, str | None]:
    try:
        module = __import__(name)
        return True, str(getattr(module, "__version__", "unknown")), None
    except Exception as exc:  # noqa: BLE001
        return False, None, f"{type(exc).__name__}: {exc}"


def get_distro() -> dict[str, str]:
    try:
        return {str(k): str(v) for k, v in platform.freedesktop_os_release().items()}
    except Exception:
        os_release = Path("/etc/os-release")
        if not os_release.exists():
            return {}
        data: dict[str, str] = {}
        for line in os_release.read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key] = value.strip().strip('"')
        return data


def run_nvidia_smi() -> dict[str, Any]:
    command = [
        "nvidia-smi",
        "--query-gpu=name,driver_version",
        "--format=csv,noheader",
    ]
    try:
        completed = subprocess.run(command, text=True, capture_output=True, timeout=20, check=False)
    except Exception as exc:  # noqa: BLE001
        return {
            "nvidia_smi_available": False,
            "gpu_name": None,
            "driver_version": None,
            "error": f"{type(exc).__name__}: {exc}",
        }

    stdout = completed.stdout.strip()
    first_line = stdout.splitlines()[0] if stdout else ""
    gpu_name = None
    driver_version = None
    if completed.returncode == 0 and first_line:
        parts = [part.strip() for part in first_line.split(",", 1)]
        gpu_name = parts[0] if parts else None
        driver_version = parts[1] if len(parts) > 1 else None
    return {
        "nvidia_smi_available": completed.returncode == 0,
        "gpu_name": gpu_name,
        "driver_version": driver_version,
        "returncode": completed.returncode,
        "stdout": stdout,
        "stderr": completed.stderr.strip(),
    }


def inspect_torch() -> dict[str, Any]:
    ok, version, error = import_module_version("torch")
    payload: dict[str, Any] = {
        "torch_import_ok": ok,
        "torch_version": version,
        "torch_error": error,
        "torch_cuda_version": None,
        "torch_cuda_available": False,
        "torch_gpu_name": None,
    }
    if not ok:
        return payload
    try:
        import torch

        payload["torch_cuda_version"] = torch.version.cuda
        payload["torch_cuda_available"] = bool(torch.cuda.is_available())
        payload["torch_gpu_name"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    except Exception as exc:  # noqa: BLE001
        payload["torch_error"] = f"{type(exc).__name__}: {exc}"
    return payload


def inspect_adapter(adapter_path: Path) -> dict[str, Any]:
    config_path = adapter_path / "adapter_config.json"
    safetensors_path = adapter_path / "adapter_model.safetensors"
    bin_path = adapter_path / "adapter_model.bin"
    adapter_model_exists = safetensors_path.exists() or bin_path.exists()
    payload: dict[str, Any] = {
        "adapter_path": str(adapter_path),
        "adapter_path_exists": adapter_path.exists(),
        "adapter_config_exists": config_path.exists(),
        "adapter_model_exists": adapter_model_exists,
        "adapter_model_candidates": [
            str(path)
            for path in (safetensors_path, bin_path)
            if path.exists()
        ],
        "base_model_name_or_path": None,
        "base_model_path_exists": None,
        "lora_r": None,
        "lora_alpha": None,
        "target_modules": [],
        "adapter_config_error": None,
    }
    if not config_path.exists():
        return payload
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        payload["adapter_config_error"] = f"{type(exc).__name__}: {exc}"
        return payload

    base_model = config.get("base_model_name_or_path")
    payload["base_model_name_or_path"] = base_model
    if isinstance(base_model, str) and base_model.startswith("/"):
        payload["base_model_path_exists"] = Path(base_model).exists()
    payload["lora_r"] = config.get("r")
    payload["lora_alpha"] = config.get("lora_alpha")
    payload["target_modules"] = config.get("target_modules") or []
    return payload


def build_report(adapter_path: Path) -> dict[str, Any]:
    nvidia = run_nvidia_smi()
    torch_info = inspect_torch()
    vllm_ok, vllm_version, vllm_error = import_module_version("vllm")
    transformers_ok, transformers_version, transformers_error = import_module_version("transformers")
    openai_ok, openai_version, openai_error = import_module_version("openai")
    adapter = inspect_adapter(adapter_path)

    failures: list[str] = []
    recommendations: list[str] = []

    if not nvidia["nvidia_smi_available"]:
        failures.append("nvidia-smi is unavailable in this environment")
        recommendations.append("Repair WSL GPU visibility before installing or starting vLLM.")
    if not torch_info["torch_import_ok"]:
        failures.append("torch import failed")
        recommendations.append("Install a vLLM-compatible torch wheel inside the isolated serving env.")
    elif not torch_info["torch_cuda_available"]:
        failures.append("torch CUDA is unavailable")
        recommendations.append("Check torch/CUDA wheel compatibility and WSL NVIDIA driver exposure.")
    if not vllm_ok:
        failures.append("vLLM import failed")
        recommendations.append("Install vLLM only in the isolated serving env, not the training env.")
    if not adapter["adapter_path_exists"]:
        failures.append("adapter path does not exist")
    if not adapter["adapter_config_exists"]:
        failures.append("adapter_config.json does not exist")
    if not adapter["adapter_model_exists"]:
        failures.append("adapter weights do not exist")
    if adapter.get("base_model_path_exists") is False:
        failures.append("adapter base model path does not exist")
    if not transformers_ok:
        recommendations.append("Install transformers in the isolated serving env.")
    if not openai_ok:
        recommendations.append("Install openai in the isolated serving env for API smoke tests.")

    status = "ok"
    if failures:
        status = "failed"
    elif recommendations:
        status = "caution"

    return {
        "generated_at": utc_now(),
        "python_executable": sys.executable,
        "python_version": sys.version,
        "platform": platform.platform(),
        "distro": get_distro(),
        **nvidia,
        **torch_info,
        "vllm_import_ok": vllm_ok,
        "vllm_version": vllm_version,
        "vllm_error": vllm_error,
        "transformers_import_ok": transformers_ok,
        "transformers_version": transformers_version,
        "transformers_error": transformers_error,
        "openai_import_ok": openai_ok,
        "openai_version": openai_version,
        "openai_error": openai_error,
        **adapter,
        "status": status,
        "failures": failures,
        "recommendations": recommendations,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect the isolated Device2 vLLM serving runtime.")
    parser.add_argument("--adapter-path", type=Path, default=DEFAULT_ADAPTER_PATH)
    parser.add_argument("--json", action="store_true", help="Emit JSON. JSON is also the default output format.")
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_report(args.adapter_path)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    sys.stdout.write(text)


if __name__ == "__main__":
    main()
