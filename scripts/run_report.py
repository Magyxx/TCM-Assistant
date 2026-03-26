from app.schemas.report_schemas import RunState
from app.chains.report_chain import run_turn


def print_final_report(state: RunState):
    report = state.final_report
    if report is None:
        print("\n当前尚未生成 final_report。")
        return

    print("\n最终结构化结果：")
    print(f"triage_level: {report.triage_level}")
    print(f"info_complete: {report.info_complete}")
    print(f"followup_needed: {report.followup_needed}")

    if report.missing_core_fields:
        print("missing_core_fields:", "、".join(report.missing_core_fields))
    else:
        print("missing_core_fields: 无")

    print("\n[Summary]")
    print(report.summary)

    print("\n[Impression]")
    print(report.impression)

    print("\n[Advice]")
    for idx, item in enumerate(report.advice, start=1):
        print(f"{idx}. {item}")


def print_state(state: RunState):
    print("\n当前累计状态：")
    print(state.model_dump_json(indent=2, ensure_ascii=False))

    if state.next_question:
        print(f"\n下一问：{state.next_question}")
    else:
        print("\n系统已不再继续追问。")
        print_final_report(state)

    print("-" * 60)


def main():
    state = RunState()

    print("中医问诊辅助系统（report 版本），输入 exit 退出。")
    while True:
        user_input = input("用户: ").strip()
        if user_input.lower() == "exit":
            break

        state = run_turn(state, user_input)
        print_state(state)


if __name__ == "__main__":
    main()