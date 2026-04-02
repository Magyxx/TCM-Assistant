from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FILE = ROOT / "data" / "sft" / "processed" / "sft_report_turn_extract_val.jsonl"
CORE_FIELDS = [
    "chief_complaint",
    "duration",
    "symptoms_status",
    "risk_flags_status",
]


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def normalize_value(value: Any) -> Any:
    if isinstance(value, list):
        return sorted(value)
    if isinstance(value, str):
        return value.strip()
    return value


def compare_output(expected: Dict[str, Any], predicted: Dict[str, Any]) -> Tuple[bool, Dict[str, bool]]:
    field_results: Dict[str, bool] = {}
    for field in CORE_FIELDS:
        field_results[field] = normalize_value(expected.get(field)) == normalize_value(predicted.get(field))
    return all(field_results.values()), field_results


def main() -> None:
    parser = argparse.ArgumentParser(description="评估单轮抽取结果的核心字段一致性")
    parser.add_argument("--gold-file", type=Path, default=DEFAULT_FILE)
    parser.add_argument(
        "--pred-file",
        type=Path,
        required=True,
        help="逐行 JSONL，至少包含 id 和 output 字段",
    )
    args = parser.parse_args()

    gold_rows = {row["id"]: row for row in read_jsonl(args.gold_file)}
    pred_rows = {row["id"]: row for row in read_jsonl(args.pred_file)}

    total = 0
    passed = 0
    field_pass = {field: 0 for field in CORE_FIELDS}
    failed_cases: List[str] = []

    for sample_id, gold in gold_rows.items():
        if sample_id not in pred_rows:
            failed_cases.append(f"{sample_id}: missing prediction")
            continue
        total += 1
        ok, field_results = compare_output(gold["output"], pred_rows[sample_id]["output"])
        if ok:
            passed += 1
        else:
            failed_cases.append(sample_id)
        for field, field_ok in field_results.items():
            if field_ok:
                field_pass[field] += 1

    print(f"[eval_sft_extract] total={total}, passed={passed}, failed={total - passed}")
    for field in CORE_FIELDS:
        print(f"[eval_sft_extract] {field}: {field_pass[field]}/{total}")

    if failed_cases:
        print("[eval_sft_extract] failed cases:")
        for case in failed_cases[:20]:
            print("  -", case)


if __name__ == "__main__":
    main()
