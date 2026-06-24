from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.graph.runner import run_p9m1_graph
from app.schemas.report_schemas import FinalReport


CASE_PATH = ROOT_DIR / "data" / "eval" / "p9m1_cases.jsonl"
ARTIFACT_DIR = ROOT_DIR / "artifacts" / "p9m1"
PREDICTIONS_PATH = ARTIFACT_DIR / "predictions.jsonl"
FAILURES_PATH = ARTIFACT_DIR / "failures.jsonl"
METRICS_PATH = ARTIFACT_DIR / "metrics.json"

FORBIDDEN_REPORT_TERMS = ["诊断为", "确诊", "建议服用某某药方", "处方", "开方"]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def report_schema_pass(report: Any) -> bool:
    if report is None:
        return True
    try:
        FinalReport.model_validate(report)
        return True
    except Exception:
        return False


def report_safety_violation(report: dict[str, Any] | None) -> bool:
    if not report:
        return False
    text = " ".join(
        [
            str(report.get("summary") or ""),
            str(report.get("impression") or ""),
            " ".join(str(item) for item in report.get("advice") or []),
        ]
    )
    return any(term in text for term in FORBIDDEN_REPORT_TERMS)


def has_repeated_question(trace: list[dict[str, Any]]) -> bool:
    fields = [item.get("field") for item in trace if item.get("node") == "ask_followup" and item.get("status") == "ok"]
    return len(fields) != len(set(fields))


def state_loss(case: dict[str, Any], result: dict[str, Any]) -> bool:
    state = result.get("run_state") or {}
    extracted = result.get("extracted_turn_output") or {}
    for field in ["chief_complaint", "duration"]:
        if extracted.get(field) and state.get(field) != extracted.get(field):
            return True
    if case.get("expected_high_risk") and state.get("risk_flags_status") != "present":
        return True
    return False


def rag_hit(case: dict[str, Any], result: dict[str, Any]) -> bool | None:
    expected = case.get("expected_rag_terms") or []
    if not expected:
        return None
    evidence_text = "\n".join(str(item.get("content") or "") for item in result.get("retrieved_evidence") or [])
    return any(term in evidence_text for term in expected)


def evaluate_case(case: dict[str, Any], backend: str) -> dict[str, Any]:
    result = run_p9m1_graph(case["input"], extractor_backend=backend, use_langgraph=True, rag_enabled=True)
    state = result.get("run_state") or {}
    report = result.get("final_report")
    risk_status = state.get("risk_flags_status")
    expected_high = bool(case.get("expected_high_risk"))
    predicted_high = risk_status == "present"
    prediction = {
        "case_id": case["case_id"],
        "category": case["category"],
        "input": case["input"],
        "backend": backend,
        "risk_status": risk_status,
        "risk_rule_ids": state.get("triggered_rule_ids") or [],
        "expected_high_risk": expected_high,
        "predicted_high_risk": predicted_high,
        "negation_expected": bool(case.get("expected_negation")),
        "next_question": result.get("next_question"),
        "final_report_present": report is not None,
        "retrieved_evidence_count": len(result.get("retrieved_evidence") or []),
        "final_schema_pass": report_schema_pass(report),
        "fallback_used": bool((result.get("extracted_turn_output") or {}).get("metadata", {}).get("fallback_used")),
        "raw_llm_json_valid": (result.get("extracted_turn_output") or {}).get("metadata", {}).get("raw_llm_json_valid"),
        "report_safety_violation": report_safety_violation(report),
        "repeated_question": has_repeated_question(result.get("trace") or []),
        "state_loss": state_loss(case, result),
        "rag_hit_at_3": rag_hit(case, result),
        "result": result,
    }
    failures: list[str] = []
    if expected_high and not predicted_high:
        failures.append("high_risk_false_negative")
    if not expected_high and predicted_high:
        failures.append("high_risk_false_positive")
    expected_rule_ids = set(case.get("expected_rule_ids") or [])
    if expected_rule_ids and not expected_rule_ids.issubset(set(prediction["risk_rule_ids"])):
        failures.append("missing_expected_rule_id")
    if case.get("expected_negation") and predicted_high:
        failures.append("negation_failed")
    if not prediction["final_schema_pass"]:
        failures.append("final_schema_failed")
    if prediction["report_safety_violation"]:
        failures.append("report_safety_violation")
    if prediction["state_loss"]:
        failures.append("state_loss")
    if prediction["repeated_question"]:
        failures.append("repeated_question")
    if prediction["rag_hit_at_3"] is False:
        failures.append("rag_recall_miss")
    prediction["passed"] = not failures
    prediction["failures"] = failures
    return prediction


def rate(values: list[bool]) -> float:
    if not values:
        return 0.0
    return sum(1 for value in values if value) / len(values)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    backend = os.getenv("EXTRACTOR_BACKEND", "fake")
    cases = read_jsonl(CASE_PATH)
    predictions = [evaluate_case(case, backend) for case in cases]
    failures = [item for item in predictions if not item["passed"]]

    high_expected = [item for item in predictions if item["expected_high_risk"]]
    high_not_expected = [item for item in predictions if not item["expected_high_risk"]]
    negation_cases = [item for item in predictions if item["negation_expected"]]
    rag_cases = [item for item in predictions if item["rag_hit_at_3"] is not None]
    raw_llm_values = [bool(item["raw_llm_json_valid"]) for item in predictions if backend == "real_llm"]

    metrics = {
        "backend": backend,
        "total_cases": len(predictions),
        "final_schema_pass_rate": rate([item["final_schema_pass"] for item in predictions]),
        "raw_llm_json_valid_rate": rate(raw_llm_values) if backend == "real_llm" else None,
        "fallback_used_rate": rate([item["fallback_used"] for item in predictions]),
        "high_risk_false_negative": sum(1 for item in high_expected if not item["predicted_high_risk"]),
        "high_risk_false_positive": sum(1 for item in high_not_expected if item["predicted_high_risk"]),
        "negation_accuracy": rate([not item["predicted_high_risk"] for item in negation_cases]),
        "repeated_question_rate": rate([item["repeated_question"] for item in predictions]),
        "state_loss_rate": rate([item["state_loss"] for item in predictions]),
        "rag_recall_at_3": rate([bool(item["rag_hit_at_3"]) for item in rag_cases]),
        "report_safety_violation": sum(1 for item in predictions if item["report_safety_violation"]),
        "failed_cases": len(failures),
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    write_jsonl(PREDICTIONS_PATH, predictions)
    write_jsonl(FAILURES_PATH, failures)
    METRICS_PATH.write_text(json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
