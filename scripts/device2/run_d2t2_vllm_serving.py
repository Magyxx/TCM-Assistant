from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_PATH = Path("/mnt/e/models/Qwen2.5-1.5B-Instruct")
DEFAULT_REPORT_PATH = ROOT / "reports" / "device2" / "DEVICE2_VLLM_SERVING_REPORT.md"
DEFAULT_DEFERRED_PATH = ROOT / "reports" / "device2" / "vllm_deferred_report.md"
DEFAULT_METRICS_PATH = ROOT / "artifacts" / "device2" / "d2t2_vllm_serving.json"
DEFAULT_SERVING_ENV = Path.home() / "venvs" / "tcm-device2-serving-py312-vllm-d2t2"
DEFAULT_UV = Path.home() / "venvs" / "tcm-device2-tools" / "bin" / "uv"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def run_command(command: list[str], timeout: int = 1200) -> dict[str, Any]:
    started = time.time()
    try:
        completed = subprocess.run(
            command,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return {
            "command": command,
            "returncode": completed.returncode,
            "stdout_tail": completed.stdout[-4000:],
            "stderr_tail": completed.stderr[-4000:],
            "elapsed_seconds": round(time.time() - started, 3),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "returncode": 124,
            "stdout_tail": (exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-4000:] if isinstance(exc.stderr, str) else "",
            "elapsed_seconds": round(time.time() - started, 3),
            "timeout": True,
        }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def python_bin(venv: Path) -> Path:
    return venv / "bin" / "python"


def ensure_serving_env(venv: Path, uv: Path, create_env: bool) -> list[dict[str, Any]]:
    commands: list[dict[str, Any]] = []
    if python_bin(venv).exists():
        return commands
    if not create_env:
        return [
            {
                "command": [],
                "returncode": 1,
                "stderr_tail": f"serving env does not exist: {venv}",
                "stdout_tail": "",
                "elapsed_seconds": 0,
            }
        ]
    if not uv.exists():
        return [
            {
                "command": [],
                "returncode": 1,
                "stderr_tail": f"uv not found: {uv}",
                "stdout_tail": "",
                "elapsed_seconds": 0,
            }
        ]
    commands.append(run_command([str(uv), "venv", "--seed", "--python", "3.12", str(venv)], timeout=1200))
    return commands


def install_serving_packages(
    venv: Path,
    vllm_spec: str,
    install_vllm: bool,
    install_timeout: int,
    transformers_spec: str | None,
) -> list[dict[str, Any]]:
    commands: list[dict[str, Any]] = []
    py = str(python_bin(venv))
    if not Path(py).exists():
        return commands
    commands.append(run_command([py, "-m", "ensurepip", "--upgrade"], timeout=1200))
    commands.append(run_command([py, "-m", "pip", "install", "--upgrade", "pip"], timeout=1200))
    commands.append(run_command([py, "-m", "pip", "install", "openai"], timeout=1200))
    if install_vllm:
        commands.append(run_command([py, "-m", "pip", "install", vllm_spec], timeout=install_timeout))
    if transformers_spec:
        commands.append(run_command([py, "-m", "pip", "install", transformers_spec], timeout=1200))
    return commands


def inspect_serving_env(venv: Path) -> dict[str, Any]:
    py = python_bin(venv)
    if not py.exists():
        return {"ok": False, "error": f"python not found: {py}"}
    code = r"""
import importlib
import json
payload = {"imports": {}}
for name in ["torch", "vllm", "openai"]:
    try:
        mod = importlib.import_module(name)
        payload["imports"][name] = {"ok": True, "version": getattr(mod, "__version__", "unknown")}
    except Exception as exc:
        payload["imports"][name] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
try:
    import torch
    payload["torch"] = {
        "version": torch.__version__,
        "cuda_version": torch.version.cuda,
        "cuda_available": torch.cuda.is_available(),
        "device_count": torch.cuda.device_count(),
        "device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
    }
except Exception as exc:
    payload["torch"] = {"error": f"{type(exc).__name__}: {exc}"}
print(json.dumps(payload, ensure_ascii=False))
"""
    result = run_command([str(py), "-c", code], timeout=300)
    payload: dict[str, Any] = {"command_result": result, "ok": False}
    if result["returncode"] == 0:
        try:
            payload.update(json.loads(result["stdout_tail"].strip().splitlines()[-1]))
        except Exception as exc:  # noqa: BLE001
            payload["parse_error"] = f"{type(exc).__name__}: {exc}"
    imports = payload.get("imports", {})
    payload["ok"] = bool(imports.get("vllm", {}).get("ok")) and bool(imports.get("torch", {}).get("ok"))
    return payload


def http_json(url: str, payload: dict[str, Any] | None = None, timeout: int = 10) -> dict[str, Any]:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        body = response.read().decode("utf-8", errors="replace")
        return {"status": response.status, "body": json.loads(body)}


def start_vllm_server(args: argparse.Namespace, adapter_path: Path | None, log_path: Path) -> dict[str, Any]:
    py = python_bin(args.serving_env)
    command = [
        str(py),
        "-m",
        "vllm.entrypoints.openai.api_server",
        "--model",
        str(args.model_path),
        "--host",
        args.host,
        "--port",
        str(args.port),
        "--served-model-name",
        args.base_model_name,
        "--trust-remote-code",
    ]
    if adapter_path is not None:
        command.extend(["--enable-lora", "--lora-modules", f"{args.lora_model_name}={adapter_path}"])

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log_handle:
        process = subprocess.Popen(command, stdout=log_handle, stderr=subprocess.STDOUT, text=True)

    base_url = f"http://{args.host}:{args.port}/v1"
    checks: dict[str, Any] = {"command": command, "log_path": str(log_path), "started_pid": process.pid}
    try:
        deadline = time.time() + args.server_timeout
        models_result: dict[str, Any] | None = None
        last_error = None
        while time.time() < deadline:
            if process.poll() is not None:
                last_error = f"server exited early with code {process.returncode}"
                break
            try:
                models_result = http_json(f"{base_url}/models", timeout=5)
                break
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                time.sleep(5)
        checks["models"] = models_result
        checks["models_ok"] = models_result is not None and models_result.get("status") == 200
        checks["last_poll_error"] = last_error

        if checks["models_ok"]:
            base_payload = {
                "model": args.base_model_name,
                "messages": [{"role": "user", "content": "Return JSON: {\"ok\": true}"}],
                "max_tokens": 64,
                "temperature": 0,
            }
            try:
                checks["base_chat"] = http_json(f"{base_url}/chat/completions", payload=base_payload, timeout=60)
                checks["base_chat_ok"] = checks["base_chat"].get("status") == 200
            except Exception as exc:  # noqa: BLE001
                checks["base_chat"] = {"error": f"{type(exc).__name__}: {exc}"}
                checks["base_chat_ok"] = False

            if adapter_path is not None:
                lora_payload = dict(base_payload)
                lora_payload["model"] = args.lora_model_name
                try:
                    checks["lora_chat"] = http_json(f"{base_url}/chat/completions", payload=lora_payload, timeout=60)
                    checks["lora_chat_ok"] = checks["lora_chat"].get("status") == 200
                except Exception as exc:  # noqa: BLE001
                    checks["lora_chat"] = {"error": f"{type(exc).__name__}: {exc}"}
                    checks["lora_chat_ok"] = False
            else:
                checks["lora_chat_ok"] = False
        else:
            checks["base_chat_ok"] = False
            checks["lora_chat_ok"] = False
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=30)
        checks["exit_code"] = process.returncode
        try:
            checks["log_tail"] = log_path.read_text(encoding="utf-8", errors="replace")[-12000:]
        except OSError as exc:
            checks["log_tail_error"] = f"{type(exc).__name__}: {exc}"
    return checks


def classify_failure(inspect: dict[str, Any], server: dict[str, Any] | None) -> str | None:
    imports = inspect.get("imports", {})
    if not imports.get("vllm", {}).get("ok"):
        return "vLLM import failed"
    torch_info = inspect.get("torch", {})
    if not torch_info.get("cuda_available"):
        return "CUDA / torch / vLLM ABI mismatch"
    if server and not server.get("models_ok"):
        log_path = server.get("log_path")
        if log_path:
            try:
                log_text = Path(log_path).read_text(encoding="utf-8", errors="replace")[-12000:]
                if "all_special_tokens_extended" in log_text or "transformers" in log_text and "AttributeError" in log_text:
                    return "transformers / vLLM dependency conflict"
            except OSError:
                pass
        return "WSL runtime issue"
    if server and server.get("models_ok") and not server.get("lora_chat_ok"):
        return "LoRA adapter format not accepted"
    return None


def write_reports(report_path: Path, deferred_path: Path, payload: dict[str, Any]) -> None:
    status = payload["status"]
    failure = payload.get("failure_reason")
    lines = [
        "# Device2 vLLM Serving Report",
        "",
        "Stage: `D2-T2: vLLM Repair and Serving Integration`",
        "",
        f"Generated at: `{payload['generated_at']}`",
        "",
        f"Status: `{status}`",
        "",
        "## Environment Isolation",
        "",
        f"* training env: `{payload['training_env']}`",
        f"* serving env: `{payload['serving_env']}`",
        "* training env was not modified by vLLM installation or serving probes",
        "",
        "## Version Matrix",
        "",
        "```json",
        json.dumps(payload.get("inspect", {}), ensure_ascii=False, indent=2),
        "```",
        "",
        "## Serving Smoke",
        "",
        f"* `/v1/models`: `{payload.get('models_ok')}`",
        f"* `/v1/chat/completions` base: `{payload.get('base_chat_ok')}`",
        f"* `/v1/chat/completions` LoRA: `{payload.get('lora_chat_ok')}`",
        "",
    ]
    if failure:
        lines.extend(["## Failure Classification", "", f"* `{failure}`", ""])
    server = payload.get("server") or {}
    if server.get("log_tail"):
        lines.extend(
            [
                "## Server Log Tail",
                "",
                "```text",
                server["log_tail"][-6000:],
                "```",
                "",
            ]
        )
    write_text(report_path, "\n".join(lines))

    if status != "ok_full":
        write_text(
            deferred_path,
            "\n".join(
                [
                    "# vLLM Deferred Report",
                    "",
                    "Stage: `D2-T2: vLLM Repair and Serving Integration`",
                    "",
                    "Status: `serving_deferred`",
                    "",
                    f"Failure reason: `{failure or 'unknown'}`",
                    "",
                    "D2-T1 training/evaluation remains valid because vLLM serving is isolated from the training runtime.",
                    "",
                    "Next action: repair the serving stack without changing the training environment.",
                    "",
                ]
            ),
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run D2-T2 vLLM serving repair and smoke checks.")
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--adapter-path", type=Path, default=None)
    parser.add_argument("--serving-env", type=Path, default=DEFAULT_SERVING_ENV)
    parser.add_argument("--uv", type=Path, default=DEFAULT_UV)
    parser.add_argument("--vllm-spec", default="vllm")
    parser.add_argument("--create-env", action="store_true")
    parser.add_argument("--install-vllm", action="store_true")
    parser.add_argument("--start-server", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8011)
    parser.add_argument("--server-timeout", type=int, default=300)
    parser.add_argument("--install-timeout", type=int, default=3600)
    parser.add_argument("--transformers-spec", default=None)
    parser.add_argument("--base-model-name", default="local_base")
    parser.add_argument("--lora-model-name", default="local_lora")
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--deferred-path", type=Path, default=DEFAULT_DEFERRED_PATH)
    parser.add_argument("--metrics-path", type=Path, default=DEFAULT_METRICS_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    commands: list[dict[str, Any]] = []
    commands.extend(ensure_serving_env(args.serving_env, args.uv, args.create_env))
    env_ok = python_bin(args.serving_env).exists()
    if env_ok:
        commands.extend(
            install_serving_packages(
                args.serving_env,
                args.vllm_spec,
                args.install_vllm,
                args.install_timeout,
                args.transformers_spec,
            )
        )

    inspect = inspect_serving_env(args.serving_env)
    server: dict[str, Any] | None = None
    if args.start_server and inspect.get("ok") and inspect.get("torch", {}).get("cuda_available"):
        log_root = Path(os.environ.get("TCM_DEVICE2_ARTIFACTS", "/mnt/e/ai_artifacts/tcm_assistant_device2"))
        log_path = log_root / "d2t2" / "vllm_server.log"
        server = start_vllm_server(args, args.adapter_path, log_path)

    models_ok = bool(server and server.get("models_ok"))
    base_chat_ok = bool(server and server.get("base_chat_ok"))
    lora_chat_ok = bool(server and server.get("lora_chat_ok"))
    status = "ok_full" if models_ok and base_chat_ok and lora_chat_ok else "serving_deferred"
    failure = classify_failure(inspect, server)
    payload = {
        "generated_at": utc_now(),
        "stage": "D2-T2: vLLM Repair and Serving Integration",
        "status": status,
        "failure_reason": failure,
        "training_env": sys.prefix,
        "serving_env": str(args.serving_env),
        "model_path": str(args.model_path),
        "adapter_path": str(args.adapter_path) if args.adapter_path else None,
        "commands": commands,
        "inspect": inspect,
        "server": server,
        "models_ok": models_ok,
        "base_chat_ok": base_chat_ok,
        "lora_chat_ok": lora_chat_ok,
    }
    write_json(args.metrics_path, payload)
    write_reports(args.report_path, args.deferred_path, payload)
    print(json.dumps({"status": status, "failure_reason": failure, "metrics": str(args.metrics_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
