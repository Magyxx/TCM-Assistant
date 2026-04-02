import json

from app.chains.sft_infer_chain import run_sft_turn


def default_state():
    return {
        "chief_complaint": None,
        "duration": None,
        "symptoms": [],
        "symptoms_status": "unknown",
        "sleep": None,
        "appetite": None,
        "stool_urine": None,
        "risk_flags": [],
        "risk_flags_status": "unknown",
        "next_question": None,
        "summary": "",
        "final_report": None,
    }


if __name__ == "__main__":
    state_json = default_state()
    user_input = "最近胃胀一周了，没有腹痛，也没有呕吐、便血这些情况。"

    result = run_sft_turn(
        state_json=state_json,
        user_input=user_input,
        base_model_path=r"E:\models\Qwen2.5-1.5B-Instruct",
        adapter_path=r"outputs\sft_lora_run2_manual_only\final_adapter",
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))