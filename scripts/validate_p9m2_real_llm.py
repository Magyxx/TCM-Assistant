from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.graph.runner import run_p9m1_graph
from app.schemas.report_schemas import FinalReport


CASE_PATH = ROOT_DIR / "data" / "eval" / "p9m2_real_llm_smoke_cases.jsonl"
ARTIFACT_DIR = ROOT_DIR / "artifacts" / "p9m2"
METRICS_PATH = ARTIFACT_DIR / "real_llm_smoke_metrics.json"
PREDICTIONS_PATH = ARTIFACT_DIR / "real_llm_predictions.jsonl"
FAILURES_PATH = ARTIFACT_DIR / "real_llm_failures.jsonl"


def enabled() -> bool:
    return os.getenv("ENABLE_REAL_LLM", "false").strip().lower() in {"1", "true", "yes", "on"}


def live_allowed() -> bool:
    return os.getenv("P9M2_ALLOW_REAL_LLM_LIVE", "false").strip().lower() in {"1", "true", "yes", "on"}


def missing_config() -> list[str]:
    return [name for name in ["OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL"] if not os.getenv(name)]


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


def percentile(values: list[int], pct: float) -> int:
    if not values:
        return 0
    values = sorted(values)
    idx = min(len(values) - 1, int(round((len(values) - 1) * pct)))
    return values[idx]


def report_schema_pass(report: Any) -> bool:
    if report is None:
        return True
    try:
        FinalReport.model_validate(report)
        return True
    except Exception:
        return False


def write_skip(reason: str) -> dict[str, Any]:
    metrics = {
        "status": "skipped",
        "total_cases": 0,
        "skipped": True,
        "skip_reason": reason,
        "raw_llm_json_valid_rate": None,
        "turn_output_schema_pass_rate": None,
        "final_schema_pass_rate": None,
        "fallback_used_rate": None,
        "high_risk_false_negative": 0,
        "high_risk_false_positive": 0,
        "negation_accuracy": None,
        "report_safety_violation": 0,
        "latency_ms_avg": 0,
        "latency_ms_p95": 0,
        "token_usage_total": 0,
        "token_usage_available": False,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    METRICS_PATH.write_text(json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_jsonl(PREDICTIONS_PATH, [])
    write_jsonl(FAILURES_PATH, [])
    return metrics


def run_case(case: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    result = run_p9m1_graph(case["input"], extractor_backend="real_llm", use_langgraph=True)
    latency = int((time.perf_counter() - started) * 1000)
    turn = result.get("extracted_turn_output") or {}
    metadata = turn.get("metadata") or {}
    state = result.get("run_state") or {}
    expected_high = bool(case.get("expected_high_risk"))
    predicted_high = state.get("risk_flags_status") == "present"
    prediction = {
        "case_id": case["case_id"],
        "category": case["category"],
        "latency_ms": latency,
        "raw_llm_json_valid": bool(metadata.get("raw_llm_json_valid")),
        "turn_output_schema_pass": bool(turn),
        "final_schema_pass": report_schema_pass(result.get("final_report")),
        "fallback_used": bool(metadata.get("fallback_used")),
        "risk_status": state.get("risk_flags_status"),
        "expected_high_risk": expected_high,
        "predicted_high_risk": predicted_high,
        "negation_expected": bool(case.get("expected_negation")),
        "report_safety_violation": False,
        "token_usage": metadata.get("token_usage"),
        "error_type": metadata.get("error_type"),
        "skip_reason": metadata.get("skip_reason"),
    }
    failures = []
    if expected_high and not predicted_high:
        failures.append("high_risk_false_negative")
    if not expected_high and predicted_high:
        failures.append("high_risk_false_positive")
    if not prediction["turn_output_schema_pass"]:
        failures.append("turn_output_schema_failed")
    if not prediction["final_schema_pass"]:
        failures.append("final_schema_failed")
    prediction["failures"] = failures
    prediction["passed"] = not failures
    return prediction


def main() -> int:
    parser = argparse.ArgumentParser(description="P9M2 real LLM smoke validation.")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if not enabled():
        metrics = write_skip("ENABLE_REAL_LLM=false")
        print(json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    missing = missing_config()
    if missing:
        metrics = write_skip("missing_config:" + ",".join(missing))
        print(json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if not live_allowed():
        metrics = write_skip("P9M2_ALLOW_REAL_LLM_LIVE=false")
        print(json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    cases = read_jsonl(CASE_PATH)[: args.limit]
    predictions = [run_case(case) for case in cases]
    failures = [item for item in predictions if not item["passed"]]
    latencies = [int(item["latency_ms"]) for item in predictions]
    high_expected = [item for item in predictions if item["expected_high_risk"]]
    high_not_expected = [item for item in predictions if not item["expected_high_risk"]]
    negation = [item for item in predictions if item["negation_expected"]]
    token_values = [item["token_usage"] for item in predictions if isinstance(item.get("token_usage"), int)]
    metrics = {
        "status": "ok" if not failures else "failed",
        "total_cases": len(predictions),
        "skipped": False,
        "skip_reason": None,
        "raw_llm_json_valid_rate": rate([item["raw_llm_json_valid"] for item in predictions]),
        "turn_output_schema_pass_rate": rate([item["turn_output_schema_pass"] for item in predictions]),
        "final_schema_pass_rate": rate([item["final_schema_pass"] for item in predictions]),
        "fallback_used_rate": rate([item["fallback_used"] for item in predictions]),
        "high_risk_false_negative": sum(1 for item in high_expected if not item["predicted_high_risk"]),
        "high_risk_false_positive": sum(1 for item in high_not_expected if item["predicted_high_risk"]),
        "negation_accuracy": rate([not item["predicted_high_risk"] for item in negation]),
        "report_safety_violation": sum(1 for item in predictions if item["report_safety_violation"]),
        "latency_ms_avg": int(statistics.mean(latencies)) if latencies else 0,
        "latency_ms_p95": percentile(latencies, 0.95),
        "token_usage_total": sum(token_values),
        "token_usage_available": bool(token_values),
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    METRICS_PATH.write_text(json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_jsonl(PREDICTIONS_PATH, predictions)
    write_jsonl(FAILURES_PATH, failures)
    print(json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
