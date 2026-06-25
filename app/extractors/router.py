from __future__ import annotations

from copy import deepcopy
import os

from app.extractors.base import ExtractorBackend
from app.extractors.fake_extractor import FakeExtractorBackend
from app.extractors.local_lora_extractor import LocalLoRAExtractorBackend, LocalVLLMExtractorBackend
from app.extractors.real_llm_extractor import RealLLMExtractorBackend
from app.extractors.result import ExtractorResult
from app.extractors.rule_fallback_extractor import RuleFallbackExtractorBackend
from app.schemas.report_schemas import RunState, TurnOutput


TRUTHY_ENV_VALUES = {"1", "true", "yes", "on"}

P11_BACKEND_CONTRACT_MATRIX: dict[str, dict[str, object]] = {
    "fake": {
        "backend_name": "fake",
        "enabled_by_default": True,
        "required_env": [],
        "optional_dependency": None,
        "live_service_required": False,
        "output_contract": "TurnOutput candidate wrapped in ExtractorResult",
        "schema_guard_required": True,
        "malformed_json_behavior": "not applicable; deterministic local rules",
        "risk_authority": "risk_rules_layer",
        "fallback_behavior": "not a fallback backend",
        "skip_reason_when_unavailable": None,
        "tests_covered": ["test_p11_backend_matrix", "test_p11_post_lora_regression"],
    },
    "fallback": {
        "backend_name": "fallback",
        "enabled_by_default": False,
        "required_env": [],
        "optional_dependency": None,
        "live_service_required": False,
        "output_contract": "TurnOutput candidate wrapped in ExtractorResult",
        "schema_guard_required": True,
        "malformed_json_behavior": "not applicable; deterministic local rules",
        "risk_authority": "risk_rules_layer",
        "fallback_behavior": "rule fallback is the terminal safe fallback",
        "skip_reason_when_unavailable": None,
        "tests_covered": ["test_p11_backend_matrix", "test_p11_post_lora_regression"],
    },
    "rule_fallback": {
        "backend_name": "rule_fallback",
        "enabled_by_default": False,
        "required_env": [],
        "optional_dependency": None,
        "live_service_required": False,
        "output_contract": "TurnOutput candidate wrapped in ExtractorResult",
        "schema_guard_required": True,
        "malformed_json_behavior": "not applicable; deterministic local rules",
        "risk_authority": "risk_rules_layer",
        "fallback_behavior": "rule fallback is the terminal safe fallback",
        "skip_reason_when_unavailable": None,
        "tests_covered": ["test_p11_backend_matrix", "test_p11_post_lora_regression"],
    },
    "real_llm": {
        "backend_name": "real_llm",
        "enabled_by_default": False,
        "required_env": ["ENABLE_REAL_LLM", "OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL"],
        "optional_dependency": "langchain_openai",
        "live_service_required": True,
        "output_contract": "TurnOutput candidate wrapped in ExtractorResult",
        "schema_guard_required": True,
        "malformed_json_behavior": "schema failure or safe rule fallback with metadata",
        "risk_authority": "risk_rules_layer",
        "fallback_behavior": "rule fallback when disabled, missing config, or schema failure",
        "skip_reason_when_unavailable": "ENABLE_REAL_LLM=false",
        "tests_covered": ["test_p11_backend_matrix", "test_p11_runtime_skip_reasons"],
    },
    "openai_compatible": {
        "backend_name": "openai_compatible",
        "enabled_by_default": False,
        "required_env": ["ENABLE_REAL_LLM", "OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL"],
        "optional_dependency": "langchain_openai",
        "live_service_required": True,
        "output_contract": "TurnOutput candidate wrapped in ExtractorResult",
        "schema_guard_required": True,
        "malformed_json_behavior": "schema failure or safe rule fallback with metadata",
        "risk_authority": "risk_rules_layer",
        "fallback_behavior": "rule fallback when disabled, missing config, or schema failure",
        "skip_reason_when_unavailable": "ENABLE_REAL_LLM=false",
        "tests_covered": ["test_p11_backend_matrix", "test_p11_runtime_skip_reasons"],
    },
    "cloud_llm": {
        "backend_name": "cloud_llm",
        "enabled_by_default": False,
        "required_env": ["ENABLE_REAL_LLM", "OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL"],
        "optional_dependency": "langchain_openai",
        "live_service_required": True,
        "output_contract": "TurnOutput candidate wrapped in ExtractorResult",
        "schema_guard_required": True,
        "malformed_json_behavior": "schema failure or safe rule fallback with metadata",
        "risk_authority": "risk_rules_layer",
        "fallback_behavior": "rule fallback when disabled, missing config, or schema failure",
        "skip_reason_when_unavailable": "ENABLE_REAL_LLM=false",
        "tests_covered": ["test_p11_backend_matrix", "test_p11_runtime_skip_reasons"],
    },
    "local_vllm": {
        "backend_name": "local_vllm",
        "enabled_by_default": False,
        "required_env": ["LOCAL_LLM_BASE_URL", "LOCAL_LLM_MODEL"],
        "optional_dependency": "OpenAI-compatible local vLLM service",
        "live_service_required": True,
        "output_contract": "TurnOutput candidate wrapped in ExtractorResult",
        "schema_guard_required": True,
        "malformed_json_behavior": "reject candidate and return auditable rule fallback",
        "risk_authority": "risk_rules_layer",
        "fallback_behavior": "rule fallback when service unavailable or candidate fails schema",
        "skip_reason_when_unavailable": "RUN_LOCAL_VLLM_SMOKE is not enabled",
        "tests_covered": [
            "test_p11_backend_matrix",
            "test_p11_runtime_skip_reasons",
            "test_p11_extractor_contract",
        ],
    },
    "local_lora": {
        "backend_name": "local_lora",
        "enabled_by_default": False,
        "required_env": ["LOCAL_LLM_BASE_URL", "LOCAL_LLM_MODEL"],
        "optional_dependency": "OpenAI-compatible local vLLM service serving LoRA adapter",
        "live_service_required": True,
        "output_contract": "TurnOutput candidate wrapped in ExtractorResult",
        "schema_guard_required": True,
        "malformed_json_behavior": "reject candidate and return auditable rule fallback",
        "risk_authority": "risk_rules_layer",
        "fallback_behavior": "rule fallback when service unavailable or candidate fails schema",
        "skip_reason_when_unavailable": "RUN_LOCAL_VLLM_SMOKE is not enabled",
        "tests_covered": [
            "test_p11_backend_matrix",
            "test_p11_local_lora_safety_boundary",
            "test_p11_post_lora_regression",
        ],
    },
    "local_base": {
        "backend_name": "local_base",
        "enabled_by_default": False,
        "required_env": [],
        "optional_dependency": "reserved Device2 integration point",
        "live_service_required": False,
        "output_contract": "ExtractorResult.skipped",
        "schema_guard_required": True,
        "malformed_json_behavior": "not applicable; backend is reserved",
        "risk_authority": "risk_rules_layer",
        "fallback_behavior": "clean skip",
        "skip_reason_when_unavailable": "reserved_for_device2_integration",
        "tests_covered": ["test_p11_backend_matrix"],
    },
}


def _env_truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in TRUTHY_ENV_VALUES


def get_backend_skip_reason_when_unavailable(mode: str) -> str | None:
    selected = mode.strip()
    if selected in {"fake", "auto", "fallback", "rule_fallback"}:
        return None
    if selected == "local_base":
        return "reserved_for_device2_integration"
    if selected in {"real_llm", "openai_compatible", "cloud_llm"}:
        enabled = _env_truthy(os.getenv("ENABLE_REAL_LLM") or os.getenv("TCM_ALLOW_REAL_LLM"))
        if not enabled:
            return "ENABLE_REAL_LLM=false"
        missing = [
            name
            for name in ["OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL"]
            if not os.getenv(name)
        ]
        if missing:
            return f"missing_api_config:{','.join(missing)}"
        return None
    if selected in {"local_lora", "local_vllm"}:
        if not _env_truthy(os.getenv("RUN_LOCAL_VLLM_SMOKE")):
            return "RUN_LOCAL_VLLM_SMOKE is not enabled"
        return None
    return "unknown_backend"


def get_backend_contract_matrix() -> dict[str, dict[str, object]]:
    matrix = deepcopy(P11_BACKEND_CONTRACT_MATRIX)
    matrix["auto"] = {
        **matrix["fake"],
        "backend_name": "auto",
        "enabled_by_default": True,
        "fallback_behavior": "routes to fake unless EXTRACTOR_BACKEND or TCM_EXTRACTOR_MODE overrides it",
    }
    for mode, contract in matrix.items():
        contract["skip_reason_when_unavailable"] = get_backend_skip_reason_when_unavailable(mode)
    return matrix


class ReservedDevice2ExtractorBackend:
    def __init__(self, mode: str) -> None:
        self.mode = mode

    def extract(
        self,
        user_input: str,
        *,
        state: RunState | dict | None = None,
        memory: dict | None = None,
        config: dict | None = None,
        session_id: str | None = None,
        turn_id: str | None = None,
    ) -> ExtractorResult:
        return ExtractorResult.skipped(
            mode=self.mode,
            skip_reason="reserved_for_device2_integration",
            metadata={"error_type": "reserved_backend"},
        )

    def extract_turn(self, user_input: str, state=None) -> TurnOutput:
        result = self.extract(user_input, state=state)
        return TurnOutput(
            summary=f"{self.mode} reserved for device2 integration",
            metadata=result.metadata,
        )


def build_extractor_backend_registry() -> dict[str, ExtractorBackend]:
    fake = FakeExtractorBackend()
    fallback = RuleFallbackExtractorBackend()
    real = RealLLMExtractorBackend("real_llm")
    openai_compatible = RealLLMExtractorBackend("openai_compatible")
    return {
        "fake": fake,
        "auto": fake,
        "rule_fallback": fallback,
        "fallback": fallback,
        "real_llm": real,
        "openai_compatible": openai_compatible,
        "cloud_llm": openai_compatible,
        "local_base": ReservedDevice2ExtractorBackend("local_base"),
        "local_lora": LocalLoRAExtractorBackend(),
        "local_vllm": LocalVLLMExtractorBackend(),
    }


def get_extractor_backend(mode: str | None = None) -> ExtractorBackend:
    selected = (mode or os.getenv("EXTRACTOR_BACKEND") or os.getenv("TCM_EXTRACTOR_MODE") or "fake").strip()
    registry = build_extractor_backend_registry()
    if selected not in registry:
        valid = ", ".join(sorted(registry))
        raise ValueError(f"unknown extractor backend: {selected}; valid backends: {valid}")
    return registry[selected]


__all__ = [
    "P11_BACKEND_CONTRACT_MATRIX",
    "ReservedDevice2ExtractorBackend",
    "build_extractor_backend_registry",
    "get_backend_contract_matrix",
    "get_backend_skip_reason_when_unavailable",
    "get_extractor_backend",
]
