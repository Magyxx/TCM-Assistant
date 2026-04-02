from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

import torch
from datasets import Dataset
from peft import LoraConfig, TaskType
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    DataCollatorForLanguageModeling,
    Trainer,
    TrainingArguments,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRAIN = ROOT / "data" / "sft" / "processed" / "sft_report_turn_extract_train_messages.jsonl"
DEFAULT_VAL = ROOT / "data" / "sft" / "processed" / "sft_report_turn_extract_val_messages.jsonl"
DEFAULT_OUTPUT_DIR = ROOT / "outputs" / "sft_lora"


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def ensure_pad_token(tokenizer: AutoTokenizer) -> None:
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token


def format_messages(tokenizer: AutoTokenizer, messages: List[Dict[str, str]]) -> str:
    if hasattr(tokenizer, "apply_chat_template") and tokenizer.chat_template:
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=False,
        )
    # 兜底方案：即使底模没有 chat template，也能先跑通
    parts = []
    for msg in messages:
        role = msg["role"].upper()
        parts.append(f"[{role}]\n{msg['content']}")
    return "\n\n".join(parts)


def build_dataset(path: Path, tokenizer: AutoTokenizer, max_length: int) -> Dataset:
    rows = read_jsonl(path)
    texts = [format_messages(tokenizer, row["messages"]) for row in rows]
    dataset = Dataset.from_dict({"text": texts})

    def tokenize(batch: Dict[str, List[str]]) -> Dict[str, Any]:
        return tokenizer(
            batch["text"],
            truncation=True,
            max_length=max_length,
        )

    return dataset.map(tokenize, batched=True, remove_columns=["text"])


def guess_target_modules(model_name: str) -> List[str]:
    lowered = model_name.lower()
    if "qwen" in lowered or "llama" in lowered or "mistral" in lowered:
        return ["q_proj", "k_proj", "v_proj", "o_proj", "up_proj", "down_proj", "gate_proj"]
    if "chatglm" in lowered:
        return ["query_key_value", "dense", "dense_h_to_4h", "dense_4h_to_h"]
    return ["q_proj", "v_proj"]


def main() -> None:
    parser = argparse.ArgumentParser(description="使用 LoRA 训练单轮结构化抽取任务")
    parser.add_argument("--model-name", type=str, required=True, help="例如 Qwen/Qwen2.5-1.5B-Instruct")
    parser.add_argument("--train-file", type=Path, default=DEFAULT_TRAIN)
    parser.add_argument("--val-file", type=Path, default=DEFAULT_VAL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--max-length", type=int, default=1024)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--num-train-epochs", type=int, default=3)
    parser.add_argument("--per-device-train-batch-size", type=int, default=1)
    parser.add_argument("--per-device-eval-batch-size", type=int, default=1)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=8)
    parser.add_argument("--logging-steps", type=int, default=10)
    parser.add_argument("--eval-steps", type=int, default=50)
    parser.add_argument("--save-steps", type=int, default=50)
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument("--bf16", action="store_true")
    parser.add_argument("--fp16", action="store_true")
    args = parser.parse_args()

    tokenizer = AutoTokenizer.from_pretrained(args.model_name, use_fast=False)
    ensure_pad_token(tokenizer)

    dtype = torch.bfloat16 if args.bf16 else (torch.float16 if args.fp16 else torch.float32)
    model = AutoModelForCausalLM.from_pretrained(
        args.model_name,
        device_map="auto",
    )

    peft_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        inference_mode=False,
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        bias="none",
        target_modules=guess_target_modules(args.model_name),
    )

    # transformers 集成 PEFT 的常见方式
    model.add_adapter(peft_config)
    model.enable_adapters()

    train_dataset = build_dataset(args.train_file, tokenizer, args.max_length)
    eval_dataset = build_dataset(args.val_file, tokenizer, args.max_length) if args.val_file.exists() else None

    training_args = TrainingArguments(
        output_dir=str(args.output_dir),
        learning_rate=args.learning_rate,
        num_train_epochs=args.num_train_epochs,
        per_device_train_batch_size=args.per_device_train_batch_size,
        per_device_eval_batch_size=args.per_device_eval_batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        logging_steps=args.logging_steps,
        eval_strategy="steps" if eval_dataset is not None else "no",
        eval_steps=args.eval_steps,
        save_steps=args.save_steps,
        save_total_limit=2,
        bf16=args.bf16,
        fp16=args.fp16,
        report_to="none",
        remove_unused_columns=False,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        data_collator=DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False),
    )

    trainer.train()
    trainer.save_model(str(args.output_dir / "final_adapter"))
    tokenizer.save_pretrained(str(args.output_dir / "final_adapter"))

    print("[train_sft_lora] 训练完成")
    print(f"[train_sft_lora] 适配器输出目录: {args.output_dir / 'final_adapter'}")


if __name__ == "__main__":
    main()
