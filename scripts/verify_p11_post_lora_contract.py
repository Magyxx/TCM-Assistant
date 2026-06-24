from __future__ import annotations

import argparse
import fnmatch
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

STAGE = "P11-M1_POST_LORA_RUNTIME_CONTRACT"
BASE_MAIN = "2338dcaca7f1f1b27ab19c9fdb4265ca649b4382"
DEFAULT_OUTPUT = ROOT_DIR / "artifacts" / "p11" / "post_lora_runtime_contract.json"

MODEL_WEIGHT_PATTERNS = [
    "*.safetensors",
    "*.bin",
    "*.pt",
    "*.pth",
    "*.ckpt",
    "*.gguf",
    "adapter_model*",
    "pytorch_model*",
]


class MockClient:
    def __init__(self, content: str) -> None:
        self.content = content

    def create_chat_completion(self, messages):
        return {"choices": [{"message": {"content": self.content}}]}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _git(args: list[str]) -> str:
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
    return [line.strip().replace("\\", "/") for line in _git(["ls-files"]).splitlines() if line.strip()]


def _tracked_model_weights(files: list[str]) -> list[str]:
    matches: list[str] = []
    for path in files:
        name = Path(path).name
        if any(fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(path, pattern) for pattern in MODEL_WEIGHT_PATTERNS):
            matches.append(path)
    return matches


def _tracked_exact_env(files: list[str]) -> list[str]:
    return [path for path in files if Path(path).name == ".env"]


def _text(paths: list[Path]) -> str:
    chunks: list[str] = []
    for path in paths:
        if path.exists():
            chunks.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks)


def _old_extract_turn_signature_absent() -> bool:
    text = _text(
        [
            ROOT_DIR / "app" / "extractors" / "local_lora_extractor.py",
            ROOT_DIR / "app" / "extractors" / "router.py",
            ROOT_DIR / "app" / "extractors" / "__init__.py",
        ]
    )
    return "extract_turn(state, user_input" not in text and "def extract_turn(state, user_input" not in text


def _backend_result_in_tests_absent() -> bool:
    needle = "Backend" + "Result"
    test_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in (ROOT_DIR / "tests").glob("test*.py")
    )
    return needle not in test_text


def _run_graph(user_input: str, *, extractor_backend: str) -> dict[str, Any]:
    from app.graph.runner import run_p9m1_graph

    with tempfile.TemporaryDirectory() as temp_dir:
        return run_p9m1_graph(
            user_input,
            extractor_backend=extractor_backend,
            use_langgraph=False,
            graph_events_path=Path(temp_dir) / "graph_events.jsonl",
        )


def _backend_matrix_summary() -> dict[str, dict[str, Any]]:
    from app.extractors.router import build_extractor_backend_registry, get_backend_contract_matrix
    from app.schemas.report_schemas import RunState

    registry = build_extractor_backend_registry()
    matrix = get_backend_contract_matrix()
    summary: dict[str, dict[str, Any]] = {}
    for mode in ["fake", "fallback", "cloud_llm", "real_llm", "openai_compatible", "local_vllm", "local_lora"]:
        contract = matrix[mode]
        registered = mode in registry
        schema_guard = "passed_or_skipped"
        if mode in {"fake", "fallback"} and registered:
            result = registry[mode].extract("胃胀一周，没有胸痛", state=RunState())
            schema_guard = "passed" if result.schema_pass else "failed"
        summary[mode] = {
            "registered": registered,
            "default_safe": mode == "fake" or not bool(contract["enabled_by_default"]),
            "enabled_by_default": bool(contract["enabled_by_default"]),
            "schema_guard": schema_guard,
            "live_required": bool(contract["live_service_required"]),
            "skip_reason": contract["skip_reason_when_unavailable"],
            "risk_authority": contract["risk_authority"],
            "output_contract": contract["output_contract"],
        }
    return summary


def _malformed_json_guard() -> dict[str, Any]:
    from app.extractors.local_lora_extractor import LocalLoRAExtractorBackend
    from app.schemas.report_schemas import RunState

    result = LocalLoRAExtractorBackend(client=MockClient("not json")).extract("胃胀一周", state=RunState())
    return {
        "passed": bool(
            result.fallback_used
            and result.metadata.get("error_type") == "json_invalid"
            and result.metadata.get("schema_guard") == "failed"
            and result.metadata.get("raw_llm_json_valid") is False
        ),
        "metadata": result.metadata,
    }


def _local_lora_no_risk_authority() -> dict[str, Any]:
    from app.extractors.openai_compatible_client import OpenAICompatibleChatClient

    original = OpenAICompatibleChatClient.create_chat_completion

    def mock_completion(self, messages):
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "chief_complaint": "胃胀",
                                "duration": "半天",
                                "symptoms": [],
                                "symptoms_status": "none",
                                "risk_flags": [],
                                "risk_flags_status": "none",
                                "summary": "candidate attempted to clear risk",
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }

    OpenAICompatibleChatClient.create_chat_completion = mock_completion
    try:
        result = _run_graph("胸痛伴呼吸困难半天", extractor_backend="local_lora")
    finally:
        OpenAICompatibleChatClient.create_chat_completion = original

    rule_ids = result.get("risk_rule_ids") or []
    return {
        "passed": result.get("risk_status") == "present"
        and "P0_RISK_CHEST_PAIN" in rule_ids
        and "P0_RISK_DYSPNEA" in rule_ids,
        "risk_status": result.get("risk_status"),
        "risk_rule_ids": rule_ids,
    }


def _risk_rules_fallback() -> dict[str, Any]:
    result = _run_graph("便血两天", extractor_backend="fake")
    rule_ids = result.get("risk_rule_ids") or []
    return {
        "passed": result.get("risk_status") == "present" and "P0_RISK_GI_BLEEDING" in rule_ids,
        "risk_status": result.get("risk_status"),
        "risk_rule_ids": rule_ids,
    }


def _rag_core_field_overwrite_blocked() -> dict[str, Any]:
    from app.rag.rag_guard import guard_rag_update

    fields = ["chief_complaint", "duration", "risk_status", "risk_rule_ids"]
    blocked = {field: guard_rag_update({field: "retrieved evidence"}).allowed is False for field in fields}
    return {"passed": all(blocked.values()), "blocked": blocked}


def verify() -> dict[str, Any]:
    from app.extractors.router import build_extractor_backend_registry, get_backend_contract_matrix

    tracked_files = _tracked_files()
    model_weights = _tracked_model_weights(tracked_files)
    exact_env = _tracked_exact_env(tracked_files)
    registry = build_extractor_backend_registry()
    matrix = get_backend_contract_matrix()
    backend_matrix = _backend_matrix_summary()
    malformed = _malformed_json_guard()
    risk_fallback = _risk_rules_fallback()
    lora_risk = _local_lora_no_risk_authority()
    rag_guard = _rag_core_field_overwrite_blocked()
    optional_modes = ["real_llm", "openai_compatible", "cloud_llm", "local_vllm", "local_lora"]
    optional_skip_reasons = {
        mode: matrix[mode]["skip_reason_when_unavailable"]
        for mode in optional_modes
    }

    contract_checks = {
        "old_extract_turn_signature_absent": _old_extract_turn_signature_absent(),
        "backend_result_in_tests_absent": _backend_result_in_tests_absent(),
        "schema_guard_required": all(bool(item["schema_guard_required"]) for item in matrix.values()),
        "malformed_json_guard": "passed" if malformed["passed"] else "failed",
        "risk_rules_fallback": "passed" if risk_fallback["passed"] else "failed",
        "local_lora_no_risk_authority": bool(lora_risk["passed"]),
        "rag_core_field_overwrite_blocked": bool(rag_guard["passed"]),
        "optional_backends_have_skip_reasons": all(bool(optional_skip_reasons[mode]) for mode in optional_modes),
    }
    sensitive_files = {
        "tracked_model_weights": bool(model_weights),
        "tracked_model_weight_paths": model_weights,
        "tracked_exact_env": bool(exact_env),
        "tracked_exact_env_paths": exact_env,
    }
    registered_checks = {
        "local_lora_registered": "local_lora" in registry,
        "local_vllm_registered": "local_vllm" in registry,
    }
    boolean_checks = [
        *registered_checks.values(),
        contract_checks["old_extract_turn_signature_absent"],
        contract_checks["backend_result_in_tests_absent"],
        contract_checks["schema_guard_required"],
        contract_checks["optional_backends_have_skip_reasons"],
        contract_checks["local_lora_no_risk_authority"],
        contract_checks["rag_core_field_overwrite_blocked"],
        not sensitive_files["tracked_model_weights"],
        not sensitive_files["tracked_exact_env"],
        malformed["passed"],
        risk_fallback["passed"],
    ]
    git_status = _git(["status", "--short"])
    live_smoke_enabled = str(os.getenv("RUN_LOCAL_VLLM_SMOKE", "")).strip().lower() in {"1", "true", "yes", "on"}
    payload = {
        "stage": STAGE,
        "status": "ok" if all(boolean_checks) else "failed",
        "branch": _git(["branch", "--show-current"]),
        "base_main": BASE_MAIN,
        "origin_main": _git(["rev-parse", "origin/main"]),
        "commit": _git(["rev-parse", "HEAD"]),
        "backend_matrix": backend_matrix,
        "registered_checks": registered_checks,
        "contract_checks": contract_checks,
        "optional_backend_skip_reasons": optional_skip_reasons,
        "samples": {
            "malformed_json_guard": malformed,
            "risk_rules_fallback": risk_fallback,
            "local_lora_no_risk_authority": lora_risk,
            "rag_core_field_overwrite_blocked": rag_guard,
        },
        "sensitive_files": sensitive_files,
        "live_vllm_smoke": {
            "status": "not_run" if live_smoke_enabled else "skipped",
            "skip_reason": "" if live_smoke_enabled else "RUN_LOCAL_VLLM_SMOKE is not enabled",
        },
        "worktree_clean": git_status == "",
        "git_status_short": git_status.splitlines(),
    }
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify P11-M1 post-LoRA runtime contract baseline.")
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
