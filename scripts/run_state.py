import json
from app.chains.stateful_chain import chain

def main():
    state = {
        "chief_complaint": None,
        "duration": None,
        "symptoms": [],
        "sleep": None,
        "appetite": None,
        "stool_urine": None,
        "risk_flags": [],
        "next_question": None,
        "summary": None
    }

    print("中医问诊辅助系统（带状态累积），输入 exit 退出。")

    while True:
        text = input("用户: ").strip()
        if text.lower() == "exit":
            break

        response = chain.invoke({
            "current_state": json.dumps(state, ensure_ascii=False, indent=2),
            "user_input": text
        })

        new_state = json.loads(response.content)
        state = new_state

        print("当前问诊状态：")
        print(json.dumps(state, ensure_ascii=False, indent=2))
        print("-" * 50)

if __name__ == "__main__":
    main()