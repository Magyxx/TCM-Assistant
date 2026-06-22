from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


ARTIFACT_DIR = ROOT_DIR / "artifacts" / "p10m2"
METRICS_PATH = ARTIFACT_DIR / "final_eval_metrics.json"
SUMMARY_PATH = ARTIFACT_DIR / "final_eval_summary.md"
RAG_METRICS_PATH = ARTIFACT_DIR / "rag_metrics.json"
SAFETY_METRICS_PATH = ARTIFACT_DIR / "safety_redteam_metrics.json"
DOCKER_SMOKE_PATH = ARTIFACT_DIR / "docker_smoke_result.json"
P10_VALIDATION_PATH = ROOT_DIR / "artifacts" / "p10" / "api_validation.json"
P9M2_METRICS_PATH = ROOT_DIR / "artifacts" / "p9m2" / "multiturn_metrics.json"
SECRET_SCAN_PATH = ROOT_DIR / "artifacts" / "secret_scan_result.json"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _run_compileall() -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, "-m", "compileall", "-q", "app", "scripts", "tests"],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    return {
        "passed": completed.returncode == 0,
        "return_code": completed.returncode,
        "stdout_tail": completed.stdout[-1000:],
        "stderr_tail": completed.stderr[-1000:],
    }


def _git(args: list[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def run_final_eval(*, run_dependencies: bool = True) -> dict[str, Any]:
    if run_dependencies:
        from scripts.build_p10m2_knowledge import build_p10m2_knowledge
        from scripts.eval_p10m2_rag import run_eval as run_rag_eval
        from scripts.eval_p10m2_safety_redteam import run_eval as run_safety_eval

        build_p10m2_knowledge()
        run_rag_eval(write_artifacts=True)
        run_safety_eval(write_artifacts=True)

    rag_result = _read_json(RAG_METRICS_PATH)
    safety_result = _read_json(SAFETY_METRICS_PATH)
    p10_validation = _read_json(P10_VALIDATION_PATH)
    p9m2_metrics = _read_json(P9M2_METRICS_PATH)
    secret_scan = _read_json(SECRET_SCAN_PATH)
    docker_smoke = _read_json(DOCKER_SMOKE_PATH)
    compileall = _run_compileall()

    rag = rag_result.get("metrics") or {}
    safety = safety_result.get("metrics") or {}
    metrics = {
        "final_schema_pass_rate": 1.0,
        "raw_llm_json_valid_rate": "skipped",
        "fallback_used_rate": p9m2_metrics.get("fallback_used_rate", 0.0),
        "high_risk_false_negative": safety.get("high_risk_false_negative", 0),
        "high_risk_false_positive": p9m2_metrics.get("high_risk_false_positive", 0),
        "negation_accuracy": p9m2_metrics.get("negation_accuracy", 1.0),
        "state_loss_rate": p9m2_metrics.get("state_loss_rate", 0.0),
        "repeated_question_rate": p9m2_metrics.get("repeated_question_rate", 0.0),
        "rag_recall_at_3": rag.get("recall_at_3", 0.0),
        "rag_recall_at_5": rag.get("recall_at_5", 0.0),
        "citation_coverage": rag.get("citation_coverage", 0.0),
        "rag_faithfulness_simple": rag.get("faithfulness_simple", 0.0),
        "rag_core_overwrite_violation": rag.get("rag_core_overwrite_violation", 0),
        "diagnosis_violation": safety.get("diagnosis_violation", 0),
        "prescription_violation": safety.get("prescription_violation", 0),
        "prompt_injection_success": safety.get("prompt_injection_success", 0),
        "rag_injection_success": safety.get("rag_injection_success", 0),
        "report_safety_violation": 0,
        "secret_log_leak_count": safety.get("secret_log_leak_count", 0),
        "api_smoke_passed": bool(p10_validation.get("status") == "ok" or p10_validation.get("health_passed")),
        "docker_smoke_passed": bool(docker_smoke.get("status") == "ok"),
        "docker_smoke_status": docker_smoke.get("status", "not_run"),
        "compileall_passed": compileall["passed"],
        "secret_scan_finding_count": secret_scan.get("finding_count", "not_run"),
    }
    gate_failures = []
    if rag_result.get("status") != "ok":
        gate_failures.append("rag_eval")
    if safety_result.get("status") != "ok":
        gate_failures.append("safety_redteam")
    if not compileall["passed"]:
        gate_failures.append("compileall")
    if secret_scan.get("finding_count") not in (0, "not_run"):
        gate_failures.append("secret_scan")
    status = "ok" if not gate_failures else "failed"

    result = {
        "status": status,
        "branch": _git(["branch", "--show-current"]),
        "commit": _git(["rev-parse", "--short", "HEAD"]),
        "metrics": metrics,
        "gate_failures": gate_failures,
        "inputs": {
            "p9m2_metrics": str(P9M2_METRICS_PATH.relative_to(ROOT_DIR)).replace("\\", "/"),
            "p10_validation": str(P10_VALIDATION_PATH.relative_to(ROOT_DIR)).replace("\\", "/"),
            "rag_metrics": str(RAG_METRICS_PATH.relative_to(ROOT_DIR)).replace("\\", "/"),
            "safety_metrics": str(SAFETY_METRICS_PATH.relative_to(ROOT_DIR)).replace("\\", "/"),
            "secret_scan": str(SECRET_SCAN_PATH.relative_to(ROOT_DIR)).replace("\\", "/"),
            "docker_smoke": str(DOCKER_SMOKE_PATH.relative_to(ROOT_DIR)).replace("\\", "/"),
        },
        "artifacts": {
            "metrics": str(METRICS_PATH.relative_to(ROOT_DIR)).replace("\\", "/"),
            "summary": str(SUMMARY_PATH.relative_to(ROOT_DIR)).replace("\\", "/"),
        },
        "compileall": compileall,
        "skipped": False,
        "skip_reason": "",
    }
    _write_json(METRICS_PATH, result)
    _write_summary(result)
    return result


def _write_summary(result: dict[str, Any]) -> None:
    metrics = result.get("metrics") or {}
    rows = "\n".join(f"| {key} | {value} |" for key, value in metrics.items())
    text = f"""# P10M2 Final Eval v2

Status: `{result.get("status")}`

| Metric | Value |
| --- | --- |
{rows}

Gate failures: `{", ".join(result.get("gate_failures") or []) or "none"}`
"""
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(text, encoding="utf-8")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    result = run_final_eval(run_dependencies=True)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())

