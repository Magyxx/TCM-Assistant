from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from app.chains.turn_extractor import ExtractionResult as LegacyExtractionResult
from app.schemas.report_schemas import TurnOutput


class ExtractorResult(BaseModel):
    mode: str
    raw_output: Any = None
    parsed_output: Any = None
    turn_output: Optional[TurnOutput] = None
    schema_pass: bool = False
    fallback_used: bool = False
    error: Optional[str] = None
    skip_reason: Optional[str] = None
    latency_ms: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def status(self) -> str:
        if self.skip_reason:
            return "skipped"
        return "passed" if self.schema_pass and self.error is None else "failed"

    @classmethod
    def from_legacy(
        cls,
        legacy: LegacyExtractionResult,
        *,
        mode: str,
        skip_reason: str | None = None,
        latency_ms: float | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> "ExtractorResult":
        turn_output = None
        schema_pass = False
        parsed_output = legacy.turn_output.model_dump() if legacy.turn_output else None
        try:
            if legacy.turn_output is not None:
                turn_output = TurnOutput.model_validate(legacy.turn_output)
                parsed_output = turn_output.model_dump()
                schema_pass = True
        except Exception:
            turn_output = None
            schema_pass = False

        merged_metadata = {
            "legacy_mode": legacy.mode,
            "legacy_extractor_mode": legacy.extractor_mode or legacy.mode,
            "strategy": legacy.strategy,
            "json_valid": legacy.json_valid,
            "raw_llm_json_valid": legacy.raw_llm_json_valid,
            "schema_valid": legacy.schema_valid,
            "final_schema_pass": legacy.final_schema_pass,
            "fallback_used": legacy.fallback_used,
            "model_name": legacy.model_name,
            "error_type": legacy.error_type,
            "error_message_preview": legacy.error_message_preview,
            "repair_used": False,
        }
        if metadata:
            merged_metadata.update(metadata)
        return cls(
            mode=mode,
            raw_output=legacy.raw_text,
            parsed_output=parsed_output,
            turn_output=turn_output,
            schema_pass=bool(schema_pass and legacy.final_schema_pass),
            fallback_used=bool(legacy.fallback_used),
            error=legacy.error,
            skip_reason=skip_reason,
            latency_ms=latency_ms,
            metadata=merged_metadata,
        )

    @classmethod
    def schema_failure(
        cls,
        *,
        mode: str,
        raw_output: Any,
        error: str,
        metadata: Dict[str, Any] | None = None,
    ) -> "ExtractorResult":
        return cls(
            mode=mode,
            raw_output=raw_output,
            parsed_output=None,
            turn_output=None,
            schema_pass=False,
            fallback_used=False,
            error=error,
            metadata={**(metadata or {}), "schema_guard": "failed"},
        )
