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
    def backend(self) -> str:
        return str(self.metadata.get("backend") or self.mode)

    @property
    def model(self) -> str | None:
        model = self.metadata.get("model_name") or self.metadata.get("model")
        return str(model) if model else None

    @property
    def raw_json_valid(self) -> bool:
        if "raw_llm_json_valid" in self.metadata:
            return bool(self.metadata["raw_llm_json_valid"])
        if "json_valid" in self.metadata:
            return bool(self.metadata["json_valid"])
        return bool(self.schema_pass)

    @property
    def parsed_json(self) -> Any:
        return self.parsed_output

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
            "backend": mode,
            "model_name": legacy.model_name,
            "error_type": legacy.error_type,
            "error_message_preview": legacy.error_message_preview,
            "repair_used": False,
            "schema_guard": "passed" if schema_pass and legacy.final_schema_pass else "failed",
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
    def from_turn_output(
        cls,
        *,
        mode: str,
        turn_output: TurnOutput | Dict[str, Any] | None,
        raw_output: Any = None,
        parsed_output: Any = None,
        fallback_used: bool = False,
        error: str | None = None,
        skip_reason: str | None = None,
        latency_ms: float | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> "ExtractorResult":
        merged_metadata = {
            "backend": mode,
            "json_valid": True,
            "raw_llm_json_valid": True,
            "schema_valid": False,
            "final_schema_pass": False,
            "fallback_used": fallback_used,
            "schema_guard": "failed",
        }
        if metadata:
            merged_metadata.update(metadata)

        validated: TurnOutput | None = None
        schema_pass = False
        parsed = parsed_output
        try:
            if turn_output is not None:
                validated = TurnOutput.model_validate(turn_output)
                parsed = parsed if parsed is not None else validated.model_dump()
                schema_pass = True
        except Exception as exc:
            merged_metadata.setdefault("error_type", exc.__class__.__name__)
            merged_metadata.setdefault("error_message_preview", str(exc)[:240])

        merged_metadata["schema_valid"] = bool(schema_pass)
        if metadata is None or "final_schema_pass" not in metadata:
            merged_metadata["final_schema_pass"] = bool(schema_pass)
        merged_metadata["validated_output_schema_guard"] = "passed" if schema_pass else "failed"
        if metadata is None or "schema_guard" not in metadata:
            merged_metadata["schema_guard"] = "passed" if schema_pass else "failed"
        merged_metadata["fallback_used"] = bool(fallback_used or merged_metadata.get("fallback_used"))

        return cls(
            mode=mode,
            raw_output=raw_output,
            parsed_output=parsed,
            turn_output=validated,
            schema_pass=schema_pass,
            fallback_used=bool(merged_metadata["fallback_used"]),
            error=error,
            skip_reason=skip_reason or merged_metadata.get("skip_reason"),
            latency_ms=latency_ms,
            metadata=merged_metadata,
        )

    @classmethod
    def skipped(
        cls,
        *,
        mode: str,
        skip_reason: str,
        raw_output: Any = None,
        metadata: Dict[str, Any] | None = None,
    ) -> "ExtractorResult":
        return cls(
            mode=mode,
            raw_output=raw_output,
            parsed_output=None,
            turn_output=None,
            schema_pass=False,
            fallback_used=False,
            skip_reason=skip_reason,
            metadata={
                "backend": mode,
                "skip_reason": skip_reason,
                "schema_guard": "skipped",
                "json_valid": False,
                "raw_llm_json_valid": False,
                "schema_valid": False,
                "final_schema_pass": False,
                **(metadata or {}),
            },
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
            metadata={
                "backend": mode,
                "json_valid": False,
                "raw_llm_json_valid": False,
                "schema_valid": False,
                "final_schema_pass": False,
                **(metadata or {}),
                "schema_guard": "failed",
            },
        )
