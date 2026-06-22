from __future__ import annotations

from pathlib import Path
from typing import Any, List

from pydantic import BaseModel, Field

from app.schemas.report_schemas import FinalReport
from app.storage.models import RagEvidenceRecord


P6B_PHASE = "P6B"
P6B_RETRIEVAL_MODE = "p6b_runtime_bm25"
P6B_INDEX_VERSION = "kb.index.v0"
P6B_CHUNK_SCHEMA_VERSION = "kb.chunk.v0"
P6B_FORBIDDEN_STATE_WRITES = [
    "chief_complaint",
    "duration",
    "risk_status",
    "risk_rule_ids",
    "risk_flags_status",
    "risk_flags",
]


class P6EvidenceChunk(BaseModel):
    source_id: str
    chunk_id: str
    title: str
    content: str
    score: float
    retrieval_mode: str
    index_version: str
    chunk_hash: str
    source_rights_status: str
    source_safety_status: str
    source_provenance_status: str
    section: str = ""
    trust_level: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class P6EvidenceReference(BaseModel):
    source_id: str
    chunk_id: str
    title: str
    section: str = ""
    chunk_hash: str
    source_rights_status: str
    source_safety_status: str
    source_provenance_status: str


class P6EvidencePack(BaseModel):
    phase: str = P6B_PHASE
    query: str
    evidence: List[P6EvidenceChunk] = Field(default_factory=list)
    retrieval_mode: str = P6B_RETRIEVAL_MODE
    index_version: str = P6B_INDEX_VERSION
    chunk_schema_version: str = P6B_CHUNK_SCHEMA_VERSION
    source_manifest_version: str
    index_path: str
    chunks_path: str
    source_manifest_path: str
    fallback_used: bool = False
    fallback_reason: str | None = None
    core_state_readonly: bool = True
    risk_rule_first: bool = True
    can_diagnose: bool = False
    can_prescribe: bool = False
    can_create_treatment_plan: bool = False
    forbidden_state_writes: List[str] = Field(default_factory=lambda: list(P6B_FORBIDDEN_STATE_WRITES))

    def references(self) -> list[P6EvidenceReference]:
        return [
            P6EvidenceReference(
                source_id=item.source_id,
                chunk_id=item.chunk_id,
                title=item.title,
                section=item.section,
                chunk_hash=item.chunk_hash,
                source_rights_status=item.source_rights_status,
                source_safety_status=item.source_safety_status,
                source_provenance_status=item.source_provenance_status,
            )
            for item in self.evidence
        ]


def _path_text(value: Path | str) -> str:
    return str(value).replace("\\", "/")


def build_empty_p6_evidence_pack(
    query: str,
    *,
    source_manifest_version: str,
    index_path: Path | str,
    chunks_path: Path | str,
    source_manifest_path: Path | str,
) -> P6EvidencePack:
    return P6EvidencePack(
        query=query,
        source_manifest_version=source_manifest_version,
        index_path=_path_text(index_path),
        chunks_path=_path_text(chunks_path),
        source_manifest_path=_path_text(source_manifest_path),
    )


def attach_p6_evidence_to_report(report: FinalReport, pack: P6EvidencePack) -> FinalReport:
    updated = report.model_copy(deep=True)
    references = [item.model_dump() for item in pack.references()]
    updated.metadata = {
        **updated.metadata,
        "retrieved_evidence": [item.model_dump() for item in pack.evidence],
        "p6b_evidence_pack": pack.model_dump(),
        "p6b_evidence_references": references,
        "p6b_report_evidence_reference_pass": len(references) == len(pack.evidence),
        "rag_core_state_readonly": pack.core_state_readonly,
        "rag_forbidden_state_writes": list(pack.forbidden_state_writes),
        "rag_retriever_mode": pack.retrieval_mode,
        "rag_index_version": pack.index_version,
    }
    return updated


class P7EvidencePersistenceSummary(BaseModel):
    retrieved_count: int
    used_count: int
    rag_evidence_persistence_pass: bool
    rag_boundary_pass: bool = True
    core_state_mutation_count_by_rag: int = 0


def evidence_pack_to_storage_records(
    pack: P6EvidencePack,
    *,
    session_id: str,
    turn_id: str,
    used_chunk_ids: set[str] | None = None,
    used_in_report_section: str | None = None,
) -> list[RagEvidenceRecord]:
    used_chunk_ids = used_chunk_ids or set()
    records: list[RagEvidenceRecord] = []
    for item in pack.evidence:
        is_used = item.chunk_id in used_chunk_ids
        records.append(
            RagEvidenceRecord(
                session_id=session_id,
                turn_id=turn_id,
                source_id=item.source_id,
                chunk_id=item.chunk_id,
                chunk_hash=item.chunk_hash,
                index_version=item.index_version,
                score=float(item.score),
                retrieval_mode=item.retrieval_mode,
                used_in_report_section=used_in_report_section if is_used else None,
                is_used=is_used,
                evidence=item.model_dump(),
            )
        )
    return records


def summarize_evidence_persistence(records: list[RagEvidenceRecord]) -> P7EvidencePersistenceSummary:
    retrieved_count = len(records)
    used_count = sum(1 for item in records if item.is_used)
    required_pass = all(
        item.source_id
        and item.chunk_id
        and item.chunk_hash
        and item.index_version
        and item.retrieval_mode
        for item in records
    )
    used_labels_pass = all(
        bool(item.used_in_report_section) for item in records if item.is_used
    )
    return P7EvidencePersistenceSummary(
        retrieved_count=retrieved_count,
        used_count=used_count,
        rag_evidence_persistence_pass=required_pass and used_labels_pass,
    )
