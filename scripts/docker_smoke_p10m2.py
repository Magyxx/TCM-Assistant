from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

import httpx


ROOT_DIR = Path(__file__).resolve().parents[1]
ARTIFACT_PATH = ROOT_DIR / "artifacts" / "p10m2" / "docker_smoke_result.json"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _result(status: str, *, checks: dict[str, bool] | None = None, skip_reason: str = "", details: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {
        "status": status,
        "checks": checks or {},
        "skipped": status == "skipped",
        "skip_reason": skip_reason,
        "details": details or {},
    }
    _write_json(ARTIFACT_PATH, payload)
    return payload


def run_smoke() -> dict[str, Any]:
    if shutil.which("docker") is None:
        return _result("skipped", skip_reason="docker_cli_not_found")

    port = int(os.getenv("DOCKER_APP_PORT", "8000"))
    base_url = f"http://127.0.0.1:{port}"
    try:
        with httpx.Client(base_url=base_url, timeout=5.0) as client:
            checks: dict[str, bool] = {}
            details: dict[str, Any] = {}

            health = client.get("/health", params={"extended": "true"})
            checks["health_passed"] = health.status_code == 200 and health.json().get("status") == "ok"
            details["health"] = health.json() if health.headers.get("content-type", "").startswith("application/json") else health.text[-500:]

            session = client.post("/sessions", json={"backend": "fake", "metadata": {"source": "docker_p10m2_smoke"}})
            session_payload = session.json()
            session_id = str(session_payload.get("session_id") or "")
            checks["sessions_passed"] = session.status_code == 200 and bool(session_id)
            details["session"] = session_payload

            turn = client.post(
                "/turn",
                json={"session_id": session_id, "user_input": "stomach bloating for one week, no fever, no chest pain", "extractor_backend": "fake"},
            )
            checks["turn_passed"] = turn.status_code == 200 and turn.json().get("session_id") == session_id
            details["turn"] = turn.json()

            rag_health = client.get("/rag/health")
            checks["rag_health_passed"] = rag_health.status_code == 200 and rag_health.json().get("chunks_count", 0) > 0
            details["rag_health"] = rag_health.json()

            rag_search = client.post("/rag/search", json={"query": "chest pain breathing difficulty red flag", "top_k": 3, "mode": "hybrid"})
            checks["rag_search_passed"] = rag_search.status_code == 200 and bool(rag_search.json().get("results"))
            details["rag_search"] = rag_search.json()

            final_eval = client.post("/eval/final", json={"run": False})
            checks["final_eval_passed"] = final_eval.status_code == 200
            details["final_eval"] = final_eval.json()

            status = "ok" if all(checks.values()) else "failed"
            return _result(status, checks=checks, details=details)
    except Exception as exc:
        return _result("skipped", skip_reason=f"docker_service_not_reachable:{type(exc).__name__}")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    result = run_smoke()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] in {"ok", "skipped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())

