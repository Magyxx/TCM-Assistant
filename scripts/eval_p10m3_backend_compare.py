from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

ARTIFACT_DIR = ROOT_DIR / "artifacts" / "p10m3"
DEFAULT_OUTPUT = ARTIFACT_DIR / "backend_compare_metrics.json"

CASES = [
    {
        "case_id": "digestive_negation",
        "user_input": "胃胀一周，没有发热，也不胸痛",
        "expected_chief": "胃胀",
        "expected_duration": "一周",
        "expected_risk": "none",
    },
    {
        "case_id": "high_risk_chest_dyspnea",
        "user_input": "胸痛伴呼吸困难半天",
        "expected_chief": "胸痛",
        "expected_duration": "半天",
        "expected_risk": "present",
    },
    {
        "case_id": "complete_digestive",
        "user_input": "胃痛两天，睡眠一般，食欲下降，大便正常，小便正常，没有其他症状，没有胸痛",
        "expected_chief": "胃痛",
        "expected_duration": "两天",
        "expected_risk": "none",
    },
]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _git(args: list[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def _mock_content_for(text: str) -> str:
    chief = None
    for term in ["胃胀", "胃痛", "胸痛"]:
        if term in text:
            chief = term
            break
    duration = None
    for term in ["半天", "一周", "两天"]:
        if term in text:
            duration = term
            break
    return json.dumps(
        {
            "chief_complaint": chief,
            "duration": duration,
            "symptoms": [],
            "symptoms_status": "none" if "没有其他症状" in text else "unknown",
            "risk_flags": [],
            "risk_flags_status": "none",
            "summary": "p10m3 mock local_lora compare output",
        },
        ensure_ascii=False,
    )


def run_eval() -> dict[str, Any]:
    from app.extractors.openai_compatible_client import OpenAICompatibleChatClient
    from app.graph.runner import run_p9m1_graph

    original = OpenAICompatibleChatClient.create_chat_completion

    def mock_completion(self, messages):
        return {"choices": [{"message": {"content": _mock_content_for(messages[1]["content"])}}]}

    predictions: list[dict[str, Any]] = []
    backends = ["fake", "fallback", "local_lora"]
    try:
        OpenAICompatibleChatClient.create_chat_completion = mock_completion
        for backend in backends:
            for case in CASES:
                result = run_p9m1_graph(case["user_input"], extractor_backend=backend, use_langgraph=False)
                state = result.get("run_state") or {}
                prediction = {
                    "backend": backend,
                    "case_id": case["case_id"],
                    "chief_complaint": state.get("chief_complaint"),
                    "duration": state.get("duration"),
                    "risk_status": result.get("risk_status"),
                    "fallback_used": (result.get("extracted_turn_output") or {}).get("metadata", {}).get("fallback_used"),
                    "schema_guard": (result.get("extracted_turn_output") or {}).get("metadata", {}).get("schema_guard"),
                    "chief_match": state.get("chief_complaint") == case["expected_chief"],
                    "duration_match": state.get("duration") == case["expected_duration"],
                    "risk_match": result.get("risk_status") == case["expected_risk"],
                }
                prediction["case_passed"] = bool(
                    prediction["chief_match"] and prediction["duration_match"] and prediction["risk_match"]
                )
                predictions.append(prediction)
    finally:
        OpenAICompatibleChatClient.create_chat_completion = original

    metrics: dict[str, Any] = {}
    for backend in backends:
        rows = [item for item in predictions if item["backend"] == backend]
        total = max(1, len(rows))
        metrics[backend] = {
            "case_count": len(rows),
            "case_pass_rate": sum(1 for item in rows if item["case_passed"]) / total,
            "chief_match_rate": sum(1 for item in rows if item["chief_match"]) / total,
            "duration_match_rate": sum(1 for item in rows if item["duration_match"]) / total,
            "risk_match_rate": sum(1 for item in rows if item["risk_match"]) / total,
            "fallback_used_rate": sum(1 for item in rows if item["fallback_used"]) / total,
        }

    result = {
        "status": "ok",
        "branch": _git(["branch", "--show-current"]),
        "commit": _git(["rev-parse", "--short", "HEAD"]),
        "metrics": metrics,
        "predictions": predictions,
        "live_local_lora": {
            "status": "skipped",
            "skip_reason": "backend_compare uses deterministic mock local_lora on Device1",
        },
        "artifacts": {
            "backend_compare_metrics": str(DEFAULT_OUTPUT.relative_to(ROOT_DIR)).replace("\\", "/"),
        },
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="P10M3 backend compare eval scaffold.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Artifact output path.")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    result = run_eval()
    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT_DIR / output
    _write_json(output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) if args.json else result["status"])
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
