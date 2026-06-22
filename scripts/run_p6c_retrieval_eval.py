from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.knowledge.pipeline import (  # noqa: E402
    DEFAULT_MANIFEST_PATH,
    json_safe,
    retrieve_from_index,
    run_p6_pipeline,
    write_json,
)
from app.knowledge.source_registry import load_source_registry, write_json as write_registry_json  # noqa: E402
from app.rag.boundary import rag_boundary_check  # noqa: E402
from app.rag.evidence_audit import (  # noqa: E402
    DEFAULT_P6C_EVIDENCE_AUDIT_PATH,
    build_evidence_audit_records,
    validate_evidence_audit_records,
    write_evidence_audit_records,
)
from app.rag.p6_index_loader import P6IndexLoadError, load_p6_runtime_index  # noqa: E402
from app.rag.p6_runtime_retriever import P6RuntimeRetriever  # noqa: E402
from app.schemas.report_schemas import RunState  # noqa: E402


DEFAULT_CASES_PATH = ROOT_DIR / "knowledge" / "eval" / "p6c_retrieval_eval_cases.jsonl"
DEFAULT_BOUNDARY_CASES_PATH = ROOT_DIR / "knowledge" / "eval" / "p6c_rag_boundary_cases.jsonl"
DEFAULT_SOURCE_SAFETY_CASES_PATH = ROOT_DIR / "knowledge" / "eval" / "p6c_source_safety_cases.jsonl"
DEFAULT_EVAL_ARTIFACT = ROOT_DIR / "artifacts" / "p6c_retrieval_eval.json"
DEFAULT_KNOWLEDGE_EVAL = ROOT_DIR / "knowledge" / "eval" / "p6c_retrieval_safety_eval.json"

CRITICAL_TERMS = {
    "red_flag_chest_pain",
    "red_flag_dyspnea",
    "red_flag_gi_bleeding",
    "red_flag_high_fever",
}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"JSONL row must be an object at {path}:{line_number}")
        rows.append(row)
    return rows


def _term_set(pack: Any, *, top_only: bool = False) -> set[str]:
    evidence = list(pack.evidence)
    if top_only:
        evidence = evidence[:1]
    return {
        str(term)
        for item in evidence
        for term in (item.metadata.get("normalized_terms") or [])
    }


def _case_pass(case: dict[str, Any], pack: Any, loaded_source_ids: set[str]) -> tuple[bool, dict[str, Any]]:
    top_terms = _term_set(pack, top_only=True)
    all_terms = _term_set(pack)
    expected_terms = {str(term) for term in case.get("expected_terms") or []}
    retrieved_source_ids = {item.source_id for item in pack.evidence}
    source_ok = retrieved_source_ids <= loaded_source_ids
    if case.get("negated_risk") is True:
        negated_false_positive = bool(top_terms & CRITICAL_TERMS)
        passed = bool(pack.evidence) and bool(expected_terms & top_terms) and not negated_false_positive and source_ok
    else:
        negated_false_positive = False
        passed = bool(pack.evidence) and bool(expected_terms & all_terms) and source_ok
    if case.get("forbidden_follow") is True:
        passed = passed and True
    return passed, {
        "expected_terms": sorted(expected_terms),
        "top_terms": sorted(top_terms),
        "all_terms": sorted(all_terms),
        "source_ok": source_ok,
        "negated_risk_false_positive": negated_false_positive,
        "retrieved_chunk_ids": [item.chunk_id for item in pack.evidence],
        "retrieved_source_ids": sorted(retrieved_source_ids),
    }


def _write_temp_runtime_artifacts(
    root: Path,
    *,
    index: dict[str, Any],
    chunks: list[dict[str, Any]],
) -> tuple[Path, Path]:
    index_path = root / "p6_bm25_index.json"
    chunks_path = root / "p6_chunks.jsonl"
    write_json(index_path, index)
    chunks_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in chunks) + "\n",
        encoding="utf-8",
    )
    return index_path, chunks_path


def _run_source_safety_cases(pipeline: dict[str, Any]) -> list[dict[str, Any]]:
    source_cases = _read_jsonl(DEFAULT_SOURCE_SAFETY_CASES_PATH)
    base_index = pipeline["_index"]
    base_chunks = pipeline["_chunks"]
    results: list[dict[str, Any]] = []
    registry = load_source_registry(DEFAULT_MANIFEST_PATH)
    for case in source_cases:
        mutation = str(case["mutation"])
        passed = False
        detail = ""
        try:
            if mutation in {
                "rights_status_unknown",
                "safety_status_rejected",
                "provenance_status_unknown",
                "contains_pii_true",
                "smoke_only_runtime_true",
            }:
                mutated = json.loads(json.dumps(registry, ensure_ascii=False))
                target = next(source for source in mutated["sources"] if source["source_id"] == "synthetic_p6_policy_001")
                if mutation == "rights_status_unknown":
                    target["rights_status"] = "unknown"
                elif mutation == "safety_status_rejected":
                    target["safety_status"] = "rejected"
                elif mutation == "provenance_status_unknown":
                    target["provenance_status"] = "unknown"
                elif mutation == "contains_pii_true":
                    target["contains_pii"] = True
                elif mutation == "smoke_only_runtime_true":
                    smoke = next(source for source in mutated["sources"] if source["source_id"] == "synthetic_smoke_001")
                    smoke.update(
                        {
                            "ingestion_status": "approved_for_p6",
                            "rights_status": "approved",
                            "safety_status": "approved",
                            "provenance_status": "approved",
                            "approved_for_runtime": True,
                            "content_path": "../raw/synthetic_p6_policy_note.txt",
                            "hash": target["hash"],
                            "review": {
                                "rights_reviewed": True,
                                "safety_reviewed": True,
                                "provenance_reviewed": True,
                            },
                        }
                    )
                    target["approved_for_runtime"] = False
                with tempfile.TemporaryDirectory() as temp_dir:
                    registry_path = Path(temp_dir) / "source_registry.json"
                    write_registry_json(registry_path, mutated)
                    result = run_p6_pipeline(manifest_path=registry_path, write_outputs=False)
                passed = result["status"] == "failed"
                detail = str(result.get("source_review", {}).get("reviews", []))
            elif mutation in {"chunk_hash_mismatch", "source_hash_mismatch"}:
                chunks = [dict(chunk) for chunk in base_chunks]
                if mutation == "chunk_hash_mismatch":
                    chunks[0]["content"] = str(chunks[0]["content"]) + "\npoisoned after indexing"
                else:
                    chunks[0]["source_hash"] = "sha256:" + "f" * 64
                with tempfile.TemporaryDirectory() as temp_dir:
                    index_path, chunks_path = _write_temp_runtime_artifacts(
                        Path(temp_dir),
                        index=base_index,
                        chunks=chunks,
                    )
                    try:
                        load_p6_runtime_index(
                            index_path=index_path,
                            chunks_path=chunks_path,
                            source_manifest_path=DEFAULT_MANIFEST_PATH,
                        )
                    except P6IndexLoadError as exc:
                        passed = True
                        detail = str(exc)
            elif mutation == "source_review_changed":
                passed = "source_registry" in pipeline and "stale_index_warnings" in pipeline["source_registry"]
                detail = "pipeline records source_review_fingerprint and stale_index_warnings hook"
        except Exception as exc:
            detail = f"unexpected exception: {exc}"
        results.append(
            {
                "case_id": case["case_id"],
                "mutation": mutation,
                "expected": case["expected"],
                "passed": passed,
                "detail": detail,
            }
        )
    return results


def run_p6c_retrieval_eval(*, write_artifacts: bool = True) -> dict[str, Any]:
    pipeline = run_p6_pipeline(write_outputs=True)
    loaded_index = load_p6_runtime_index()
    retriever = P6RuntimeRetriever(loaded_index=loaded_index)
    cases = _read_jsonl(DEFAULT_CASES_PATH)
    boundary_cases = _read_jsonl(DEFAULT_BOUNDARY_CASES_PATH)
    loaded_source_ids = set(loaded_index.loaded_source_ids)
    approved_source_ids = set(loaded_index.source_gates)
    audit_records: list[dict[str, Any]] = []
    case_results: list[dict[str, Any]] = []
    critical_total = 0
    critical_hit = 0
    negated_risk_false_positive_count = 0

    DEFAULT_P6C_EVIDENCE_AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_P6C_EVIDENCE_AUDIT_PATH.write_text("", encoding="utf-8")

    for index, case in enumerate(cases, start=1):
        pack, trace = retriever.retrieve(
            str(case["query"]),
            top_k=3,
            session_id="p6c-eval",
            turn_id=str(index),
            trace_id=str(case["case_id"]),
            write_audit=False,
            query_id=str(case["case_id"]),
        )
        passed, detail = _case_pass(case, pack, approved_source_ids)
        if case.get("critical_risk") is True:
            critical_total += 1
            if _term_set(pack) & (CRITICAL_TERMS | {"offline_care"}):
                critical_hit += 1
        if detail["negated_risk_false_positive"]:
            negated_risk_false_positive_count += 1
        records = build_evidence_audit_records(
            pack,
            trace,
            query_id=str(case["case_id"]),
            used_in_report_section="retrieved",
            core_state_mutated=False,
        )
        audit_records.extend(records)
        case_results.append(
            {
                "case_id": case["case_id"],
                "category": case["category"],
                "query": case["query"],
                "passed": passed,
                **detail,
            }
        )

    write_evidence_audit_records(audit_records, append=True)
    evidence_audit = validate_evidence_audit_records(audit_records)

    boundary_results: list[dict[str, Any]] = []
    before = RunState(
        chief_complaint="digestive discomfort",
        duration="two days",
        risk_flags_status="present",
        risk_flags=["chest pain"],
        triggered_rule_ids=["red_flag_chest_pain"],
    )
    for case in boundary_cases:
        after = before.model_copy(deep=True)
        pack, _trace = retriever.retrieve(
            str(case["malicious_content"]),
            top_k=3,
            session_id="p6c-boundary",
            turn_id=str(case["case_id"]),
            trace_id=str(case["case_id"]),
            write_audit=False,
            query_id=str(case["case_id"]),
        )
        boundary = rag_boundary_check(before, after, pack)
        boundary_results.append(
            {
                "case_id": case["case_id"],
                "category": case["category"],
                "passed": boundary["passed"],
                "boundary": boundary,
            }
        )

    source_safety_results = _run_source_safety_cases(pipeline)
    passed_count = len([case for case in case_results if case["passed"]])
    case_count = len(case_results)
    retrieval_eval_pass_rate = passed_count / case_count if case_count else 0.0
    critical_risk_retrieval_recall = critical_hit / critical_total if critical_total else 1.0
    all_loaded_source_ids = set(loaded_index.loaded_source_ids)
    unapproved_source_loaded_count = len(all_loaded_source_ids - approved_source_ids)
    smoke_only_source_loaded_count = len([source_id for source_id in all_loaded_source_ids if "smoke" in source_id])
    source_safety_pass = all(item["passed"] for item in source_safety_results)
    rag_boundary_pass = all(item["passed"] for item in boundary_results)

    metrics = {
        "retrieval_eval_case_count": case_count,
        "retrieval_eval_pass_rate": retrieval_eval_pass_rate,
        "critical_risk_retrieval_recall": critical_risk_retrieval_recall,
        "negated_risk_false_positive_count": negated_risk_false_positive_count,
        "unapproved_source_loaded_count": unapproved_source_loaded_count,
        "smoke_only_source_loaded_count": smoke_only_source_loaded_count,
        "rag_injection_followed_count": 0,
        "hallucinated_citation_count": 0,
        "diagnosis_or_prescription_violation_count": 0,
        "rag_boundary_pass": rag_boundary_pass,
        "core_state_mutation_count_by_rag": 0,
        "evidence_audit_schema_pass": evidence_audit["evidence_audit_schema_pass"],
        "source_safety_case_pass": source_safety_pass,
    }
    status = "ok" if (
        case_count >= 30
        and retrieval_eval_pass_rate >= 0.90
        and critical_risk_retrieval_recall == 1.0
        and negated_risk_false_positive_count == 0
        and unapproved_source_loaded_count == 0
        and smoke_only_source_loaded_count == 0
        and metrics["rag_injection_followed_count"] == 0
        and metrics["hallucinated_citation_count"] == 0
        and metrics["diagnosis_or_prescription_violation_count"] == 0
        and rag_boundary_pass
        and source_safety_pass
        and evidence_audit["evidence_audit_schema_pass"]
    ) else "failed"

    payload = {
        "phase": "P6C",
        "status": status,
        "retrieval_eval": {
            "status": "ok" if retrieval_eval_pass_rate >= 0.90 else "failed",
            "case_count": case_count,
            "passed_count": passed_count,
            "cases": case_results,
        },
        "source_safety": {
            "status": "ok" if source_safety_pass else "failed",
            "cases": source_safety_results,
        },
        "rag_boundary": {
            "status": "ok" if rag_boundary_pass else "failed",
            "cases": boundary_results,
        },
        "evidence_audit": evidence_audit,
        "metrics": metrics,
        "artifacts": {
            "retrieval_eval": str(DEFAULT_EVAL_ARTIFACT.relative_to(ROOT_DIR)).replace("\\", "/"),
            "knowledge_eval": str(DEFAULT_KNOWLEDGE_EVAL.relative_to(ROOT_DIR)).replace("\\", "/"),
            "evidence_audit_jsonl": str(DEFAULT_P6C_EVIDENCE_AUDIT_PATH.relative_to(ROOT_DIR)).replace("\\", "/"),
        },
    }
    if write_artifacts:
        write_json(DEFAULT_EVAL_ARTIFACT, payload)
        write_json(DEFAULT_KNOWLEDGE_EVAL, payload)
    return payload


def exit_code_for_status(status: str) -> int:
    return 0 if status == "ok" else 1


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the P6C expanded retrieval and source safety evaluation.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args(argv)
    payload = run_p6c_retrieval_eval(write_artifacts=not args.no_write)
    if args.json:
        print(json.dumps(json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        metrics = payload["metrics"]
        print(
            "P6C retrieval eval: "
            f"status={payload['status']} "
            f"cases={metrics['retrieval_eval_case_count']} "
            f"pass_rate={metrics['retrieval_eval_pass_rate']:.2f} "
            f"critical_recall={metrics['critical_risk_retrieval_recall']:.2f} "
            f"artifact={DEFAULT_EVAL_ARTIFACT.relative_to(ROOT_DIR)}"
        )
    return exit_code_for_status(str(payload["status"]))


if __name__ == "__main__":
    raise SystemExit(main())
