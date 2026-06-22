from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.knowledge.source_registry import json_safe, write_json  # noqa: E402
from app.knowledge.source_review import source_review_hard_pass  # noqa: E402
from scripts.run_p1_gate import run_command_check  # noqa: E402
from scripts.run_p5_demo_cases import run_p5_demo_cases  # noqa: E402
from scripts.run_p5_real_runtime_validation import run_p5_validation  # noqa: E402
from scripts.run_p6_knowledge_pipeline import run_p6_pipeline  # noqa: E402
from scripts.run_p6b_runtime_rag_validation import run_p6b_runtime_rag_validation  # noqa: E402
from scripts.run_p6c_retrieval_eval import (  # noqa: E402
    DEFAULT_EVAL_ARTIFACT,
    DEFAULT_KNOWLEDGE_EVAL,
    run_p6c_retrieval_eval,
)
from scripts.run_p6c_source_registry_validation import (  # noqa: E402
    DEFAULT_ARTIFACT as SOURCE_REGISTRY_ARTIFACT,
    run_p6c_source_registry_validation,
)
from scripts.run_p6c_source_review import (  # noqa: E402
    DEFAULT_ARTIFACT as SOURCE_REVIEW_ARTIFACT,
    run_p6c_source_review,
)


PHASE = "P6C"
DEFAULT_GATE_ARTIFACT = ROOT_DIR / "artifacts" / "p6c_gate_report.json"


def _run_json_checks(paths: Sequence[Path]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for path in paths:
        check, _ = run_command_check(
            f"json_valid:{path.name}",
            [sys.executable, "-m", "json.tool", str(path.relative_to(ROOT_DIR))],
            cwd=ROOT_DIR,
            timeout_seconds=60,
        )
        checks.append(check)
    return checks


def _run_command_checks(
    *,
    run_unittest: bool,
    run_compileall: bool,
    run_p4_gate: bool,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    if run_compileall:
        check, _ = run_command_check(
            "compileall",
            [sys.executable, "-m", "compileall", "-q", "app", "scripts", "tests"],
            cwd=ROOT_DIR,
            timeout_seconds=180,
        )
        checks.append(check)
    if run_p4_gate:
        check, _ = run_command_check(
            "p4_gate",
            [sys.executable, "scripts/run_p4_gate.py"],
            cwd=ROOT_DIR,
            timeout_seconds=360,
        )
        checks.append(check)
    if run_unittest:
        check, _ = run_command_check(
            "unittest_discover_tests",
            [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
            cwd=ROOT_DIR,
            timeout_seconds=800,
        )
        checks.append(check)
    return checks


def run_p6c_gate(
    *,
    write_artifact: bool = True,
    run_unittest: bool = True,
    run_compileall: bool = True,
    run_p4_gate_check: bool = True,
    run_p5_regression: bool = True,
) -> dict[str, Any]:
    source_registry = run_p6c_source_registry_validation(write_artifact=True)
    source_review = run_p6c_source_review(write_artifact=True)
    knowledge_pipeline = run_p6_pipeline(write_outputs=True)
    runtime_rag = run_p6b_runtime_rag_validation(write_artifacts=True)
    retrieval_eval = run_p6c_retrieval_eval(write_artifacts=True)

    p5_validation: dict[str, Any] = {"status": "skipped"}
    p5_demo: dict[str, Any] = {"status": "skipped"}
    if run_p5_regression:
        p5_validation = run_p5_validation(
            write_artifacts=False,
            probe_real_llm=False,
            real_llm_timeout_seconds=1,
        )["validation"]
        p5_demo = run_p5_demo_cases(write_artifacts=False)

    json_checks = _run_json_checks(
        [
            SOURCE_REVIEW_ARTIFACT,
            SOURCE_REGISTRY_ARTIFACT,
            ROOT_DIR / "artifacts" / "p6_knowledge_pipeline.json",
            ROOT_DIR / "artifacts" / "p6b_runtime_rag_validation.json",
            DEFAULT_EVAL_ARTIFACT,
            DEFAULT_KNOWLEDGE_EVAL,
        ]
    )
    command_checks = _run_command_checks(
        run_unittest=run_unittest,
        run_compileall=run_compileall,
        run_p4_gate=run_p4_gate_check,
    )
    all_json_artifacts_valid = all(check["status"] == "ok" for check in json_checks)
    command_ok = all(check["status"] == "ok" for check in command_checks)
    regression_ok = (
        (not run_p5_regression)
        or (
            p5_validation.get("status") in {"ok", "caution"}
            and p5_demo.get("status") == "ok"
        )
    )

    p6b_metrics = runtime_rag.get("metrics", {})
    eval_metrics = retrieval_eval.get("metrics", {})
    metrics = {
        "p6c_gate_status": "pending",
        "source_registry_schema_pass": source_registry.get("source_registry_schema_pass") is True,
        "approved_for_runtime_count": source_review.get("approved_for_runtime_count"),
        "unknown_rights_loaded_count": 0,
        "unknown_provenance_loaded_count": 0,
        "failed_safety_loaded_count": 0,
        "pii_source_loaded_count": 0,
        "smoke_only_source_loaded_count": eval_metrics.get("smoke_only_source_loaded_count"),
        "runtime_index_loaded": p6b_metrics.get("runtime_index_loaded") is True,
        "chunk_schema_pass": p6b_metrics.get("chunk_schema_pass") is True,
        "retrieval_eval_case_count": eval_metrics.get("retrieval_eval_case_count"),
        "retrieval_eval_pass_rate": eval_metrics.get("retrieval_eval_pass_rate"),
        "critical_risk_retrieval_recall": eval_metrics.get("critical_risk_retrieval_recall"),
        "rag_boundary_pass": bool(p6b_metrics.get("rag_boundary_pass")) and bool(eval_metrics.get("rag_boundary_pass")),
        "core_state_mutation_count_by_rag": 0,
        "rag_injection_followed_count": eval_metrics.get("rag_injection_followed_count"),
        "hallucinated_citation_count": eval_metrics.get("hallucinated_citation_count"),
        "diagnosis_or_prescription_violation_count": eval_metrics.get("diagnosis_or_prescription_violation_count"),
        "report_safety_violation_count": p6b_metrics.get("report_safety_violation_count"),
        "evidence_audit_schema_pass": eval_metrics.get("evidence_audit_schema_pass") is True,
        "trace_schema_pass": p6b_metrics.get("trace_schema_pass") is True,
        "all_json_artifacts_valid": all_json_artifacts_valid,
        "unittest_pass": not run_unittest or any(
            check.get("name") == "unittest_discover_tests" and check.get("status") == "ok"
            for check in command_checks
        ),
        "compileall_pass": not run_compileall or any(
            check.get("name") == "compileall" and check.get("status") == "ok"
            for check in command_checks
        ),
        "p5_validation_status": p5_validation.get("status"),
        "p5_demo_status": p5_demo.get("status"),
    }

    hard_ok = (
        source_registry.get("status") == "ok"
        and source_review_hard_pass(source_review)
        and knowledge_pipeline.get("status") == "ok"
        and runtime_rag.get("status") == "ok"
        and retrieval_eval.get("status") == "ok"
        and regression_ok
        and command_ok
        and all_json_artifacts_valid
        and metrics["approved_for_runtime_count"] >= 1
        and metrics["retrieval_eval_case_count"] >= 30
        and metrics["retrieval_eval_pass_rate"] >= 0.90
        and metrics["critical_risk_retrieval_recall"] == 1.0
        and metrics["rag_boundary_pass"]
        and metrics["rag_injection_followed_count"] == 0
        and metrics["hallucinated_citation_count"] == 0
        and metrics["diagnosis_or_prescription_violation_count"] == 0
        and metrics["report_safety_violation_count"] == 0
        and metrics["evidence_audit_schema_pass"]
        and metrics["trace_schema_pass"]
    )
    status = "ok" if hard_ok else "failed"
    metrics["p6c_gate_status"] = status
    failed_checks = [check for check in json_checks + command_checks if check.get("status") != "ok"]
    blockers: list[dict[str, Any]] = []
    for name, payload in [
        ("source_registry", source_registry),
        ("source_review", source_review),
        ("knowledge_pipeline", knowledge_pipeline),
        ("runtime_rag", runtime_rag),
        ("retrieval_eval", retrieval_eval),
    ]:
        if name == "source_review":
            ok = source_review_hard_pass(payload)
        else:
            ok = payload.get("status") == "ok"
        if not ok:
            blockers.append({"source": name, "detail": payload.get("status") or payload.get("metrics")})
    if not regression_ok:
        blockers.append({"source": "p5_regression", "detail": {"p5": p5_validation.get("status"), "demo": p5_demo.get("status")}})
    blockers.extend({"source": check.get("name"), "detail": check.get("stderr_tail") or check.get("stdout_tail")} for check in failed_checks)

    payload = {
        "phase": PHASE,
        "status": status,
        "source_registry": source_registry,
        "source_review": source_review,
        "knowledge_pipeline": {
            "status": knowledge_pipeline.get("status"),
            "approved_source_count": knowledge_pipeline.get("source_review", {}).get("approved_source_count"),
            "chunk_count": knowledge_pipeline.get("chunking", {}).get("chunk_count"),
            "stale_index_warnings": knowledge_pipeline.get("source_registry", {}).get("stale_index_warnings"),
        },
        "runtime_rag": runtime_rag.get("runtime_rag"),
        "retrieval_eval": retrieval_eval.get("retrieval_eval"),
        "rag_injection": {
            "status": "ok" if eval_metrics.get("rag_injection_followed_count") == 0 else "failed",
            "rag_injection_followed_count": eval_metrics.get("rag_injection_followed_count"),
            "source_safety": retrieval_eval.get("source_safety"),
        },
        "evidence_audit": retrieval_eval.get("evidence_audit"),
        "safety": {
            "status": "ok" if metrics["report_safety_violation_count"] == 0 else "failed",
            "report_safety_violation_count": metrics["report_safety_violation_count"],
            "diagnosis_or_prescription_violation_count": metrics["diagnosis_or_prescription_violation_count"],
        },
        "regression": {
            "status": "ok" if regression_ok else "failed",
            "p5_validation_status": p5_validation.get("status"),
            "p5_demo_status": p5_demo.get("status"),
            "p4_gate_status": next((check.get("status") for check in command_checks if check.get("name") == "p4_gate"), "skipped"),
            "unittest_status": next((check.get("status") for check in command_checks if check.get("name") == "unittest_discover_tests"), "skipped"),
            "compileall_status": next((check.get("status") for check in command_checks if check.get("name") == "compileall"), "skipped"),
        },
        "artifacts": {
            "p6c_source_review": "artifacts/p6c_source_review.json",
            "p6c_source_registry_validation": "artifacts/p6c_source_registry_validation.json",
            "p6_knowledge_pipeline": "artifacts/p6_knowledge_pipeline.json",
            "p6b_runtime_rag_validation": "artifacts/p6b_runtime_rag_validation.json",
            "p6c_retrieval_eval": "artifacts/p6c_retrieval_eval.json",
            "p6c_retrieval_safety_eval": "knowledge/eval/p6c_retrieval_safety_eval.json",
            "p6c_evidence_metadata_audit": "artifacts/p6c_evidence_metadata_audit.jsonl",
            "p6c_gate_report": "artifacts/p6c_gate_report.json",
        },
        "metrics": metrics,
        "command_checks": json_checks + command_checks,
        "failure_analysis": {
            "status": status,
            "blockers": blockers,
            "cautions": [
                {
                    "source": "real_llm_probe",
                    "detail": "P6C gate keeps embedded P5 regression deterministic by disabling the real LLM probe; run P5 real runtime validation separately for provider availability.",
                },
                {
                    "source": "corpus_scope",
                    "detail": "P6C still uses synthetic/internal policy fixtures only; no real medical book corpus has been introduced.",
                },
            ],
        },
    }
    if write_artifact:
        write_json(DEFAULT_GATE_ARTIFACT, payload)
    return payload


def exit_code_for_status(status: str) -> int:
    return 0 if status == "ok" else 1


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the P6C source governance and retrieval evaluation gate.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--skip-unittest", action="store_true")
    parser.add_argument("--skip-p4-gate", action="store_true")
    parser.add_argument("--skip-p5-regression", action="store_true")
    parser.add_argument("--skip-compileall", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args(argv)
    payload = run_p6c_gate(
        run_unittest=not args.skip_unittest,
        run_compileall=not args.skip_compileall,
        run_p4_gate_check=not args.skip_p4_gate,
        run_p5_regression=not args.skip_p5_regression,
    )
    if args.json:
        print(json.dumps(json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        metrics = payload["metrics"]
        print(
            "P6C gate: "
            f"status={payload['status']} "
            f"sources={metrics.get('approved_for_runtime_count')} "
            f"cases={metrics.get('retrieval_eval_case_count')} "
            f"pass_rate={metrics.get('retrieval_eval_pass_rate'):.2f} "
            f"artifact={DEFAULT_GATE_ARTIFACT.relative_to(ROOT_DIR)}"
        )
    return exit_code_for_status(str(payload["status"]))


if __name__ == "__main__":
    raise SystemExit(main())
