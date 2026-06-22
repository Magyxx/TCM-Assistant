from __future__ import annotations

import os

from app.extractors.base import ExtractorBackend
from app.extractors.fake_extractor import FakeExtractorBackend
from app.extractors.real_llm_extractor import RealLLMExtractorBackend
from app.extractors.rule_fallback_extractor import RuleFallbackExtractorBackend


class ReservedDevice2ExtractorBackend:
    def __init__(self, mode: str) -> None:
        self.mode = mode

    def extract_turn(self, user_input: str, state=None):
        raise NotImplementedError(f"{self.mode} reserved for device2 integration")


def get_extractor_backend(mode: str | None = None) -> ExtractorBackend:
    selected = (mode or os.getenv("EXTRACTOR_BACKEND") or os.getenv("TCM_EXTRACTOR_MODE") or "fake").strip()
    registry: dict[str, ExtractorBackend] = {
        "fake": FakeExtractorBackend(),
        "rule_fallback": RuleFallbackExtractorBackend(),
        "fallback": RuleFallbackExtractorBackend(),
        "real_llm": RealLLMExtractorBackend(),
        "local_base": ReservedDevice2ExtractorBackend("local_base"),
        "local_lora": ReservedDevice2ExtractorBackend("local_lora"),
    }
    if selected not in registry:
        valid = ", ".join(sorted(registry))
        raise ValueError(f"unknown extractor backend: {selected}; valid backends: {valid}")
    return registry[selected]


__all__ = ["ReservedDevice2ExtractorBackend", "get_extractor_backend"]
