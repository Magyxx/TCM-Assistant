from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.device2.eval_compare_backends import (  # noqa: E402
    DEFAULT_BADCASES,
    DEFAULT_PREDICTIONS,
    badcase_rows,
    write_jsonl,
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract compact D2-P6C backend badcase samples.")
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--output", type=Path, default=DEFAULT_BADCASES)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = badcase_rows(read_jsonl(args.predictions))
    write_jsonl(args.output, rows)
    if args.json:
        print(json.dumps({"status": "ok", "badcase_count": len(rows), "output": str(args.output)}, ensure_ascii=False, indent=2))
    else:
        print(f"D2-P6C badcases: {len(rows)} -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
