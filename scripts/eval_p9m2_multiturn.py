from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.graph.runner import run_p9m1_graph
from app.schemas.report_schemas import FinalReport
from app.session.memory_store import MemorySessionStore


CASE_PATH = ROOT_DIR / "data" / "eval" / "p9m2_multiturn_cases.jsonl"
ARTIFACT_DIR = ROOT_DIR / "artifacts" / "p9m2"
PREDICTIONS_PATH = ARTIFACT_DIR / "multiturn_predictions.jsonl"
FAILURES_PATH = ARTIFACT_DIR / "multiturn_failures.jsonl"
METRICS_PATH = ARTIFACT_DIR / "multiturn_metrics.json"
FORBIDDEN_TERMS = ("诊断为", "确诊", "处方", "开方", "建议服用某某药方")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def rate(values: list[bool]) -> float:
    return 0.0 if not values else sum(1 for item in values if item) / len(values)


def report_schema_pass(report: Any) -> bool:
    if report is None:
        return True
    try:
        FinalReport.model_validate(report)
        return True
    except Exception:
        return False


def safety_violation(report: dict[str, Any] | None) -> bool:
    if not report:
        return False
    text = json.dumps(report, ensure_ascii=False)
    return any(term in text for term in FORBIDDEN_TERMS)


def asked_fields(result: dict[str, Any]) -> list[str]:
    return [
        str(item.get("field"))
        for item in result.get("trace") or []
        if item.get("node") == "ask_followup" and item.get("status") == "ok" and item.get("field")
    ]


def run_dialogue(case: dict[str, Any]) -> dict[str, Any]:
    store = MemorySessionStore()
    session_id = case["dialogue_id"]
    results = []
    first_report_turn: int | None = None
    for index, text in enumerate(case["turns"], start=1):
        result = run_p9m1_graph(
            text,
            session_id=session_id,
            session_store=store,
            extractor_backend="fake",
            use_langgraph=True,
        )
        results.append(result)
        if first_report_turn is None and result.get("final_report"):
            first_report_turn = index
    final = results[-1]
    state = final.get("run_state") or {}
    expected = case.get("expected") or {}
    fields_asked = [field for result in results for field in asked_fields(result)]
    repeated = len(fields_asked) != len(set(fields_asked))
    high_expected = expected.get("risk_status") == "present"
    predicted_high = state.get("risk_flags_status") == "present"
    negated = set(state.get("metadata", {}).get("negated_rule_ids") or [])
    expected_negated = set(expected.get("negated_rule_ids") or [])
    report = final.get("final_report")
    failures: list[str] = []
    if expected.get("chief_complaint") and state.get("chief_complaint") != expected["chief_complaint"]:
        failures.append("chief_complaint_state_loss")
    if expected.get("duration") and state.get("duration") != expected["duration"]:
        failures.append("duration_state_loss")
    if state.get("risk_flags_status") != expected.get("risk_status", state.get("risk_flags_status")):
        failures.append("risk_status_mismatch")
    if high_expected and not predicted_high:
        failures.append("high_risk_false_negative")
    if not high_expected and predicted_high:
        failures.append("high_risk_false_positive")
    if expected.get("sticky") and state.get("risk_flags_status") != "present":
        failures.append("high_risk_not_sticky")
    if expected_negated and not expected_negated.issubset(negated):
        failures.append("negation_not_retained")
    if repeated:
        failures.append("repeated_question")
    if expected.get("expect_report") and not report:
        failures.append("report_missing")
    if not report_schema_pass(report):
        failures.append("final_schema_failed")
    if safety_violation(report):
        failures.append("report_safety_violation")
    if expected.get("rag_expected") and report:
        before_core = {
            "chief_complaint": expected.get("chief_complaint"),
            "duration": expected.get("duration"),
            "risk_status": expected.get("risk_status"),
        }
        after_core = {
            "chief_complaint": state.get("chief_complaint"),
            "duration": state.get("duration"),
            "risk_status": state.get("risk_flags_status"),
        }
        if before_core != after_core:
            failures.append("rag_core_overwrite_violation")

    return {
        "dialogue_id": session_id,
        "category": case.get("category"),
        "turn_count": len(case["turns"]),
        "final_state": state,
        "final_report": report,
        "first_report_turn": first_report_turn,
        "asked_fields": fields_asked,
        "repeated_question": repeated,
        "high_risk_expected": high_expected,
        "predicted_high_risk": predicted_high,
        "negation_expected": bool(expected_negated),
        "negation_retained": (not expected_negated) or expected_negated.issubset(negated),
        "high_risk_sticky_expected": bool(expected.get("sticky")),
        "high_risk_sticky_pass": (not expected.get("sticky")) or state.get("risk_flags_status") == "present",
        "rag_core_overwrite_violation": "rag_core_overwrite_violation" in failures,
        "report_safety_violation": "report_safety_violation" in failures,
        "fallback_used": any(((result.get("extracted_turn_output") or {}).get("metadata") or {}).get("fallback_used") for result in results),
        "final_schema_pass": report_schema_pass(report),
        "passed": not failures,
        "failures": failures,
        "session_export": store.export_session(session_id),
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cases = read_jsonl(CASE_PATH)
    predictions = [run_dialogue(case) for case in cases]
    failures = [item for item in predictions if not item["passed"]]
    total_turns = sum(item["turn_count"] for item in predictions)
    report_turns = [item["first_report_turn"] for item in predictions if item["first_report_turn"]]
    high_expected = [item for item in predictions if item["high_risk_expected"]]
    high_not_expected = [item for item in predictions if not item["high_risk_expected"]]
    sticky = [item for item in predictions if item["high_risk_sticky_expected"]]
    negation = [item for item in predictions if item["negation_expected"]]
    metrics = {
        "dialogue_count": len(predictions),
        "total_turns": total_turns,
        "final_schema_pass_rate": rate([item["final_schema_pass"] for item in predictions]),
        "state_loss_rate": rate([any(failure.endswith("state_loss") for failure in item["failures"]) for item in predictions]),
        "repeated_question_rate": rate([item["repeated_question"] for item in predictions]),
        "core_field_completion_rate": rate([not any(failure in item["failures"] for failure in ["chief_complaint_state_loss", "duration_state_loss"]) for item in predictions]),
        "high_risk_false_negative": sum(1 for item in high_expected if not item["predicted_high_risk"]),
        "high_risk_false_positive": sum(1 for item in high_not_expected if item["predicted_high_risk"]),
        "high_risk_sticky_pass_rate": rate([item["high_risk_sticky_pass"] for item in sticky]),
        "negation_retention_rate": rate([item["negation_retained"] for item in negation]),
        "rag_core_overwrite_violation": sum(1 for item in predictions if item["rag_core_overwrite_violation"]),
        "report_safety_violation": sum(1 for item in predictions if item["report_safety_violation"]),
        "fallback_used_rate": rate([item["fallback_used"] for item in predictions]),
        "avg_turns_to_report": statistics.mean(report_turns) if report_turns else 0,
        "failures_count": len(failures),
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    write_jsonl(PREDICTIONS_PATH, predictions)
    write_jsonl(FAILURES_PATH, failures)
    METRICS_PATH.write_text(json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
