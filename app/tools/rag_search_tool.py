from __future__ import annotations

from typing import Any, Dict

from app.rag.bm25_stub import search as search_bm25_stub
from app.rag.p6_runtime_retriever import retrieve_p6_evidence


def invoke(payload: Dict[str, Any]) -> Dict[str, Any]:
    query = str(payload.get("query") or "")
    if payload.get("enabled") is False or payload.get("enable_rag") is False:
        pack = search_bm25_stub(query, top_k=int(payload.get("top_k") or 3), enabled=False)
        return {
            "evidence": [],
            "evidence_pack": pack.model_dump(),
            "trace": {"status": "skipped", "skip_reason": pack.skip_reason},
            "rag_boundary_pass": True,
            "core_state_mutation_count_by_rag": 0,
        }
    stub_pack = search_bm25_stub(query, top_k=int(payload.get("top_k") or 3), enabled=True)
    pack, trace = retrieve_p6_evidence(
        query,
        top_k=int(payload.get("top_k") or 3),
        write_audit=False,
    )
    return {
        "evidence": [item.model_dump() for item in pack.evidence],
        "evidence_pack": stub_pack.model_dump(),
        "trace": trace,
        "rag_boundary_pass": True,
        "core_state_mutation_count_by_rag": 0,
    }
