from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.api.report_audit import audit_report
from app.chains.turn_extractor import extract_turn, get_missing_api_config
from app.graphs.consultation_graph import build_consultation_graph, run_consultation_graph
from app.rag.evidence_boundary import (
    attach_evidence_pack,
    build_evidence_pack,
    core_state_snapshot,
)
from app.safety.report_safety import safety_post_check_report
from app.schemas.report_schemas import FinalReport, RunState
from scripts.run_p4_gate import run_p4_gate


PHASE = "P5"
DEFAULT_VALIDATION_ARTIFACT = ROOT_DIR / "artifacts" / "p5_real_runtime_validation.json"
DEFAULT_TRACE_ARTIFACT = ROOT_DIR / "artifacts" / "p5_trace_samples.json"
DEFAULT_FAILURE_ARTIFACT = ROOT_DIR / "artifacts" / "p5_failure_analysis.json"
CODE_HEALTH_ARTIFACT = ROOT_DIR / "artifacts" / "code_health_gate_baseline.json"

TRACE_FIELDS = [
    "trace_id",
    "session_id",
    "turn_id",
    "case_id",
    "graph_runtime",
    "extractor_mode",
    "raw_llm_json_valid",
    "schema_pass",
    "fallback_used",
    "fallback_reason",
    "risk_status",
    "risk_rule_ids",
    "risk_reasons",
    "retrieved_evidence_count",
    "retrieved_chunk_ids",
    "rag_boundary_pass",
    "final_report_schema_pass",
    "safety_rewrite_used",
    "diagnosis_or_prescription_violation",
    "state_loss_detected",
    "repeated_question_detected",
    "latency_ms",
    "error",
]

CHANGED_FILES = [
    "app/chains/turn_extractor.py",
    "app/chains/report_chain.py",
    "scripts/run_p5_real_runtime_validation.py",
    "scripts/run_p5_demo_cases.py",
    "docs/P5_REAL_RUNTIME_DESIGN.md",
    "docs/PHASE5_REAL_RUNTIME_VALIDATION.md",
    "artifacts/p5_real_runtime_validation.json",
    "artifacts/p5_demo_results.json",
    "artifacts/p5_trace_samples.json",
    "artifacts/p5_failure_analysis.json",
    "tests/test_p5_real_runtime_validation.py",
    "tests/test_p5_rag_boundary.py",
    "tests/test_p5_extractor_modes.py",
    "tests/test_p5_multiturn_runtime.py",
]


GRAPH_RUNTIME_CASES: list[dict[str, Any]] = [
    {
        "case_id": "P5-GRAPH-01",
        "description": "LangGraph fake extractor asks follow-up for missing duration.",
        "user_input": "胃胀饭后明显",
        "extractor_mode": "fake",
        "rag_enabled": False,
        "initial_state": RunState(),
        "expect": {
            "graph_runtime": "langgraph",
            "extractor_mode": "fake",
            "chief_complaint_not_null": True,
            "duration_is_null": True,
            "final_report_exists": False,
            "next_question_contains_any": ["多久", "持续"],
        },
    },
    {
        "case_id": "P5-GRAPH-02",
        "description": "LangGraph fake extractor completes a low-risk report with BM25 evidence.",
        "user_input": "胃胀一周，没有其他症状，也没有胸痛，没有呼吸困难，没有便血",
        "extractor_mode": "fake",
        "rag_enabled": True,
        "initial_state": RunState(),
        "expect": {
            "graph_runtime": "langgraph",
            "extractor_mode": "fake",
            "duration_not_null": True,
            "risk_flags_status": "none",
            "final_report_exists": True,
            "triage_level": "observe",
            "retrieved_evidence_min": 1,
        },
    },
    {
        "case_id": "P5-GRAPH-03",
        "description": "Rule fallback keeps high-risk chest and dyspnea sticky.",
        "user_input": "胸痛、胸闷、喘不上气",
        "extractor_mode": "fallback",
        "rag_enabled": True,
        "initial_state": RunState(),
        "high_risk_expected": True,
        "expect": {
            "graph_runtime": "langgraph",
            "extractor_mode": "fallback",
            "fallback_used": True,
            "risk_flags_status": "present",
            "risk_rule_ids_include": ["P0_RISK_CHEST_PAIN", "P0_RISK_DYSPNEA"],
            "final_report_exists": True,
            "triage_level": "urgent_visit",
        },
    },
    {
        "case_id": "P5-GRAPH-04",
        "description": "Negated red flags do not become present.",
        "user_input": "没有发热，也不胸痛，没有便血",
        "extractor_mode": "fallback",
        "rag_enabled": True,
        "initial_state": RunState(
            chief_complaint="胃胀",
            duration="一周",
            symptoms_status="none",
        ),
        "expect": {
            "graph_runtime": "langgraph",
            "extractor_mode": "fallback",
            "fallback_used": True,
            "risk_flags_status": "none",
            "risk_rule_ids_absent": [
                "P0_RISK_CHEST_PAIN",
                "P0_RISK_HIGH_FEVER",
                "P0_RISK_GI_BLEEDING",
            ],
            "final_report_exists": True,
            "triage_level": "observe",
        },
    },
    {
        "case_id": "P5-GRAPH-05",
        "description": "GI bleeding triggers risk rule ids and urgent report.",
        "user_input": "最近便血",
        "extractor_mode": "fallback",
        "rag_enabled": True,
        "initial_state": RunState(),
        "high_risk_expected": True,
        "expect": {
            "graph_runtime": "langgraph",
            "extractor_mode": "fallback",
            "fallback_used": True,
            "risk_flags_status": "present",
            "risk_rule_ids_include": ["P0_RISK_GI_BLEEDING"],
            "final_report_exists": True,
            "triage_level": "urgent_visit",
        },
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def json_safe(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def status_check(name: str, ok: bool, detail: str = "", extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": name,
        "ok": bool(ok),
        "status": "ok" if ok else "failed",
        "detail": detail,
    }
    if extra:
        payload["extra"] = extra
    return payload


def report_schema_pass(report: Any) -> bool:
    if report is None:
        return False
    try:
        FinalReport.model_validate(report.model_dump() if hasattr(report, "model_dump") else report)
        return True
    except Exception:
        return False


def extract_evidence_from_graph(graph_state: dict[str, Any]) -> list[dict[str, Any]]:
    evidence = graph_state.get("retrieved_evidence") or []
    if evidence:
        return [json_safe(item) for item in evidence]
    run_state = graph_state.get("run_state")
    report = getattr(run_state, "final_report", None) if run_state is not None else None
    metadata = getattr(report, "metadata", {}) if report is not None else {}
    pack = metadata.get("p4_rag_evidence_pack") if isinstance(metadata, dict) else None
    if isinstance(pack, dict):
        return [json_safe(item) for item in pack.get("evidence") or []]
    return []


def rag_boundary_pass_for_graph(graph_state: dict[str, Any]) -> bool:
    run_state = graph_state.get("run_state")
    report = getattr(run_state, "final_report", None) if run_state is not None else None
    if report is None:
        return True
    metadata = getattr(report, "metadata", {}) or {}
    if "rag_core_state_readonly" not in metadata:
        return True
    forbidden = metadata.get("rag_forbidden_state_writes") or []
    return metadata.get("rag_core_state_readonly") is True and all(
        field in forbidden
        for field in ["chief_complaint", "duration", "risk_status", "risk_rule_ids"]
    )


def make_trace(
    *,
    case_id: str,
    session_id: str,
    turn_id: int,
    graph_state: dict[str, Any],
    latency_ms: int,
    state_loss_detected: bool = False,
    repeated_question_detected: bool = False,
    error: str | None = None,
) -> dict[str, Any]:
    run_state = graph_state.get("run_state")
    report = getattr(run_state, "final_report", None) if run_state is not None else None
    evidence = extract_evidence_from_graph(graph_state)
    safety_issues = graph_state.get("safety_issues") or []
    audit = audit_report(report, run_state) if report is not None else {"passed": True, "flags": []}
    errors = list(graph_state.get("errors") or [])
    fallback_reason = graph_state.get("error_type")
    if not fallback_reason and errors:
        fallback_reason = errors[-1]
    trace = {
        "trace_id": f"{case_id}-{turn_id}-{uuid.uuid4().hex[:10]}",
        "session_id": session_id,
        "turn_id": turn_id,
        "case_id": case_id,
        "graph_runtime": graph_state.get("graph_runtime"),
        "extractor_mode": graph_state.get("extractor_mode"),
        "raw_llm_json_valid": graph_state.get("raw_llm_json_valid"),
        "schema_pass": graph_state.get("schema_valid"),
        "fallback_used": graph_state.get("fallback_used"),
        "fallback_reason": fallback_reason,
        "risk_status": getattr(run_state, "risk_flags_status", None),
        "risk_rule_ids": list(getattr(run_state, "triggered_rule_ids", []) or []),
        "risk_reasons": list(getattr(run_state, "risk_reasons", []) or []),
        "retrieved_evidence_count": len(evidence),
        "retrieved_chunk_ids": [item.get("chunk_id") for item in evidence if isinstance(item, dict)],
        "rag_boundary_pass": rag_boundary_pass_for_graph(graph_state),
        "final_report_schema_pass": report_schema_pass(report),
        "safety_rewrite_used": bool(safety_issues),
        "diagnosis_or_prescription_violation": not bool(audit.get("passed")),
        "state_loss_detected": bool(state_loss_detected),
        "repeated_question_detected": bool(repeated_question_detected),
        "latency_ms": latency_ms,
        "error": error or ("; ".join(errors) if errors else None),
    }
    return {field: trace.get(field) for field in TRACE_FIELDS}


def trace_field_completeness_pass(traces: Sequence[dict[str, Any]]) -> bool:
    return all(all(field in trace for field in TRACE_FIELDS) for trace in traces)


def validate_graph_expectations(
    case: dict[str, Any],
    graph_state: dict[str, Any] | None,
    trace: dict[str, Any],
) -> list[dict[str, Any]]:
    expected = case.get("expect", {})
    run_state = graph_state.get("run_state") if graph_state else None
    report = getattr(run_state, "final_report", None) if run_state is not None else None
    checks: list[dict[str, Any]] = []

    if "graph_runtime" in expected:
        checks.append(status_check("graph_runtime", graph_state.get("graph_runtime") == expected["graph_runtime"]))
    if "extractor_mode" in expected:
        checks.append(status_check("extractor_mode", graph_state.get("extractor_mode") == expected["extractor_mode"]))
    if "fallback_used" in expected:
        checks.append(status_check("fallback_used", graph_state.get("fallback_used") is expected["fallback_used"]))
    if expected.get("chief_complaint_not_null"):
        checks.append(status_check("chief_complaint_not_null", bool(getattr(run_state, "chief_complaint", None))))
    if expected.get("duration_is_null"):
        checks.append(status_check("duration_is_null", getattr(run_state, "duration", None) is None))
    if expected.get("duration_not_null"):
        checks.append(status_check("duration_not_null", bool(getattr(run_state, "duration", None))))
    if "risk_flags_status" in expected:
        checks.append(status_check("risk_flags_status", getattr(run_state, "risk_flags_status", None) == expected["risk_flags_status"]))
    if "risk_rule_ids_include" in expected:
        rule_ids = set(getattr(run_state, "triggered_rule_ids", []) or [])
        checks.append(status_check("risk_rule_ids_include", set(expected["risk_rule_ids_include"]).issubset(rule_ids)))
    if "risk_rule_ids_absent" in expected:
        rule_ids = set(getattr(run_state, "triggered_rule_ids", []) or [])
        checks.append(status_check("risk_rule_ids_absent", not (set(expected["risk_rule_ids_absent"]) & rule_ids)))
    if "final_report_exists" in expected:
        checks.append(status_check("final_report_exists", (report is not None) is expected["final_report_exists"]))
    if "triage_level" in expected:
        checks.append(status_check("triage_level", getattr(report, "triage_level", None) == expected["triage_level"]))
    if "retrieved_evidence_min" in expected:
        checks.append(status_check("retrieved_evidence_min", trace["retrieved_evidence_count"] >= expected["retrieved_evidence_min"]))
    if "next_question_contains_any" in expected:
        question = getattr(run_state, "next_question", None) or ""
        checks.append(
            status_check(
                "next_question_contains_any",
                any(term in question for term in expected["next_question_contains_any"]),
                question,
            )
        )

    checks.extend(
        [
            status_check("rag_boundary_pass", trace["rag_boundary_pass"] is True),
            status_check("no_safety_rewrite", trace["safety_rewrite_used"] is False),
            status_check(
                "no_diagnosis_or_prescription_violation",
                trace["diagnosis_or_prescription_violation"] is False,
            ),
            status_check("no_state_loss", trace["state_loss_detected"] is False),
        ]
    )
    if report is not None:
        checks.append(status_check("final_report_schema_pass", trace["final_report_schema_pass"] is True))
    return checks


def run_graph_runtime_cases() -> dict[str, Any]:
    case_results: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []
    for case in GRAPH_RUNTIME_CASES:
        started = time.perf_counter()
        graph_state: dict[str, Any] = {}
        error: str | None = None
        try:
            graph_state = run_consultation_graph(
                case["initial_state"].model_copy(deep=True),
                case["user_input"],
                use_langgraph=True,
                extractor_mode=case["extractor_mode"],
                rag_enabled=case.get("rag_enabled", True),
            )
        except Exception as exc:  # pragma: no cover - captured in artifact if runtime breaks
            error = f"{type(exc).__name__}: {exc}"
        latency_ms = int((time.perf_counter() - started) * 1000)

        trace = make_trace(
            case_id=case["case_id"],
            session_id=f"p5-runtime-{case['case_id'].lower()}",
            turn_id=1,
            graph_state=graph_state,
            latency_ms=latency_ms,
            error=error,
        )
        checks = validate_graph_expectations(case, graph_state, trace) if not error else [
            status_check("runtime_exception", False, error or "")
        ]
        passed = all(check["ok"] for check in checks)
        traces.append(trace)
        case_results.append(
            {
                "case_id": case["case_id"],
                "description": case["description"],
                "user_input": case["user_input"],
                "extractor_mode_requested": case["extractor_mode"],
                "graph_runtime": trace["graph_runtime"],
                "passed": passed,
                "checks": checks,
                "trace_id": trace["trace_id"],
                "state_snapshot": json_safe(graph_state.get("run_state")) if graph_state else None,
                "final_report": json_safe(getattr(graph_state.get("run_state"), "final_report", None)) if graph_state else None,
            }
        )

    passed_count = len([case for case in case_results if case["passed"]])
    return {
        "status": "ok" if passed_count == len(case_results) else "failed",
        "cases_total": len(case_results),
        "cases_passed": passed_count,
        "cases_failed": len(case_results) - passed_count,
        "case_results": case_results,
        "traces": traces,
    }


def run_bm25_rag_smoke() -> dict[str, Any]:
    state = RunState(
        chief_complaint="胃胀",
        duration="一周",
        symptoms_status="none",
        risk_flags_status="none",
    )
    before = core_state_snapshot(state)
    pack = build_evidence_pack(state, top_k=3, mode="bm25_only")
    after = core_state_snapshot(state)
    ok = (
        before == after
        and len(pack.evidence) > 0
        and pack.core_state_readonly is True
        and "risk_status" in pack.forbidden_state_writes
        and "risk_rule_ids" in pack.forbidden_state_writes
        and pack.can_diagnose is False
        and pack.can_prescribe is False
    )
    return {
        "status": "ok" if ok else "failed",
        "query": pack.query,
        "evidence_count": len(pack.evidence),
        "retrieved_chunk_ids": [item.chunk_id for item in pack.evidence],
        "retriever_types": list(dict.fromkeys(item.retriever_type for item in pack.evidence)),
        "core_state_before": before,
        "core_state_after": after,
        "core_state_unchanged": before == after,
        "boundary": {
            "core_state_readonly": pack.core_state_readonly,
            "forbidden_state_writes": pack.forbidden_state_writes,
            "risk_rule_first": pack.risk_rule_first,
            "can_diagnose": pack.can_diagnose,
            "can_prescribe": pack.can_prescribe,
            "can_create_treatment_plan": pack.can_create_treatment_plan,
            "allowed_uses": pack.allowed_uses,
        },
    }


def run_rag_boundary_validation() -> dict[str, Any]:
    state = RunState(
        chief_complaint="胃胀",
        duration="一周",
        symptoms_status="none",
        risk_flags_status="none",
    )
    before = core_state_snapshot(state)
    report = FinalReport(
        summary="问诊信息整理：胃胀，一周。",
        impression="当前仅整理问诊信息，不作为诊断。",
        advice=["继续记录变化，如加重建议线下咨询医生。"],
        triage_level="observe",
        info_complete=True,
        missing_core_fields=[],
        followup_needed=False,
    )
    pack = build_evidence_pack(state, top_k=2, mode="bm25_only")
    enhanced = attach_evidence_pack(report, pack)
    after = core_state_snapshot(state)
    report_fields_same = all(
        getattr(enhanced, field) == getattr(report, field)
        for field in ["summary", "impression", "advice", "triage_level", "info_complete", "missing_core_fields", "followup_needed"]
    )
    ok = before == after and report_fields_same and enhanced.metadata.get("rag_core_state_readonly") is True
    return {
        "status": "ok" if ok else "failed",
        "core_state_before": before,
        "core_state_after": after,
        "core_state_unchanged": before == after,
        "report_contract_fields_unchanged": report_fields_same,
        "metadata_added": sorted(set(enhanced.metadata) - set(report.metadata)),
        "forbidden_state_writes": enhanced.metadata.get("rag_forbidden_state_writes", []),
        "allowed_uses": pack.allowed_uses,
    }


def run_report_safety_validation() -> dict[str, Any]:
    report = FinalReport(
        summary="问诊信息整理：用户要求越界医疗结论。",
        impression="当前内容仅用于问诊信息整理，不是诊断，也不能替代医生判断。",
        advice=[
            "不能提供超出问诊整理范围的内容。",
            "如症状持续或加重，建议线下咨询医生。",
        ],
        triage_level="observe",
        info_complete=True,
        missing_core_fields=[],
        followup_needed=False,
    )
    checked = safety_post_check_report(report)
    audit = audit_report(checked.report)
    ok = checked.issues == [] and audit.get("passed") is True and report_schema_pass(checked.report)
    return {
        "status": "ok" if ok else "failed",
        "report_safety_violation_count": len(checked.issues),
        "diagnosis_or_prescription_violation_count": len(audit.get("flags") or []),
        "final_report_schema_pass": report_schema_pass(checked.report),
        "safety_rewrite_used": checked.rewritten,
        "audit": audit,
    }


def run_extractor_mode_checks(*, probe_real_llm: bool, real_llm_timeout_seconds: int) -> dict[str, Any]:
    fake = extract_turn(RunState(), "胃胀一周，没有其他症状", extractor_mode="fake")
    fallback = extract_turn(RunState(), "胸痛、胸闷、喘不上气", extractor_mode="fallback")
    real_probe = probe_real_llm_availability(timeout_seconds=real_llm_timeout_seconds) if probe_real_llm else {
        "status": "skipped",
        "availability": "not_probed",
        "attempted": False,
        "caution": "real_llm probe skipped by caller",
        "metrics": {
            "attempt_count": 0,
            "raw_llm_json_valid_rate": None,
            "schema_pass_rate": None,
            "fallback_used_rate": None,
        },
    }

    mode_counts = {
        "fake": {
            "attempt_count": 1,
            "success_count": int(fake.success),
            "fallback_used_count": int(fake.fallback_used),
            "raw_llm_json_valid_count": int(fake.raw_llm_json_valid),
            "schema_pass_count": int(fake.schema_valid),
        },
        "rule_fallback": {
            "attempt_count": 1,
            "success_count": int(fallback.success),
            "fallback_used_count": int(fallback.fallback_used),
            "raw_llm_json_valid_count": int(fallback.raw_llm_json_valid),
            "schema_pass_count": int(fallback.schema_valid),
        },
        "real_llm": real_probe.get("metrics", {}),
    }
    ok = (
        fake.extractor_mode == "fake"
        and fake.fallback_used is False
        and fallback.mode == "rule_fallback"
        and fallback.fallback_used is True
        and fallback.turn_output is not None
        and fallback.turn_output.risk_flags_status == "present"
    )
    return {
        "status": "ok" if ok else "failed",
        "fake_extractor": fake.to_dict(),
        "rule_fallback": fallback.to_dict(),
        "real_llm": real_probe,
        "mode_counts": mode_counts,
        "separated_mode_names": ["fake", "rule_fallback", "real_llm"],
    }


def probe_real_llm_availability(*, timeout_seconds: int = 30) -> dict[str, Any]:
    missing = get_missing_api_config()
    if missing:
        return {
            "status": "caution",
            "availability": "unavailable",
            "attempted": False,
            "caution": f"missing_api_config: {','.join(missing)}",
            "metrics": {
                "attempt_count": 0,
                "raw_llm_json_valid_rate": None,
                "schema_pass_rate": None,
                "fallback_used_rate": None,
            },
        }

    code = r'''
import json
from app.graphs.consultation_graph import run_consultation_graph
from app.schemas.report_schemas import RunState

graph_state = run_consultation_graph(
    RunState(),
    "胃胀一周，没有其他症状，也没有胸痛",
    use_langgraph=True,
    extractor_mode="real_llm",
    rag_enabled=False,
)
payload = {
    "graph_runtime": graph_state.get("graph_runtime"),
    "extractor_mode": graph_state.get("extractor_mode"),
    "extraction_mode": graph_state.get("extraction_mode"),
    "raw_llm_json_valid": graph_state.get("raw_llm_json_valid"),
    "schema_pass": graph_state.get("schema_valid"),
    "fallback_used": graph_state.get("fallback_used"),
    "fallback_reason": graph_state.get("error_type") or "; ".join(graph_state.get("errors") or []),
    "model_name": graph_state.get("model_name"),
}
print("P5_REAL_LLM_RESULT=" + json.dumps(payload, ensure_ascii=False, sort_keys=True))
'''
    command = [sys.executable, "-c", code]
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "caution",
            "availability": "unavailable",
            "attempted": True,
            "caution": f"real_llm_probe_timeout_after={timeout_seconds}s",
            "stdout_tail": (exc.stdout or "")[-2000:],
            "stderr_tail": (exc.stderr or "")[-2000:],
            "metrics": {
                "attempt_count": 1,
                "raw_llm_json_valid_rate": 0.0,
                "schema_pass_rate": 0.0,
                "fallback_used_rate": 1.0,
            },
        }

    payload: dict[str, Any] = {}
    for line in (completed.stdout or "").splitlines():
        if line.startswith("P5_REAL_LLM_RESULT="):
            try:
                payload = json.loads(line.split("=", 1)[1])
            except json.JSONDecodeError:
                payload = {}

    if completed.returncode != 0 or not payload:
        return {
            "status": "caution",
            "availability": "unavailable",
            "attempted": True,
            "caution": f"real_llm_probe_return_code={completed.returncode}",
            "stdout_tail": (completed.stdout or "")[-2000:],
            "stderr_tail": (completed.stderr or "")[-2000:],
            "metrics": {
                "attempt_count": 1,
                "raw_llm_json_valid_rate": 0.0,
                "schema_pass_rate": 0.0,
                "fallback_used_rate": 1.0,
            },
        }

    fallback_used = bool(payload.get("fallback_used"))
    raw_ok = bool(payload.get("raw_llm_json_valid"))
    schema_ok = bool(payload.get("schema_pass"))
    available = raw_ok and schema_ok and not fallback_used
    return {
        "status": "ok" if available else "caution",
        "availability": "available" if available else "unavailable",
        "attempted": True,
        "caution": None if available else f"real_llm_fallback_or_invalid: {payload.get('fallback_reason')}",
        "probe": payload,
        "metrics": {
            "attempt_count": 1,
            "raw_llm_json_valid_rate": 1.0 if raw_ok else 0.0,
            "schema_pass_rate": 1.0 if schema_ok else 0.0,
            "fallback_used_rate": 1.0 if fallback_used else 0.0,
        },
    }


def check_code_health_artifact() -> dict[str, Any]:
    payload = load_json(CODE_HEALTH_ARTIFACT)
    if not payload:
        return {
            "status": "caution",
            "ok": False,
            "artifact_path": str(CODE_HEALTH_ARTIFACT.relative_to(ROOT_DIR)),
            "detail": "code health artifact not found or not parseable; run python scripts/run_code_health_gate.py first",
        }
    ok = payload.get("hard_gate_status") == "ok" and payload.get("status") == "ok"
    return {
        "status": "ok" if ok else "failed",
        "ok": ok,
        "artifact_path": str(CODE_HEALTH_ARTIFACT.relative_to(ROOT_DIR)),
        "detail": f"hard_gate_status={payload.get('hard_gate_status')} status={payload.get('status')}",
    }


def summarize_metrics(
    *,
    graph_cases: dict[str, Any],
    traces: Sequence[dict[str, Any]],
    extractor_modes: dict[str, Any],
    rag_smoke: dict[str, Any],
    rag_boundary: dict[str, Any],
    report_safety: dict[str, Any],
) -> dict[str, Any]:
    high_risk_cases = [
        case
        for case in graph_cases["case_results"]
        if case["case_id"] in {"P5-GRAPH-03", "P5-GRAPH-05"}
    ]
    high_risk_false_negative_count = len(
        [
            case
            for case in high_risk_cases
            if (case.get("state_snapshot") or {}).get("risk_flags_status") != "present"
        ]
    )
    state_loss_count = len([trace for trace in traces if trace["state_loss_detected"]])
    report_safety_violation_count = (
        int(report_safety.get("report_safety_violation_count", 0))
        + len([trace for trace in traces if trace["safety_rewrite_used"]])
    )
    diagnosis_or_prescription_violation_count = (
        int(report_safety.get("diagnosis_or_prescription_violation_count", 0))
        + len([trace for trace in traces if trace["diagnosis_or_prescription_violation"]])
    )
    return {
        "graph_runtime_case_count": graph_cases["cases_total"],
        "graph_runtime_case_pass_count": graph_cases["cases_passed"],
        "trace_count": len(traces),
        "trace_field_completeness_pass": trace_field_completeness_pass(traces),
        "fake_extractor_count": extractor_modes["mode_counts"]["fake"]["attempt_count"],
        "rule_fallback_count": extractor_modes["mode_counts"]["rule_fallback"]["attempt_count"],
        "real_llm_count": extractor_modes["mode_counts"]["real_llm"].get("attempt_count", 0),
        "raw_llm_json_valid_rate": extractor_modes["real_llm"]["metrics"].get("raw_llm_json_valid_rate"),
        "schema_pass_rate": extractor_modes["real_llm"]["metrics"].get("schema_pass_rate"),
        "fallback_used_rate": extractor_modes["real_llm"]["metrics"].get("fallback_used_rate"),
        "bm25_retrieved_evidence_count": rag_smoke.get("evidence_count", 0),
        "rag_boundary_pass_count": len([trace for trace in traces if trace["rag_boundary_pass"]])
        + int(rag_boundary.get("status") == "ok"),
        "report_safety_violation_count": report_safety_violation_count,
        "diagnosis_or_prescription_violation_count": diagnosis_or_prescription_violation_count,
        "high_risk_false_negative_count": high_risk_false_negative_count,
        "state_loss_rate": 0.0 if not traces else state_loss_count / len(traces),
        "state_loss_count": state_loss_count,
    }


def build_failure_analysis(
    *,
    status: str,
    hard_gate_results: dict[str, Any],
    graph_cases: dict[str, Any],
    extractor_modes: dict[str, Any],
    rag_smoke: dict[str, Any],
    rag_boundary: dict[str, Any],
    report_safety: dict[str, Any],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    cautions: list[dict[str, Any]] = []

    for name, result in hard_gate_results.items():
        if result.get("status") == "failed":
            blockers.append({"source": name, "detail": result.get("detail")})
        elif result.get("status") == "caution":
            cautions.append({"source": name, "detail": result.get("detail")})

    for case in graph_cases["case_results"]:
        if not case["passed"]:
            blockers.append({"source": case["case_id"], "detail": case["checks"]})

    for name, result in {
        "extractor_modes": extractor_modes,
        "bm25_rag_smoke": rag_smoke,
        "rag_boundary": rag_boundary,
        "report_safety": report_safety,
    }.items():
        if result.get("status") == "failed":
            blockers.append({"source": name, "detail": result})
        elif result.get("status") == "caution":
            cautions.append({"source": name, "detail": result.get("caution")})

    if extractor_modes["real_llm"].get("status") == "caution":
        cautions.append(
            {
                "source": "real_llm",
                "detail": extractor_modes["real_llm"].get("caution")
                or "real_llm unavailable; fallback was measured separately",
            }
        )

    if metrics.get("trace_field_completeness_pass") is not True:
        blockers.append({"source": "trace_schema", "detail": "trace samples are missing required fields"})
    if metrics.get("report_safety_violation_count") != 0:
        blockers.append({"source": "report_safety", "detail": "report safety violation count is non-zero"})
    if metrics.get("diagnosis_or_prescription_violation_count") != 0:
        blockers.append({"source": "report_audit", "detail": "diagnosis/prescription violation count is non-zero"})
    if metrics.get("high_risk_false_negative_count") != 0:
        blockers.append({"source": "risk_rules", "detail": "high-risk false negative count is non-zero"})
    if metrics.get("state_loss_rate") != 0.0:
        blockers.append({"source": "run_state", "detail": "state loss rate is non-zero"})

    return {
        "phase": PHASE,
        "generated_at": utc_now(),
        "status": status,
        "blockers": blockers,
        "cautions": cautions,
        "known_cautions": [
            {
                "source": "real_llm",
                "detail": "When provider/network/config is unavailable, P5 records caution and never marks it as successful.",
            },
            {
                "source": "dependency_warning",
                "detail": "Existing transformers/PyTorch warning may appear during graph import; it is not a P5 hard failure.",
            },
        ],
        "recommended_followups": [
            "Run the same P5 command in an environment with a reachable real LLM provider to replace the real_llm caution with measured pass rates.",
            "Keep RAG limited to evidence/impression/advice enrichment unless a future phase explicitly changes the product boundary.",
        ],
    }


def run_p5_validation(
    *,
    write_artifacts: bool = True,
    probe_real_llm: bool = True,
    real_llm_timeout_seconds: int = 30,
) -> dict[str, Any]:
    graph_compile_ok = build_consultation_graph() is not None
    p4_gate = run_p4_gate(run_unittest=False)
    code_health = check_code_health_artifact()
    graph_cases = run_graph_runtime_cases()
    rag_smoke = run_bm25_rag_smoke()
    rag_boundary = run_rag_boundary_validation()
    report_safety = run_report_safety_validation()
    extractor_modes = run_extractor_mode_checks(
        probe_real_llm=probe_real_llm,
        real_llm_timeout_seconds=real_llm_timeout_seconds,
    )
    traces = list(graph_cases["traces"])
    metrics = summarize_metrics(
        graph_cases=graph_cases,
        traces=traces,
        extractor_modes=extractor_modes,
        rag_smoke=rag_smoke,
        rag_boundary=rag_boundary,
        report_safety=report_safety,
    )

    hard_gate_results = {
        "p4_gate": {
            "status": "ok" if p4_gate.get("status") == "ok" else "failed",
            "detail": f"checks={p4_gate.get('checks_passed')}/{p4_gate.get('checks_total')}",
        },
        "code_health_gate": code_health,
    }
    hard_ok = p4_gate.get("status") == "ok" and code_health.get("status") in {"ok", "caution"}
    p5_core_ok = (
        graph_compile_ok
        and graph_cases["status"] == "ok"
        and graph_cases["cases_passed"] >= 5
        and rag_smoke["status"] == "ok"
        and rag_boundary["status"] == "ok"
        and report_safety["status"] == "ok"
        and extractor_modes["status"] == "ok"
        and metrics["trace_field_completeness_pass"] is True
        and metrics["report_safety_violation_count"] == 0
        and metrics["diagnosis_or_prescription_violation_count"] == 0
        and metrics["high_risk_false_negative_count"] == 0
        and metrics["state_loss_rate"] == 0.0
    )
    if not hard_ok or not p5_core_ok:
        status = "failed"
    elif extractor_modes["real_llm"].get("status") == "caution" or code_health.get("status") == "caution":
        status = "caution"
    else:
        status = "ok"

    failure_analysis = build_failure_analysis(
        status=status,
        hard_gate_results=hard_gate_results,
        graph_cases=graph_cases,
        extractor_modes=extractor_modes,
        rag_smoke=rag_smoke,
        rag_boundary=rag_boundary,
        report_safety=report_safety,
        metrics=metrics,
    )

    payload = {
        "phase": PHASE,
        "generated_at": utc_now(),
        "status": status,
        "p5_scope": (
            "Validate the real LangGraph runtime path, extractor modes, Pydantic schemas, "
            "RunState accumulation, risk rules, BM25 RAG boundary, ReportGenerator, "
            "ReportSafety, FinalReport, traces, and P5 metrics without changing API/SQLite/schema contracts."
        ),
        "changed_files": CHANGED_FILES,
        "hard_gates": hard_gate_results,
        "real_langgraph_runtime_status": {
            "status": "ok" if graph_compile_ok and graph_cases["status"] == "ok" else "failed",
            "graph_compile_ok": graph_compile_ok,
            "graph_runtime_cases_total": graph_cases["cases_total"],
            "graph_runtime_cases_passed": graph_cases["cases_passed"],
        },
        "extractor_mode_status": extractor_modes,
        "real_llm_availability": extractor_modes["real_llm"],
        "bm25_rag_smoke_test_status": rag_smoke,
        "multiturn_demo_results": {
            "artifact": "artifacts/p5_demo_results.json",
            "status": "generated_by_scripts/run_p5_demo_cases.py",
        },
        "risk_rule_validation": {
            "status": "ok" if metrics["high_risk_false_negative_count"] == 0 else "failed",
            "high_risk_false_negative_count": metrics["high_risk_false_negative_count"],
            "negated_risk_case_status": next(
                (case for case in graph_cases["case_results"] if case["case_id"] == "P5-GRAPH-04"),
                {},
            ),
        },
        "rag_boundary_validation": rag_boundary,
        "report_safety_validation": report_safety,
        "metrics_table": metrics,
        "failure_analysis": failure_analysis,
        "known_cautions": failure_analysis["known_cautions"] + failure_analysis["cautions"],
        "p5_conclusion": status,
        "p6_entry_criteria": [
            "Resolve any P5 failed blocker before expanding runtime behavior.",
            "For a clean P5 pass, rerun with reachable real_llm provider so raw_llm_json_valid_rate/schema_pass_rate are measured without fallback.",
            "Keep FastAPI contract, SQLite schema, FinalReport/RunState/TurnOutput semantics, and risk-rule semantics frozen.",
            "Use P5 traces and metrics as the minimum runtime smoke suite for P6 changes.",
        ],
        "graph_runtime_cases": graph_cases["case_results"],
    }

    trace_payload = {
        "phase": PHASE,
        "generated_at": utc_now(),
        "trace_schema_fields": TRACE_FIELDS,
        "trace_field_completeness_pass": trace_field_completeness_pass(traces),
        "sample_count": len(traces),
        "traces": traces,
    }

    if write_artifacts:
        write_json(DEFAULT_VALIDATION_ARTIFACT, payload)
        write_json(DEFAULT_TRACE_ARTIFACT, trace_payload)
        write_json(DEFAULT_FAILURE_ARTIFACT, failure_analysis)
    return {
        "validation": payload,
        "trace_samples": trace_payload,
        "failure_analysis": failure_analysis,
    }


def exit_code_for_status(status: str) -> int:
    return 1 if status == "failed" else 0


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run P5 real runtime validation.")
    parser.add_argument("--json", action="store_true", help="Print the full validation artifact JSON.")
    parser.add_argument("--skip-real-llm-probe", action="store_true", help="Skip the real_llm availability subprocess probe.")
    parser.add_argument("--real-llm-timeout", type=int, default=30, help="real_llm probe timeout in seconds.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args(argv)
    result = run_p5_validation(
        write_artifacts=True,
        probe_real_llm=not args.skip_real_llm_probe,
        real_llm_timeout_seconds=args.real_llm_timeout,
    )
    payload = result["validation"]
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        metrics = payload["metrics_table"]
        print(
            "P5 real runtime validation: "
            f"status={payload['status']} "
            f"graph_cases={metrics['graph_runtime_case_pass_count']}/{metrics['graph_runtime_case_count']} "
            f"real_llm={payload['real_llm_availability'].get('availability')} "
            f"artifact={DEFAULT_VALIDATION_ARTIFACT.relative_to(ROOT_DIR)}"
        )
    return exit_code_for_status(str(payload["status"]))


if __name__ == "__main__":
    raise SystemExit(main())
