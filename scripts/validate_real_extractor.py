from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

from app.chains.turn_extractor import extract_turn, get_missing_api_config
from app.rules.risk_rules import evaluate_risk_rules
from app.schemas.report_schemas import RunState


P0_3_RESULT_PATH = BASE_DIR / "artifacts" / "p0_3_real_llm_eval_result.json"


DEFAULT_CASES = [
    "我胃胀两天，没有其他症状，也没有胸痛",
    "我发烧了",
    "我持续高烧三天",
    "没有胸痛，也不便血",
    "后来胸闷喘不上气",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate real LLM extraction path without leaking secrets.")
    parser.add_argument("--case", action="append", help="User input case. Can be passed multiple times.")
    parser.add_argument("--limit", type=int, default=5)
    return parser.parse_args()


def _present_or_missing(value: str | None) -> str:
    return "present" if value else "missing"


def _module_status(module_name: str) -> str:
    return "present" if importlib.util.find_spec(module_name) is not None else "missing"


def _env_snapshot() -> dict:
    statuses = {
        "langgraph": _module_status("langgraph"),
        "langchain_openai": _module_status("langchain_openai"),
        "rank_bm25": _module_status("rank_bm25"),
        "pydantic": _module_status("pydantic"),
        "python_dotenv": _module_status("dotenv"),
        "openai_api_key": _present_or_missing(os.getenv("OPENAI_API_KEY")),
        "openai_base_url": _present_or_missing(os.getenv("OPENAI_BASE_URL")),
        "openai_model": _present_or_missing(os.getenv("OPENAI_MODEL")),
    }
    real_deps = (
        statuses["langgraph"] == "present"
        and statuses["langchain_openai"] == "present"
        and statuses["rank_bm25"] == "present"
    )
    api_ready = (
        statuses["openai_api_key"] == "present"
        and statuses["openai_base_url"] == "present"
        and statuses["openai_model"] == "present"
    )
    statuses["mode"] = "real-ready" if real_deps and api_ready else ("partial-real" if real_deps or api_ready else "fallback-only")
    return statuses


def _load_p0_3_result() -> dict:
    if P0_3_RESULT_PATH.exists():
        try:
            return json.loads(P0_3_RESULT_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "env": {},
        "smoke_cases": [],
        "eval_comparison": {},
        "decision": {},
    }


def _write_smoke_result(row: dict) -> None:
    P0_3_RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = _load_p0_3_result()
    data["env"] = _env_snapshot()
    cases = [item for item in data.get("smoke_cases", []) if item.get("input") != row.get("input")]
    cases.append(row)
    data["smoke_cases"] = cases
    P0_3_RESULT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def print_case(index: int, text: str) -> None:
    result = extract_turn(RunState(), text, extractor_mode="real_llm")
    turn = result.turn_output
    risk_eval = evaluate_risk_rules(text)
    row = {
        "input": text,
        "raw_llm_json_valid": result.raw_llm_json_valid,
        "final_schema_pass": result.final_schema_pass,
        "fallback_used": result.fallback_used,
        "extractor_mode": result.extractor_mode or result.mode,
        "strategy": result.strategy,
        "model_name": result.model_name,
        "chief_complaint": turn.chief_complaint if turn else None,
        "duration": turn.duration if turn else None,
        "accompanying_symptoms": turn.symptoms if turn else None,
        "risk_flags_status": turn.risk_flags_status if turn else None,
        "risk_rule_ids": risk_eval.triggered_rule_ids,
        "risk_reasons": risk_eval.risk_reasons,
        "error_type": result.error_type,
        "error_message_preview": result.error_message_preview,
    }
    _write_smoke_result(row)

    print(f"\n[case {index}]")
    print(f"input: {text}")
    print(f"raw_llm_json_valid: {result.raw_llm_json_valid}")
    print(f"final_schema_pass: {result.final_schema_pass}")
    print(f"fallback_used: {result.fallback_used}")
    print(f"extractor_mode: {result.extractor_mode or result.mode}")
    print(f"strategy: {result.strategy}")
    print(f"model_name: {result.model_name}")
    print(f"chief_complaint: {turn.chief_complaint if turn else None}")
    print(f"duration: {turn.duration if turn else None}")
    print(f"accompanying_symptoms: {turn.symptoms if turn else None}")
    print(f"risk_flags_status: {turn.risk_flags_status if turn else None}")
    print(f"risk_rule_ids: {risk_eval.triggered_rule_ids}")
    print(f"risk_reasons: {risk_eval.risk_reasons}")
    print(f"error_type: {result.error_type}")
    print(f"error_message_preview: {result.error_message_preview}")
    if result.error:
        print(f"error: {result.error}")


def main() -> None:
    args = parse_args()

    if load_dotenv is not None:
        load_dotenv(BASE_DIR / ".env")

    missing = get_missing_api_config()
    if missing:
        print("real_llm_validation_skipped: missing_api_config")
        print(f"missing_api_config: {','.join(missing)}")
        return

    cases = args.case or DEFAULT_CASES
    for index, text in enumerate(cases[: args.limit], start=1):
        print_case(index, text)


if __name__ == "__main__":
    main()
