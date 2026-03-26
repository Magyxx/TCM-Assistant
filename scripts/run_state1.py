from app.schemas.stateful1_schemas import RunState
from app.chains.stateful1_chain import run_turn, generate_final_summary


def print_state(state: RunState):
    print("\n当前累计状态：")
    print(state.model_dump_json(indent=2, ensure_ascii=False))

    if state.next_question:
        print(f"\n下一问：{state.next_question}")
    else:
        print("\n系统已不再继续追问。")
        print("总结如下：")
        print(generate_final_summary(state))
    print("-" * 60)


def main():
    state = RunState()

    print("中医问诊辅助系统（stateful 版本），输入 exit 退出。")
    while True:
        user_input = input("用户: ").strip()
        if user_input.lower() == "exit":
            break

        state = run_turn(state, user_input)
        print_state(state)


if __name__ == "__main__":
    main()