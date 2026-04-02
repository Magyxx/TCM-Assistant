import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from app.utils.sft_postprocess import postprocess_turn_output

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer


DEFAULT_MODEL_PATH = r"E:\models\Qwen2.5-1.5B-Instruct"
DEFAULT_ADAPTER_PATH = r"outputs\sft_lora_run2_manual_only\final_adapter"


def build_messages(state_json: Dict[str, Any], user_input: str) -> List[Dict[str, str]]:
    system_prompt = (
        "你是中医问诊辅助系统中的结构化抽取模块。"
        "请结合历史状态和当前用户输入，输出本轮结构化 JSON。"
        "该系统不是诊断模型，不输出确定性诊断。"
        "请优先抽取 chief_complaint、duration、symptoms、risk_flags 及其状态。"
        "严格输出 JSON。"
    )

    user_content = (
        "【历史状态 state_json】\n"
        f"{json.dumps(state_json, ensure_ascii=False, indent=2)}\n\n"
        "【当前用户输入 user_input】\n"
        f"{user_input}\n\n"
        "请基于以上内容输出严格 JSON。"
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]


def extract_json_object_text(text: str) -> Optional[str]:
    text = text.strip()

    # 先尝试 ```json ... ```
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
    if fenced:
        return fenced.group(1).strip()

    # 再尝试直接找第一个完整大括号对象
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1].strip()

    return None


def parse_json_output(text: str) -> Optional[Dict[str, Any]]:
    json_text = extract_json_object_text(text)
    if not json_text:
        return None

    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        return None


def load_model_and_tokenizer(model_path: str, adapter_path: str):
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    base_model = AutoModelForCausalLM.from_pretrained(
        model_path,
        trust_remote_code=True,
        torch_dtype="auto",
        device_map="auto",
    )

    model = PeftModel.from_pretrained(base_model, adapter_path)
    model.eval()

    return model, tokenizer


def generate_once(
    model,
    tokenizer,
    state_json: Dict[str, Any],
    user_input: str,
    max_new_tokens: int = 256,
    temperature: float = 0.2,
) -> str:
    messages = build_messages(state_json=state_json, user_input=user_input)

    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )

    inputs = tokenizer(
        text,
        return_tensors="pt",
    )

    inputs = {k: v.to(model.device) for k, v in inputs.items()}

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False if temperature == 0 else True,
            temperature=temperature,
            top_p=0.9,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )

    input_len = inputs["input_ids"].shape[1]
    new_tokens = outputs[0][input_len:]
    decoded = tokenizer.decode(new_tokens, skip_special_tokens=True)
    return decoded.strip()


def default_state() -> Dict[str, Any]:
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


def run_demo_cases(model, tokenizer) -> None:
    demo_cases = [
        {
            "name": "A1风格-单轮低风险",
            "state_json": default_state(),
            "user_input": "最近胃胀一周了，没有腹痛，也没有呕吐、便血这些情况。",
        },
        {
            "name": "否定句风险识别",
            "state_json": {
                "chief_complaint": "腹痛",
                "duration": "一天",
                "symptoms": [],
                "symptoms_status": "unknown",
                "sleep": None,
                "appetite": None,
                "stool_urine": None,
                "risk_flags": [],
                "risk_flags_status": "unknown",
                "next_question": "最近有没有出现便血、呕血、胸痛、呼吸困难等情况？",
                "summary": "",
                "final_report": None,
            },
            "user_input": "没有便血，也没有呕血。",
        },
        {
            "name": "症状新增",
            "state_json": {
                "chief_complaint": "腹泻",
                "duration": "三天",
                "symptoms": [],
                "symptoms_status": "none",
                "sleep": None,
                "appetite": None,
                "stool_urine": None,
                "risk_flags": [],
                "risk_flags_status": "none",
                "next_question": None,
                "summary": "用户主诉腹泻三天，之前已确认没有其他伴随症状和高危表现。",
                "final_report": None,
            },
            "user_input": "今天又开始头晕了。",
        },
    ]

    for idx, case in enumerate(demo_cases, start=1):
        print("=" * 80)
        print(f"[CASE {idx}] {case['name']}")
        print("- user_input:", case["user_input"])

        raw_output = generate_once(
            model=model,
            tokenizer=tokenizer,
            state_json=case["state_json"],
            user_input=case["user_input"],
        )

        print("\n[RAW OUTPUT]")
        parsed = parse_json_output(raw_output)
        print("\n[PARSED JSON]")
        if parsed is None:
            print("解析失败：未提取到合法 JSON")
        else:
            print(json.dumps(parsed, ensure_ascii=False, indent=2))

            fixed = postprocess_turn_output(
                parsed_output=parsed,
                state_json=case["state_json"],
                user_input=case["user_input"],
            )
            print("\n[POSTPROCESSED JSON]")
            print(json.dumps(fixed, ensure_ascii=False, indent=2))
        print()


def main():
    parser = argparse.ArgumentParser(description="测试 SFT LoRA adapter 推理效果")
    parser.add_argument("--model-path", default=DEFAULT_MODEL_PATH)
    parser.add_argument("--adapter-path", default=DEFAULT_ADAPTER_PATH)
    parser.add_argument("--user-input", default=None)
    parser.add_argument("--state-json", default=None, help="可传入 JSON 文件路径")
    args = parser.parse_args()

    model_path = args.model_path
    adapter_path = args.adapter_path

    print(f"[load] base model: {model_path}")
    print(f"[load] adapter   : {adapter_path}")

    model, tokenizer = load_model_and_tokenizer(
        model_path=model_path,
        adapter_path=adapter_path,
    )

    if args.user_input is not None:
        if args.state_json:
            state_path = Path(args.state_json)
            state_json = json.loads(state_path.read_text(encoding="utf-8"))
        else:
            state_json = default_state()

        raw_output = generate_once(
            model=model,
            tokenizer=tokenizer,
            state_json=state_json,
            user_input=args.user_input,
        )

        print("\n[RAW OUTPUT]")
        print(raw_output)

        parsed = parse_json_output(raw_output)
        print("\n[PARSED JSON]")
        if parsed is None:
            print("解析失败：未提取到合法 JSON")
        else:
            print(json.dumps(parsed, ensure_ascii=False, indent=2))

            fixed = postprocess_turn_output(
                parsed_output=parsed,
                state_json=state_json,
                user_input=args.user_input,
            )
            print("\n[POSTPROCESSED JSON]")
            print(json.dumps(fixed, ensure_ascii=False, indent=2))
    else:
        run_demo_cases(model, tokenizer)


if __name__ == "__main__":
    main()