from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.sft_schemas import SFTSampleOutput

DEFAULT_FILE = ROOT / "data" / "sft" / "processed" / "sft_report_turn_extract_val.jsonl"
CORE_FIELDS = [
    "chief_complaint",
    "duration",
    "symptoms_status",
    "risk_flags_status",
]
NEGATION_TAGS = {"negation_detection", "parallel_negation"}


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def validate_output_schema(output: Dict[str, Any]) -> bool:
    try:
        SFTSampleOutput.model_validate(output)
        return True
    except Exception:
        return False


def has_negation_tag(row: Dict[str, Any]) -> bool:
    meta = row.get("meta") or {}
    tags = set(meta.get("tags") or [])
    return bool(tags & NEGATION_TAGS)


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
    schema_pass = 0
    chief_total = 0
    chief_pass = 0
    risk_total = 0
    risk_pass = 0
    negation_total = 0
    negation_pass = 0
    failed_cases: List[str] = []

    for sample_id, gold in gold_rows.items():
        if sample_id not in pred_rows:
            failed_cases.append(f"{sample_id}: missing prediction")
            continue
        total += 1
        pred_output = pred_rows[sample_id].get("output", {})
        if not isinstance(pred_output, dict):
            pred_output = {}
        if validate_output_schema(pred_output):
            schema_pass += 1

        ok, field_results = compare_output(gold["output"], pred_output)
        if ok:
            passed += 1
        else:
            failed_cases.append(sample_id)
        for field, field_ok in field_results.items():
            if field_ok:
                field_pass[field] += 1

        chief_total += 1
        if field_results.get("chief_complaint"):
            chief_pass += 1
        risk_total += 1
        if field_results.get("risk_flags_status"):
            risk_pass += 1
        if has_negation_tag(gold):
            negation_total += 1
            if field_results.get("risk_flags_status"):
                negation_pass += 1

    print(f"[eval_sft_extract] total={total}, passed={passed}, failed={total - passed}")
    for field in CORE_FIELDS:
        print(f"[eval_sft_extract] {field}: {field_pass[field]}/{total}")
    print(f"[eval_sft_extract] schema_pass_rate: {schema_pass}/{total}")
    print(f"[eval_sft_extract] chief_complaint_consistency: {chief_pass}/{chief_total}")
    print(f"[eval_sft_extract] risk_recognition_consistency: {risk_pass}/{risk_total}")
    if negation_total:
        print(f"[eval_sft_extract] negation_detection_accuracy: {negation_pass}/{negation_total}")
    else:
        print("[eval_sft_extract] negation_detection_accuracy: n/a")

    if failed_cases:
        print("[eval_sft_extract] failed cases:")
        for case in failed_cases[:20]:
            print("  -", case)


if __name__ == "__main__":
    main()
