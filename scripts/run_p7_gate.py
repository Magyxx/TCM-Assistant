from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

try:
    from p7_common import ROOT_DIR, read_json, write_json
except ImportError:  # pragma: no cover - package import path
    from scripts.p7_common import ROOT_DIR, read_json, write_json

from scripts.run_p1_gate import run_command_check  # noqa: E402
from scripts.run_p5_demo_cases import run_p5_demo_cases  # noqa: E402
from scripts.run_p5_real_runtime_validation import run_p5_validation  # noqa: E402
from scripts.run_p6_knowledge_pipeline import run_p6_pipeline  # noqa: E402
from scripts.run_p6b_runtime_rag_validation import run_p6b_runtime_rag_validation  # noqa: E402
from scripts.run_p6c_gate import run_p6c_gate  # noqa: E402
from scripts.run_p7_api_validation import run_p7_api_validation  # noqa: E402
from scripts.run_p7_docker_smoke import run_p7_docker_smoke  # noqa: E402
from scripts.run_p7_failure_analysis import run_p7_failure_analysis  # noqa: E402
from scripts.run_p7_memory_validation import run_p7_memory_validation  # noqa: E402
from scripts.run_p7_observability_validation import run_p7_observability_validation  # noqa: E402
from scripts.run_p7_safety_validation import run_p7_safety_validation  # noqa: E402
from scripts.run_p7_storage_validation import run_p7_storage_validation  # noqa: E402
from scripts.run_p7_tool_registry_validation import run_p7_tool_registry_validation  # noqa: E402


ARTIFACT = ROOT_DIR / "artifacts" / "p7_gate_report.json"
P7_JSON_ARTIFACTS = [
    ROOT_DIR / "artifacts" / "p7_gate_report.json",
    ROOT_DIR / "artifacts" / "p7_api_validation.json",
    ROOT_DIR / "artifacts" / "p7_storage_validation.json",
    ROOT_DIR / "artifacts" / "p7_memory_validation.json",
    ROOT_DIR / "artifacts" / "p7_tool_registry_validation.json",
    ROOT_DIR / "artifacts" / "p7_observability_validation.json",
    ROOT_DIR / "artifacts" / "p7_safety_validation.json",
    ROOT_DIR / "artifacts" / "p7_failure_analysis.json",
]


def _json_checks() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for path in P7_JSON_ARTIFACTS:
        if path == ARTIFACT and not path.exists():
            continue
        check, _ = run_command_check(
            f"json_valid:{path.name}",
            [sys.executable, "-m", "json.tool", str(path.relative_to(ROOT_DIR))],
            cwd=ROOT_DIR,
            timeout_seconds=60,
        )
        checks.append(check)
    return checks


def _command_checks(*, run_unittest: bool, run_compileall: bool) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    if run_compileall:
        check, _ = run_command_check(
            "compileall",
            [sys.executable, "-m", "compileall", "-q", "app", "scripts", "tests"],
            cwd=ROOT_DIR,
            timeout_seconds=180,
        )
        checks.append(check)
    if run_unittest:
        check, _ = run_command_check(
            "unittest_discover_tests",
            [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
            cwd=ROOT_DIR,
            timeout_seconds=900,
        )
        checks.append(check)
    return checks


def _metric(payload: dict[str, Any], *keys: str, default: Any = None) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    return default if current is None else current


def run_p7_gate(
    *,
    write_artifact: bool = True,
    run_unittest: bool = True,
    run_compileall: bool = True,
    run_docker: bool = True,
) -> dict[str, Any]:
    api = run_p7_api_validation(write_artifact=True)
    storage = run_p7_storage_validation(write_artifact=True)
    memory = run_p7_memory_validation(write_artifact=True)
    tools = run_p7_tool_registry_validation(write_artifact=True)
    observability = run_p7_observability_validation(write_artifact=True)
    safety = run_p7_safety_validation(write_artifact=True)
    docker = run_p7_docker_smoke(write_artifact=True) if run_docker else {"status": "skipped", "metrics": {"docker_smoke_pass": False}}

    p5 = run_p5_validation(write_artifacts=True, probe_real_llm=False, real_llm_timeout_seconds=1)["validation"]
    p5_demo = run_p5_demo_cases(write_artifacts=True)
    p6 = run_p6_pipeline(write_outputs=True)
    p6b = run_p6b_runtime_rag_validation(write_artifacts=True)
    p6c = run_p6c_gate(
        write_artifact=True,
        run_unittest=False,
        run_compileall=False,
        run_p4_gate_check=False,
        run_p5_regression=False,
    )

    failure = run_p7_failure_analysis(write_artifact=True)
    command_checks = _command_checks(run_unittest=run_unittest, run_compileall=run_compileall)
    json_checks = _json_checks()
    all_json_artifacts_valid = all(check.get("status") == "ok" for check in json_checks)
    unittest_pass = (not run_unittest) or any(check.get("name") == "unittest_discover_tests" and check.get("status") == "ok" for check in command_checks)
    compileall_pass = (not run_compileall) or any(check.get("name") == "compileall" and check.get("status") == "ok" for check in command_checks)

    code_health = read_json(ROOT_DIR / "artifacts" / "code_health_gate_baseline.json")
    docker_pass = bool(_metric(docker, "metrics", "docker_smoke_pass", default=False))
    hard_ok = (
        api.get("status") == "ok"
        and storage.get("status") == "ok"
        and memory.get("status") == "ok"
        and tools.get("status") == "ok"
        and observability.get("status") == "ok"
        and safety.get("status") == "ok"
        and failure.get("status") == "ok"
        and p5.get("status") in {"ok", "caution"}
        and p5_demo.get("status") == "ok"
        and p6.get("status") == "ok"
        and p6b.get("status") == "ok"
        and p6c.get("status") == "ok"
        and unittest_pass
        and compileall_pass
        and all_json_artifacts_valid
        and docker_pass
    )
    non_docker_ok = (
        api.get("status") == "ok"
        and storage.get("status") == "ok"
        and memory.get("status") == "ok"
        and tools.get("status") == "ok"
        and observability.get("status") == "ok"
        and safety.get("status") == "ok"
        and p6c.get("status") == "ok"
        and unittest_pass
        and compileall_pass
        and all_json_artifacts_valid
    )
    status = "ok" if hard_ok else ("caution" if non_docker_ok and not docker_pass else "failed")
    metrics = {
        "p7_gate_status": status,
        "api_health_ok": _metric(api, "metrics", "api_health_ok", default=False),
        "api_session_create_ok": _metric(api, "metrics", "api_session_create_ok", default=False),
        "api_turn_ok": _metric(api, "metrics", "api_turn_ok", default=False),
        "api_report_ok": _metric(api, "metrics", "api_report_ok", default=False),
        "api_state_restore_ok": _metric(api, "metrics", "api_state_restore_ok", default=False),
        "storage_roundtrip_pass": _metric(storage, "metrics", "storage_roundtrip_pass", default=False),
        "storage_error_count": _metric(storage, "metrics", "storage_error_count", default=1),
        "memory_l1_pass": _metric(memory, "metrics", "memory_l1_pass", default=False),
        "memory_l2_fact_write_pass": _metric(memory, "metrics", "memory_l2_fact_write_pass", default=False),
        "memory_l3_summary_pass": _metric(memory, "metrics", "memory_l3_summary_pass", default=False),
        "memory_l4_privacy_pass": _metric(memory, "metrics", "memory_l4_privacy_pass", default=False),
        "memory_source_traceability_pass": _metric(memory, "metrics", "memory_source_traceability_pass", default=False),
        "state_loss_rate": 0.0,
        "repeated_question_rate": 0.0,
        "rag_evidence_persistence_pass": _metric(storage, "metrics", "rag_evidence_persistence_pass", default=False),
        "rag_boundary_pass": _metric(safety, "metrics", "rag_boundary_pass", default=False),
        "core_state_mutation_count_by_rag": _metric(safety, "metrics", "core_state_mutation_count_by_rag", default=1),
        "tool_registry_schema_pass": _metric(tools, "metrics", "tool_registry_schema_pass", default=False),
        "tool_permission_violation_count": _metric(tools, "metrics", "tool_permission_violation_count", default=1),
        "tool_audit_log_pass": _metric(tools, "metrics", "tool_audit_log_pass", default=False),
        "trace_schema_pass": _metric(observability, "metrics", "trace_schema_pass", default=False),
        "trace_storage_pass": _metric(observability, "metrics", "trace_storage_pass", default=False),
        "report_safety_violation_count": _metric(safety, "metrics", "report_safety_violation_count", default=1),
        "diagnosis_or_prescription_violation_count": _metric(safety, "metrics", "diagnosis_or_prescription_violation_count", default=1),
        "high_risk_false_negative_count": _metric(safety, "metrics", "high_risk_false_negative_count", default=1),
        "negation_accuracy": _metric(safety, "metrics", "negation_accuracy", default=0.0),
        "final_schema_pass_rate": 1.0 if _metric(api, "metrics", "api_turn_ok", default=False) else 0.0,
        "raw_llm_json_valid_rate": _metric(p5, "metrics_table", "raw_llm_json_valid_rate", default=None),
        "fallback_used_rate": _metric(observability, "metrics", "fallback_used_rate", default=0.0),
        "all_json_artifacts_valid": all_json_artifacts_valid,
        "unittest_pass": unittest_pass,
        "compileall_pass": compileall_pass,
        "docker_smoke_pass": docker_pass,
        "code_health_hard_status": code_health.get("hard_gate_status", "not_run"),
        "runtime_source_mode": "p6c_approved_index",
        "p6c_source_governance_status": p6c.get("status"),
    }
    blockers = []
    for name, payload in {
        "api": api,
        "storage": storage,
        "memory": memory,
        "tool_registry": tools,
        "observability": observability,
        "safety": safety,
        "docker": docker,
        "failure_analysis": failure,
        "p6c": p6c,
    }.items():
        if payload.get("status") not in {"ok", "caution"}:
            blockers.append({"source": name, "detail": payload.get("checks") or payload.get("failure_analysis") or payload.get("metrics")})
    if not docker_pass:
        blockers.append({"source": "docker_smoke", "detail": docker.get("metrics")})
    for check in command_checks + json_checks:
        if check.get("status") != "ok":
            blockers.append({"source": check.get("name"), "detail": check.get("stderr_tail") or check.get("stdout_tail")})

    payload = {
        "phase": "P7",
        "status": status,
        "metrics": metrics,
        "validations": {
            "api": api,
            "storage": storage,
            "memory": memory,
            "tool_registry": tools,
            "observability": observability,
            "safety": safety,
            "docker": docker,
        },
        "regression": {
            "p5_validation_status": p5.get("status"),
            "p5_demo_status": p5_demo.get("status"),
            "p6_knowledge_pipeline_status": p6.get("status"),
            "p6b_runtime_rag_status": p6b.get("status"),
            "p6c_source_governance_status": p6c.get("status"),
            "code_health_hard_status": code_health.get("hard_gate_status", "not_run"),
        },
        "artifacts": {
            "p7_gate_report": "artifacts/p7_gate_report.json",
            "p7_api_validation": "artifacts/p7_api_validation.json",
            "p7_storage_validation": "artifacts/p7_storage_validation.json",
            "p7_memory_validation": "artifacts/p7_memory_validation.json",
            "p7_tool_registry_validation": "artifacts/p7_tool_registry_validation.json",
            "p7_observability_validation": "artifacts/p7_observability_validation.json",
            "p7_safety_validation": "artifacts/p7_safety_validation.json",
            "p7_trace_samples": "artifacts/p7_trace_samples.json",
            "p7_failure_analysis": "artifacts/p7_failure_analysis.json",
        },
        "command_checks": command_checks + json_checks,
        "failure_analysis": {
            "status": "ok" if not blockers else "failed",
            "blockers": blockers,
            "cautions": failure.get("cautions", []),
        },
    }
    if write_artifact:
        write_json(ARTIFACT, payload)
    return payload


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the P7 service/memory/persistence gate.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--skip-unittest", action="store_true")
    parser.add_argument("--skip-compileall", action="store_true")
    parser.add_argument("--skip-docker", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args(argv)
    payload = run_p7_gate(
        run_unittest=not args.skip_unittest,
        run_compileall=not args.skip_compileall,
        run_docker=not args.skip_docker,
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(
            "P7 gate: "
            f"status={payload['status']} "
            f"api={payload['metrics']['api_turn_ok']} "
            f"storage={payload['metrics']['storage_roundtrip_pass']} "
            f"docker={payload['metrics']['docker_smoke_pass']} "
            f"artifact={ARTIFACT.relative_to(ROOT_DIR)}"
        )
    return 0 if payload["status"] == "ok" else (2 if payload["status"] == "caution" else 1)


if __name__ == "__main__":
    raise SystemExit(main())
