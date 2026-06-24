from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.storage.sqlite import init_db


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="artifacts/local_demo.db")
    args = parser.parse_args()
    init_db(Path(args.db))
    print(f"initialized {args.db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
