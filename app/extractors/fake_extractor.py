from __future__ import annotations

from time import perf_counter

from app.chains.turn_extractor import extract_turn
from app.extractors.base import BaseExtractor
from app.extractors.result import ExtractorResult
from app.extractors.simple_rules import build_rule_turn_output
from app.schemas.report_schemas import RunState, TurnOutput


class FakeTurnExtractor(BaseExtractor):
    mode = "fake"

    def extract(self, text: str, *, state: RunState | dict | None = None, memory: dict | None = None) -> ExtractorResult:
        started = perf_counter()
        run_state = self._coerce_state(state)
        legacy = extract_turn(run_state, text, extractor_mode="fake")
        return self._legacy_to_result(legacy, started_at=started)


class FakeExtractorBackend:
    mode = "fake"

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
        started = perf_counter()
        run_state = state if isinstance(state, RunState) else RunState.model_validate(state or {})
        output = build_rule_turn_output(user_input, state=run_state, mode=self.mode)
        output.metadata.update(
            {
                "backend": self.mode,
                "schema_guard": "passed",
                "json_valid": True,
                "schema_valid": True,
                "final_schema_pass": True,
                "fallback_used": False,
                "raw_llm_json_valid": True,
            }
        )
        return ExtractorResult.from_turn_output(
            mode=self.mode,
            raw_output=output.model_dump(),
            turn_output=output,
            fallback_used=False,
            latency_ms=round((perf_counter() - started) * 1000, 3),
            metadata=output.metadata,
        )

    def extract_turn(self, user_input: str, state: RunState | None = None) -> TurnOutput:
        result = self.extract(user_input, state=state)
        return result.turn_output or TurnOutput(summary="fake extractor failed", metadata=result.metadata)
