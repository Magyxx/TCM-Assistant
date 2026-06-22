from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.agentic.workflow_adapter import run_p4_workflow
from app.api.sqlite_store import STORE_SCHEMA_STAGE, STORE_SCHEMA_VERSION, STORE_TABLES
from app.api.versioning import API_CONTRACT_STATUS, API_VERSION
from app.memory.consultation_memory import ConsultationMemoryManager
from app.rag.evidence_boundary import build_evidence_pack, core_state_snapshot
from app.schemas.report_schemas import FinalReport, RunState
from app.tools.internal_registry import build_default_registry
from scripts.check_api_contract import build_api_contract_check_payload
from scripts.gate_utils import redact_preserving_schema as _redact_preserving_schema
from scripts.run_p1_gate import run_command_check


PHASE = "P4.5"
DEFAULT_ARTIFACT_PATH = Path("artifacts") / "p4_gate_result.json"
DEFAULT_RC_ARTIFACT_PATH = Path("artifacts") / "p4_5_gate.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


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


def check_p3_5_baseline() -> dict[str, Any]:
    payload = _load_json_file(ROOT_DIR / "artifacts" / "p3_5_rc_gate.json")
    ok = (
        payload.get("status") == "ok"
        and payload.get("current_gate_phase") == "P3.5"
        and payload.get("recommend_next") == "P4.0"
        and payload.get("api_contract_status") == "frozen"
        and payload.get("breaking_change_detected") is False
        and payload.get("diagnosis_system") is False
        and payload.get("boundary_violations") == []
    )
    return _check(
        "p3_5_baseline_artifact",
        ok,
        f"status={payload.get('status')!r} checks={payload.get('checks_passed')}/{payload.get('checks_total')}",
    )


def check_api_contract() -> dict[str, Any]:
    payload = build_api_contract_check_payload(snapshot_output=None)
    ok = (
        payload.get("status") == "ok"
        and payload.get("api_response_body_changed") is False
        and payload.get("sqlite_schema_changed") is False
        and payload.get("contract_changed") is False
    )
    return _check(
        "api_contract_frozen",
        ok,
        f"status={payload.get('status')!r} checks={payload.get('checks_passed')}/{payload.get('checks_total')}",
    )


def check_sqlite_schema() -> dict[str, Any]:
    ok = STORE_SCHEMA_VERSION == 1 and STORE_SCHEMA_STAGE == "P1.3" and set(STORE_TABLES) == {
        "schema_meta",
        "sessions",
        "session_states",
        "turns",
        "reports",
    }
    return _check(
        "sqlite_schema_compatible",
        ok,
        f"schema_version={STORE_SCHEMA_VERSION} schema_stage={STORE_SCHEMA_STAGE}",
    )


def check_workflow_adapter() -> dict[str, Any]:
    output = run_p4_workflow(
        RunState(),
        "我胃胀两天，没有胸痛",
        extractor_mode="fake",
        rag_enabled=False,
        use_langgraph=False,
    )
    state = output.get("run_state")
    metadata = getattr(state, "metadata", {}) if state is not None else {}
    workflow = metadata.get("p4_workflow") if isinstance(metadata, dict) else {}
    boundary = workflow.get("boundary") if isinstance(workflow, dict) else {}
    ok = (
        isinstance(workflow, dict)
        and workflow.get("wrapped_existing_flow") is True
        and boundary.get("api_contract_changed") is False
        and boundary.get("sqlite_schema_changed") is False
        and boundary.get("diagnosis_system") is False
    )
    return _check(
        "p4_1_workflow_adapter",
        ok,
        "adapter wraps existing flow and records non-breaking boundary",
    )


def check_memory_manager() -> dict[str, Any]:
    manager = ConsultationMemoryManager()
    previous = RunState(
        risk_flags_status="present",
        risk_flags=["胸痛"],
        triggered_rule_ids=["P0_RISK_CHEST_PAIN"],
        turn_count=1,
    )
    candidate = RunState(risk_flags_status="none", turn_count=2)
    protected = manager.enforce_high_risk_sticky(previous, candidate)
    snapshot = manager.update(
        previous_state=previous,
        current_state=protected,
        user_input="没有胸痛了",
        trace=[],
    )
    ok = (
        protected.risk_flags_status == "present"
        and snapshot.is_user_profile is False
        and snapshot.l4_long_term_memory.get("contains_raw_patient_pii") is False
        and snapshot.l2_authoritative_state.get("authoritative") is True
    )
    return _check("p4_2_memory_manager", ok, "consultation safety memory preserves high-risk state")


def check_rag_boundary() -> dict[str, Any]:
    state = RunState(chief_complaint="腹泻", duration="两天", risk_flags_status="none")
    before = core_state_snapshot(state)
    pack = build_evidence_pack(state, top_k=2, mode="bm25_only")
    after = core_state_snapshot(state)
    ok = (
        before == after
        and pack.core_state_readonly is True
        and "risk_status" in pack.forbidden_state_writes
        and pack.can_diagnose is False
        and pack.can_prescribe is False
    )
    return _check("p4_3_rag_boundary", ok, f"evidence_count={len(pack.evidence)}")


def check_tool_registry() -> dict[str, Any]:
    registry = build_default_registry()
    definitions = {definition.name: definition for definition in registry.definitions()}
    required = {
        "risk_check_tool",
        "rag_search_tool",
        "report_safety_tool",
        "export_report_tool",
        "eval_case_tool",
    }
    export_result = registry.call("export_report_tool", {"report": {"summary": "ok"}}, approved=False)
    ok = (
        set(definitions) == required
        and all(definition.input_schema and definition.output_schema and definition.audit_log for definition in definitions.values())
        and export_result.allowed is False
        and export_result.blocked_reason == "human_approval_required"
    )
    return _check("p4_4_tool_registry", ok, "default internal tools have schemas, permission metadata, and audit policy")


def check_report_boundary() -> dict[str, Any]:
    from app.api.report_validator import validate_report

    state = RunState(
        chief_complaint="胃胀",
        duration="两天",
        symptoms_status="none",
        risk_flags_status="none",
    )
    report = FinalReport(
        summary="问诊信息整理",
        impression="当前内容仅用于问诊信息整理，不是诊断，也不能替代医生判断。",
        advice=["记录变化，如加重建议线下就医。"],
        triage_level="observe",
        info_complete=True,
        missing_core_fields=[],
        followup_needed=False,
    )
    result = validate_report(report.model_dump(), state.model_dump())
    return _check("report_safety_boundary", bool(result.get("passed")), "report validator preserves safety boundary")


def run_unittest_check() -> dict[str, Any]:
    check, _ = run_command_check(
        "p4_unittest",
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.test_p4_1_workflow_adapter",
            "tests.test_p4_2_memory_manager",
            "tests.test_p4_3_rag_boundary",
            "tests.test_p4_4_tool_registry",
            "tests.test_p4_5_gate",
        ],
        cwd=ROOT_DIR,
        timeout_seconds=240,
    )
    return {
        "name": "p4_unittest",
        "status": check.get("status"),
        "ok": check.get("status") == "ok",
        "detail": f"return_code={check.get('return_code')}",
        "command": check.get("command"),
        "stdout_tail": check.get("stdout_tail"),
        "stderr_tail": check.get("stderr_tail"),
    }


def run_p4_gate(*, run_unittest: bool = True) -> dict[str, Any]:
    checks = [
        check_p3_5_baseline(),
        check_api_contract(),
        check_sqlite_schema(),
        check_workflow_adapter(),
        check_memory_manager(),
        check_rag_boundary(),
        check_tool_registry(),
        check_report_boundary(),
    ]
    if run_unittest:
        checks.append(run_unittest_check())

    failed = [check for check in checks if not check.get("ok")]
    status = "ok" if not failed else "failed"
    return {
        "phase": PHASE,
        "current_gate_phase": PHASE,
        "created_at": _utc_now(),
        "status": status,
        "recommend_next": "P4 release candidate review" if status == "ok" else "hold",
        "checks_total": len(checks),
        "checks_passed": len(checks) - len(failed),
        "checks_failed": len(failed),
        "checks": checks,
        "api_version": API_VERSION,
        "api_contract_status": API_CONTRACT_STATUS,
        "runtime_changes": True,
        "api_response_body_changed": False,
        "sqlite_schema_changed": False,
        "diagnosis_system": False,
        "boundary_violations": [check["name"] for check in failed],
        "p4_stages_completed": ["P4.0", "P4.1", "P4.2", "P4.3", "P4.4", "P4.5"],
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_redact_preserving_schema(payload), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def exit_code_for_result(result: dict[str, Any]) -> int:
    return 0 if result.get("status") == "ok" else 1


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local P4.5 regression and boundary gate.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_ARTIFACT_PATH),
        help="Primary JSON artifact path. Defaults to artifacts/p4_gate_result.json.",
    )
    parser.add_argument(
        "--rc-output",
        default=str(DEFAULT_RC_ARTIFACT_PATH),
        help="P4.5 JSON artifact path. Defaults to artifacts/p4_5_gate.json.",
    )
    parser.add_argument("--skip-unittest", action="store_true", help="Skip P4 unittest command.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = _parse_args(argv)
    result = run_p4_gate(run_unittest=not args.skip_unittest)
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
