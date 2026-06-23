from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from app.schemas.report_schemas import RunState, TurnOutput


@dataclass
class BackendResult:
    backend: str
    success: bool
    turn_output: TurnOutput | None
    raw_output: str | None
    parsed_json: dict[str, Any] | None
    json_valid: bool
    schema_pass: bool
    fallback_used: bool
    latency_ms: float | None
    error: str | None
    model_name: str | None = None
    base_url: str | None = None
    error_type: str | None = None
    schema_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "success": self.success,
            "turn_output": self.turn_output.model_dump() if self.turn_output else None,
            "raw_output": self.raw_output,
            "parsed_json": self.parsed_json,
            "json_valid": self.json_valid,
            "schema_pass": self.schema_pass,
            "fallback_used": self.fallback_used,
            "latency_ms": self.latency_ms,
            "error": self.error,
            "model_name": self.model_name,
            "base_url": self.base_url,
            "error_type": self.error_type,
            "schema_error": self.schema_error,
        }

    def to_prediction_record(
        self,
        *,
        case_id: str,
        input_text: str,
        gold: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "case_id": case_id,
            "backend": self.backend,
            "input": input_text,
            "gold": gold,
            "raw_output": self.raw_output,
            "parsed_json": self.parsed_json,
            "json_valid": self.json_valid,
            "schema_pass": self.schema_pass,
            "fallback_used": self.fallback_used,
            "latency_ms": self.latency_ms,
            "error": self.error,
            "model_name": self.model_name,
            "base_url": self.base_url,
            "error_type": self.error_type,
            "schema_error": self.schema_error,
        }

    def to_extraction_result(self) -> Any:
        from app.chains.turn_extractor import ExtractionResult

        mode = "fake_structured_output" if self.backend == "fake" else "structured_output"
        if self.fallback_used:
            mode = "rule_fallback"
        return ExtractionResult(
            success=self.success,
            turn_output=self.turn_output,
            raw_text=self.raw_output,
            error=self.error,
            mode=mode,
            strategy="extractor_backend_router",
            json_valid=self.json_valid,
            schema_valid=self.schema_pass,
            raw_llm_json_valid=self.json_valid,
            final_schema_pass=self.schema_pass,
            fallback_used=self.fallback_used,
            extractor_mode=self.backend,
            model_name=self.model_name,
            error_type=self.error_type,
            error_message_preview=self.error,
        )


class ExtractorBackend(Protocol):
    name: str

    def extract_turn(self, state: RunState, user_input: str) -> BackendResult:
        ...


def backend_result_from_local_vllm(backend: str, result: Any) -> BackendResult:
    parsed_json = result.parsed_json
    if parsed_json is None and result.turn_output is not None:
        parsed_json = result.turn_output.model_dump()
    return BackendResult(
        backend=backend,
        success=bool(result.success),
        turn_output=result.turn_output,
        raw_output=result.raw_text,
        parsed_json=parsed_json,
        json_valid=bool(result.json_valid),
        schema_pass=bool(result.schema_valid and result.final_schema_pass),
        fallback_used=bool(result.fallback_used),
        latency_ms=result.latency_ms,
        error=result.error,
        model_name=result.model_name,
        base_url=result.base_url,
        error_type=result.error_type,
        schema_error=result.schema_error,
    )


def backend_result_from_turn_output(
    backend: str,
    turn_output: TurnOutput,
    *,
    model_name: str | None = None,
    latency_ms: float | None = None,
) -> BackendResult:
    payload = turn_output.model_dump()
    raw_output = json.dumps(payload, ensure_ascii=False)
    return BackendResult(
        backend=backend,
        success=True,
        turn_output=turn_output,
        raw_output=raw_output,
        parsed_json=payload,
        json_valid=True,
        schema_pass=True,
        fallback_used=False,
        latency_ms=latency_ms,
        error=None,
        model_name=model_name,
    )
