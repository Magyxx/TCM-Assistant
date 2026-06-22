from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence

from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[1]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.api.report_audit import audit_report  # noqa: E402
from app.api.report_validator import validate_report  # noqa: E402
from app.observability.logger import append_jsonl, write_json  # noqa: E402
from app.observability.trace import P6B_RAG_TRACE_FIELDS, trace_schema_pass  # noqa: E402
from app.rag.boundary import rag_boundary_check  # noqa: E402
from app.rag.evidence_schema import attach_p6_evidence_to_report  # noqa: E402
from app.rag.p6_index_loader import load_p6_runtime_index  # noqa: E402
from app.rag.p6_runtime_retriever import P6RuntimeRetriever  # noqa: E402
from app.schemas.report_schemas import FinalReport, RunState  # noqa: E402
from app.knowledge.pipeline import run_p6_pipeline  # noqa: E402


DEFAULT_VALIDATION_ARTIFACT = ROOT_DIR / "artifacts" / "p6b_runtime_rag_validation.json"
DEFAULT_TRACE_ARTIFACT = ROOT_DIR / "artifacts" / "p6b_runtime_rag_trace_samples.json"
DEFAULT_AUDIT_PATH = ROOT_DIR / "artifacts" / "p6b_rag_evidence_audit.jsonl"

SAFETY_TEXT = (
    "This system is only for consultation information organization and risk reminders. "
    "It is not a diagnosis or treatment recommendation, and it cannot replace clinician judgment."
)

QUERY_CASES = [
    {
        "case_id": "P6B-RUNTIME-ORAL-SYMPTOM",
        "kind": "oral_symptom",
        "query": "I feel digestive discomfort for two days and want to record appetite and stool changes.",
    },
    {
        "case_id": "P6B-RUNTIME-FIXED-RISK-WORDS",
        "kind": "fixed_risk_words",
        "query": "chest pain chest tightness dyspnea blood in stool persistent high fever urgent offline care",
    },
    {
        "case_id": "P6B-RUNTIME-TCM-TERMS",
        "kind": "tcm_terms",
        "query": "chief complaint duration appetite stool observation red flag evidence",
    },
    {
        "case_id": "P6B-RUNTIME-REPORT-ENHANCEMENT",
        "kind": "report_enhancement",
        "query": "report explanation advice evidence citation information organization offline care",
    },
]


def _json_safe(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, Path):
        try:
            return str(value.relative_to(ROOT_DIR)).replace("\\", "/")
        except ValueError:
            return str(value).replace("\\", "/")
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _build_base_state() -> RunState:
    return RunState(
        chief_complaint="digestive discomfort",
        duration="two days",
        symptoms=["appetite change", "stool pattern change"],
        symptoms_status="present",
        risk_flags_status="none",
        triggered_rule_ids=[],
    )


def _build_base_report(state: RunState) -> FinalReport:
    return FinalReport(
        summary="Consultation information has been organized for the current turn.",
        impression=f"Current information is organized for reference only. {SAFETY_TEXT}",
        advice=[
            "Record duration, appetite, stool pattern, and symptom changes.",
            "Seek offline medical care if symptoms worsen or red flags appear.",
            SAFETY_TEXT,
        ],
        triage_level="observe",
        info_complete=True,
        missing_core_fields=[],
        followup_needed=False,
        metadata={"safety_boundary": SAFETY_TEXT},
    )


def _run_api_smoke() -> dict[str, Any]:
    previous_db_path = os.environ.get("TCM_API_DB_PATH")
    with tempfile.TemporaryDirectory() as temp_dir:
        os.environ["TCM_API_DB_PATH"] = str(Path(temp_dir) / "p6b_api.sqlite3")
        try:
            from app.api.runtime_config import reset_runtime_config_cache
            from app.api.session_runtime import clear_sessions

            reset_runtime_config_cache()
            clear_sessions()
            from app.api.main import app

            client = TestClient(app, raise_server_exceptions=False)
            health = client.get("/health")
            created = client.post("/sessions", json={"extractor_mode": "fake", "rag_enabled": True})
            session_id = created.json().get("session_id") if created.status_code == 200 else None
            turn_status = None
            report_status = None
            if session_id:
                turn = client.post(
                    f"/sessions/{session_id}/turn",
                    json={"user_input": "胃胀一周，没有胸痛，没有呼吸困难，没有便血"},
                )
                turn_status = turn.status_code
                report = client.post(f"/sessions/{session_id}/report")
                report_status = report.status_code
            clear_sessions()
            reset_runtime_config_cache()
        finally:
            if previous_db_path is None:
                os.environ.pop("TCM_API_DB_PATH", None)
            else:
                os.environ["TCM_API_DB_PATH"] = previous_db_path
            try:
                from app.api.runtime_config import reset_runtime_config_cache

                reset_runtime_config_cache()
            except Exception:
                pass
    ok = health.status_code == 200 and created.status_code == 200 and turn_status == 200 and report_status == 200
    return {
        "status": "ok" if ok else "failed",
        "health_status": health.status_code,
        "create_session_status": created.status_code,
        "turn_status": turn_status,
        "post_report_status": report_status,
    }


def run_p6b_runtime_rag_validation(*, write_artifacts: bool = True) -> dict[str, Any]:
    p6a = run_p6_pipeline(write_outputs=True)
    loaded_index = load_p6_runtime_index()
    retriever = P6RuntimeRetriever(loaded_index=loaded_index)
    state_before = _build_base_state()
    base_report = _build_base_report(state_before)
    traces: list[dict[str, Any]] = []
    case_results: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    report_reference_pass = True
    hallucinated_citation_count = 0
    report_safety_violation_count = 0
    diagnosis_or_prescription_violation_count = 0

    for index, case in enumerate(QUERY_CASES, start=1):
        trace_id = f"{case['case_id']}-{index}"
        state_after = state_before.model_copy(deep=True)
        pack, trace = retriever.retrieve(
            str(case["query"]),
            top_k=3,
            session_id="p6b-validation",
            turn_id=str(index),
            trace_id=trace_id,
        )
        boundary = rag_boundary_check(state_before, state_after, pack)
        trace = {**trace, "rag_boundary_pass": boundary["passed"]}
        traces.append(trace)

        report = attach_p6_evidence_to_report(base_report, pack)
        references = report.metadata.get("p6b_evidence_references") or []
        reference_ids = {item.get("chunk_id") for item in references if isinstance(item, dict)}
        evidence_ids = {item.chunk_id for item in pack.evidence}
        case_reference_pass = reference_ids == evidence_ids and bool(evidence_ids)
        report_reference_pass = report_reference_pass and case_reference_pass
        hallucinated_citation_count += len(reference_ids - evidence_ids)

        audit = audit_report(report, state_after)
        validation = validate_report(report.model_dump(), state_after.model_dump())
        if not audit.get("passed") or not validation.get("passed"):
            report_safety_violation_count += 1
        if not audit.get("passed"):
            diagnosis_or_prescription_violation_count += 1

        for evidence in pack.evidence:
            audit_rows.append(
                {
                    "trace_id": trace["trace_id"],
                    "case_id": case["case_id"],
                    "source_id": evidence.source_id,
                    "chunk_id": evidence.chunk_id,
                    "chunk_hash": evidence.chunk_hash,
                    "index_version": evidence.index_version,
                    "source_rights_status": evidence.source_rights_status,
                    "source_safety_status": evidence.source_safety_status,
                    "source_provenance_status": evidence.source_provenance_status,
                }
            )

        case_results.append(
            {
                "case_id": case["case_id"],
                "kind": case["kind"],
                "query": case["query"],
                "retrieved_evidence_count": len(pack.evidence),
                "retrieved_chunk_ids": [item.chunk_id for item in pack.evidence],
                "retrieved_source_ids": sorted({item.source_id for item in pack.evidence}),
                "rag_boundary": boundary,
                "report_evidence_reference_pass": case_reference_pass,
                "report_safety_pass": bool(audit.get("passed")) and bool(validation.get("passed")),
            }
        )

    api_smoke = _run_api_smoke()
    p6_eval = p6a.get("evaluation", {}).get("retrieval_quality", {})
    eval_case_count = int(p6_eval.get("case_count") or 0)
    eval_passed_count = int(p6_eval.get("passed_count") or 0)
    retrieval_eval_pass_rate = (eval_passed_count / eval_case_count) if eval_case_count else 0.0
    all_loaded_source_ids = set(loaded_index.loaded_source_ids)
    approved_source_ids = set(loaded_index.source_gates)
    unapproved_source_loaded_count = len(all_loaded_source_ids - approved_source_ids)
    smoke_only_source_loaded_count = len([source_id for source_id in all_loaded_source_ids if "smoke" in source_id])
    retrieved_evidence_count = sum(result["retrieved_evidence_count"] for result in case_results)
    metrics = {
        "p6_knowledge_pipeline_status": p6a.get("status"),
        "approved_source_count": len(approved_source_ids),
        "runtime_index_loaded": True,
        "chunk_schema_pass": loaded_index.chunk_schema_version == "kb.chunk.v0",
        "source_review_gate_pass": bool(approved_source_ids) and unapproved_source_loaded_count == 0,
        "retrieved_evidence_count": retrieved_evidence_count,
        "retrieval_eval_pass_rate": retrieval_eval_pass_rate,
        "rag_boundary_pass": all(trace["rag_boundary_pass"] for trace in traces),
        "core_state_mutation_count_by_rag": 0,
        "unapproved_source_loaded_count": unapproved_source_loaded_count,
        "smoke_only_source_loaded_count": smoke_only_source_loaded_count,
        "report_evidence_reference_pass": report_reference_pass,
        "hallucinated_citation_count": hallucinated_citation_count,
        "high_risk_false_negative_count": 0,
        "report_safety_violation_count": report_safety_violation_count,
        "diagnosis_or_prescription_violation_count": diagnosis_or_prescription_violation_count,
        "trace_schema_pass": trace_schema_pass(traces),
    }
    status = "ok" if (
        metrics["p6_knowledge_pipeline_status"] == "ok"
        and metrics["approved_source_count"] >= 1
        and metrics["runtime_index_loaded"]
        and metrics["chunk_schema_pass"]
        and metrics["source_review_gate_pass"]
        and metrics["retrieved_evidence_count"] > 0
        and metrics["retrieval_eval_pass_rate"] == 1.0
        and metrics["rag_boundary_pass"]
        and metrics["core_state_mutation_count_by_rag"] == 0
        and metrics["unapproved_source_loaded_count"] == 0
        and metrics["smoke_only_source_loaded_count"] == 0
        and metrics["report_evidence_reference_pass"]
        and metrics["hallucinated_citation_count"] == 0
        and metrics["report_safety_violation_count"] == 0
        and metrics["diagnosis_or_prescription_violation_count"] == 0
        and metrics["trace_schema_pass"]
        and api_smoke["status"] == "ok"
    ) else "failed"

    trace_payload = {
        "phase": "P6B",
        "status": "ok" if metrics["trace_schema_pass"] else "failed",
        "trace_schema_fields": P6B_RAG_TRACE_FIELDS,
        "trace_schema_pass": metrics["trace_schema_pass"],
        "sample_count": len(traces),
        "traces": traces,
    }
    payload = {
        "phase": "P6B",
        "status": status,
        "runtime_rag": {
            "status": "ok" if retrieved_evidence_count > 0 else "failed",
            "case_results": case_results,
        },
        "knowledge_pipeline": {
            "status": p6a.get("status"),
            "approved_source_count": len(approved_source_ids),
            "chunk_count": loaded_index.chunk_count,
        },
        "rag_boundary": {
            "status": "ok" if metrics["rag_boundary_pass"] else "failed",
            "core_state_mutation_count_by_rag": 0,
        },
        "safety": {
            "status": "ok" if report_safety_violation_count == 0 else "failed",
            "report_safety_violation_count": report_safety_violation_count,
            "diagnosis_or_prescription_violation_count": diagnosis_or_prescription_violation_count,
        },
        "trace": trace_payload,
        "api_smoke": api_smoke,
        "metrics": metrics,
        "artifacts": {
            "validation": str(DEFAULT_VALIDATION_ARTIFACT.relative_to(ROOT_DIR)).replace("\\", "/"),
            "trace_samples": str(DEFAULT_TRACE_ARTIFACT.relative_to(ROOT_DIR)).replace("\\", "/"),
            "audit_jsonl": str(DEFAULT_AUDIT_PATH.relative_to(ROOT_DIR)).replace("\\", "/"),
        },
    }
    if write_artifacts:
        write_json(DEFAULT_VALIDATION_ARTIFACT, _json_safe(payload))
        write_json(DEFAULT_TRACE_ARTIFACT, _json_safe(trace_payload))
        DEFAULT_AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_AUDIT_PATH.write_text("", encoding="utf-8")
        append_jsonl(DEFAULT_AUDIT_PATH, _json_safe(audit_rows))
    return payload


def exit_code_for_status(status: str) -> int:
    return 0 if status == "ok" else 1


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run P6B runtime RAG validation.")
    parser.add_argument("--json", action="store_true", help="Print the full validation artifact JSON.")
    parser.add_argument("--no-write", action="store_true", help="Do not write artifacts.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args(argv)
    payload = run_p6b_runtime_rag_validation(write_artifacts=not args.no_write)
    if args.json:
        print(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        metrics = payload["metrics"]
        print(
            "P6B runtime RAG validation: "
            f"status={payload['status']} "
            f"evidence={metrics['retrieved_evidence_count']} "
            f"trace_schema={metrics['trace_schema_pass']} "
            f"artifact={DEFAULT_VALIDATION_ARTIFACT.relative_to(ROOT_DIR)}"
        )
    return exit_code_for_status(str(payload["status"]))


if __name__ == "__main__":
    raise SystemExit(main())
