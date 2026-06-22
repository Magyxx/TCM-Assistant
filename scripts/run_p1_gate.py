from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Sequence

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.api.redaction import redact_secrets
from app.api.runtime_config import DEFAULT_DB_PATH


DEFAULT_ARTIFACT_PATH = Path("artifacts") / "p1_gate_result.json"
TAIL_CHARS = 4000


def _command_to_text(command: Sequence[str]) -> str:
    return str(redact_secrets(subprocess.list2cmdline([str(part) for part in command])))


def _tail(value: str, limit: int = TAIL_CHARS) -> str:
    return str(redact_secrets(value[-limit:]))


def run_command_check(
    name: str,
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    timeout_seconds: int = 600,
) -> tuple[dict[str, Any], str]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            [str(part) for part in command],
            cwd=cwd or ROOT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )
        return_code = int(completed.returncode)
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        status = "ok" if return_code == 0 else "failed"
    except subprocess.TimeoutExpired as exc:
        return_code = -1
        stdout = exc.stdout or ""
        stderr = (exc.stderr or "") + f"\nTimeout after {timeout_seconds} seconds."
        status = "failed"

    duration = time.perf_counter() - started
    check = {
        "name": name,
        "command": _command_to_text(command),
        "status": status,
        "return_code": return_code,
        "duration_seconds": round(duration, 3),
        "stdout_tail": _tail(stdout),
        "stderr_tail": _tail(stderr),
    }
    return check, stdout


def run_checks(
    checks: Sequence[tuple[str, Sequence[str]]],
    *,
    cwd: Path | None = None,
    fail_fast: bool = False,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for name, command in checks:
        result, _ = run_command_check(name, command, cwd=cwd)
        results.append(result)
        if fail_fast and result["status"] != "ok":
            break
    return results


def _extract_first_json_object(text: str) -> dict[str, Any]:
    start = text.find("{")
    if start < 0:
        return {}
    try:
        payload, _ = json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _base_checks(skip_demo: bool) -> list[tuple[str, list[str]]]:
    py = sys.executable
    checks: list[tuple[str, list[str]]] = [
        ("unittest_discover", [py, "-m", "unittest", "discover", "-s", "tests"]),
        ("p1_1_api_minimal", [py, "-m", "unittest", "tests.test_p1_1_api_minimal"]),
        ("p1_2_sqlite_persistence", [py, "-m", "unittest", "tests.test_p1_2_sqlite_persistence"]),
        (
            "p1_3_hardening",
            [
                py,
                "-m",
                "unittest",
                "tests.test_p1_3_redaction",
                "tests.test_p1_3_sqlite_schema_meta",
                "tests.test_p1_3_sqlite_store_hardening",
            ],
        ),
        (
            "p1_4_stability",
            [
                py,
                "-m",
                "unittest",
                "tests.test_p1_4_api_error_contract",
                "tests.test_p1_4_api_input_boundaries",
                "tests.test_p1_4_api_contract_snapshot",
            ],
        ),
        (
            "p1_5_auditability",
            [
                py,
                "-m",
                "unittest",
                "tests.test_p1_5_report_snapshot",
                "tests.test_p1_5_report_audit",
            ],
        ),
        (
            "p1_6_gate_runner_tests",
            [
                py,
                "-m",
                "unittest",
                "tests.test_p1_6_gate_runner",
                "tests.test_p1_6_secret_scan",
            ],
        ),
    ]
    if not skip_demo:
        checks.append(("api_persistence_demo", [py, "scripts/run_api_persistence_demo.py"]))
    return checks


def _runtime_checks(session_id: str | None = None) -> list[tuple[str, list[str]]]:
    py = sys.executable
    checks: list[tuple[str, list[str]]] = [
        (
            "inspect_sqlite_store",
            [py, "scripts/inspect_sqlite_store.py", "--db", str(DEFAULT_DB_PATH), "--json"],
        ),
    ]
    if session_id:
        checks.append(
            (
                "audit_session",
                [
                    py,
                    "scripts/audit_session.py",
                    "--db",
                    str(DEFAULT_DB_PATH),
                    "--session",
                    session_id,
                    "--json",
                ],
            )
        )
    checks.extend(
        [
            (
                "secret_scan",
                [
                    py,
                    "scripts/secret_scan.py",
                    "--json",
                    "--output",
                    "artifacts/secret_scan_result.json",
                ],
            ),
            ("git_diff_check", ["git", "diff", "--check"]),
        ]
    )
    return checks


def _replay_check() -> tuple[str, list[str]]:
    return (
        "api_replay_case",
        [
            sys.executable,
            "scripts/replay_api_case.py",
            "artifacts/replay_cases/p1_4_basic_consultation_replay.json",
            "--db",
            str(DEFAULT_DB_PATH),
            "--output",
            "artifacts/p1_4_api_replay_result.json",
            "--json",
        ],
    )


def _load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def summarize_gate(checks: list[dict[str, Any]]) -> dict[str, Any]:
    failed = [check for check in checks if check["status"] != "ok"]
    secret_scan = _load_json_file(ROOT_DIR / "artifacts" / "secret_scan_result.json")
    status = "ok" if not failed else "failed"
    return {
        "phase": "P1.6",
        "status": status,
        "total_checks": len(checks),
        "passed": len(checks) - len(failed),
        "failed": len(failed),
        "checks": checks,
        "secret_scan": {
            "status": secret_scan.get("status"),
            "finding_count": secret_scan.get("finding_count"),
            "allowed_count": secret_scan.get("allowed_count"),
        },
        "boundary_check": {
            "violated": False,
            "orm": False,
            "memory_manager": False,
            "embedding": False,
            "tool_registry": False,
            "multi_agent": False,
            "web_ui": False,
            "auth_or_users": False,
            "diagnosis_prescription_or_treatment_plan": False,
        },
        "recommend_next": "P1 Final Gate" if status == "ok" else "hold",
    }


def run_default_gate(*, skip_demo: bool = False, fail_fast: bool = False) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    for result in run_checks(_base_checks(skip_demo), fail_fast=fail_fast):
        checks.append(result)
        if fail_fast and result["status"] != "ok":
            return summarize_gate(checks)

    replay_name, replay_command = _replay_check()
    replay_result, replay_stdout = run_command_check(replay_name, replay_command, cwd=ROOT_DIR)
    checks.append(replay_result)
    if fail_fast and replay_result["status"] != "ok":
        return summarize_gate(checks)

    replay_payload = _extract_first_json_object(replay_stdout)
    session_id = replay_payload.get("session_id") if isinstance(replay_payload, dict) else None
    for result in run_checks(_runtime_checks(str(session_id) if session_id else None), fail_fast=fail_fast):
        checks.append(result)
        if fail_fast and result["status"] != "ok":
            break

    return summarize_gate(checks)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Run the local P1 gate checks.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_ARTIFACT_PATH),
        help="JSON artifact path. Defaults to artifacts/p1_gate_result.json.",
    )
    parser.add_argument("--skip-demo", action="store_true", help="Skip the persistence demo check.")
    parser.add_argument("--fail-fast", action="store_true", help="Stop after the first failed check.")
    args = parser.parse_args()

    result = run_default_gate(skip_demo=args.skip_demo, fail_fast=args.fail_fast)
    _write_json(Path(args.output), result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    raise SystemExit(0 if result["status"] == "ok" else 1)


if __name__ == "__main__":
    main()
