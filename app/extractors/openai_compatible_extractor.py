from __future__ import annotations

from time import perf_counter

from app.chains.turn_extractor import extract_turn, get_missing_api_config
from app.extractors.base import BaseExtractor
from app.extractors.result import ExtractorResult
from app.schemas.report_schemas import RunState


class OpenAICompatibleTurnExtractor(BaseExtractor):
    mode = "real_llm"

    def missing_config(self) -> list[str]:
        return get_missing_api_config()

    def extract(self, text: str, *, state: RunState | dict | None = None, memory: dict | None = None) -> ExtractorResult:
        started = perf_counter()
        run_state = self._coerce_state(state)
        missing = self.missing_config()
        legacy = extract_turn(run_state, text, extractor_mode="real_llm")
        skip_reason = f"missing_api_config:{','.join(missing)}" if missing else None
        return self._legacy_to_result(
            legacy,
            started_at=started,
            skip_reason=skip_reason,
            metadata={"missing_config": missing},
        )
