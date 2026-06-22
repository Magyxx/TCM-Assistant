from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.chains.turn_extractor import ExtractionResult
from app.schemas.report_schemas import RunState


@dataclass(frozen=True)
class ExtractorConfig:
    mode: str
    probe_real_llm: bool = False
    timeout_seconds: int = 30


@dataclass(frozen=True)
class ExtractorProbeResult:
    mode: str
    requested_mode: str
    status: str
    success: bool
    fallback_used: bool
    schema_valid: bool
    raw_llm_json_valid: bool
    final_schema_pass: bool
    risk_flags_status: str | None
    error_type: str | None = None
    error_message_preview: str | None = None
    skipped_reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "requested_mode": self.requested_mode,
            "status": self.status,
            "success": self.success,
            "fallback_used": self.fallback_used,
            "schema_valid": self.schema_valid,
            "raw_llm_json_valid": self.raw_llm_json_valid,
            "final_schema_pass": self.final_schema_pass,
            "risk_flags_status": self.risk_flags_status,
            "error_type": self.error_type,
            "error_message_preview": self.error_message_preview,
            "skipped_reason": self.skipped_reason,
        }


class TurnExtractor(Protocol):
    mode: str

    def extract(self, state: RunState, user_input: str) -> ExtractionResult:
        ...


def result_to_probe(
    *,
    requested_mode: str,
    result: ExtractionResult,
    skipped_reason: str | None = None,
) -> ExtractorProbeResult:
    turn_output = result.turn_output
    status = "skipped" if skipped_reason else ("ok" if result.final_schema_pass else "failed")
    return ExtractorProbeResult(
        mode=result.extractor_mode or result.mode,
        requested_mode=requested_mode,
        status=status,
        success=bool(result.success),
        fallback_used=bool(result.fallback_used),
        schema_valid=bool(result.schema_valid),
        raw_llm_json_valid=bool(result.raw_llm_json_valid),
        final_schema_pass=bool(result.final_schema_pass),
        risk_flags_status=getattr(turn_output, "risk_flags_status", None),
        error_type=result.error_type,
        error_message_preview=result.error_message_preview,
        skipped_reason=skipped_reason,
    )


def run_extractor_probe(extractor: TurnExtractor, user_input: str, state: RunState | None = None) -> ExtractorProbeResult:
    result = extractor.extract(state or RunState(), user_input)
    return result_to_probe(requested_mode=extractor.mode, result=result)
