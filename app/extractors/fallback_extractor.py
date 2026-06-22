from __future__ import annotations

from app.chains.turn_extractor import ExtractionResult, extract_turn
from app.schemas.report_schemas import RunState


class FallbackTurnExtractor:
    mode = "fallback"

    def extract(self, state: RunState, user_input: str) -> ExtractionResult:
        return extract_turn(state, user_input, extractor_mode="fallback")
