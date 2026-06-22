from __future__ import annotations

from time import perf_counter

from app.chains.turn_extractor import extract_turn
from app.extractors.base import BaseExtractor
from app.extractors.result import ExtractorResult
from app.schemas.report_schemas import RunState


class FakeTurnExtractor(BaseExtractor):
    mode = "fake"

    def extract(self, text: str, *, state: RunState | dict | None = None, memory: dict | None = None) -> ExtractorResult:
        started = perf_counter()
        run_state = self._coerce_state(state)
        legacy = extract_turn(run_state, text, extractor_mode="fake")
        return self._legacy_to_result(legacy, started_at=started)
