from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Protocol

from app.chains.turn_extractor import ExtractionResult as LegacyExtractionResult
from app.extractors.result import ExtractorResult
from app.schemas.report_schemas import RunState, TurnOutput


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

    def extract(self, text: str, *, state: RunState | dict | None = None, memory: dict | None = None) -> ExtractorResult:
        ...


class ExtractorBackend(Protocol):
    mode: str

    def extract(
        self,
        user_input: str,
        *,
        state: RunState | dict | None = None,
        memory: dict | None = None,
        config: dict[str, Any] | None = None,
        session_id: str | None = None,
        turn_id: str | None = None,
    ) -> ExtractorResult:
        ...

    def extract_turn(self, user_input: str, state: RunState | None = None) -> TurnOutput:
        ...


class BaseExtractor:
    mode = "base"

    def _coerce_state(self, state: RunState | dict | None) -> RunState:
        if isinstance(state, RunState):
            return state
        if isinstance(state, dict):
            return RunState.model_validate(state)
        return RunState()

    def _legacy_to_result(
        self,
        legacy: LegacyExtractionResult,
        *,
        started_at: float,
        skip_reason: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ExtractorResult:
        return ExtractorResult.from_legacy(
            legacy,
            mode=self.mode,
            skip_reason=skip_reason,
            latency_ms=round((perf_counter() - started_at) * 1000, 3),
            metadata=metadata,
        )


def result_to_probe(
    *,
    requested_mode: str,
    result: ExtractorResult,
    skipped_reason: str | None = None,
) -> ExtractorProbeResult:
    turn_output = result.turn_output
    skip_reason = skipped_reason or result.skip_reason
    status = "skipped" if skip_reason else ("ok" if result.schema_pass else "failed")
    metadata = result.metadata
    return ExtractorProbeResult(
        mode=result.mode,
        requested_mode=requested_mode,
        status=status,
        success=bool(result.schema_pass and not result.error),
        fallback_used=bool(result.fallback_used),
        schema_valid=bool(result.schema_pass),
        raw_llm_json_valid=bool(metadata.get("raw_llm_json_valid")),
        final_schema_pass=bool(result.schema_pass),
        risk_flags_status=getattr(turn_output, "risk_flags_status", None),
        error_type=metadata.get("error_type"),
        error_message_preview=metadata.get("error_message_preview") or result.error,
        skipped_reason=skip_reason,
    )


def run_extractor_probe(extractor: TurnExtractor, user_input: str, state: RunState | None = None) -> ExtractorProbeResult:
    result = extractor.extract(user_input, state=state or RunState())
    return result_to_probe(requested_mode=extractor.mode, result=result)
