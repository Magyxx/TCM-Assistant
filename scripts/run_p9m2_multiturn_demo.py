from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.graph.runner import run_p9m1_graph
from app.session.sqlite_store import DEFAULT_SQLITE_PATH, SQLiteSessionStore


DEMO_TURNS = [
    "最近胃胀，饭后明显",
    "差不多一周",
    "没有发热，也不胸痛",
    "睡眠一般，大便有点稀",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run P9M2 multi-turn demo.")
    parser.add_argument("--backend", default="fake")
    parser.add_argument("--db", default=str(DEFAULT_SQLITE_PATH))
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    store = SQLiteSessionStore(args.db)
    session = store.create_session()
    results = []
    for text in DEMO_TURNS:
        results.append(
            run_p9m1_graph(
                text,
                session_id=session.session_id,
                session_store=store,
                extractor_backend=args.backend,
                use_langgraph=True,
            )
        )
    final = results[-1]
    payload = {
        "session_id": session.session_id,
        "trace_id": final.get("trace_id"),
        "turns": DEMO_TURNS,
        "accumulated_run_state": final.get("run_state"),
        "risk_status": final.get("risk_status"),
        "risk_reasons": final.get("risk_reasons"),
        "missing_core_fields": final.get("missing_core_fields"),
        "next_question": final.get("next_question"),
        "final_report": final.get("final_report"),
        "graph_events_path": final.get("graph_events_path"),
        "session_store_path": str(Path(args.db)),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
