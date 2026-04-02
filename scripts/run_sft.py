import argparse
import json
from pathlib import Path
from typing import Optional

from app.chains.report_chain import merge_state
from app.chains.sft_infer_chain import run_sft_turn
from app.schemas.report_schemas import RunState, TurnOutput


DEFAULT_BASE_MODEL_PATH = r"E:\models\Qwen2.5-1.5B-Instruct"
DEFAULT_ADAPTER_PATH = r"outputs\sft_lora_run2_manual_only\final_adapter"


def print_state(state: RunState) -> None:
    print("\n" + "=" * 80)
    print("[CURRENT STATE]")
    print(json.dumps(state.model_dump(), ensure_ascii=False, indent=2))
    print("=" * 80 + "\n")


def load_state_from_file(path: str) -> RunState:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return RunState.model_validate(data)


def save_state_to_file(state: RunState, path: str) -> None:
    Path(path).write_text(
        json.dumps(state.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def run_one_turn(
    state: RunState,
    user_input: str,
    base_model_path: str,
    adapter_path: str,
    show_debug: bool = True,
) -> RunState:
    state_json = state.model_dump()

    sft_result = run_sft_turn(
        state_json=state_json,
        user_input=user_input,
        base_model_path=base_model_path,
        adapter_path=adapter_path,
    )

    debug_info = sft_result.pop("_debug", None)

    turn_output = TurnOutput.model_validate(sft_result)

    if show_debug and debug_info is not None:
        print("\n" + "-" * 80)
        print("[SFT RAW OUTPUT]")
        print(debug_info.get("raw_text"))
        print("\n[SFT PARSED OUTPUT]")
        print(json.dumps(debug_info.get("parsed"), ensure_ascii=False, indent=2))
        print("\n[SFT POSTPROCESSED OUTPUT]")
        print(json.dumps(turn_output.model_dump(), ensure_ascii=False, indent=2))
        print("-" * 80 + "\n")

    new_state = merge_state(state, turn_output, user_input)
    return new_state


def interactive_loop(
    base_model_path: str,
    adapter_path: str,
    init_state: Optional[RunState] = None,
    save_state_path: Optional[str] = None,
) -> None:
    state = init_state or RunState()

    print("[run_sft] 已进入本地 SFT 交互模式")
    print(f"[run_sft] base_model_path = {base_model_path}")
    print(f"[run_sft] adapter_path    = {adapter_path}")
    print("输入 exit / quit 退出，输入 state 查看当前状态，输入 save 保存状态。\n")

    while True:
        user_input = input("用户：").strip()

        if not user_input:
            continue

        if user_input.lower() in {"exit", "quit"}:
            print("[run_sft] 退出")
            break

        if user_input.lower() == "state":
            print_state(state)
            continue

        if user_input.lower() == "save":
            if save_state_path:
                save_state_to_file(state, save_state_path)
                print(f"[run_sft] 状态已保存到: {save_state_path}")
            else:
                print("[run_sft] 未指定 --save-state-path，无法保存")
            continue

        try:
            state = run_one_turn(
                state=state,
                user_input=user_input,
                base_model_path=base_model_path,
                adapter_path=adapter_path,
                show_debug=True,
            )
        except Exception as e:
            print(f"[run_sft] 本轮执行失败: {e}")
            continue

        print_state(state)

        if save_state_path:
            save_state_to_file(state, save_state_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="本地 SFT LoRA 问诊交互脚本")
    parser.add_argument(
        "--base-model-path",
        default=DEFAULT_BASE_MODEL_PATH,
        help="基础模型本地目录",
    )
    parser.add_argument(
        "--adapter-path",
        default=DEFAULT_ADAPTER_PATH,
        help="LoRA adapter 目录",
    )
    parser.add_argument(
        "--load-state-path",
        default=None,
        help="从 JSON 文件加载初始 RunState",
    )
    parser.add_argument(
        "--save-state-path",
        default=None,
        help="将当前 RunState 持续保存到 JSON 文件",
    )
    args = parser.parse_args()

    if args.load_state_path:
        state = load_state_from_file(args.load_state_path)
    else:
        state = RunState()

    interactive_loop(
        base_model_path=args.base_model_path,
        adapter_path=args.adapter_path,
        init_state=state,
        save_state_path=args.save_state_path,
    )


if __name__ == "__main__":
    main()