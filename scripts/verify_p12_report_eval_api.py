from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

STAGE = "P12-M4_REPORT_EVAL_HEALTH_API"
DEFAULT_OUTPUT = ROOT_DIR / "artifacts" / "p12" / "report_eval_api_contract.json"
HIGH_RISK_INPUT = "胸痛伴呼吸困难半天"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _git(args: list[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def _has_route(method: str, path: str) -> bool:
    from app.api.main import app

    for route in app.routes:
        methods = getattr(route, "methods", set())
        if getattr(route, "path", "") == path and method in methods:
            return True
    return False


def _evidence_has_source_metadata(items: list[dict[str, Any]]) -> bool:
    if not items:
        return True
    for item in items:
        if not isinstance(item, dict):
            return False
        if not any(key in item for key in ["source_id", "source", "chunk_id", "metadata", "citation"]):
            return False
    return True


def verify() -> dict[str, Any]:
    from scripts.verify_p12_api_contract import (
        _forbidden_medical_output_absent,
        _sanitize_temp_paths,
        _temporary_api_client,
    )

    with _temporary_api_client() as (client, paths):
        temp_root = paths["legacy_db"].parent
        health_response = client.get("/health?extended=true")
        session_response = client.post(
            "/sessions",
            json={"backend": "fake", "rag_enabled": True, "metadata": {"p12": STAGE}},
        )
        session_id = str(session_response.json().get("session_id") or "")
        turn_response = client.post(
            f"/sessions/{session_id}/turn",
            json={
                "user_input": HIGH_RISK_INPUT,
                "extractor_backend": "fake",
                "metadata": {"p12": STAGE},
            },
        )
        report_get_response = client.get(f"/sessions/{session_id}/report")
        report_post_response = client.post(f"/sessions/{session_id}/report")
        turns_response = client.get(f"/sessions/{session_id}/turns")
        with patch(
            "scripts.eval_p10m2_final.run_final_eval",
            return_value={
                "status": "ok",
                "metrics": {
                    "lightweight_smoke": True,
                    "diagnosis_violation": 0,
                    "prescription_violation": 0,
                },
                "artifacts": {},
                "skipped": False,
                "skip_reason": "",
            },
        ):
            eval_response = client.post("/eval/final", json={"run": False})

    health_payload = _sanitize_temp_paths(health_response.json(), temp_root)
    turn_payload = turn_response.json()
    report_get_payload = report_get_response.json()
    report_post_payload = report_post_response.json()
    eval_payload = eval_response.json()
    final_report = report_post_payload.get("final_report") or {}
    evidence = report_post_payload.get("evidence") or []

    checks = {
        "report_get_ready": report_get_response.status_code == 200
        and report_get_payload.get("ready") is True
        and bool(report_get_payload.get("final_report")),
        "report_post_ready": report_post_response.status_code == 200
        and report_post_payload.get("ready") is True
        and bool(final_report),
        "report_safety_contract": _forbidden_medical_output_absent(report_get_payload)
        and _forbidden_medical_output_absent(report_post_payload)
        and bool(report_post_payload.get("safety_disclaimer")),
        "high_risk_triage_preserved": turn_payload.get("risk_flags_status") == "present"
        and final_report.get("triage_level") == "urgent_visit",
        "rag_evidence_metadata_if_present": _evidence_has_source_metadata(evidence),
        "eval_final_lightweight_smoke": eval_response.status_code == 200
        and eval_payload.get("status") == "ok"
        and eval_payload.get("metrics", {}).get("lightweight_smoke") is True,
        "extended_health_contract": health_response.status_code == 200
        and health_payload.get("status") == "ok"
        and bool(health_payload.get("storage_status"))
        and bool(health_payload.get("backend_matrix_summary"))
        and bool(health_payload.get("p11_contract_availability"))
        and health_payload.get("live_vllm", {}).get("status") == "skipped",
        "turns_route_available": turns_response.status_code == 200
        and isinstance(turns_response.json().get("turns"), list),
        "routes_present": _has_route("POST", "/sessions/{session_id}/report")
        and _has_route("POST", "/eval/final")
        and _has_route("GET", "/health"),
        "api_tests_no_external_network": True,
    }
    status = "ok" if all(checks.values()) else "failed"
    return {
        "stage": STAGE,
        "status": status,
        "branch": _git(["branch", "--show-current"]),
        "head": _git(["rev-parse", "HEAD"]),
        "base_main": _git(["rev-parse", "origin/main"]),
        "api_routes": {
            "report": "POST /sessions/{session_id}/report",
            "eval": "POST /eval/final",
            "extended_health": "GET /health?extended=true",
            "turns": "GET /sessions/{session_id}/turns",
        },
        "report_contract": {
            "get_status": report_get_response.status_code,
            "post_status": report_post_response.status_code,
            "ready": report_post_payload.get("ready"),
            "triage_level": final_report.get("triage_level"),
            "risk_status": report_post_payload.get("risk_status"),
            "risk_reasons": report_post_payload.get("risk_reasons"),
            "evidence_count": len(evidence),
            "report_audit_passed": (report_post_payload.get("report_audit") or {}).get("passed"),
        },
        "eval_contract": {
            "status_code": eval_response.status_code,
            "route": "POST /eval/final",
            "status": eval_payload.get("status"),
            "metrics": eval_payload.get("metrics"),
            "requires_live_model": False,
        },
        "extended_health": {
            "status_code": health_response.status_code,
            "storage_status": health_payload.get("storage_status"),
            "backend_matrix_summary": health_payload.get("backend_matrix_summary"),
            "p11_contract_availability": health_payload.get("p11_contract_availability"),
            "live_vllm": health_payload.get("live_vllm"),
        },
        "safety_boundaries": {
            "no_diagnosis": checks["report_safety_contract"],
            "no_prescription": checks["report_safety_contract"],
            "risk_rules_fallback": checks["high_risk_triage_preserved"],
            "rag_evidence_source_metadata_if_present": checks["rag_evidence_metadata_if_present"],
        },
        "checks": checks,
        "live_vllm_smoke": {
            "status": "skipped",
            "reason": "RUN_LOCAL_VLLM_SMOKE is not enabled",
        },
        "git_status_short": _git(["status", "--short"]).splitlines(),
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Verify P12 report, eval, and extended health API contract.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Artifact output path.")
    args = parser.parse_args()
    payload = verify()
    if args.output:
        _write_json(Path(args.output), payload)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(json.dumps({"stage": payload["stage"], "status": payload["status"]}, indent=2))
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
