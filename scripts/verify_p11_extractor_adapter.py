from __future__ import annotations

import argparse
import fnmatch
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

STAGE = "P11-M2_EXTRACTOR_ADAPTER_CONTRACT"
DEFAULT_OUTPUT = ROOT_DIR / "artifacts" / "p11" / "extractor_adapter_contract.json"

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

REQUIRED_MODES = [
    "fake",
    "fallback",
    "rule_fallback",
    "real_llm",
    "openai_compatible",
    "cloud_llm",
    "local_vllm",
    "local_lora",
]
OPTIONAL_MODES = ["real_llm", "openai_compatible", "cloud_llm", "local_vllm", "local_lora"]

VALID_TURN_OUTPUT_JSON = json.dumps(
    {
        "chief_complaint": "stomach discomfort",
        "duration": "two days",
        "symptoms": [],
        "symptoms_status": "none",
        "risk_flags": [],
        "risk_flags_status": "none",
        "summary": "mock extractor candidate",
    },
    ensure_ascii=False,
)


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


def _runtime_probe(mode: str) -> dict[str, Any]:
    from app.extractors.adapter import validate_extractor_result_contract
    from app.extractors.router import get_extractor_backend
    from app.schemas.report_schemas import RunState

    backend = get_extractor_backend(mode)
    result = backend.extract("stomach discomfort for two days", state=RunState())
    summary = result.contract_summary()
    return {
        "requested_mode": mode,
        "backend_mode": backend.mode,
        "contract": summary,
        "validation_failures": validate_extractor_result_contract(result),
        "turn_output_schema_guard": summary["validated_output_schema_guard"],
    }


def _local_mock_probe(mode: str) -> dict[str, Any]:
    from app.extractors.adapter import validate_extractor_result_contract
    from app.extractors.local_lora_extractor import LocalLoRAExtractorBackend, LocalVLLMExtractorBackend
    from app.schemas.report_schemas import RunState

    backend = (
        LocalVLLMExtractorBackend(client=MockClient(VALID_TURN_OUTPUT_JSON))
        if mode == "local_vllm"
        else LocalLoRAExtractorBackend(client=MockClient(VALID_TURN_OUTPUT_JSON))
    )
    result = backend.extract("stomach discomfort for two days", state=RunState())
    summary = result.contract_summary()
    return {
        "requested_mode": mode,
        "backend_mode": backend.mode,
        "contract": summary,
        "validation_failures": validate_extractor_result_contract(result),
        "turn_output_schema_guard": summary["validated_output_schema_guard"],
    }


def _malformed_json_guard() -> dict[str, Any]:
    from app.extractors.local_lora_extractor import LocalLoRAExtractorBackend
    from app.schemas.report_schemas import RunState

    state = RunState(chief_complaint="existing complaint", risk_flags_status="present", risk_flags=["existing risk"])
    before = state.model_dump()
    result = LocalLoRAExtractorBackend(client=MockClient("not json")).extract(
        "stomach discomfort for two days",
        state=state,
    )
    summary = result.contract_summary()
    passed = (
        summary["fallback_used"] is True
        and summary["error_type"] == "json_invalid"
        and summary["schema_guard"] == "failed"
        and summary["raw_llm_json_valid"] is False
        and summary["candidate_schema_pass"] is False
        and state.model_dump() == before
    )
    return {
        "passed": passed,
        "state_unchanged": state.model_dump() == before,
        "contract": summary,
        "metadata": result.metadata,
    }


def _repair_and_retry_record() -> dict[str, Any]:
    from app.extractors.local_lora_extractor import LocalLoRAExtractorBackend
    from app.schemas.report_schemas import RunState

    wrapped = f"Here is the JSON:\n```json\n{VALID_TURN_OUTPUT_JSON}\n```"
    result = LocalLoRAExtractorBackend(client=MockClient(wrapped)).extract(
        "stomach discomfort for two days",
        state=RunState(),
    )
    summary = result.contract_summary()
    return {
        "passed": result.schema_pass is True
        and summary["repair_used"] is True
        and summary["retry_count"] == 0,
        "contract": summary,
    }


def verify() -> dict[str, Any]:
    from app.extractors.router import build_extractor_backend_registry, get_backend_contract_matrix

    tracked = _tracked_files()
    matrix = get_backend_contract_matrix()
    registry = build_extractor_backend_registry()
    env = {
        "ENABLE_REAL_LLM": "false",
        "TCM_ALLOW_REAL_LLM": "false",
        "RUN_LOCAL_VLLM_SMOKE": "0",
        "OPENAI_API_KEY": "",
        "OPENAI_BASE_URL": "",
        "OPENAI_MODEL": "",
    }
    with patch.dict(os.environ, env, clear=False):
        runtime_probes = {
            mode: (_local_mock_probe(mode) if mode in {"local_lora", "local_vllm"} else _runtime_probe(mode))
            for mode in REQUIRED_MODES
        }

    malformed = _malformed_json_guard()
    repair = _repair_and_retry_record()
    optional_skip_reasons = {
        mode: matrix[mode]["skip_reason_when_unavailable"]
        for mode in OPTIONAL_MODES
    }
    checks = {
        "backend_protocol_present": all(
            mode in registry and hasattr(registry[mode], "extract") and hasattr(registry[mode], "extract_turn")
            for mode in REQUIRED_MODES
        ),
        "backend_matrix_coverage": all(mode in matrix for mode in REQUIRED_MODES),
        "schema_guard_required": all(bool(matrix[mode]["schema_guard_required"]) for mode in REQUIRED_MODES),
        "risk_authority_is_rules_layer": all(matrix[mode]["risk_authority"] == "risk_rules_layer" for mode in REQUIRED_MODES),
        "result_contract_fields": all(not probe["validation_failures"] for probe in runtime_probes.values()),
        "turn_output_schema_guard_recorded": all(
            probe["turn_output_schema_guard"] in {"passed", "failed", "skipped"} for probe in runtime_probes.values()
        ),
        "optional_backends_have_skip_reasons": all(bool(reason) for reason in optional_skip_reasons.values()),
        "malformed_json_logged": bool(malformed["passed"]),
        "fallback_used_explicit": all(
            "fallback_used" in probe["contract"] and isinstance(probe["contract"]["fallback_used"], bool)
            for probe in runtime_probes.values()
        ),
        "repair_and_retry_recorded": bool(repair["passed"]),
        "local_backends_not_default": not matrix["local_lora"]["enabled_by_default"]
        and not matrix["local_vllm"]["enabled_by_default"],
        "local_state_unchanged_on_malformed_json": bool(malformed["state_unchanged"]),
    }
    sensitive_files = {
        "tracked_model_weights": _tracked_model_weights(tracked),
        "tracked_exact_env": _tracked_exact_env(tracked),
    }
    status = "ok" if all(checks.values()) and not sensitive_files["tracked_model_weights"] and not sensitive_files["tracked_exact_env"] else "failed"
    git_status = _git(["status", "--short"])
    return {
        "stage": STAGE,
        "status": status,
        "branch": _git(["branch", "--show-current"]),
        "commit": _git(["rev-parse", "HEAD"]),
        "origin_main": _git(["rev-parse", "origin/main"]),
        "checks": checks,
        "backend_matrix": {mode: matrix[mode] for mode in REQUIRED_MODES},
        "backend_probes": runtime_probes,
        "optional_backend_skip_reasons": optional_skip_reasons,
        "malformed_json_guard": malformed,
        "repair_and_retry_record": repair,
        "sensitive_files": sensitive_files,
        "live_vllm_smoke": {
            "status": "skipped",
            "skip_reason": "RUN_LOCAL_VLLM_SMOKE is not enabled",
        },
        "git_status_short": git_status.splitlines(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify P11-M2 extractor adapter contract.")
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
