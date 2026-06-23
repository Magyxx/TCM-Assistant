from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.sft_schemas import SFTMessagesSample, SFTSample


DEFAULT_FILES = [
    ROOT / "data" / "sft" / "processed" / "sft_report_turn_extract_train.jsonl",
    ROOT / "data" / "sft" / "processed" / "sft_report_turn_extract_val.jsonl",
    ROOT / "data" / "sft" / "processed" / "sft_report_turn_extract_train_messages.jsonl",
    ROOT / "data" / "sft" / "processed" / "sft_report_turn_extract_val_messages.jsonl",
    ROOT / "data" / "sft" / "processed" / "train_sft_risk_repair.jsonl",
    ROOT / "data" / "sft" / "processed" / "valid_sft_risk_repair.jsonl",
    ROOT / "data" / "sft" / "processed" / "train_sft_risk_repair_messages.jsonl",
    ROOT / "data" / "sft" / "processed" / "valid_sft_risk_repair_messages.jsonl",
    ROOT / "data" / "sft" / "eval" / "eval_risk_repair.jsonl",
    ROOT / "data" / "sft" / "eval" / "eval_negation_repair.jsonl",
]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def schema_for(path: Path) -> type[SFTSample] | type[SFTMessagesSample]:
    return SFTMessagesSample if path.name.endswith("_messages.jsonl") else SFTSample


def validate_file(path: Path) -> dict[str, Any]:
    rows = read_jsonl(path)
    schema = schema_for(path)
    errors: list[str] = []
    ids: set[str] = set()
    for index, row in enumerate(rows, start=1):
        try:
            validated = schema.model_validate(row)
            row_id = str(validated.id)
            if row_id in ids:
                errors.append(f"line {index}: duplicate id {row_id}")
            ids.add(row_id)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"line {index}: {type(exc).__name__}: {exc}")
    return {
        "path": str(path.relative_to(ROOT)),
        "rows": len(rows),
        "schema": schema.__name__,
        "ok": not errors,
        "errors": errors[:20],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate device2 SFT JSONL files.")
    parser.add_argument("--all", action="store_true", help="Validate default original and risk repair files.")
    parser.add_argument("files", nargs="*", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths = DEFAULT_FILES if args.all else args.files
    if not paths:
        raise SystemExit("provide files or --all")
    results = []
    for path in paths:
        if not path.exists():
            results.append({"path": str(path), "ok": False, "errors": ["missing file"]})
            continue
        results.append(validate_file(path))
    ok = all(item["ok"] for item in results)
    print(json.dumps({"ok": ok, "files": results}, ensure_ascii=False, indent=2))
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

