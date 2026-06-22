from __future__ import annotations

from app.extractors.simple_rules import build_rule_turn_output
from app.schemas.report_schemas import RunState, TurnOutput


class RuleFallbackExtractorBackend:
    mode = "rule_fallback"

    def extract_turn(self, user_input: str, state: RunState | None = None) -> TurnOutput:
        return build_rule_turn_output(user_input, state=state, mode=self.mode)


__all__ = ["RuleFallbackExtractorBackend"]
