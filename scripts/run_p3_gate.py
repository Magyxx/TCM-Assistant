from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.api.versioning import API_CONTRACT_STATUS, API_STAGE, API_VERSION
from scripts.gate_utils import redact_preserving_schema as _redact_preserving_schema
from scripts.run_p1_gate import run_command_check


DEFAULT_ARTIFACT_PATH = Path("artifacts") / "p3_gate_result.json"
DEFAULT_RC_ARTIFACT_PATH = Path("artifacts") / "p3_5_rc_gate.json"
PHASE = "P3.5"
RECOMMEND_NEXT = "P4.0"


CheckSpec = dict[str, Any]


ARTIFACTS = {
    "p1_gate": Path("artifacts") / "p1_gate_result.json",
    "p2_gate": Path("artifacts") / "p2_gate_result.json",
    "runtime_config": Path("artifacts") / "p3_1_runtime_config.json",
    "observability": Path("artifacts") / "p3_2_observability.json",
    "release_packaging": Path("artifacts") / "p3_3_release_packaging_check.json",
    "api_contract": Path("artifacts") / "p3_4_api_contract_check.json",
    "case_corpus": Path("artifacts") / "p2_case_corpus_eval.json",
    "long_session": Path("artifacts") / "p2_4_long_session_reliability.json",
    "secret_scan": Path("artifacts") / "secret_scan_result.json",
    "p1_contract_snapshot": Path("artifacts") / "p1_api_contract_snapshot.json",
}

BOUNDARY_FLAG_KEYS = (
    "orm",
    "memory_manager",
    "embedding",
    "tool_registry",
    "multi_agent",
    "web_ui",
    "auth_or_users",
    "diagnosis_prescription_or_treatment_plan",
)


def _load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _artifact_path(name: str) -> Path:
    return ROOT_DIR / ARTIFACTS[name]


def default_check_specs(*, skip_long_session: bool = False) -> list[CheckSpec]:
    py = sys.executable
    checks: list[CheckSpec] = [
        {
            "name": "p1_gate",
            "command": [py, "scripts/run_p1_gate.py", "--output", str(ARTIFACTS["p1_gate"])],
            "timeout_seconds": 900,
        },
        {
            "name": "p2_gate",
            "command": [py, "scripts/run_p2_gate.py", "--output", str(ARTIFACTS["p2_gate"])],
            "timeout_seconds": 1500,
        },
        {
            "name": "runtime_config_check",
            "command": [
                py,
                "scripts/check_runtime_config.py",
                "--json",
                "--output",
                str(ARTIFACTS["runtime_config"]),
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
                str(ARTIFACTS["observability"]),
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
                str(ARTIFACTS["release_packaging"]),
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
                str(ARTIFACTS["api_contract"]),
            ],
            "timeout_seconds": 120,
        },
        {
            "name": "case_corpus_eval",
            "command": [
                py,
                "scripts/run_case_corpus_eval.py",
                "artifacts/eval_cases/",
                "--output",
                str(ARTIFACTS["case_corpus"]),
            ],
            "timeout_seconds": 420,
        },
    ]
    if not skip_long_session:
        checks.append(
            {
                "name": "long_session_reliability",
                "command": [
                    py,
                    "scripts/run_long_session_demo.py",
                    "--turns",
                    "50",
                    "--sessions",
                    "3",
                    "--output",
                    str(ARTIFACTS["long_session"]),
                ],
                "timeout_seconds": 480,
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
                    str(ARTIFACTS["secret_scan"]),
                ],
                "timeout_seconds": 180,
            },
            {
                "name": "git_diff_check",
                "command": ["git", "diff", "--check"],
                "timeout_seconds": 120,
            },
            {
                "name": "unittest_discover",
                "command": [py, "-m", "unittest", "discover", "-s", "tests", "-p", "test*.py"],
                "timeout_seconds": 900,
            },
        ]
    )
    return checks


def run_p3_checks(
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
        if fail_fast and check.get("status") != "ok":
            break
    return checks


def _gate_check_status(gate_payload: dict[str, Any], check_name: str) -> str | None:
    for check in gate_payload.get("checks") or []:
        if isinstance(check, dict) and check.get("name") == check_name:
            return str(check.get("status")) if check.get("status") is not None else None
    return None


def summary_only_checks(*, skip_long_session: bool = False) -> list[dict[str, Any]]:
    p1_gate = _load_json_file(_artifact_path("p1_gate"))
    p2_gate = _load_json_file(_artifact_path("p2_gate"))
    artifact_statuses = [
        ("p1_gate", p1_gate.get("status")),
        ("p2_gate", p2_gate.get("status")),
        ("runtime_config_check", _load_json_file(_artifact_path("runtime_config")).get("status")),
        ("observability_check", _load_json_file(_artifact_path("observability")).get("status")),
        ("release_packaging_check", _load_json_file(_artifact_path("release_packaging")).get("status")),
        ("api_contract_check", _load_json_file(_artifact_path("api_contract")).get("status")),
        ("case_corpus_eval", _load_json_file(_artifact_path("case_corpus")).get("status")),
    ]
    if not skip_long_session:
        artifact_statuses.append(
            ("long_session_reliability", _load_json_file(_artifact_path("long_session")).get("status"))
        )
    artifact_statuses.extend(
        [
            ("secret_scan", _load_json_file(_artifact_path("secret_scan")).get("status")),
            ("git_diff_check", _gate_check_status(p2_gate, "git_diff_check")),
            ("unittest_discover", _gate_check_status(p2_gate, "unittest_discover")),
        ]
    )
    return [
        {
            "name": name,
            "command": "summary-only artifact status",
            "status": "ok" if status == "ok" else "failed",
            "return_code": 0 if status == "ok" else 1,
            "duration_seconds": 0.0,
            "stdout_tail": "",
            "stderr_tail": "" if status == "ok" else f"artifact status={status!r}",
        }
        for name, status in artifact_statuses
    ]


def _boundary_violations_from_payload(payload: dict[str, Any], *, prefix: str) -> list[str]:
    violations: list[str] = []
    boundary = payload.get("boundary_check")
    if isinstance(boundary, dict):
        for key in BOUNDARY_FLAG_KEYS:
            if bool(boundary.get(key)):
                violations.append(f"{prefix}.{key}")
        if bool(boundary.get("violated")):
            violations.append(f"{prefix}.violated")
    if bool(payload.get("boundary_violated")):
        violations.append(f"{prefix}.boundary_violated")
    return violations


def _collect_boundary_violations(artifacts: dict[str, dict[str, Any]], diagnosis_system: bool) -> list[str]:
    violations: list[str] = []
    for name in (
        "p1_gate",
        "p2_gate",
        "runtime_config",
        "observability",
        "release_packaging",
        "api_contract",
        "case_corpus",
        "long_session",
    ):
        violations.extend(_boundary_violations_from_payload(artifacts.get(name, {}), prefix=name))
    if diagnosis_system:
        violations.append("health_contract.diagnosis_system")
    return sorted(set(violations))


def _breaking_change_detected(artifacts: dict[str, dict[str, Any]]) -> bool:
    for name in ("observability", "release_packaging", "api_contract"):
        payload = artifacts.get(name, {})
        if bool(payload.get("contract_changed")):
            return True
        if bool(payload.get("api_response_body_changed")):
            return True
        if bool(payload.get("sqlite_schema_changed")):
            return True
    return False


def _section_status(payload: dict[str, Any]) -> str | None:
    status = payload.get("status")
    return str(status) if status is not None else None


def _summarize_case_corpus(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": payload.get("status"),
        "case_count": payload.get("case_count"),
        "passed": payload.get("passed"),
        "failed": payload.get("failed"),
        "state_validation": payload.get("state_validation"),
        "report_validation": payload.get("report_validation"),
        "boundary_check": payload.get("boundary_check"),
    }


def _summarize_p1_gate(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": payload.get("status"),
        "phase": payload.get("phase"),
        "total_checks": payload.get("total_checks"),
        "passed": payload.get("passed"),
        "failed": payload.get("failed"),
        "boundary_check": payload.get("boundary_check"),
    }


def _summarize_p2_gate(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": payload.get("status"),
        "phase": payload.get("phase"),
        "current_gate_phase": payload.get("current_gate_phase"),
        "total_checks": payload.get("total_checks"),
        "passed": payload.get("passed"),
        "failed": payload.get("failed"),
        "recommend_next": payload.get("recommend_next"),
        "boundary_check": payload.get("boundary_check"),
    }


def _summarize_runtime_config(payload: dict[str, Any]) -> dict[str, Any]:
    runtime_config = payload.get("runtime_config") or {}
    return {
        "status": payload.get("status"),
        "phase": payload.get("phase"),
        "runtime_mode": runtime_config.get("runtime_mode"),
        "db_path_source": runtime_config.get("db_path_source"),
        "redact_logs": runtime_config.get("redact_logs"),
        "openai_api_key_present": runtime_config.get("openai_api_key_present"),
        "checks_total": len(payload.get("checks") or []),
        "errors": len(payload.get("errors") or []),
        "warnings": len(payload.get("warnings") or []),
        "boundary_check": payload.get("boundary_check"),
    }


def _summarize_observability(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": payload.get("status"),
        "phase": payload.get("phase"),
        "structured_logging": payload.get("structured_logging"),
        "redaction_enabled": payload.get("redaction_enabled"),
        "request_id_supported": payload.get("request_id_supported"),
        "contract_changed": payload.get("contract_changed"),
        "sqlite_schema_changed": payload.get("sqlite_schema_changed"),
        "checks_total": len(payload.get("checks") or []),
        "boundary_violated": payload.get("boundary_violated"),
    }


def _summarize_release_packaging(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": payload.get("status"),
        "phase": payload.get("phase"),
        "checks_total": payload.get("checks_total"),
        "checks_passed": payload.get("checks_passed"),
        "contract_changed": payload.get("contract_changed"),
        "sqlite_schema_changed": payload.get("sqlite_schema_changed"),
        "boundary_violated": payload.get("boundary_violated"),
        "errors": len(payload.get("errors") or []),
    }


def _summarize_api_contract(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": payload.get("status"),
        "phase": payload.get("phase"),
        "api_version": payload.get("api_version"),
        "contract_status": payload.get("contract_status"),
        "checks_total": payload.get("checks_total"),
        "checks_passed": payload.get("checks_passed"),
        "public_endpoint_count": payload.get("public_endpoint_count"),
        "version_endpoint_supported": payload.get("version_endpoint_supported"),
        "version_headers_supported": payload.get("version_headers_supported"),
        "contract_changed": payload.get("contract_changed"),
        "api_response_body_changed": payload.get("api_response_body_changed"),
        "sqlite_schema_changed": payload.get("sqlite_schema_changed"),
        "boundary_violated": payload.get("boundary_violated"),
        "errors": len(payload.get("errors") or []),
    }


def _summarize_long_session(payload: dict[str, Any], *, skip_long_session: bool) -> dict[str, Any]:
    return {
        "skipped": bool(skip_long_session),
        "status": None if skip_long_session else payload.get("status"),
        "phase": None if skip_long_session else payload.get("phase"),
        "sessions": None if skip_long_session else payload.get("sessions"),
        "turns_per_session": None if skip_long_session else payload.get("turns_per_session"),
        "secret_found": None if skip_long_session else payload.get("secret_found"),
        "boundary_check": None if skip_long_session else payload.get("boundary_check"),
    }


def _summarize_secret_scan(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": payload.get("status"),
        "finding_count": payload.get("finding_count"),
        "allowed_count": payload.get("allowed_count"),
        "scanned_files": payload.get("scanned_files"),
    }


def summarize_p3_gate(checks: list[dict[str, Any]], *, skip_long_session: bool = False) -> dict[str, Any]:
    artifacts = {name: _load_json_file(_artifact_path(name)) for name in ARTIFACTS}
    p1_snapshot = artifacts.get("p1_contract_snapshot", {})
    diagnosis_system = bool((p1_snapshot.get("health_contract") or {}).get("diagnosis_system"))
    breaking_change_detected = _breaking_change_detected(artifacts)
    boundary_violations = _collect_boundary_violations(artifacts, diagnosis_system)
    failed_checks = [check for check in checks if check.get("status") != "ok"]
    invariant_failures = []
    if API_VERSION != "v1":
        invariant_failures.append("api_version")
    if API_CONTRACT_STATUS != "frozen":
        invariant_failures.append("api_contract_status")
    if breaking_change_detected:
        invariant_failures.append("breaking_change_detected")
    if diagnosis_system:
        invariant_failures.append("diagnosis_system")
    if boundary_violations:
        invariant_failures.append("boundary_violations")

    status = "ok" if not failed_checks and not invariant_failures else "failed"
    passed_checks = len(checks) - len(failed_checks)
    git_diff_status = next((check for check in checks if check.get("name") == "git_diff_check"), {})
    unittest_status = next((check for check in checks if check.get("name") == "unittest_discover"), {})
    api_contract = artifacts.get("api_contract", {})

    return {
        "stage": PHASE,
        "phase": PHASE,
        "current_gate_phase": PHASE,
        "recommend_next": RECOMMEND_NEXT if status == "ok" else "hold",
        "status": status,
        "checks_total": len(checks),
        "checks_passed": passed_checks,
        "checks_failed": len(failed_checks),
        "checks": checks,
        "invariant_failures": invariant_failures,
        "api_version": API_VERSION,
        "api_stage": API_STAGE,
        "api_contract_status": API_CONTRACT_STATUS,
        "api_contract_artifact_status": api_contract.get("status"),
        "breaking_change_detected": breaking_change_detected,
        "contract_changed": bool(api_contract.get("contract_changed")),
        "api_response_body_changed": bool(api_contract.get("api_response_body_changed")),
        "sqlite_schema_changed": bool(api_contract.get("sqlite_schema_changed")),
        "diagnosis_system": diagnosis_system,
        "boundary_violations": boundary_violations,
        "p1_gate": _summarize_p1_gate(artifacts.get("p1_gate", {})),
        "p2_gate": _summarize_p2_gate(artifacts.get("p2_gate", {})),
        "runtime_config": _summarize_runtime_config(artifacts.get("runtime_config", {})),
        "observability": _summarize_observability(artifacts.get("observability", {})),
        "release_packaging": _summarize_release_packaging(artifacts.get("release_packaging", {})),
        "api_contract": _summarize_api_contract(api_contract),
        "case_corpus": _summarize_case_corpus(artifacts.get("case_corpus", {})),
        "long_session": _summarize_long_session(
            artifacts.get("long_session", {}),
            skip_long_session=skip_long_session,
        ),
        "secret_scan": _summarize_secret_scan(artifacts.get("secret_scan", {})),
        "git_diff_check": {
            "status": git_diff_status.get("status"),
            "return_code": git_diff_status.get("return_code"),
            "stderr_tail": git_diff_status.get("stderr_tail"),
        },
        "unittest": {
            "status": unittest_status.get("status"),
            "return_code": unittest_status.get("return_code"),
            "stderr_tail": unittest_status.get("stderr_tail"),
        },
        "artifact_paths": {name: str(path).replace("\\", "/") for name, path in ARTIFACTS.items()},
    }


def run_p3_gate(
    *,
    check_specs: Sequence[CheckSpec] | None = None,
    fail_fast: bool = False,
    skip_long_session: bool = False,
    summary_only: bool = False,
    cwd: Path | None = None,
) -> dict[str, Any]:
    if summary_only:
        checks = summary_only_checks(skip_long_session=skip_long_session)
    else:
        specs = list(check_specs) if check_specs is not None else default_check_specs(skip_long_session=skip_long_session)
        checks = run_p3_checks(specs, fail_fast=fail_fast, cwd=cwd)
    return summarize_p3_gate(checks, skip_long_session=skip_long_session)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_redact_preserving_schema(payload), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def exit_code_for_result(result: dict[str, Any]) -> int:
    return 0 if result.get("status") == "ok" else 1


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local P3.5 release-candidate gate checks.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_ARTIFACT_PATH),
        help="Primary JSON artifact path. Defaults to artifacts/p3_gate_result.json.",
    )
    parser.add_argument(
        "--rc-output",
        default=str(DEFAULT_RC_ARTIFACT_PATH),
        help="RC gate JSON artifact path. Defaults to artifacts/p3_5_rc_gate.json.",
    )
    parser.add_argument("--fail-fast", action="store_true", help="Stop after the first failed check.")
    parser.add_argument(
        "--skip-long-session",
        action="store_true",
        help="Skip the P2.4 long-session reliability check.",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Build the P3.5 summary from existing artifacts without executing checks.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = _parse_args(argv)
    result = run_p3_gate(
        fail_fast=args.fail_fast,
        skip_long_session=args.skip_long_session,
        summary_only=args.summary_only,
    )
    output_path = Path(args.output)
    rc_output_path = Path(args.rc_output)
    write_json(output_path, result)
    if rc_output_path != output_path:
        write_json(rc_output_path, result)
    if args.json:
        print(json.dumps(_redact_preserving_schema(result), ensure_ascii=False, indent=2, sort_keys=True))
    return exit_code_for_result(result)


if __name__ == "__main__":
    raise SystemExit(main())
