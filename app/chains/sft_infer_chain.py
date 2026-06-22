import json
import re
from typing import Any, Dict, Optional, Tuple

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer
from app.utils.sft_postprocess import postprocess_turn_output


DEFAULT_BASE_MODEL_PATH = r"E:\models\Qwen2.5-1.5B-Instruct"
DEFAULT_ADAPTER_PATH = r"outputs\sft_lora_run2_manual_only\final_adapter"


def build_sft_messages(state_json: Dict[str, Any], user_input: str) -> list[dict[str, str]]:
    system_prompt = (
        "你是中医问诊辅助系统中的单轮结构化抽取模块。\n"
        "请根据历史状态 state_json 和当前用户输入 user_input，输出本轮结构化 JSON。\n"
        "这是中医问诊辅助系统，不是诊断模型。\n"
        "不要输出诊断，不要输出 final_report，不要输出额外字段。\n"
        "只允许输出以下字段：\n"
        "chief_complaint, duration, symptoms, symptoms_status, sleep, appetite, "
        "stool_urine, risk_flags, risk_flags_status, next_question, summary。\n"
        "其中 symptoms_status 和 risk_flags_status 只能是 unknown / none / present。\n"
        "next_question 只能是 null 或字符串。\n"
        "严格输出 JSON object。"
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
    text = (text or "").strip()
    if not text:
        return None

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
    if fenced:
        return fenced.group(1).strip()

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


def parse_json_output(raw_text: str) -> Optional[Dict[str, Any]]:
    json_text = extract_json_object_text(raw_text)
    if not json_text:
        return None
    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        return None


class SFTInferChain:
    def __init__(
        self,
        base_model_path: str = DEFAULT_BASE_MODEL_PATH,
        adapter_path: str = DEFAULT_ADAPTER_PATH,
        max_new_tokens: int = 256,
        temperature: float = 0.0,
    ) -> None:
        self.base_model_path = base_model_path
        self.adapter_path = adapter_path
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature

        self.tokenizer = None
        self.model = None

    def load(self) -> None:
        if self.model is not None and self.tokenizer is not None:
            return

        tokenizer = AutoTokenizer.from_pretrained(
            self.base_model_path,
            trust_remote_code=True,
        )
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        base_model = AutoModelForCausalLM.from_pretrained(
            self.base_model_path,
            trust_remote_code=True,
            torch_dtype="auto",
            device_map="auto",
        )

        # 防止重复挂载 adapter
        if hasattr(base_model, "peft_config"):
            model = base_model
        else:
            model = PeftModel.from_pretrained(base_model, self.adapter_path)

        if hasattr(model, "generation_config") and model.generation_config is not None:
            model.generation_config.do_sample = False
            model.generation_config.temperature = None
            model.generation_config.top_p = None
            model.generation_config.top_k = None

        model.eval()

        self.tokenizer = tokenizer
        self.model = model

        print("[sft_infer_chain] base model has peft_config:", hasattr(base_model, "peft_config"))
        print("[sft_infer_chain] final model has peft_config:", hasattr(model, "peft_config"))

    def generate_raw(self, state_json: Dict[str, Any], user_input: str) -> str:
        self.load()
        assert self.model is not None
        assert self.tokenizer is not None

        messages = build_sft_messages(state_json=state_json, user_input=user_input)

        prompt_text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        inputs = self.tokenizer(prompt_text, return_tensors="pt")
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}

        generate_kwargs = {
            "max_new_tokens": self.max_new_tokens,
            "pad_token_id": self.tokenizer.pad_token_id,
            "eos_token_id": self.tokenizer.eos_token_id,
        }

        if self.temperature and self.temperature > 0:
            generate_kwargs["do_sample"] = True
            generate_kwargs["temperature"] = self.temperature
            generate_kwargs["top_p"] = 0.9
        else:
            generate_kwargs["do_sample"] = False

        with torch.no_grad():
            outputs = self.model.generate(**inputs, **generate_kwargs)

        input_len = inputs["input_ids"].shape[1]
        new_tokens = outputs[0][input_len:]
        decoded = self.tokenizer.decode(new_tokens, skip_special_tokens=True)
        return decoded.strip()

    def run(
        self,
        state_json: Dict[str, Any],
        user_input: str,
    ) -> Dict[str, Any]:
        raw_text = self.generate_raw(state_json=state_json, user_input=user_input)
        parsed = parse_json_output(raw_text)

        if parsed is None:
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
                "summary": "模型输出未成功解析为 JSON，本轮结果已回退为默认结构。",
                "_debug": {
                    "raw_text": raw_text,
                    "parsed": None,
                    "parse_failed": True,
                },
            }

        fixed = postprocess_turn_output(
            parsed_output=parsed,
            state_json=state_json,
            user_input=user_input,
        )
        fixed["_debug"] = {
            "raw_text": raw_text,
            "parsed": parsed,
            "parse_failed": False,
        }
        return fixed

    def run_with_debug(
        self,
        state_json: Dict[str, Any],
        user_input: str,
    ) -> Tuple[Dict[str, Any], str, Optional[Dict[str, Any]]]:
        raw_text = self.generate_raw(state_json=state_json, user_input=user_input)
        parsed = parse_json_output(raw_text)

        if parsed is None:
            fallback = {
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
                "summary": "模型输出未成功解析为 JSON，本轮结果已回退为默认结构。",
            }
            return fallback, raw_text, None

        fixed = postprocess_turn_output(
            parsed_output=parsed,
            state_json=state_json,
            user_input=user_input,
        )
        return fixed, raw_text, parsed


_default_chain: Optional[SFTInferChain] = None


def get_sft_infer_chain(
    base_model_path: str = DEFAULT_BASE_MODEL_PATH,
    adapter_path: str = DEFAULT_ADAPTER_PATH,
) -> SFTInferChain:
    global _default_chain
    if _default_chain is None:
        _default_chain = SFTInferChain(
            base_model_path=base_model_path,
            adapter_path=adapter_path,
        )
    return _default_chain


def run_sft_turn(
    state_json: Dict[str, Any],
    user_input: str,
    base_model_path: str = DEFAULT_BASE_MODEL_PATH,
    adapter_path: str = DEFAULT_ADAPTER_PATH,
) -> Dict[str, Any]:
    chain = get_sft_infer_chain(
        base_model_path=base_model_path,
        adapter_path=adapter_path,
    )
    return chain.run(state_json=state_json, user_input=user_input)
