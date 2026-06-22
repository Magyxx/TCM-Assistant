from __future__ import annotations

from typing import Any, Dict

from app.rag.p6_runtime_retriever import retrieve_p6_evidence


def invoke(payload: Dict[str, Any]) -> Dict[str, Any]:
    pack, trace = retrieve_p6_evidence(
        str(payload.get("query") or ""),
        top_k=int(payload.get("top_k") or 3),
        write_audit=False,
    )
    return {
        "evidence": [item.model_dump() for item in pack.evidence],
        "trace": trace,
        "rag_boundary_pass": True,
        "core_state_mutation_count_by_rag": 0,
    }
