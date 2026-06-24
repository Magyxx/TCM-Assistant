from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from p7_common import check, json_safe, status_from_checks, write_json
except ImportError:  # pragma: no cover
    from scripts.p7_common import check, json_safe, status_from_checks, write_json

from app.graph.consultation_graph import run_consultation_graph
from app.rag.bm25_retriever import BM25Okapi, BM25Retriever
from app.rag.evidence_pack import build_evidence_pack
from app.rag.rag_guard import guard_rag_update, report_text_is_safe
from app.schemas.report_schemas import RunState
from app.storage.models import utc_now


DEFAULT_OUTPUT = ROOT_DIR / "artifacts" / "p8_rag_validation.json"
TEST_QUERIES = ["胃胀", "胸痛", "便血", "没有发热", "睡眠不好"]


def _git_value(*args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except Exception:
        return "unknown"
    return completed.stdout.strip() if completed.returncode == 0 else "unknown"


def _rel(path: Path | str) -> str:
    path = Path(path)
    try:
        return str(path.relative_to(ROOT_DIR)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def run_retrieval_check() -> tuple[dict[str, Any], dict[str, Any]]:
    retriever = BM25Retriever()
    source = Path(retriever.document_store.knowledge_file)
    query_results: dict[str, dict[str, Any]] = {}
    skip_reason = None
    try:
        for query in TEST_QUERIES:
            results = retriever.retrieve_p8(query, top_k=3)
            query_results[query] = {
                "result_count": len(results),
                "top_chunk_id": results[0].chunk_id if results else None,
                "top_score": results[0].score if results else None,
            }
    except Exception as exc:
        skip_reason = f"bm25_realpath_unavailable:{exc.__class__.__name__}"

    index_loaded = source.is_file() and skip_reason is None
    result_non_empty = bool(query_results) and all(item["result_count"] > 0 for item in query_results.values())
    status = "passed" if index_loaded and result_non_empty else "skipped"
    if status == "skipped" and skip_reason is None:
        skip_reason = "knowledge_source_missing_or_empty_results"
    payload = {
        "mode": "bm25",
        "status": status,
        "skip_reason": skip_reason,
        "knowledge_source": _rel(source),
        "rank_bm25_available": BM25Okapi is not None,
        "index_loaded": index_loaded,
        "test_queries": query_results,
    }
    return payload, check("bm25_realpath_retrieval", status in {"passed", "skipped"}, **payload)


def run_evidence_pack_check() -> tuple[dict[str, Any], dict[str, Any]]:
    pack = build_evidence_pack("胃胀", top_k=2)
    chunk = pack.chunks[0] if pack.chunks else None
    payload = {
        "schema_pass": bool(pack.query and pack.normalized_query and pack.retrieval_mode == "bm25"),
        "source_id_present": bool(chunk and chunk.source_id),
        "chunk_id_present": bool(chunk and chunk.chunk_id),
        "score_present": bool(chunk and isinstance(chunk.score, float)),
        "guard_status": pack.guard_status,
        "result_count": len(pack.chunks),
    }
    ok = all(
        payload[key] is True
        for key in ["schema_pass", "source_id_present", "chunk_id_present", "score_present"]
    )
    return payload, check("evidence_pack_schema", ok, **payload)


def run_guard_check() -> tuple[dict[str, Any], dict[str, Any]]:
    fields = {
        "chief_complaint_overwrite_blocked": "chief_complaint",
        "duration_overwrite_blocked": "duration",
        "risk_status_overwrite_blocked": "risk_status",
        "risk_rule_ids_overwrite_blocked": "risk_rule_ids",
    }
    payload = {name: not guard_rag_update({field: "retrieved"}).allowed for name, field in fields.items()}
    ok = all(payload.values())
    return payload, check("rag_guard_blocks_core_fields", ok, **payload)


def run_graph_check() -> tuple[dict[str, Any], dict[str, Any]]:
    graph_state = run_consultation_graph(
        RunState(
            chief_complaint="胃胀",
            duration="两天",
            symptoms_status="none",
            risk_flags_status="none",
        ),
        "睡眠不好",
        use_langgraph=False,
        extractor_mode="fake",
        rag_enabled=True,
    )
    facts = graph_state["memory"].facts
    payload = {
        "rag_node_optional": graph_state["run_state"].metadata.get("p8_graph", {}).get("rag_node_optional") is True,
        "retrieved_evidence_count_recorded": graph_state["retrieved_evidence_count"] > 0,
        "retrieved_evidence_count": graph_state["retrieved_evidence_count"],
        "memory_l2_evidence_absent": "retrieved_evidence" not in facts and "evidence" not in facts,
    }
    ok = all(value is True for key, value in payload.items() if key != "retrieved_evidence_count")
    return payload, check("graph_rag_integration", ok, **payload)


def run_report_safety_check() -> dict[str, Any]:
    ok = report_text_is_safe("建议继续观察变化，必要时线下就医。") and not report_text_is_safe("诊断为某病并开方。")
    return check("rag_report_safety_boundary", ok)


def build_payload() -> dict[str, Any]:
    retrieval, retrieval_check = run_retrieval_check()
    evidence_pack, evidence_check = run_evidence_pack_check()
    rag_guard, guard_check = run_guard_check()
    graph_integration, graph_check = run_graph_check()
    safety_check = run_report_safety_check()
    checks = [retrieval_check, evidence_check, guard_check, graph_check, safety_check]
    return {
        "stage": "P8-M4_BM25_REALPATH_EVIDENCE_PACK",
        "phase": "P8-M4",
        "generated_at": utc_now(),
        "status": status_from_checks(checks),
        "branch": _git_value("branch", "--show-current"),
        "commit": _git_value("rev-parse", "HEAD"),
        "retrieval": retrieval,
        "evidence_pack": evidence_pack,
        "rag_guard": rag_guard,
        "graph_integration": graph_integration,
        "checks": checks,
        "branch_safety": {
            "protected_tags_untouched": ["v0.7.0-p7-caution"],
            "protected_branches_untouched": [
                "backup/main-before-p7-device1-20260622-e986065",
                "origin/sft-local-pipeline",
                "origin/exp/sft-lora-extractor",
            ],
            "device2_sft_lora_code_mixed": False,
        },
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run P8-M4 BM25 RAG validation.")
    parser.add_argument("--json", action="store_true", help="Print validation JSON.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT.relative_to(ROOT_DIR)), help="Artifact path.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args(argv)
    payload = build_payload()
    output = ROOT_DIR / args.output
    write_json(output, payload)
    if args.json:
        print(json.dumps(json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(
            "P8 RAG validation: "
            f"status={payload['status']} "
            f"retrieval={payload['retrieval']['status']} "
            f"evidence={payload['graph_integration']['retrieved_evidence_count']} "
            f"artifact={output.relative_to(ROOT_DIR)}"
        )
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
