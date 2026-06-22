from __future__ import annotations

import shutil
import subprocess
from typing import Any

try:
    from p7_common import ROOT_DIR, check, status_from_checks, write_json
except ImportError:  # pragma: no cover - package import path
    from scripts.p7_common import ROOT_DIR, check, status_from_checks, write_json


ARTIFACT = ROOT_DIR / "artifacts" / "p7_docker_smoke.json"


def run_p7_docker_smoke(*, write_artifact: bool = True) -> dict[str, Any]:
    docker = shutil.which("docker")
    files_present = all((ROOT_DIR / path).exists() for path in ["Dockerfile", "docker-compose.yml", ".env.example"])
    checks = [check("docker_files_present", files_present)]
    docker_runtime_available = bool(docker)
    compose_config_status = "skipped"
    stdout_tail = ""
    stderr_tail = ""
    if docker:
        completed = subprocess.run(
            [docker, "compose", "config"],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        compose_config_status = "ok" if completed.returncode == 0 else "failed"
        stdout_tail = (completed.stdout or "")[-2000:]
        stderr_tail = (completed.stderr or "")[-2000:]
        checks.append(check("docker_compose_config_pass", completed.returncode == 0, stderr_tail))
    else:
        checks.append(check("docker_runtime_available", False, "docker CLI not found"))
    payload = {
        "phase": "P7",
        "status": status_from_checks(checks),
        "checks": checks,
        "metrics": {
            "docker_smoke_pass": status_from_checks(checks) == "ok",
            "docker_runtime_available": docker_runtime_available,
            "compose_config_status": compose_config_status,
        },
        "stdout_tail": stdout_tail,
        "stderr_tail": stderr_tail,
    }
    if write_artifact:
        write_json(ARTIFACT, payload)
    return payload


def main() -> int:
    payload = run_p7_docker_smoke()
    print(f"P7 docker smoke: status={payload['status']} artifact={ARTIFACT.relative_to(ROOT_DIR)}")
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
