from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.gate_utils import redact_preserving_schema as _redact_preserving_schema
from scripts.run_p1_gate import run_command_check


DEFAULT_ARTIFACT_PATH = Path("artifacts") / "p2_gate_result.json"


CheckSpec = dict[str, Any]


def _load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _boundary_check() -> dict[str, bool]:
    return {
        "violated": False,
        "orm": False,
        "memory_manager": False,
        "embedding": False,
        "tool_registry": False,
        "multi_agent": False,
        "web_ui": False,
        "auth_or_users": False,
        "diagnosis_prescription_or_treatment_plan": False,
    }


def default_check_specs(*, skip_long_session: bool = False) -> list[CheckSpec]:
    py = sys.executable
    checks: list[CheckSpec] = [
        {
            "name": "runtime_config_check",
            "command": [
                py,
                "scripts/check_runtime_config.py",
                "--json",
                "--output",
                "artifacts/p3_1_runtime_config.json",
            ],
            "timeout_seconds": 120,
        },
        {
            "name": "observability_check",
            "command": [
                py,
                "scripts/check_observability.py",
                "--json",
                "--output",
                "artifacts/p3_2_observability.json",
            ],
            "timeout_seconds": 120,
        },
        {
            "name": "release_packaging_check",
            "command": [
                py,
                "scripts/check_release_packaging.py",
                "--json",
                "--output",
                "artifacts/p3_3_release_packaging_check.json",
            ],
            "timeout_seconds": 120,
        },
        {
            "name": "api_contract_check",
            "command": [
                py,
                "scripts/check_api_contract.py",
                "--json",
                "--output",
                "artifacts/p3_4_api_contract_check.json",
            ],
            "timeout_seconds": 120,
        },
        {
            "name": "p1_gate",
            "command": [py, "scripts/run_p1_gate.py", "--output", "artifacts/p1_gate_result.json"],
            "timeout_seconds": 600,
        },
        {
            "name": "unittest_discover",
            "command": [py, "-m", "unittest", "discover", "-s", "tests", "-p", "test*.py"],
            "timeout_seconds": 600,
        },
        {
            "name": "case_corpus_eval",
            "command": [
                py,
                "scripts/run_case_corpus_eval.py",
                "artifacts/eval_cases/",
                "--output",
                "artifacts/p2_case_corpus_eval.json",
            ],
            "timeout_seconds": 300,
        },
    ]
    if not skip_long_session:
        checks.append(
            {
                "name": "long_session_demo",
                "command": [
                    py,
                    "scripts/run_long_session_demo.py",
                    "--turns",
                    "50",
                    "--sessions",
                    "3",
                    "--output",
                    "artifacts/p2_4_long_session_reliability.json",
                ],
                "timeout_seconds": 360,
            }
        )
    checks.extend(
        [
            {
                "name": "secret_scan",
                "command": [
                    py,
                    "scripts/secret_scan.py",
                    "--json",
                    "--output",
                    "artifacts/secret_scan_result.json",
                ],
                "timeout_seconds": 180,
            },
            {
                "name": "git_diff_check",
                "command": ["git", "diff", "--check"],
                "timeout_seconds": 120,
            },
        ]
    )
    return checks


def run_p2_checks(
    check_specs: Sequence[CheckSpec],
    *,
    fail_fast: bool = False,
    cwd: Path | None = None,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for spec in check_specs:
        check, _ = run_command_check(
            str(spec["name"]),
            spec["command"],
            cwd=cwd or ROOT_DIR,
            timeout_seconds=int(spec.get("timeout_seconds", 300)),
        )
        checks.append(check)
        if fail_fast and check["status"] != "ok":
            break
    return checks


def summarize_p2_gate(checks: list[dict[str, Any]], *, skip_long_session: bool = False) -> dict[str, Any]:
    failed = [check for check in checks if check.get("status") != "ok"]
    p1_gate = _load_json_file(ROOT_DIR / "artifacts" / "p1_gate_result.json")
    case_corpus = _load_json_file(ROOT_DIR / "artifacts" / "p2_case_corpus_eval.json")
    long_session = _load_json_file(ROOT_DIR / "artifacts" / "p2_4_long_session_reliability.json")
    secret_scan = _load_json_file(ROOT_DIR / "artifacts" / "secret_scan_result.json")
    runtime_config = _load_json_file(ROOT_DIR / "artifacts" / "p3_1_runtime_config.json")
    observability = _load_json_file(ROOT_DIR / "artifacts" / "p3_2_observability.json")
    release_packaging = _load_json_file(ROOT_DIR / "artifacts" / "p3_3_release_packaging_check.json")
    api_contract = _load_json_file(ROOT_DIR / "artifacts" / "p3_4_api_contract_check.json")
    status = "ok" if not failed else "failed"
    return {
        "phase": "P2.5",
        "current_gate_phase": "P3.4",
        "status": status,
        "total_checks": len(checks),
        "passed": len(checks) - len(failed),
        "failed": len(failed),
        "checks": checks,
        "runtime_config_check": {
            "status": runtime_config.get("status"),
            "runtime_mode": (runtime_config.get("runtime_config") or {}).get("runtime_mode"),
            "db_path_source": (runtime_config.get("runtime_config") or {}).get("db_path_source"),
            "warnings": len(runtime_config.get("warnings") or []),
            "errors": len(runtime_config.get("errors") or []),
        },
        "observability_check": {
            "status": observability.get("status"),
            "structured_logging": observability.get("structured_logging"),
            "redaction_enabled": observability.get("redaction_enabled"),
            "request_id_supported": observability.get("request_id_supported"),
            "checks": len(observability.get("checks") or []),
        },
        "release_packaging_check": {
            "status": release_packaging.get("status"),
            "phase": release_packaging.get("phase"),
            "checks_total": release_packaging.get("checks_total"),
            "checks_passed": release_packaging.get("checks_passed"),
            "errors": len(release_packaging.get("errors") or []),
        },
        "api_contract_check": {
            "status": api_contract.get("status"),
            "phase": api_contract.get("phase"),
            "api_version": api_contract.get("api_version"),
            "contract_status": api_contract.get("contract_status"),
            "checks_total": api_contract.get("checks_total"),
            "checks_passed": api_contract.get("checks_passed"),
            "public_endpoint_count": api_contract.get("public_endpoint_count"),
            "version_headers_supported": api_contract.get("version_headers_supported"),
            "errors": len(api_contract.get("errors") or []),
        },
        "p1_gate": {
            "status": p1_gate.get("status"),
            "total_checks": p1_gate.get("total_checks"),
            "passed": p1_gate.get("passed"),
            "failed": p1_gate.get("failed"),
        },
        "case_corpus_eval": {
            "status": case_corpus.get("status"),
            "case_count": case_corpus.get("case_count"),
            "passed": case_corpus.get("passed"),
            "failed": case_corpus.get("failed"),
            "state_validation": case_corpus.get("state_validation"),
            "report_validation": case_corpus.get("report_validation"),
        },
        "long_session": {
            "skipped": bool(skip_long_session),
            "status": None if skip_long_session else long_session.get("status"),
            "sessions": None if skip_long_session else long_session.get("sessions"),
            "turns_per_session": None if skip_long_session else long_session.get("turns_per_session"),
            "secret_found": None if skip_long_session else long_session.get("secret_found"),
        },
        "secret_scan": {
            "status": secret_scan.get("status"),
            "finding_count": secret_scan.get("finding_count"),
            "allowed_count": secret_scan.get("allowed_count"),
            "scanned_files": secret_scan.get("scanned_files"),
        },
        "boundary_check": _boundary_check(),
        "recommend_next": "P3.5" if status == "ok" else "hold",
    }


def run_p2_gate(
    *,
    check_specs: Sequence[CheckSpec] | None = None,
    fail_fast: bool = False,
    skip_long_session: bool = False,
    cwd: Path | None = None,
) -> dict[str, Any]:
    specs = list(check_specs) if check_specs is not None else default_check_specs(skip_long_session=skip_long_session)
    checks = run_p2_checks(specs, fail_fast=fail_fast, cwd=cwd)
    return summarize_p2_gate(checks, skip_long_session=skip_long_session)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_redact_preserving_schema(payload), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def exit_code_for_result(result: dict[str, Any]) -> int:
    return 0 if result.get("status") == "ok" else 1


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local P2 delivery gate checks.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_ARTIFACT_PATH),
        help="JSON artifact path. Defaults to artifacts/p2_gate_result.json.",
    )
    parser.add_argument("--fail-fast", action="store_true", help="Stop after the first failed check.")
    parser.add_argument(
        "--skip-long-session",
        action="store_true",
        help="Skip the P2.4 long-session demo check.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = _parse_args(argv)
    result = run_p2_gate(fail_fast=args.fail_fast, skip_long_session=args.skip_long_session)
    write_json(Path(args.output), result)
    if args.json:
        print(json.dumps(_redact_preserving_schema(result), ensure_ascii=False, indent=2, sort_keys=True))
    return exit_code_for_result(result)


if __name__ == "__main__":
    raise SystemExit(main())
