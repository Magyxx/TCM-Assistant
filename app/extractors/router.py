from __future__ import annotations

import os

from app.extractors.base import ExtractorBackend
from app.extractors.fake_extractor import FakeExtractorBackend
from app.extractors.local_lora_extractor import LocalLoRAExtractorBackend
from app.extractors.real_llm_extractor import RealLLMExtractorBackend
from app.extractors.result import ExtractorResult
from app.extractors.rule_fallback_extractor import RuleFallbackExtractorBackend
from app.schemas.report_schemas import RunState, TurnOutput


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
    }


def get_extractor_backend(mode: str | None = None) -> ExtractorBackend:
    selected = (mode or os.getenv("EXTRACTOR_BACKEND") or os.getenv("TCM_EXTRACTOR_MODE") or "fake").strip()
    registry = build_extractor_backend_registry()
    if selected not in registry:
        valid = ", ".join(sorted(registry))
        raise ValueError(f"unknown extractor backend: {selected}; valid backends: {valid}")
    return registry[selected]


__all__ = ["ReservedDevice2ExtractorBackend", "build_extractor_backend_registry", "get_extractor_backend"]
