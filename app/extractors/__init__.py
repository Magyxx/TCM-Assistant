from app.extractors.base import BaseExtractor, ExtractorBackend, ExtractorConfig, ExtractorProbeResult, run_extractor_probe
from app.extractors.fake_extractor import FakeExtractorBackend, FakeTurnExtractor
from app.extractors.fallback_extractor import FallbackTurnExtractor
from app.extractors.local_lora_extractor import LocalLoRAExtractorBackend, LocalVLLMExtractorBackend
from app.extractors.openai_compatible_client import LocalLLMConfig, OpenAICompatibleChatClient
from app.extractors.openai_compatible_extractor import OpenAICompatibleTurnExtractor
from app.extractors.registry import get_extractor
from app.extractors.router import (
    build_extractor_backend_registry,
    get_backend_contract_matrix,
    get_backend_skip_reason_when_unavailable,
    get_extractor_backend,
)
from app.extractors.rule_fallback_extractor import RuleFallbackExtractorBackend
from app.extractors.real_llm_extractor import RealLLMExtractorBackend
from app.extractors.result import ExtractorResult
from app.extractors.structured_output_adapter import ExtractorAdapter, extract_turn_with_adapter

__all__ = [
    "BaseExtractor",
    "ExtractorBackend",
    "ExtractorAdapter",
    "ExtractorConfig",
    "ExtractorProbeResult",
    "ExtractorResult",
    "FakeTurnExtractor",
    "FakeExtractorBackend",
    "FallbackTurnExtractor",
    "LocalLLMConfig",
    "LocalLoRAExtractorBackend",
    "LocalVLLMExtractorBackend",
    "OpenAICompatibleChatClient",
    "OpenAICompatibleTurnExtractor",
    "RealLLMExtractorBackend",
    "RuleFallbackExtractorBackend",
    "build_extractor_backend_registry",
    "extract_turn_with_adapter",
    "get_backend_contract_matrix",
    "get_backend_skip_reason_when_unavailable",
    "get_extractor",
    "get_extractor_backend",
    "run_extractor_probe",
]
