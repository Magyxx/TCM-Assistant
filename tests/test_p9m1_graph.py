from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from app.graph.runner import run_p9m1_graph


ROOT_DIR = Path(__file__).resolve().parents[1]


def test_fake_backend_runs_complete_p9m1_graph() -> None:
    result = run_p9m1_graph(
        "胃胀一周，没有其他症状，睡眠一般，食欲一般，大便正常，小便正常，没有胸痛，没有呼吸困难，没有便血",
        extractor_backend="fake",
        use_langgraph=True,
    )

    assert result["session_id"]
    assert result["risk_status"] == "none"
    assert result["final_report"] is not None
    assert result["retrieved_evidence"]
    assert result["run_state"]["chief_complaint"] == "胃胀"
    assert result["run_state"]["duration"] == "一周"
    assert result["final_report"]["metadata"]["rag_core_fields_read_only"] is True


def test_rag_evidence_does_not_override_core_state_fields() -> None:
    result = run_p9m1_graph(
        "胃痛两天，睡眠一般，食欲下降，大便正常，小便正常，没有其他症状，没有胸痛",
        extractor_backend="fake",
        use_langgraph=False,
    )

    assert result["retrieved_evidence"]
    assert result["run_state"]["chief_complaint"] == "胃痛"
    assert result["run_state"]["duration"] == "两天"
    assert result["run_state"]["risk_flags_status"] == "none"
    assert result["run_state"]["triggered_rule_ids"] == []


def test_eval_script_generates_metrics_json() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/eval_p9m1_graph.py"],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    metrics_path = ROOT_DIR / "artifacts" / "p9m1" / "metrics.json"
    assert metrics_path.exists()
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert metrics["total_cases"] >= 30
    assert metrics["high_risk_false_negative"] == 0
    assert metrics["report_safety_violation"] == 0
