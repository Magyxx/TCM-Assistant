from __future__ import annotations

import os

from app.chains.turn_extractor import extract_turn, get_missing_api_config
from app.extractors.simple_rules import build_rule_turn_output
from app.schemas.report_schemas import RunState, TurnOutput


def _real_llm_enabled() -> bool:
    value = os.getenv("ENABLE_REAL_LLM", os.getenv("TCM_ALLOW_REAL_LLM", "false"))
    return value.strip().lower() in {"1", "true", "yes", "on"}


class RealLLMExtractorBackend:
    mode = "real_llm"

    def extract_turn(self, user_input: str, state: RunState | None = None) -> TurnOutput:
        state = state or RunState()
        if not _real_llm_enabled():
            output = build_rule_turn_output(user_input, state=state, mode="real_llm")
            output.summary = "real_llm skipped because ENABLE_REAL_LLM=false; rule fallback output returned."
            output.metadata.update(
                {
                    "backend": self.mode,
                    "error_type": "real_llm_disabled",
                    "skip_reason": "ENABLE_REAL_LLM=false",
                    "fallback_used": True,
                    "raw_llm_json_valid": False,
                    "final_schema_pass": True,
                }
            )
            return output

        missing = get_missing_api_config()
        if missing:
            output = build_rule_turn_output(user_input, state=state, mode="real_llm")
            output.summary = "real_llm skipped because API configuration is incomplete; rule fallback output returned."
            output.metadata.update(
                {
                    "backend": self.mode,
                    "error_type": "missing_api_config",
                    "skip_reason": f"missing_api_config:{','.join(missing)}",
                    "missing_config": missing,
                    "fallback_used": True,
                    "raw_llm_json_valid": False,
                    "final_schema_pass": True,
                }
            )
            return output

        result = extract_turn(state, user_input, extractor_mode="real_llm")
        if result.turn_output is None:
            output = build_rule_turn_output(user_input, state=state, mode="real_llm")
            output.metadata.update(
                {
                    "backend": self.mode,
                    "error_type": result.error_type or "real_llm_schema_failure",
                    "error_message_preview": result.error_message_preview or result.error,
                    "fallback_used": True,
                    "raw_llm_json_valid": bool(result.raw_llm_json_valid),
                    "final_schema_pass": False,
                }
            )
            return output

        output = TurnOutput.model_validate(result.turn_output)
        output.metadata.update(
            {
                "backend": self.mode,
                "raw_llm_json_valid": bool(result.raw_llm_json_valid),
                "final_schema_pass": bool(result.final_schema_pass),
                "fallback_used": bool(result.fallback_used),
                "error_type": result.error_type,
                "error_message_preview": result.error_message_preview,
            }
        )
        return output


__all__ = ["RealLLMExtractorBackend"]
