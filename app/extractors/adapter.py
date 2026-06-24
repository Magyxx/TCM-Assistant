from __future__ import annotations

from typing import Any

from app.extractors.result import ExtractorResult


P11_EXTRACTOR_CONTRACT_FIELDS = (
    "backend_name",
    "backend_mode",
    "status",
    "schema_pass",
    "candidate_schema_pass",
    "schema_guard",
    "validated_output_schema_guard",
    "fallback_used",
    "latency_ms",
    "error_type",
    "skip_reason",
    "json_valid",
    "raw_llm_json_valid",
    "repair_used",
    "repair_supported",
    "retry_count",
    "retry_supported",
)


def summarize_extractor_result(result: ExtractorResult) -> dict[str, Any]:
    return result.contract_summary()


def validate_extractor_result_contract(result: ExtractorResult) -> list[str]:
    summary = summarize_extractor_result(result)
    failures: list[str] = []
    for field in P11_EXTRACTOR_CONTRACT_FIELDS:
        if field not in summary:
            failures.append(f"missing:{field}")

    if not summary.get("backend_name"):
        failures.append("empty:backend_name")
    if not summary.get("backend_mode"):
        failures.append("empty:backend_mode")
    if summary.get("schema_guard") not in {"passed", "failed", "skipped"}:
        failures.append("invalid:schema_guard")
    if summary.get("validated_output_schema_guard") not in {"passed", "failed", "skipped"}:
        failures.append("invalid:validated_output_schema_guard")
    if summary.get("latency_ms") is not None and float(summary["latency_ms"]) < 0:
        failures.append("invalid:latency_ms")
    if int(summary.get("retry_count") or 0) < 0:
        failures.append("invalid:retry_count")
    return failures


__all__ = [
    "P11_EXTRACTOR_CONTRACT_FIELDS",
    "summarize_extractor_result",
    "validate_extractor_result_contract",
]
