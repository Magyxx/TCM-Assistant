from __future__ import annotations

import argparse
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


DEMO_CASES = [
    "胃胀一周，没有发热，不胸痛",
    "胸痛伴呼吸困难",
    "便血两天",
    "头痛三天，未见发热",
    "睡眠差一个月，食欲一般",
]


def compact_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "session_id": result.get("session_id"),
        "graph_runtime": result.get("graph_runtime"),
        "extracted_turn_output": result.get("extracted_turn_output"),
        "run_state": result.get("run_state"),
        "risk_status": result.get("risk_status"),
        "risk_reasons": result.get("risk_reasons"),
        "missing_core_fields": result.get("missing_core_fields"),
        "next_question": result.get("next_question"),
        "retrieved_evidence": result.get("retrieved_evidence"),
        "final_report": result.get("final_report"),
        "trace": result.get("trace"),
        "errors": result.get("errors"),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run P9M1 real-path consultation graph demo.")
    parser.add_argument("--input", help="Single user input to run through the P9M1 graph.")
    parser.add_argument("--backend", default=os.getenv("EXTRACTOR_BACKEND", "fake"), help="Extractor backend: fake, rule_fallback, real_llm.")
    parser.add_argument("--sequential", action="store_true", help="Force the sequential fallback runner.")
    parser.add_argument("--all-cases", action="store_true", help="Run the built-in demo cases.")
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()
    inputs = DEMO_CASES if args.all_cases or not args.input else [args.input]
    outputs = []
    for item in inputs:
        result = run_p9m1_graph(
            item,
            extractor_backend=args.backend,
            use_langgraph=not args.sequential,
            rag_enabled=True,
        )
        outputs.append({"input": item, "result": compact_result(result)})
    payload: Any = outputs[0]["result"] if len(outputs) == 1 else outputs
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
