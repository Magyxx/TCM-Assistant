from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from app.graph.runner import run_p9m1_graph
from app.session.memory_store import MemorySessionStore


ROOT_DIR = Path(__file__).resolve().parents[1]


def run_turns(turns: list[str]) -> dict:
    store = MemorySessionStore()
    session_id = "test-p9m2-multiturn"
    result = {}
    for text in turns:
        result = run_p9m1_graph(text, session_id=session_id, session_store=store, extractor_backend="fake", use_langgraph=False)
    result["session_export"] = store.export_session(session_id)
    return result


def test_multiturn_fills_chief_and_duration_without_state_loss() -> None:
    result = run_turns(["胃胀", "一周", "没有其他症状", "睡眠一般，食欲一般，大便正常，小便正常，没有胸痛"])

    assert result["run_state"]["chief_complaint"] == "胃胀"
    assert result["run_state"]["duration"] == "一周"
    assert result["final_report"] is not None


def test_negated_risk_retained_across_later_turns() -> None:
    result = run_turns(["没有发热，也不胸痛", "胃胀一周", "没有其他症状", "睡眠一般，食欲一般，大便正常，小便正常"])

    assert result["run_state"]["risk_flags_status"] == "none"
    assert "P0_RISK_CHEST_PAIN" in result["run_state"]["metadata"]["negated_rule_ids"]
    assert "P0_RISK_HIGH_FEVER" in result["run_state"]["metadata"]["negated_rule_ids"]


def test_high_risk_stays_sticky_after_improvement_text() -> None:
    result = run_turns(["胸痛伴呼吸困难", "现在好点了", "睡眠一般"])

    assert result["run_state"]["risk_flags_status"] == "present"
    assert {"P0_RISK_CHEST_PAIN", "P0_RISK_DYSPNEA"}.issubset(set(result["run_state"]["triggered_rule_ids"]))


def test_answered_fields_are_not_repeatedly_asked() -> None:
    result = run_turns(["胃胀一周", "大便正常，小便正常", "没有其他症状", "睡眠一般，食欲一般，没有发热"])
    asked = [
        event["payload"]["metadata"].get("field")
        for event in result["session_export"]["events"]
        if event["event_type"] == "graph_event" and event["payload"]["node"] == "ask_followup"
    ]
    asked = [field for field in asked if field]

    assert len(asked) == len(set(asked))
    assert "stool" not in asked[1:]


def test_eval_p9m2_multiturn_generates_metrics() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/eval_p9m2_multiturn.py"],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    metrics = json.loads((ROOT_DIR / "artifacts/p9m2/multiturn_metrics.json").read_text(encoding="utf-8"))
    assert metrics["dialogue_count"] >= 50
    assert metrics["state_loss_rate"] == 0.0
    assert metrics["high_risk_false_negative"] == 0
