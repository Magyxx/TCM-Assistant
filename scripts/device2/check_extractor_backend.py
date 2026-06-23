from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.chains.turn_extractor import extract_turn
from app.extractors.router import get_extractor_backend
from app.graphs.consultation_graph import run_consultation_graph
from app.schemas.report_schemas import RunState, TurnOutput


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Print and smoke-test the active ExtractorBackend.")
    parser.add_argument("--backend", default=os.getenv("EXTRACTOR_BACKEND", "local_lora"))
    parser.add_argument("--base-url", default=os.getenv("LOCAL_LLM_BASE_URL", "http://127.0.0.1:8000/v1"))
    parser.add_argument("--model", default=os.getenv("LOCAL_LLM_MODEL", "tcm-extractor-lora"))
    parser.add_argument("--api-key", default=os.getenv("LOCAL_LLM_API_KEY", "EMPTY"))
    parser.add_argument("--input", default="胃胀一周，饭后明显，没有发热，不胸痛")
    parser.add_argument("--run-graph", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def run(args: argparse.Namespace) -> dict[str, Any]:
    os.environ["EXTRACTOR_BACKEND"] = args.backend
    os.environ["LOCAL_LLM_BASE_URL"] = args.base_url
    os.environ["LOCAL_LLM_MODEL"] = args.model
    os.environ["LOCAL_LLM_API_KEY"] = args.api_key
    backend = get_extractor_backend(
        args.backend,
        base_url=args.base_url,
        model=args.model,
        api_key=args.api_key,
        allow_fallback=False,
    )
    result = extract_turn(RunState(), args.input, extractor_mode="auto")
    schema_pass = False
    schema_error = None
    try:
        if result.turn_output is not None:
            TurnOutput.model_validate(result.turn_output.model_dump())
            schema_pass = True
    except Exception as exc:  # noqa: BLE001
        schema_error = f"{type(exc).__name__}: {exc}"

    graph_payload: dict[str, Any] | None = None
    if args.run_graph:
        graph = run_consultation_graph(
            RunState(),
            args.input,
            use_langgraph=False,
            extractor_mode="auto",
            rag_enabled=False,
        )
        run_state = graph.get("run_state") or RunState()
        graph_payload = {
            "graph_runtime": graph.get("graph_runtime"),
            "extractor_mode": graph.get("extractor_mode"),
            "schema_valid": graph.get("schema_valid"),
            "fallback_used": graph.get("fallback_used"),
            "risk_flags_status": run_state.risk_flags_status,
            "turn_count": run_state.turn_count,
            "errors": graph.get("errors") or [],
        }

    return {
        "EXTRACTOR_BACKEND": args.backend,
        "backend_class": backend.__class__.__name__,
        "input": args.input,
        "result": result.to_dict(),
        "turn_output_schema_pass": schema_pass,
        "turn_output_schema_error": schema_error,
        "graph": graph_payload,
    }


def main() -> None:
    args = parse_args()
    payload = run(args)
    if args.json:
        sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        return
    print(f"EXTRACTOR_BACKEND={payload['EXTRACTOR_BACKEND']}")
    print(f"backend_class={payload['backend_class']}")
    print(f"schema_pass={payload['turn_output_schema_pass']}")
    print(f"fallback_used={payload['result'].get('fallback_used')}")
    print(f"error={payload['result'].get('error')}")


if __name__ == "__main__":
    main()
