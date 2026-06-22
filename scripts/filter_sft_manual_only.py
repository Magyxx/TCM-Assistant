import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


DEFAULT_INPUT_TRAIN = Path("data/sft/processed/sft_report_turn_extract_train.jsonl")
DEFAULT_INPUT_VAL = Path("data/sft/processed/sft_report_turn_extract_val.jsonl")

DEFAULT_OUTPUT_TRAIN = Path("data/sft/processed/sft_report_turn_extract_train_manual_only.jsonl")
DEFAULT_OUTPUT_VAL = Path("data/sft/processed/sft_report_turn_extract_val_manual_only.jsonl")

DEFAULT_OUTPUT_TRAIN_MESSAGES = Path("data/sft/processed/sft_report_turn_extract_train_manual_only_messages.jsonl")
DEFAULT_OUTPUT_VAL_MESSAGES = Path("data/sft/processed/sft_report_turn_extract_val_manual_only_messages.jsonl")


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def filter_manual(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        meta = row.get("meta", {})
        source = meta.get("source")
        if source == "manual":
            out.append(row)
    return out


def build_messages_row(row: Dict[str, Any]) -> Dict[str, Any]:
    system_prompt = row["system_prompt"]
    state_json = row["input"]["state_json"]
    user_input = row["input"]["user_input"]
    output = row["output"]

    user_content = (
        "【历史状态 state_json】\n"
        f"{json.dumps(state_json, ensure_ascii=False, indent=2)}\n\n"
        "【当前用户输入 user_input】\n"
        f"{user_input}\n\n"
        "请基于以上内容输出严格 JSON。"
    )

    return {
        "id": row["id"],
        "task": row["task"],
        "messages": [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_content,
            },
            {
                "role": "assistant",
                "content": json.dumps(output, ensure_ascii=False),
            },
        ],
        "meta": row.get("meta", {}),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="筛选 manual-only SFT 数据集")
    parser.add_argument("--train-file", default=str(DEFAULT_INPUT_TRAIN))
    parser.add_argument("--val-file", default=str(DEFAULT_INPUT_VAL))
    parser.add_argument("--output-train", default=str(DEFAULT_OUTPUT_TRAIN))
    parser.add_argument("--output-val", default=str(DEFAULT_OUTPUT_VAL))
    parser.add_argument("--output-train-messages", default=str(DEFAULT_OUTPUT_TRAIN_MESSAGES))
    parser.add_argument("--output-val-messages", default=str(DEFAULT_OUTPUT_VAL_MESSAGES))
    args = parser.parse_args()

    train_rows = read_jsonl(Path(args.train_file))
    val_rows = read_jsonl(Path(args.val_file))

    train_manual = filter_manual(train_rows)
    val_manual = filter_manual(val_rows)

    train_manual_messages = [build_messages_row(r) for r in train_manual]
    val_manual_messages = [build_messages_row(r) for r in val_manual]

    write_jsonl(Path(args.output_train), train_manual)
    write_jsonl(Path(args.output_val), val_manual)
    write_jsonl(Path(args.output_train_messages), train_manual_messages)
    write_jsonl(Path(args.output_val_messages), val_manual_messages)

    print(f"[filter_manual_only] train manual rows = {len(train_manual)}")
    print(f"[filter_manual_only] val manual rows   = {len(val_manual)}")
    print("[filter_manual_only] 输出文件:")
    print(f"  - {args.output_train}")
    print(f"  - {args.output_val}")
    print(f"  - {args.output_train_messages}")
    print(f"  - {args.output_val_messages}")


if __name__ == "__main__":
    main()
