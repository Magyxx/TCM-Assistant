from __future__ import annotations

import argparse
import fnmatch
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

STAGE = "D2-MP1_LOCAL_LORA_MAIN_PORT"
MAIN_BASE_HEAD = "56f69eb2693fe3eecd4f1baf43603798d3b2aff9"
DEVICE2_BRANCH = "origin/feature/device2-local-lora-extractor"
DEVICE2_HEAD = "8150e3cafec233f0afebcf4f67626b0a7224db21"
PORT_BRANCH = "port/device2-local-lora-current-interface"
DEFAULT_OUTPUT = ROOT_DIR / "artifacts" / "device2_local_lora_port_validation.json"

PORT_CODE_PATHS = [
    ROOT_DIR / "app" / "extractors" / "local_lora_extractor.py",
    ROOT_DIR / "app" / "extractors" / "router.py",
    ROOT_DIR / "app" / "extractors" / "__init__.py",
    ROOT_DIR / "tests" / "test_local_lora_extractor.py",
    ROOT_DIR / "tests" / "test_local_lora_schema_guard.py",
]

FORBIDDEN_TRACKED_PATTERNS = [
    "*.safetensors",
    "*.bin",
    "*.pt",
    "*.pth",
    "*.gguf",
    "adapter_model*",
    "checkpoint*",
    "pytorch_model*",
    "model-*.safetensors",
]


class MockChatCompletionClient:
    def __init__(self, content: str) -> None:
        self.content = content

    def create_chat_completion(self, messages):
        return {"choices": [{"message": {"content": self.content}}]}


def _run_git(args: list[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def _tracked_files() -> list[str]:
    output = _run_git(["ls-files"])
    return [line.strip().replace("\\", "/") for line in output.splitlines() if line.strip()]


def _port_text() -> str:
    chunks: list[str] = []
    for path in PORT_CODE_PATHS:
        if path.exists():
            chunks.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks)


def _valid_turn_json() -> str:
    return json.dumps(
        {
            "chief_complaint": "胃胀",
            "duration": "一周",
            "symptoms": [],
            "symptoms_status": "none",
            "risk_flags": [],
            "risk_flags_status": "none",
            "summary": "mock local LoRA candidate",
        },
        ensure_ascii=False,
    )


def _secret_scan_status() -> str:
    try:
        from scripts.secret_scan import scan_paths

        result = scan_paths([ROOT_DIR], include_runtime=False)
    except Exception:
        return "failed"
    return "passed" if result.get("status") == "ok" and result.get("finding_count") == 0 else "failed"


def _no_weights_tracked(files: list[str]) -> bool:
    for path in files:
        name = Path(path).name
        for pattern in FORBIDDEN_TRACKED_PATTERNS:
            if fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(path, pattern):
                return False
    return True


def _no_env_tracked(files: list[str]) -> bool:
    for path in files:
        name = Path(path).name
        if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
            return False
    return True


def verify() -> dict[str, Any]:
    from app.extractors.local_lora_extractor import LocalLoRAExtractorBackend
    from app.extractors.result import ExtractorResult
    from app.extractors.router import get_extractor_backend
    from app.graph.runner import run_p9m1_graph
    from app.schemas.report_schemas import RunState
    from app.extractors.openai_compatible_client import OpenAICompatibleChatClient

    tracked_files = _tracked_files()
    port_text = _port_text()
    lora_backend = get_extractor_backend("local_lora")
    vllm_backend = get_extractor_backend("local_vllm")

    mock_result = LocalLoRAExtractorBackend(client=MockChatCompletionClient(_valid_turn_json())).extract(
        "胃胀一周，没有其他症状",
        state=RunState(),
    )
    malformed_result = LocalLoRAExtractorBackend(client=MockChatCompletionClient("not json")).extract(
        "胃胀一周",
        state=RunState(),
    )
    schema_result = LocalLoRAExtractorBackend(
        client=MockChatCompletionClient(json.dumps({"risk_flags_status": "clear"}, ensure_ascii=False))
    ).extract("胃胀一周", state=RunState())

    original = OpenAICompatibleChatClient.create_chat_completion

    def high_risk_mock(self, messages):
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "chief_complaint": "胸痛",
                                "duration": "半天",
                                "symptoms": [],
                                "symptoms_status": "unknown",
                                "risk_flags": [],
                                "risk_flags_status": "none",
                                "summary": "model attempted to clear risk",
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }

    OpenAICompatibleChatClient.create_chat_completion = high_risk_mock
    try:
        high_risk_graph = run_p9m1_graph("胸痛伴呼吸困难半天", extractor_backend="local_lora", use_langgraph=False)
    finally:
        OpenAICompatibleChatClient.create_chat_completion = original

    checks = {
        "uses_current_extractor_result": isinstance(mock_result, ExtractorResult),
        "no_backend_result": "BackendResult" not in port_text,
        "no_extract_turn_legacy_required": "extract_turn(state, user_input" not in port_text
        and "def extract_turn(state, user_input" not in port_text,
        "router_registered": lora_backend.mode == "local_lora" and vllm_backend.mode == "local_vllm",
        "mock_vllm_success": mock_result.schema_pass is True
        and mock_result.metadata.get("json_valid") is True
        and mock_result.metadata.get("schema_pass") is True,
        "schema_guard": schema_result.metadata.get("error_type") == "schema_mismatch"
        and schema_result.metadata.get("schema_pass") is False,
        "malformed_json_guard": malformed_result.metadata.get("error_type") == "json_invalid"
        and malformed_result.metadata.get("json_valid") is False,
        "risk_rules_not_bypassed": high_risk_graph.get("risk_status") == "present"
        and "P0_RISK_CHEST_PAIN" in high_risk_graph.get("risk_rule_ids", [])
        and "P0_RISK_DYSPNEA" in high_risk_graph.get("risk_rule_ids", []),
        "live_vllm_default_skipped": os.getenv("RUN_LOCAL_VLLM_SMOKE", "0").strip().lower()
        not in {"1", "true", "yes"},
        "no_weights_tracked": _no_weights_tracked(tracked_files),
        "no_env_tracked": _no_env_tracked(tracked_files),
        "secret_scan": _secret_scan_status(),
    }
    boolean_checks = [value for key, value in checks.items() if key != "secret_scan"]
    status = "ok" if all(boolean_checks) and checks["secret_scan"] == "passed" else "failed"
    return {
        "stage": STAGE,
        "status": status,
        "main_head": MAIN_BASE_HEAD,
        "source_device2_branch": DEVICE2_BRANCH,
        "source_device2_head": DEVICE2_HEAD,
        "current_branch": _run_git(["branch", "--show-current"]),
        "current_base_with_main": _run_git(["merge-base", "HEAD", "main"]),
        "checks": checks,
        "skipped": {
            "live_vllm": "RUN_LOCAL_VLLM_SMOKE is not enabled"
            if checks["live_vllm_default_skipped"]
            else "",
        },
        "metadata_samples": {
            "mock": mock_result.metadata,
            "malformed_json": malformed_result.metadata,
            "schema_guard": schema_result.metadata,
        },
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify D2-MP1 local LoRA port to the current extractor interface.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Artifact output path.")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    result = verify()
    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT_DIR / output
    _write_json(output, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(result["status"])
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
