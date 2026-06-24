from __future__ import annotations

from scripts.eval_p10m2_final import run_final_eval
from scripts.eval_p10m2_rag import run_eval as run_rag_eval
from scripts.eval_p10m2_safety_redteam import run_eval as run_safety_eval


def test_p10m2_final_eval_metrics_exist() -> None:
    run_rag_eval(write_artifacts=True)
    run_safety_eval(write_artifacts=True)
    result = run_final_eval(run_dependencies=False)

    assert result["metrics"]["rag_recall_at_5"] >= 0.85
    assert result["metrics"]["diagnosis_violation"] == 0
    assert "docker_smoke_passed" in result["metrics"]

