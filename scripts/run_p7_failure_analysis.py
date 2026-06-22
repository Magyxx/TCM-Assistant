from __future__ import annotations

from typing import Any

try:
    from p7_common import ROOT_DIR, read_json, write_json
except ImportError:  # pragma: no cover - package import path
    from scripts.p7_common import ROOT_DIR, read_json, write_json


ARTIFACT = ROOT_DIR / "artifacts" / "p7_failure_analysis.json"
INPUTS = {
    "api": ROOT_DIR / "artifacts" / "p7_api_validation.json",
    "storage": ROOT_DIR / "artifacts" / "p7_storage_validation.json",
    "memory": ROOT_DIR / "artifacts" / "p7_memory_validation.json",
    "tool_registry": ROOT_DIR / "artifacts" / "p7_tool_registry_validation.json",
    "observability": ROOT_DIR / "artifacts" / "p7_observability_validation.json",
    "safety": ROOT_DIR / "artifacts" / "p7_safety_validation.json",
    "docker": ROOT_DIR / "artifacts" / "p7_docker_smoke.json",
}


def run_p7_failure_analysis(*, write_artifact: bool = True) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    cautions: list[dict[str, Any]] = []
    for name, path in INPUTS.items():
        payload = read_json(path)
        if not payload:
            blockers.append({"source": name, "detail": f"missing artifact: {path.name}"})
            continue
        if payload.get("status") != "ok":
            if name == "docker" and payload.get("metrics", {}).get("docker_runtime_available") is False:
                cautions.append({"source": name, "detail": "docker CLI unavailable; runtime smoke could not be executed"})
            else:
                blockers.append({"source": name, "detail": payload.get("checks") or payload.get("metrics")})
    payload = {
        "phase": "P7",
        "status": "failed" if blockers else "ok",
        "blockers": blockers,
        "cautions": cautions,
        "known_limitations": [
            "PostgreSQL is schema-ready only unless TCM_DB_URL and a driver are provided.",
            "Docker runtime smoke depends on local Docker availability.",
            "P7 does not add MCP server, multi-agent station, frontend, diagnosis, or prescription flows.",
        ],
    }
    if write_artifact:
        write_json(ARTIFACT, payload)
    return payload


def main() -> int:
    payload = run_p7_failure_analysis()
    print(f"P7 failure analysis: status={payload['status']} artifact={ARTIFACT.relative_to(ROOT_DIR)}")
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
