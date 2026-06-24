from __future__ import annotations

import os
from time import perf_counter

from app.chains.turn_extractor import extract_turn, get_missing_api_config
from app.extractors.result import ExtractorResult
from app.extractors.simple_rules import build_rule_turn_output
from app.schemas.report_schemas import RunState, TurnOutput


def _real_llm_enabled() -> bool:
    value = os.getenv("ENABLE_REAL_LLM", os.getenv("TCM_ALLOW_REAL_LLM", "false"))
    return value.strip().lower() in {"1", "true", "yes", "on"}


class RealLLMExtractorBackend:
    def __init__(self, mode: str = "real_llm") -> None:
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
        started = perf_counter()
        state = state if isinstance(state, RunState) else RunState.model_validate(state or {})
        if not _real_llm_enabled():
            output = build_rule_turn_output(user_input, state=state, mode="real_llm")
            skip_reason = "ENABLE_REAL_LLM=false"
            output.summary = "real_llm skipped because ENABLE_REAL_LLM=false; rule fallback output returned."
            output.metadata.update(
                {
                    "backend": self.mode,
                    "error_type": "real_llm_disabled",
                    "skip_reason": skip_reason,
                    "fallback_used": True,
                    "json_valid": False,
                    "raw_llm_json_valid": False,
                    "schema_valid": True,
                    "schema_guard": "passed",
                    "final_schema_pass": True,
                }
            )
            return ExtractorResult.from_turn_output(
                mode=self.mode,
                raw_output=None,
                turn_output=output,
                fallback_used=True,
                skip_reason=skip_reason,
                latency_ms=round((perf_counter() - started) * 1000, 3),
                metadata=output.metadata,
            )

        missing = get_missing_api_config()
        if missing:
            output = build_rule_turn_output(user_input, state=state, mode="real_llm")
            skip_reason = f"missing_api_config:{','.join(missing)}"
            output.summary = "real_llm skipped because API configuration is incomplete; rule fallback output returned."
            output.metadata.update(
                {
                    "backend": self.mode,
                    "error_type": "missing_api_config",
                    "skip_reason": skip_reason,
                    "missing_config": missing,
                    "fallback_used": True,
                    "json_valid": False,
                    "raw_llm_json_valid": False,
                    "schema_valid": True,
                    "schema_guard": "passed",
                    "final_schema_pass": True,
                }
            )
            return ExtractorResult.from_turn_output(
                mode=self.mode,
                raw_output=None,
                turn_output=output,
                fallback_used=True,
                skip_reason=skip_reason,
                latency_ms=round((perf_counter() - started) * 1000, 3),
                metadata=output.metadata,
            )

        result = extract_turn(state, user_input, extractor_mode="real_llm")
        if result.turn_output is None:
            output = build_rule_turn_output(user_input, state=state, mode="real_llm")
            output.metadata.update(
                {
                    "backend": self.mode,
                    "error_type": result.error_type or "real_llm_schema_failure",
                    "error_message_preview": result.error_message_preview or result.error,
                    "fallback_used": True,
                    "json_valid": bool(result.json_valid),
                    "raw_llm_json_valid": bool(result.raw_llm_json_valid),
                    "schema_valid": True,
                    "schema_guard": "passed",
                    "final_schema_pass": False,
                }
            )
            return ExtractorResult.from_turn_output(
                mode=self.mode,
                raw_output=result.raw_text,
                turn_output=output,
                fallback_used=True,
                latency_ms=round((perf_counter() - started) * 1000, 3),
                metadata=output.metadata,
            )

        output = TurnOutput.model_validate(result.turn_output)
        output.metadata.update(
            {
                "backend": self.mode,
                "json_valid": bool(result.json_valid),
                "raw_llm_json_valid": bool(result.raw_llm_json_valid),
                "schema_valid": bool(result.schema_valid),
                "schema_guard": "passed" if result.final_schema_pass else "failed",
                "final_schema_pass": bool(result.final_schema_pass),
                "fallback_used": bool(result.fallback_used),
                "error_type": result.error_type,
                "error_message_preview": result.error_message_preview,
            }
        )
        return ExtractorResult.from_turn_output(
            mode=self.mode,
            raw_output=result.raw_text,
            turn_output=output,
            fallback_used=bool(result.fallback_used),
            latency_ms=round((perf_counter() - started) * 1000, 3),
            metadata=output.metadata,
        )

    def extract_turn(self, user_input: str, state: RunState | None = None) -> TurnOutput:
        result = self.extract(user_input, state=state)
        return result.turn_output or TurnOutput(summary=result.skip_reason or result.error, metadata=result.metadata)


__all__ = ["RealLLMExtractorBackend"]
