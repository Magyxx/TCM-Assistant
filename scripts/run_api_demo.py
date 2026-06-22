from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.api.main import app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a local P1.1 API demo with TestClient.")
    parser.add_argument(
        "--extractor",
        choices=["fake", "fallback", "real_llm"],
        default="fake",
        help="Extractor mode for the demo session. Defaults to fake to avoid external API dependency.",
    )
    args = parser.parse_args()

    client = TestClient(app)

    session_resp = client.post(
        "/sessions",
        json={"extractor_mode": args.extractor, "rag_enabled": True},
    )
    session_resp.raise_for_status()
    session = session_resp.json()
    session_id = session["session_id"]

    print(f"session_id: {session_id}")
    print(f"extractor_mode: {session['extractor_mode']}")

    turns = [
        "最近胃胀，饭后明显，睡眠一般",
        "大概持续一周，没有发热，也不胸痛",
    ]
    last_turn = None
    for index, text in enumerate(turns, start=1):
        response = client.post(
            f"/sessions/{session_id}/turn",
            json={"user_input": text},
        )
        response.raise_for_status()
        last_turn = response.json()
        metadata = last_turn.get("metadata") or {}
        print(f"turn_{index}_count: {last_turn.get('turn_count')}")
        print(f"turn_{index}_risk_flags_status: {last_turn.get('risk_flags_status')}")
        print(f"turn_{index}_next_question: {last_turn.get('next_question')}")
        print(f"turn_{index}_metadata.graph_runtime: {metadata.get('graph_runtime')}")
        print(f"turn_{index}_metadata.extractor_mode: {metadata.get('extractor_mode')}")
        print(f"turn_{index}_metadata.fallback_used: {metadata.get('fallback_used')}")

    state_resp = client.get(f"/sessions/{session_id}/state")
    state_resp.raise_for_status()
    state = state_resp.json()
    print(f"state_turn_count: {state.get('turn_count')}")
    print(f"state_next_question: {state.get('next_question')}")

    report_resp = client.get(f"/sessions/{session_id}/report")
    report_resp.raise_for_status()
    report = report_resp.json()
    print(f"final_report ready: {report.get('ready')}")
    if report.get("ready"):
        final_report = report.get("final_report") or {}
        print("final_report summary:")
        print(final_report.get("summary"))

    print("demo_result:")
    print(
        json.dumps(
            {
                "session_id": session_id,
                "turn_count": state.get("turn_count"),
                "final_report_ready": report.get("ready"),
                "last_metadata": (last_turn or {}).get("metadata", {}),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
