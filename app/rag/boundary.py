from __future__ import annotations

from typing import Any

from app.rag.evidence_schema import P6B_FORBIDDEN_STATE_WRITES, P6EvidencePack
from app.schemas.report_schemas import RunState


CORE_STATE_ALIASES = {
    "chief_complaint": "chief_complaint",
    "duration": "duration",
    "risk_status": "risk_flags_status",
    "risk_rule_ids": "triggered_rule_ids",
    "risk_flags_status": "risk_flags_status",
    "risk_flags": "risk_flags",
    "symptoms": "symptoms",
}


class RagBoundaryViolation(ValueError):
    pass


def core_state_snapshot(state: RunState) -> dict[str, Any]:
    return {
        public_name: getattr(state, model_field)
        for public_name, model_field in CORE_STATE_ALIASES.items()
    }


def assert_rag_did_not_mutate_core_state(before: RunState, after: RunState) -> None:
    before_snapshot = core_state_snapshot(before)
    after_snapshot = core_state_snapshot(after)
    changed = [
        name
        for name in before_snapshot
        if before_snapshot.get(name) != after_snapshot.get(name)
    ]
    if changed:
        raise RagBoundaryViolation(f"RAG mutated core RunState fields: {changed}")

    if before.risk_flags_status == "present" and after.risk_flags_status != "present":
        raise RagBoundaryViolation("RAG downgraded high-risk status")
    if before.risk_flags_status == "none" and after.risk_flags_status == "present":
        raise RagBoundaryViolation("RAG changed negated risk status to present")


def assert_evidence_pack_is_boundary_safe(pack: P6EvidencePack) -> None:
    required = {"chief_complaint", "duration", "risk_status", "risk_rule_ids"}
    forbidden = set(pack.forbidden_state_writes)
    if not pack.core_state_readonly:
        raise RagBoundaryViolation("P6 evidence pack is not marked core_state_readonly")
    if not pack.risk_rule_first:
        raise RagBoundaryViolation("P6 evidence pack is not marked risk_rule_first")
    if not required <= forbidden:
        raise RagBoundaryViolation("P6 evidence pack missing forbidden state write fields")
    if pack.can_diagnose or pack.can_prescribe or pack.can_create_treatment_plan:
        raise RagBoundaryViolation("P6 evidence pack violates diagnosis/prescription boundary")


def rag_boundary_check(before: RunState, after: RunState, pack: P6EvidencePack | None = None) -> dict[str, Any]:
    try:
        assert_rag_did_not_mutate_core_state(before, after)
        if pack is not None:
            assert_evidence_pack_is_boundary_safe(pack)
    except RagBoundaryViolation as exc:
        return {
            "status": "failed",
            "passed": False,
            "violation": str(exc),
            "forbidden_state_writes": list(P6B_FORBIDDEN_STATE_WRITES),
        }
    return {
        "status": "ok",
        "passed": True,
        "violation": None,
        "forbidden_state_writes": list(P6B_FORBIDDEN_STATE_WRITES),
    }
