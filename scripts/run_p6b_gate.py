from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.observability.logger import write_json  # noqa: E402
from scripts.run_p1_gate import run_command_check  # noqa: E402
from scripts.run_p5_demo_cases import run_p5_demo_cases  # noqa: E402
from scripts.run_p5_real_runtime_validation import run_p5_validation  # noqa: E402
from scripts.run_p6_knowledge_pipeline import run_p6_pipeline  # noqa: E402
from scripts.run_p6b_runtime_rag_validation import (  # noqa: E402
    DEFAULT_TRACE_ARTIFACT,
    DEFAULT_VALIDATION_ARTIFACT,
    run_p6b_runtime_rag_validation,
)


PHASE = "P6B"
DEFAULT_GATE_ARTIFACT = ROOT_DIR / "artifacts" / "p6b_gate_report.json"


def _json_safe(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, Path):
        try:
            return str(value.relative_to(ROOT_DIR)).replace("\\", "/")
        except ValueError:
            return str(value).replace("\\", "/")
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _check(name: str, ok: bool, detail: str = "", extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {
        "name": name,
        "status": "ok" if ok else "failed",
        "ok": bool(ok),
        "detail": detail,
    }
    if extra:
        payload["extra"] = extra
    return payload


def _run_json_checks(paths: Sequence[Path]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for path in paths:
        check, _ = run_command_check(
            f"json_valid:{path.name}",
            [sys.executable, "-m", "json.tool", str(path.relative_to(ROOT_DIR))],
            cwd=ROOT_DIR,
            timeout_seconds=60,
        )
        checks.append(check)
    return checks


def _run_command_checks(*, run_unittest: bool, run_compileall: bool, run_p4_gate: bool) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    if run_compileall:
        check, _ = run_command_check(
            "compileall",
            [sys.executable, "-m", "compileall", "-q", "app", "scripts", "tests"],
            cwd=ROOT_DIR,
            timeout_seconds=120,
        )
        checks.append(check)
    if run_p4_gate:
        check, _ = run_command_check(
            "p4_gate",
            [sys.executable, "scripts/run_p4_gate.py"],
            cwd=ROOT_DIR,
            timeout_seconds=300,
        )
        checks.append(check)
    if run_unittest:
        check, _ = run_command_check(
            "unittest_discover_tests",
            [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
            cwd=ROOT_DIR,
            timeout_seconds=700,
        )
        checks.append(check)
    return checks


def run_p6b_gate(
    *,
    write_artifact: bool = True,
    run_unittest: bool = True,
    run_compileall: bool = True,
    run_p4_gate_check: bool = True,
    run_p5_regression: bool = True,
) -> dict[str, Any]:
    knowledge_pipeline = run_p6_pipeline(write_outputs=True)
    runtime_validation = run_p6b_runtime_rag_validation(write_artifacts=True)
    p5_validation: dict[str, Any] = {"status": "skipped"}
    p5_demo: dict[str, Any] = {"status": "skipped"}
    if run_p5_regression:
        p5_validation = run_p5_validation(
            write_artifacts=False,
            probe_real_llm=False,
            real_llm_timeout_seconds=1,
        )["validation"]
        p5_demo = run_p5_demo_cases(write_artifacts=False)

    json_checks = _run_json_checks(
        [
            ROOT_DIR / "artifacts" / "p6_knowledge_pipeline.json",
            DEFAULT_VALIDATION_ARTIFACT,
            DEFAULT_TRACE_ARTIFACT,
        ]
    )
    command_checks = _run_command_checks(
        run_unittest=run_unittest,
        run_compileall=run_compileall,
        run_p4_gate=run_p4_gate_check,
    )
    all_command_checks = json_checks + command_checks
    all_json_artifacts_valid = all(check.get("status") == "ok" for check in json_checks)
    regression_ok = (
        (not run_p5_regression)
        or (
            p5_validation.get("status") in {"ok", "caution"}
            and p5_demo.get("status") == "ok"
        )
    )
    command_ok = all(check.get("status") == "ok" for check in command_checks)
    runtime_metrics = runtime_validation.get("metrics", {})
    gate_metrics = {
        **runtime_metrics,
        "all_json_artifacts_valid": all_json_artifacts_valid,
        "unittest_pass": not run_unittest or any(
            check.get("name") == "unittest_discover_tests" and check.get("status") == "ok"
            for check in command_checks
        ),
        "compileall_pass": not run_compileall or any(
            check.get("name") == "compileall" and check.get("status") == "ok"
            for check in command_checks
        ),
        "p5_validation_status": p5_validation.get("status"),
        "p5_demo_status": p5_demo.get("status"),
    }
    hard_ok = (
        knowledge_pipeline.get("status") == "ok"
        and runtime_validation.get("status") == "ok"
        and regression_ok
        and command_ok
        and all_json_artifacts_valid
    )
    status = "ok" if hard_ok else "failed"
    failed_checks = [
        check
        for check in all_command_checks
        if check.get("status") != "ok"
    ]
    blockers = []
    if knowledge_pipeline.get("status") != "ok":
        blockers.append({"source": "knowledge_pipeline", "detail": knowledge_pipeline.get("status")})
    if runtime_validation.get("status") != "ok":
        blockers.append({"source": "runtime_rag", "detail": runtime_validation.get("metrics")})
    if not regression_ok:
        blockers.append({"source": "p5_regression", "detail": {"p5": p5_validation.get("status"), "demo": p5_demo.get("status")}})
    blockers.extend({"source": check.get("name"), "detail": check.get("stderr_tail") or check.get("stdout_tail")} for check in failed_checks)

    payload = {
        "phase": PHASE,
        "status": status,
        "knowledge_pipeline": {
            "status": knowledge_pipeline.get("status"),
            "approved_source_count": knowledge_pipeline.get("source_review", {}).get("approved_source_count"),
            "chunk_count": knowledge_pipeline.get("chunking", {}).get("chunk_count"),
        },
        "runtime_rag": runtime_validation.get("runtime_rag"),
        "rag_boundary": runtime_validation.get("rag_boundary"),
        "safety": runtime_validation.get("safety"),
        "trace": {
            "status": runtime_validation.get("trace", {}).get("status"),
            "trace_schema_pass": runtime_validation.get("trace", {}).get("trace_schema_pass"),
            "sample_count": runtime_validation.get("trace", {}).get("sample_count"),
        },
        "regression": {
            "status": "ok" if regression_ok else "failed",
            "p5_validation_status": p5_validation.get("status"),
            "p5_demo_status": p5_demo.get("status"),
            "p4_gate_status": next(
                (check.get("status") for check in command_checks if check.get("name") == "p4_gate"),
                "skipped",
            ),
            "unittest_status": next(
                (check.get("status") for check in command_checks if check.get("name") == "unittest_discover_tests"),
                "skipped",
            ),
            "compileall_status": next(
                (check.get("status") for check in command_checks if check.get("name") == "compileall"),
                "skipped",
            ),
        },
        "artifacts": {
            "p6_knowledge_pipeline": "artifacts/p6_knowledge_pipeline.json",
            "p6b_runtime_rag_validation": "artifacts/p6b_runtime_rag_validation.json",
            "p6b_runtime_rag_trace_samples": "artifacts/p6b_runtime_rag_trace_samples.json",
            "p6b_rag_evidence_audit": "artifacts/p6b_rag_evidence_audit.jsonl",
            "p6b_gate_report": "artifacts/p6b_gate_report.json",
        },
        "metrics": gate_metrics,
        "command_checks": all_command_checks,
        "failure_analysis": {
            "status": status,
            "blockers": blockers,
            "cautions": [
                {
                    "source": "real_llm_probe",
                    "detail": "P6B gate uses deterministic P5 regression with real_llm probe disabled; run P5 separately in a reachable provider environment for real_llm availability measurement.",
                }
            ],
        },
    }
    if write_artifact:
        write_json(DEFAULT_GATE_ARTIFACT, _json_safe(payload))
    return payload


def exit_code_for_status(status: str) -> int:
    return 0 if status == "ok" else 1


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the P6B runtime RAG integration gate.")
    parser.add_argument("--json", action="store_true", help="Print the full gate artifact JSON.")
    parser.add_argument("--skip-unittest", action="store_true", help="Skip full unittest discovery.")
    parser.add_argument("--skip-p4-gate", action="store_true", help="Skip nested P4 gate command.")
    parser.add_argument("--skip-p5-regression", action="store_true", help="Skip in-process P5 regression checks.")
    parser.add_argument("--skip-compileall", action="store_true", help="Skip compileall command.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args(argv)
    payload = run_p6b_gate(
        run_unittest=not args.skip_unittest,
        run_compileall=not args.skip_compileall,
        run_p4_gate_check=not args.skip_p4_gate,
        run_p5_regression=not args.skip_p5_regression,
    )
    if args.json:
        print(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        metrics = payload["metrics"]
        print(
            "P6B gate: "
            f"status={payload['status']} "
            f"runtime_evidence={metrics.get('retrieved_evidence_count')} "
            f"json={metrics.get('all_json_artifacts_valid')} "
            f"artifact={DEFAULT_GATE_ARTIFACT.relative_to(ROOT_DIR)}"
        )
    return exit_code_for_status(str(payload["status"]))


if __name__ == "__main__":
    raise SystemExit(main())
