from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Sequence

from app.knowledge.source_registry import ROOT_DIR, utc_now
from app.observability.logger import append_jsonl
from app.rag.evidence_schema import P6EvidenceChunk, P6EvidencePack


DEFAULT_P6C_EVIDENCE_AUDIT_PATH = ROOT_DIR / "artifacts" / "p6c_evidence_metadata_audit.jsonl"

P6C_EVIDENCE_AUDIT_FIELDS = [
    "trace_id",
    "session_id",
    "query_id",
    "source_id",
    "chunk_id",
    "chunk_hash",
    "source_hash",
    "index_version",
    "registry_version",
    "review_version",
    "retrieval_mode",
    "score",
    "source_rights_status",
    "source_safety_status",
    "source_provenance_status",
    "approved_for_runtime",
    "used_in_report_section",
    "core_state_mutated",
    "created_at",
]


def build_evidence_audit_records(
    pack: P6EvidencePack,
    trace: dict[str, Any],
    *,
    query_id: str,
    used_in_report_section: str = "retrieved",
    core_state_mutated: bool = False,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in pack.evidence:
        records.append(
            evidence_chunk_to_audit_record(
                item,
                trace,
                query_id=query_id,
                used_in_report_section=used_in_report_section,
                core_state_mutated=core_state_mutated,
            )
        )
    return records


def evidence_chunk_to_audit_record(
    item: P6EvidenceChunk,
    trace: dict[str, Any],
    *,
    query_id: str,
    used_in_report_section: str,
    core_state_mutated: bool,
) -> dict[str, Any]:
    metadata = dict(item.metadata or {})
    payload = {
        "trace_id": str(trace.get("trace_id") or ""),
        "session_id": str(trace.get("session_id") or ""),
        "query_id": query_id,
        "source_id": item.source_id,
        "chunk_id": item.chunk_id,
        "chunk_hash": item.chunk_hash,
        "source_hash": str(metadata.get("source_hash") or ""),
        "index_version": item.index_version,
        "registry_version": str(metadata.get("registry_version") or ""),
        "review_version": str(metadata.get("review_version") or ""),
        "retrieval_mode": item.retrieval_mode,
        "score": float(item.score),
        "source_rights_status": item.source_rights_status,
        "source_safety_status": item.source_safety_status,
        "source_provenance_status": item.source_provenance_status,
        "approved_for_runtime": bool(metadata.get("approved_for_runtime")),
        "used_in_report_section": used_in_report_section,
        "core_state_mutated": bool(core_state_mutated),
        "created_at": utc_now(),
    }
    return {field: payload[field] for field in P6C_EVIDENCE_AUDIT_FIELDS}


def validate_evidence_audit_records(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    for index, record in enumerate(records, start=1):
        missing = [field for field in P6C_EVIDENCE_AUDIT_FIELDS if field not in record]
        if missing:
            failures.append({"row": index, "reason": f"missing fields: {', '.join(missing)}"})
            continue
        if record.get("core_state_mutated") is not False:
            failures.append({"row": index, "reason": "core_state_mutated must be false"})
        if record.get("approved_for_runtime") is not True:
            failures.append({"row": index, "reason": "approved_for_runtime must be true"})
        for field in ("trace_id", "session_id", "query_id", "source_id", "chunk_id", "chunk_hash"):
            if not record.get(field):
                failures.append({"row": index, "reason": f"{field} must be non-empty"})
    return {
        "status": "ok" if not failures and bool(records) else "failed",
        "evidence_audit_schema_pass": not failures and bool(records),
        "record_count": len(records),
        "failures": failures,
    }


def write_evidence_audit_records(
    records: Iterable[dict[str, Any]],
    *,
    path: Path | str = DEFAULT_P6C_EVIDENCE_AUDIT_PATH,
    append: bool = True,
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not append:
        path.write_text("", encoding="utf-8")
    append_jsonl(path, records)
