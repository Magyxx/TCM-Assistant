from __future__ import annotations

from app.chains.turn_extractor import ExtractionResult, extract_turn, get_missing_api_config
from app.schemas.report_schemas import RunState


class OpenAICompatibleTurnExtractor:
    mode = "real_llm"

    def missing_config(self) -> list[str]:
        return get_missing_api_config()

    def extract(self, state: RunState, user_input: str) -> ExtractionResult:
        return extract_turn(state, user_input, extractor_mode="real_llm")
