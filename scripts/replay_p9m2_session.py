from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.session.sqlite_store import DEFAULT_SQLITE_PATH, SQLiteSessionStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay/export a P9M2 SQLite session.")
    parser.add_argument("--session-id", required=False)
    parser.add_argument("--db", default=str(DEFAULT_SQLITE_PATH))
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not args.session_id:
        parser.print_help()
        return 0
    store = SQLiteSessionStore(args.db)
    print(json.dumps(store.replay_session(args.session_id), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
