from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.safety.p10m2_redteam import evaluate_case, summarize_predictions
from scripts.p10m2_case_data import SAFETY_CASES_PATH, ensure_case_files


ARTIFACT_DIR = ROOT_DIR / "artifacts" / "p10m2"
METRICS_PATH = ARTIFACT_DIR / "safety_redteam_metrics.json"
PREDICTIONS_PATH = ARTIFACT_DIR / "safety_redteam_predictions.jsonl"
FAILURES_PATH = ARTIFACT_DIR / "safety_redteam_failures.jsonl"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def run_eval(*, write_artifacts: bool = True) -> dict[str, Any]:
    ensure_case_files()
    cases = _read_jsonl(SAFETY_CASES_PATH)
    predictions = [evaluate_case(case) for case in cases]
    metrics = summarize_predictions(predictions)
    failure_keys = [
        "diagnosis_violation",
        "prescription_violation",
        "prompt_injection_success",
        "rag_injection_success",
        "high_risk_false_negative",
        "missing_safety_disclaimer",
        "secret_log_leak_count",
    ]
    failures = [
        item
        for item in predictions
        if any(int(item.get(key, 0)) > 0 for key in failure_keys)
    ]
    status = "ok" if not failures else "failed"
    result = {
        "status": status,
        "metrics": metrics,
        "artifacts": {
            "cases": str(SAFETY_CASES_PATH.relative_to(ROOT_DIR)).replace("\\", "/"),
            "metrics": str(METRICS_PATH.relative_to(ROOT_DIR)).replace("\\", "/"),
            "predictions": str(PREDICTIONS_PATH.relative_to(ROOT_DIR)).replace("\\", "/"),
            "failures": str(FAILURES_PATH.relative_to(ROOT_DIR)).replace("\\", "/"),
        },
        "skipped": False,
        "skip_reason": "",
    }
    if write_artifacts:
        _write_json(METRICS_PATH, result)
        _write_jsonl(PREDICTIONS_PATH, predictions)
        _write_jsonl(FAILURES_PATH, failures)
    return result


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    result = run_eval(write_artifacts=True)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())

