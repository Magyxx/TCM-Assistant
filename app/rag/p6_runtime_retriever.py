from __future__ import annotations

import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.knowledge.pipeline import tokenize
from app.rag.evidence_audit import build_evidence_audit_records, write_evidence_audit_records
from app.rag.evidence_schema import (
    P6B_RETRIEVAL_MODE,
    P6EvidenceChunk,
    P6EvidencePack,
    build_empty_p6_evidence_pack,
)
from app.rag.p6_index_loader import LoadedP6RuntimeIndex, load_p6_runtime_index
from app.observability.trace import build_p6b_rag_trace


QUERY_EXPANSIONS = {
    "胃不舒服": ["digestive", "discomfort", "appetite", "stool"],
    "胸痛": ["chest", "pain", "red_flag_chest_pain"],
    "胸闷": ["chest", "tightness", "red_flag_chest_pain"],
    "呼吸困难": ["dyspnea", "red_flag_dyspnea"],
    "便血": ["blood", "stool", "red_flag_gi_bleeding"],
    "高热": ["high", "fever", "red_flag_high_fever"],
    "意识异常": ["red", "flag", "urgent", "offline", "care"],
    "胃胀": ["digestive", "discomfort", "appetite", "stool"],
    "胀得慌": ["digestive", "discomfort", "duration"],
    "睡不好": ["symptom", "changes", "duration"],
    "拉肚子": ["stool", "digestive", "discomfort"],
    "腹泻": ["digestive", "stool", "duration"],
    "便溏": ["stool", "digestive"],
    "畏寒": ["symptom", "changes"],
    "脘腹胀满": ["digestive", "discomfort", "appetite"],
    "纳差": ["appetite", "digestive"],
    "食欲": ["appetite"],
    "大便": ["stool"],
    "没有发热": ["symptom", "changes"],
    "不胸痛": ["symptom", "changes"],
    "未见便血": ["symptom", "changes"],
    "风险提示": ["red", "flag", "offline", "care"],
    "问诊建议": ["duration", "appetite", "stool", "symptom", "changes"],
    "继续观察": ["duration", "symptom", "changes"],
    "安全声明": ["information", "organization", "evidence", "citation"],
    "证据引用": ["information", "evidence", "citation"],
    "信息整理": ["information", "organization", "evidence"],
    "改写风险状态": ["downgrade", "risk", "triage", "red", "flag"],
    "降低高风险": ["downgrade", "high", "risk", "triage"],
    "输出处方": ["must", "not", "prescribe"],
    "诊断": ["must", "not", "diagnose", "information", "organization"],
    "开方": ["must", "not", "prescribe", "information", "organization"],
    "剂量": ["must", "not", "prescribe"],
    "药物": ["must", "not", "prescribe"],
}

NEGATED_RISK_MARKERS = {
    "胸痛": ["不胸痛", "没有胸痛", "无胸痛"],
    "胸闷": ["没有胸闷", "无胸闷"],
    "呼吸困难": ["没有呼吸困难", "无呼吸困难"],
    "便血": ["未见便血", "没有便血", "无便血"],
    "高热": ["没有高热", "无高热"],
}


class P6RuntimeRetriever:
    def __init__(
        self,
        *,
        index_path: Path | str | None = None,
        chunks_path: Path | str | None = None,
        source_manifest_path: Path | str | None = None,
        loaded_index: LoadedP6RuntimeIndex | None = None,
    ) -> None:
        if loaded_index is not None:
            self.loaded_index = loaded_index
        else:
            kwargs: dict[str, Any] = {}
            if index_path is not None:
                kwargs["index_path"] = index_path
            if chunks_path is not None:
                kwargs["chunks_path"] = chunks_path
            if source_manifest_path is not None:
                kwargs["source_manifest_path"] = source_manifest_path
            self.loaded_index = load_p6_runtime_index(**kwargs)

    def _expanded_query_tokens(self, query: str) -> set[str]:
        tokens = set(tokenize(query))
        for marker, additions in QUERY_EXPANSIONS.items():
            negations = NEGATED_RISK_MARKERS.get(marker) or []
            if any(negation in query for negation in negations):
                continue
            if marker in query:
                tokens.update(additions)
        return tokens

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 3,
        session_id: str | None = None,
        turn_id: str | None = None,
        trace_id: str | None = None,
        write_audit: bool = True,
        query_id: str | None = None,
    ) -> tuple[P6EvidencePack, dict[str, Any]]:
        trace_id = trace_id or f"p6b-{uuid4().hex[:12]}"
        started = time.perf_counter()
        query_tokens = self._expanded_query_tokens(query)
        scored: list[tuple[float, dict[str, Any]]] = []
        for chunk in self.loaded_index.chunks:
            content_tokens = set(tokenize(str(chunk["content"])))
            normalized_terms = set(str(term) for term in (chunk.get("normalized_terms") or []))
            score = float(len(query_tokens & content_tokens))
            score += float(len(query_tokens & normalized_terms) * 3)
            scored.append((score, chunk))

        scored.sort(key=lambda item: (item[0], str(item[1]["chunk_id"])), reverse=True)
        evidence: list[P6EvidenceChunk] = []
        for score, chunk in scored[:top_k]:
            if score <= 0:
                continue
            source_id = str(chunk["source_id"])
            gate = self.loaded_index.source_gates[source_id]
            evidence.append(
                P6EvidenceChunk(
                    source_id=source_id,
                    chunk_id=str(chunk["chunk_id"]),
                    title=str(chunk["title"]),
                    content=str(chunk["content"]),
                    score=score,
                    retrieval_mode=P6B_RETRIEVAL_MODE,
                    index_version=self.loaded_index.index_version,
                    chunk_hash=str(chunk["hash"]),
                    source_rights_status=gate.rights_status,
                    source_safety_status=gate.safety_status,
                    source_provenance_status=gate.provenance_status,
                    section=str(chunk.get("section") or ""),
                    trust_level=gate.trust_level,
                    metadata={
                        "risk_level": chunk.get("risk_level"),
                        "normalized_terms": list(chunk.get("normalized_terms") or []),
                        "source_hash": chunk.get("source_hash") or gate.source_hash,
                        "registry_version": chunk.get("registry_version") or gate.registry_version,
                        "review_version": chunk.get("review_version") or gate.review_version,
                        "approved_for_runtime": gate.approved_for_runtime,
                    },
                )
            )

        pack = build_empty_p6_evidence_pack(
            query,
            source_manifest_version=self.loaded_index.source_manifest_version,
            index_path=self.loaded_index.index_path,
            chunks_path=self.loaded_index.chunks_path,
            source_manifest_path=self.loaded_index.source_manifest_path,
        )
        pack.evidence = evidence
        latency_ms = int((time.perf_counter() - started) * 1000)
        trace = build_p6b_rag_trace(
            session_id=session_id,
            turn_id=turn_id,
            trace_id=trace_id,
            rag_runtime_enabled=True,
            rag_index_path=str(self.loaded_index.index_path),
            rag_index_version=self.loaded_index.index_version,
            chunk_schema_version=self.loaded_index.chunk_schema_version,
            source_manifest_version=self.loaded_index.source_manifest_version,
            evidence=evidence,
            retrieval_mode=P6B_RETRIEVAL_MODE,
            fallback_used=False,
            fallback_reason=None,
            rag_boundary_pass=True,
            latency_ms=latency_ms,
        )
        if write_audit and evidence:
            write_evidence_audit_records(
                build_evidence_audit_records(
                    pack,
                    trace,
                    query_id=query_id or trace["turn_id"],
                    used_in_report_section="retrieved",
                    core_state_mutated=False,
                )
            )
        return pack, trace


def retrieve_p6_evidence(
    query: str,
    *,
    top_k: int = 3,
    session_id: str | None = None,
    turn_id: str | None = None,
    trace_id: str | None = None,
    write_audit: bool = True,
    query_id: str | None = None,
) -> tuple[P6EvidencePack, dict[str, Any]]:
    return P6RuntimeRetriever().retrieve(
        query,
        top_k=top_k,
        session_id=session_id,
        turn_id=turn_id,
        trace_id=trace_id,
        write_audit=write_audit,
        query_id=query_id,
    )
