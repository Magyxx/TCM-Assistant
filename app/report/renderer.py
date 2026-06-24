from __future__ import annotations

from typing import Any

from app.report.safety import check_report_safety
from app.report.schemas import FinalReportSkeleton, SAFETY_DISCLAIMER


def _collected_facts_from_state(state: dict[str, Any]) -> dict[str, Any]:
    if isinstance(state.get("collected_facts"), dict):
        return dict(state["collected_facts"])
    if isinstance(state.get("facts"), dict):
        return dict(state["facts"])
    fact_fields = [
        "chief_complaint",
        "duration",
        "symptoms",
        "symptoms_status",
        "sleep",
        "appetite",
        "stool",
        "urination",
        "stool_urine",
    ]
    return {
        field: state.get(field)
        for field in fact_fields
        if state.get(field) not in (None, "", [], {}, "unknown")
    }


def build_report_skeleton(
    *,
    session_id: str,
    state: dict[str, Any] | None = None,
    evidence_pack: dict[str, Any] | None = None,
) -> FinalReportSkeleton:
    state = state or {}
    collected = _collected_facts_from_state(state)
    missing = list(state.get("missing_core_fields") or [])
    risk_reasons = list(state.get("risk_reasons") or [])
    skeleton = FinalReportSkeleton(
        session_id=session_id,
        summary="Deterministic report skeleton for inquiry organization; no LLM report generation was used.",
        collected_facts=collected,
        missing_core_fields=missing,
        risk_status=str(state.get("risk_status") or state.get("risk_flags_status") or "unknown"),
        risk_reasons=risk_reasons,
        evidence_pack=evidence_pack,
        safety_disclaimer=SAFETY_DISCLAIMER,
    )
    skeleton.safety_check = check_report_safety(" ".join([skeleton.summary, *skeleton.advice, skeleton.safety_disclaimer]))
    return skeleton
