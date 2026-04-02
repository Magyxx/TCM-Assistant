from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from app.prompts.sft_prompt import build_sft_user_message
from app.schemas.sft_schemas import SFTMessagesSample, SFTSample


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "sft" / "raw" / "sft_report_turn_extract_raw.jsonl"
DEFAULT_OUT_DIR = ROOT / "data" / "sft" / "processed"


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def to_messages(sample: Dict[str, Any]) -> Dict[str, Any]:
    validated = SFTSample.model_validate(sample)
    assistant_json = json.dumps(validated.output.model_dump(mode="json"), ensure_ascii=False)
    message_sample = SFTMessagesSample(
        id=validated.id,
        task=validated.task,
        messages=[
            {"role": "system", "content": validated.system_prompt},
            {
                "role": "user",
                "content": build_sft_user_message(
                    state_json=validated.input.state_json,
                    user_input=validated.input.user_input,
                ),
            },
            {"role": "assistant", "content": assistant_json},
        ],
        meta=validated.meta,
    )
    return message_sample.model_dump(mode="json")


def split_rows(rows: List[Dict[str, Any]], val_ratio: float) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    if not rows:
        return [], []
    split_index = max(1, int(len(rows) * (1 - val_ratio))) if len(rows) > 1 else 1
    split_index = min(split_index, len(rows) - 1) if len(rows) > 1 else 1
    if len(rows) == 1:
        return rows, []
    return rows[:split_index], rows[split_index:]


def main() -> None:
    parser = argparse.ArgumentParser(description="将 SFT 原始样本转换为 messages 训练格式")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--val-ratio", type=float, default=0.2)
    args = parser.parse_args()

    rows = read_jsonl(args.input)
    train_rows, val_rows = split_rows(rows, args.val_ratio)

    train_messages = [to_messages(row) for row in train_rows]
    val_messages = [to_messages(row) for row in val_rows]

    write_jsonl(args.out_dir / "sft_report_turn_extract_train.jsonl", train_rows)
    write_jsonl(args.out_dir / "sft_report_turn_extract_val.jsonl", val_rows)
    write_jsonl(args.out_dir / "sft_report_turn_extract_train_messages.jsonl", train_messages)
    write_jsonl(args.out_dir / "sft_report_turn_extract_val_messages.jsonl", val_messages)

    print(f"[convert_sft_dataset] train={len(train_rows)}, val={len(val_rows)}")
    print(f"[convert_sft_dataset] 输出目录: {args.out_dir}")


if __name__ == "__main__":
    main()
