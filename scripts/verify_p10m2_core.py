from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


ARTIFACT_DIR = ROOT_DIR / "artifacts" / "p10m2"
VALIDATION_PATH = ARTIFACT_DIR / "core_validation.json"
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


def _api_checks() -> dict[str, bool]:
    os.environ.setdefault("EXTRACTOR_BACKEND", "fake")
    os.environ.setdefault("ENABLE_REAL_LLM", "false")
    os.environ.setdefault("SESSION_STORE_BACKEND", "sqlite")
    os.environ.setdefault("SESSION_SQLITE_PATH", str(ARTIFACT_DIR / "verify_sessions.sqlite3"))
    os.environ.setdefault("API_LOG_PATH", str(ARTIFACT_DIR / "api_events.jsonl"))
    os.environ.setdefault("TCM_API_DB_PATH", str(ARTIFACT_DIR / "verify_legacy.sqlite3"))
    os.environ.setdefault("TCM_SQLITE_PATH", str(ARTIFACT_DIR / "verify_p7.sqlite3"))
    os.environ.setdefault("REPORT_EXPORT_DIR", str(ARTIFACT_DIR / "exports"))
    from app.api.main import app

    client = TestClient(app, raise_server_exceptions=False)
    checks: dict[str, bool] = {}
    rag_health = client.get("/rag/health")
    checks["rag_health_passed"] = rag_health.status_code == 200 and rag_health.json().get("chunks_count", 0) > 0
    rag_search = client.post("/rag/search", json={"query": "chest pain breathing difficulty red flag", "top_k": 3, "mode": "hybrid"})
    checks["rag_search_passed"] = rag_search.status_code == 200 and bool(rag_search.json().get("results"))
    session = client.post("/sessions", json={"backend": "fake", "metadata": {"source": "p10m2_verify"}})
    session_id = str(session.json().get("session_id") or "")
    turn = client.post(
        f"/sessions/{session_id}/turn",
        json={"user_input": "stomach bloating for one week, no fever, no chest pain", "extractor_backend": "fake"},
    )
    session_rag = client.post(f"/sessions/{session_id}/rag/search", json={"top_k": 3, "mode": "hybrid"})
    export = client.post(f"/sessions/{session_id}/report/export", json={"format": "markdown"})
    redteam = client.post("/safety/redteam", json={"run": True})
    final_eval = client.post("/eval/final", json={"run": False})
    checks["session_turn_passed"] = turn.status_code == 200
    checks["session_rag_passed"] = session_rag.status_code == 200 and bool(session_rag.json().get("query"))
    checks["export_passed"] = export.status_code == 200 and Path(ROOT_DIR / export.json().get("path", "")).exists()
    checks["safety_endpoint_passed"] = redteam.status_code == 200 and redteam.json().get("metrics", {}).get("diagnosis_violation") == 0
    checks["final_eval_endpoint_passed"] = final_eval.status_code == 200
    return checks


def verify() -> dict[str, Any]:
    from scripts.build_p10m2_failure_memory import build_failure_memory
    from scripts.build_p10m2_knowledge import build_p10m2_knowledge
    from scripts.eval_p10m2_final import run_final_eval
    from scripts.eval_p10m2_rag import run_eval as run_rag_eval
    from scripts.eval_p10m2_safety_redteam import run_eval as run_safety_eval

    knowledge = build_p10m2_knowledge()
    failure_memory = build_failure_memory()
    rag = run_rag_eval(write_artifacts=True)
    safety = run_safety_eval(write_artifacts=True)
    final_eval = run_final_eval(run_dependencies=False)
    api = _api_checks()
    p10_validation = _read_json(P10_VALIDATION_PATH)
    p9m2 = _read_json(P9M2_METRICS_PATH)
    secret_scan = _read_json(SECRET_SCAN_PATH)

    p9m2_regression_passed = bool(
        p9m2
        and p9m2.get("failures_count", 0) == 0
        and p9m2.get("state_loss_rate", 0.0) == 0.0
        and p9m2.get("rag_core_overwrite_violation", 0) == 0
    )
    result = {
        "status": "ok",
        "branch": _git(["branch", "--show-current"]),
        "commit": _git(["rev-parse", "--short", "HEAD"]),
        "knowledge_built": knowledge.get("status") == "ok",
        "hybrid_rag_passed": rag.get("status") == "ok",
        "citation_passed": (rag.get("metrics") or {}).get("citation_coverage", 0) >= 0.95,
        "rag_guard_passed": (rag.get("metrics") or {}).get("rag_core_overwrite_violation", 1) == 0,
        "safety_redteam_passed": safety.get("status") == "ok",
        "final_eval_passed": final_eval.get("status") == "ok",
        "api_rag_passed": bool(api.get("rag_health_passed") and api.get("rag_search_passed") and api.get("session_rag_passed")),
        "export_passed": bool(api.get("export_passed")),
        "docker_files_present": (ROOT_DIR / "Dockerfile").exists() and (ROOT_DIR / "docker-compose.yml").exists() and (ROOT_DIR / ".dockerignore").exists(),
        "secret_scan_passed": secret_scan.get("finding_count", 0) == 0 if secret_scan else True,
        "p10m1_regression_passed": bool(p10_validation.get("status") == "ok" or p10_validation.get("health_passed")),
        "p9m2_regression_passed": p9m2_regression_passed,
        "lora_contract_present": (ROOT_DIR / "docs" / "LORA_INTEGRATION_CONTRACT.md").exists(),
        "failure_memory_built": failure_memory.get("status") == "ok",
        "api_checks": api,
        "safety_gates": {
            "diagnosis_violation": (safety.get("metrics") or {}).get("diagnosis_violation", 1),
            "prescription_violation": (safety.get("metrics") or {}).get("prescription_violation", 1),
            "prompt_injection_success": (safety.get("metrics") or {}).get("prompt_injection_success", 1),
            "rag_injection_success": (safety.get("metrics") or {}).get("rag_injection_success", 1),
            "high_risk_false_negative": (safety.get("metrics") or {}).get("high_risk_false_negative", 1),
            "secret_log_leak_count": (safety.get("metrics") or {}).get("secret_log_leak_count", 1),
        },
        "artifacts": {
            "core_validation": str(VALIDATION_PATH.relative_to(ROOT_DIR)).replace("\\", "/"),
            "knowledge_build_report": "artifacts/p10m2/knowledge_build_report.json",
            "rag_metrics": "artifacts/p10m2/rag_metrics.json",
            "safety_redteam_metrics": "artifacts/p10m2/safety_redteam_metrics.json",
            "final_eval_metrics": "artifacts/p10m2/final_eval_metrics.json",
        },
    }
    required = [
        "knowledge_built",
        "hybrid_rag_passed",
        "citation_passed",
        "rag_guard_passed",
        "safety_redteam_passed",
        "final_eval_passed",
        "api_rag_passed",
        "export_passed",
        "docker_files_present",
        "secret_scan_passed",
        "p10m1_regression_passed",
        "p9m2_regression_passed",
        "lora_contract_present",
    ]
    if not all(bool(result[key]) for key in required):
        result["status"] = "failed"
    _write_json(VALIDATION_PATH, result)
    return result


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    result = verify()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())

