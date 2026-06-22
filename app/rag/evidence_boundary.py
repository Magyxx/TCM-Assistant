from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field

from app.rag.base import EvidenceChunk
from app.rag.hybrid_retriever import HybridMode, HybridRetriever
from app.schemas.report_schemas import FinalReport, RunState


CORE_STATE_FIELDS = (
    "chief_complaint",
    "duration",
    "risk_flags_status",
    "risk_flags",
    "triggered_rule_ids",
)


class EvidencePack(BaseModel):
    phase: str = "P4.3"
    query: str
    evidence: List[EvidenceChunk] = Field(default_factory=list)
    allowed_uses: List[str] = Field(default_factory=lambda: ["impression", "advice", "report_explanation"])
    forbidden_state_writes: List[str] = Field(
        default_factory=lambda: [
            "chief_complaint",
            "duration",
            "risk_status",
            "risk_rule_ids",
            "risk_flags_status",
            "risk_flags",
        ]
    )
    core_state_readonly: bool = True
    risk_rule_first: bool = True
    can_diagnose: bool = False
    can_prescribe: bool = False
    can_create_treatment_plan: bool = False


def state_to_evidence_query(state: RunState) -> str:
    parts: List[str] = []
    if state.chief_complaint:
        parts.append(f"chief_complaint:{state.chief_complaint}")
    if state.duration:
        parts.append(f"duration:{state.duration}")
    if state.symptoms:
        parts.append(f"symptoms:{' | '.join(state.symptoms)}")
    if state.risk_flags:
        parts.append(f"risk_flags:{' | '.join(state.risk_flags)}")
    parts.append(f"risk_flags_status:{state.risk_flags_status}")
    parts.append("consultation information organization risk warning offline care")
    return "; ".join(parts)


def build_evidence_pack(
    state: RunState,
    *,
    top_k: int = 3,
    mode: HybridMode = "bm25_only",
) -> EvidencePack:
    query = state_to_evidence_query(state)
    evidence = HybridRetriever(mode=mode).retrieve(query, top_k=top_k)
    return EvidencePack(query=query, evidence=evidence)


def core_state_snapshot(state: RunState) -> Dict[str, Any]:
    return {field: getattr(state, field) for field in CORE_STATE_FIELDS}


def assert_core_state_unchanged(before: RunState, after: RunState) -> None:
    before_snapshot = core_state_snapshot(before)
    after_snapshot = core_state_snapshot(after)
    if before_snapshot != after_snapshot:
        changed = [
            field
            for field in CORE_STATE_FIELDS
            if before_snapshot.get(field) != after_snapshot.get(field)
        ]
        raise ValueError(f"RAG boundary violation: core state changed: {changed}")


def attach_evidence_pack(report: FinalReport, pack: EvidencePack) -> FinalReport:
    updated = report.model_copy(deep=True)
    updated.metadata = {
        **updated.metadata,
        "p4_rag_evidence_pack": pack.model_dump(),
        "rag_core_state_readonly": pack.core_state_readonly,
        "rag_forbidden_state_writes": list(pack.forbidden_state_writes),
    }
    return updated

