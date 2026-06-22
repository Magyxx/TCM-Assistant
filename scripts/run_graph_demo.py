from __future__ import annotations

import argparse
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.chains.turn_extractor import get_missing_api_config
from app.graphs.consultation_graph import run_consultation_graph
from app.schemas.report_schemas import RunState


DEFAULT_TURNS = {
    "fake": ["我胃胀两天，没有其他症状，也没有胸痛"],
    "fallback": ["我持续高烧三天"],
    "real_llm": ["我胃胀两天，没有其他症状，也没有胸痛"],
}


def print_state(state: RunState, graph_state: dict) -> None:
    print("\n[GRAPH DEMO STATE]")
    print(state.model_dump_json(indent=2, ensure_ascii=False))
    print("[GRAPH DEMO METADATA]")
    print(f"graph_runtime: {graph_state.get('graph_runtime')}")
    print(f"extractor_mode_requested: {graph_state.get('extractor_mode_requested')}")
    print(f"extractor_mode: {graph_state.get('extractor_mode')}")
    print(f"extraction_mode: {graph_state.get('extraction_mode')}")
    print(f"strategy: {graph_state.get('strategy')}")
    print(f"model_name: {graph_state.get('model_name')}")
    print(f"fallback_used: {graph_state.get('fallback_used')}")
    print(f"final_schema_pass: {graph_state.get('final_schema_pass')}")
    print(f"error_type: {graph_state.get('error_type')}")
    print(f"risk_rule_ids: {graph_state.get('triggered_rule_ids') or state.triggered_rule_ids}")

    if state.next_question:
        print(f"\n下一问：{state.next_question}")
    elif state.final_report:
        print("\n最终结构化结果：")
        print(state.final_report.model_dump_json(indent=2, ensure_ascii=False))
    else:
        print("\n系统已停止常规追问。")

    if graph_state.get("errors"):
        print("\n[graph warnings]")
        for item in graph_state["errors"]:
            print("-", item)

    print("-" * 60)


def run_turns(turns: list[str], extractor: str, use_langgraph: bool = True) -> RunState:
    run_state = RunState()
    active_extractor = extractor
    if extractor == "real_llm" and get_missing_api_config():
        print("real_llm_validation_skipped: missing_api_config")
        print(f"missing_api_config: {','.join(get_missing_api_config())}")
        active_extractor = "fallback"

    for user_input in turns:
        print(f"用户: {user_input}")
        graph_state = run_consultation_graph(
            run_state=run_state,
            user_input=user_input,
            use_langgraph=use_langgraph,
            extractor_mode=active_extractor,
        )
        run_state = graph_state["run_state"]
        print_state(run_state, graph_state)
    return run_state


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LangGraph consultation demo for P0/P0.2 validation.")
    parser.add_argument("--extractor", choices=["fake", "fallback", "real_llm"], default="fallback")
    parser.add_argument("--turn", action="append", help="Add a user turn for the non-interactive demo.")
    parser.add_argument("--interactive", action="store_true", help="Run an interactive CLI loop.")
    parser.add_argument("--sequential", action="store_true", help="Force the sequential graph fallback runner.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    use_langgraph = not args.sequential

    if not args.interactive:
        turns = args.turn or DEFAULT_TURNS[args.extractor]
        run_turns(turns=turns, extractor=args.extractor, use_langgraph=use_langgraph)
        return

    run_state = RunState()
    active_extractor = args.extractor
    if args.extractor == "real_llm" and get_missing_api_config():
        print("real_llm_validation_skipped: missing_api_config")
        print(f"missing_api_config: {','.join(get_missing_api_config())}")
        active_extractor = "fallback"

    print("中医问诊辅助系统（LangGraph P0 demo），输入 exit 退出。")
    while True:
        user_input = input("用户: ").strip()
        if user_input.lower() == "exit":
            break

        graph_state = run_consultation_graph(
            run_state=run_state,
            user_input=user_input,
            use_langgraph=use_langgraph,
            extractor_mode=active_extractor,
        )
        run_state = graph_state["run_state"]
        print_state(run_state, graph_state)


if __name__ == "__main__":
    main()
