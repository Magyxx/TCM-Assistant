from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_PATH = Path("artifacts") / "code_health_gate_baseline.json"
PHASE = "P4.6.2"
TAIL_CHARS = 4000


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _tail(value: str, limit: int = TAIL_CHARS) -> str:
    return value[-limit:]


def _command_to_text(command: Sequence[str]) -> str:
    return subprocess.list2cmdline([str(part) for part in command])


def _run_command(
    name: str,
    command: Sequence[str],
    *,
    timeout_seconds: int,
    check_type: str,
) -> dict[str, Any]:
    started = time.perf_counter()
    command_text = _command_to_text(command)
    try:
        completed = subprocess.run(
            [str(part) for part in command],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )
        return_code = int(completed.returncode)
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        status = "ok" if return_code == 0 else ("failed" if check_type == "hard" else "caution")
        details = "return_code=0" if return_code == 0 else f"return_code={return_code}"
    except FileNotFoundError as exc:
        return_code = -127
        stdout = ""
        stderr = str(exc)
        status = "failed" if check_type == "hard" else "caution"
        details = f"command_not_found: {command[0]}"
    except subprocess.TimeoutExpired as exc:
        return_code = -1
        stdout = exc.stdout or ""
        stderr = (exc.stderr or "") + f"\nTimeout after {timeout_seconds} seconds."
        status = "failed" if check_type == "hard" else "caution"
        details = f"timeout_after={timeout_seconds}s"

    duration = time.perf_counter() - started
    result = {
        "name": name,
        "check_type": check_type,
        "command": command_text,
        "status": status,
        "blocking": check_type == "hard",
        "return_code": return_code,
        "duration_seconds": round(duration, 3),
        "details": details,
        "stdout_tail": _tail(stdout),
        "stderr_tail": _tail(stderr),
    }
    if name == "unittest_discover_tests":
        combined = f"{stdout}\n{stderr}"
        match = re.search(r"Ran\s+(\d+)\s+tests?\s+in\s+([0-9.]+)s", combined)
        if match:
            result["unittest_summary"] = {
                "tests_run": int(match.group(1)),
                "duration_seconds_reported": float(match.group(2)),
                "ok": "\nOK" in combined or combined.rstrip().endswith("OK"),
            }
    return result


def _hard_specs(output_path: Path) -> list[dict[str, Any]]:
    py = sys.executable
    return [
        {
            "name": "compileall",
            "command": [py, "-m", "compileall", "-q", "app", "scripts", "tests"],
            "timeout_seconds": 120,
        },
        {
            "name": "p4_gate",
            "command": [py, "scripts/run_p4_gate.py"],
            "timeout_seconds": 300,
        },
        {
            "name": "unittest_discover_tests",
            "command": [py, "-m", "unittest", "discover", "-s", "tests"],
            "timeout_seconds": 600,
        },
        {
            "name": "baseline_json_valid",
            "command": [py, "-m", "json.tool", str(output_path)],
            "timeout_seconds": 60,
        },
    ]


def _soft_specs() -> list[dict[str, Any]]:
    return [
        {
            "name": "ruff_check",
            "command": ["ruff", "check", "app", "scripts", "tests"],
            "timeout_seconds": 120,
        },
        {
            "name": "ruff_format_check",
            "command": ["ruff", "format", "--check", "app", "scripts", "tests"],
            "timeout_seconds": 120,
        },
        {
            "name": "mypy",
            "command": ["mypy", "app", "scripts", "--ignore-missing-imports"],
            "timeout_seconds": 180,
        },
        {
            "name": "vulture",
            "command": ["vulture", "app", "scripts", "tests", "--min-confidence", "80"],
            "timeout_seconds": 180,
        },
        {
            "name": "radon_cc",
            "command": ["radon", "cc", "app", "scripts", "-s", "-a"],
            "timeout_seconds": 180,
        },
        {
            "name": "deptry",
            "command": ["deptry", "."],
            "timeout_seconds": 180,
        },
    ]


def _summarize_soft(soft_checks: Sequence[dict[str, Any]]) -> str:
    if not soft_checks:
        return "skipped"
    if all(check.get("status") == "ok" for check in soft_checks):
        return "ok"
    return "caution"


def _known_cautions(soft_checks: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    cautions: list[dict[str, Any]] = []
    for check in soft_checks:
        if check.get("status") != "ok":
            cautions.append(
                {
                    "source": check.get("name"),
                    "risk": "caution",
                    "details": check.get("details"),
                    "command": check.get("command"),
                }
            )
    cautions.extend(
        [
            {
                "source": "test_discovery",
                "risk": "caution",
                "details": "Use python -m unittest discover -s tests. Root-level python -m unittest discover previously discovered 0 tests.",
            },
            {
                "source": "transformers_torch_version",
                "risk": "caution",
                "details": "P4 gate may emit the existing transformers/PyTorch version warning; this is recorded as a dependency caution, not a code-health hard failure.",
            },
        ]
    )
    return cautions


def _untouched_risky_items() -> list[dict[str, str]]:
    return [
        {
            "item": "TurnOutput, RunState, FinalReport",
            "risk": "risky",
            "status": "untouched",
            "reason": "Schema field semantics are frozen.",
        },
        {
            "item": "FastAPI response schema and API contract",
            "risk": "risky",
            "status": "untouched",
            "reason": "Public contract is frozen.",
        },
        {
            "item": "SQLite schema",
            "risk": "risky",
            "status": "untouched",
            "reason": "Persistence schema is frozen.",
        },
        {
            "item": "Risk rule semantics",
            "risk": "risky",
            "status": "untouched",
            "reason": "Risk behavior is outside this gate-baseline phase.",
        },
        {
            "item": "Legacy, gate, SFT, and RAG compatibility entrypoints",
            "risk": "caution",
            "status": "untouched",
            "reason": "No compatibility entrypoint deletion or movement is allowed.",
        },
        {
            "item": "High-complexity functions and duplicate helpers",
            "risk": "caution",
            "status": "untouched",
            "reason": "No helper merging or complexity refactor is allowed.",
        },
        {
            "item": "Mojibake/user-visible Chinese literals",
            "risk": "risky",
            "status": "untouched",
            "reason": "Literal repair may alter user-visible output.",
        },
    ]


def _build_payload(
    *,
    hard_checks: Sequence[dict[str, Any]],
    soft_checks: Sequence[dict[str, Any]],
    output_path: Path,
) -> dict[str, Any]:
    failed_hard = [check for check in hard_checks if check.get("status") != "ok"]
    hard_status = "ok" if not failed_hard else "failed"
    soft_status = _summarize_soft(soft_checks)
    return {
        "phase": PHASE,
        "generated_at": _utc_now(),
        "artifact_path": str(output_path),
        "status": hard_status,
        "hard_gate_status": hard_status,
        "soft_report_status": soft_status,
        "hard_checks_total": len(hard_checks),
        "hard_checks_passed": len(hard_checks) - len(failed_hard),
        "hard_checks_failed": len(failed_hard),
        "hard_checks": list(hard_checks),
        "soft_checks_total": len(soft_checks),
        "soft_checks_caution": len([check for check in soft_checks if check.get("status") != "ok"]),
        "soft_checks": list(soft_checks),
        "test_discovery_correction": {
            "official_unittest_command": f"{sys.executable} -m unittest discover -s tests",
            "project_command": "python -m unittest discover -s tests",
            "reason": "Root-level unittest discovery can report 0 tests; the repository's real test suite lives under tests/.",
        },
        "known_cautions": _known_cautions(soft_checks),
        "untouched_risky_items": _untouched_risky_items(),
        "next_recommended_phase": {
            "name": "P4.6.3 Soft Tool Adoption",
            "items": [
                "Install dev-only tools from requirements-dev.txt outside runtime requirements.",
                "Run soft tools and triage results without auto-fixing broad historical issues.",
                "Add focused exclusions or config only after human review.",
                "Keep schema, API, SQLite, risk-rule, legacy, SFT, and RAG compatibility boundaries frozen.",
            ],
        },
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    (ROOT_DIR / path).parent.mkdir(parents=True, exist_ok=True)
    (ROOT_DIR / path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def run_code_health_gate(*, output_path: Path = DEFAULT_OUTPUT_PATH, run_soft: bool = True) -> dict[str, Any]:
    hard_checks: list[dict[str, Any]] = []
    hard_specs = _hard_specs(output_path)

    for spec in hard_specs[:-1]:
        hard_checks.append(
            _run_command(
                spec["name"],
                spec["command"],
                timeout_seconds=int(spec["timeout_seconds"]),
                check_type="hard",
            )
        )

    soft_checks: list[dict[str, Any]] = []
    if run_soft:
        for spec in _soft_specs():
            soft_checks.append(
                _run_command(
                    spec["name"],
                    spec["command"],
                    timeout_seconds=int(spec["timeout_seconds"]),
                    check_type="soft",
                )
            )

    bootstrap_payload = _build_payload(hard_checks=hard_checks, soft_checks=soft_checks, output_path=output_path)
    _write_json(output_path, bootstrap_payload)

    json_spec = hard_specs[-1]
    hard_checks.append(
        _run_command(
            json_spec["name"],
            json_spec["command"],
            timeout_seconds=int(json_spec["timeout_seconds"]),
            check_type="hard",
        )
    )

    final_payload = _build_payload(hard_checks=hard_checks, soft_checks=soft_checks, output_path=output_path)
    _write_json(output_path, final_payload)
    return final_payload


def exit_code_for_result(payload: dict[str, Any]) -> int:
    return 0 if payload.get("hard_gate_status") == "ok" else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the P4.6.2 code health gate baseline.")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help=f"JSON artifact path. Defaults to {DEFAULT_OUTPUT_PATH}.",
    )
    parser.add_argument(
        "--skip-soft",
        action="store_true",
        help="Skip soft report tools. Hard gate still runs.",
    )
    parser.add_argument("--json", action="store_true", help="Print the full JSON payload.")
    args = parser.parse_args(argv)

    payload = run_code_health_gate(output_path=Path(args.output), run_soft=not args.skip_soft)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(
            "P4.6.2 code health gate: "
            f"hard={payload['hard_gate_status']} "
            f"soft={payload['soft_report_status']} "
            f"hard_checks={payload['hard_checks_passed']}/{payload['hard_checks_total']} "
            f"artifact={args.output}"
        )
    return exit_code_for_result(payload)


if __name__ == "__main__":
    raise SystemExit(main())
