from __future__ import annotations

import os
from typing import Dict

from app.extractors.base import TurnExtractor
from app.extractors.fake_extractor import FakeTurnExtractor
from app.extractors.fallback_extractor import FallbackTurnExtractor
from app.extractors.openai_compatible_extractor import OpenAICompatibleTurnExtractor


def build_extractor_registry() -> Dict[str, TurnExtractor]:
    fake = FakeTurnExtractor()
    fallback = FallbackTurnExtractor()
    real = OpenAICompatibleTurnExtractor()
    return {
        "fake": fake,
        "fallback": fallback,
        "rule_fallback": fallback,
        "real_llm": real,
        "auto": real,
    }


def get_extractor(mode: str | None = None) -> TurnExtractor:
    selected = mode or os.getenv("TCM_EXTRACTOR_MODE", "auto")
    registry = build_extractor_registry()
    return registry.get(selected, registry["fallback"])
