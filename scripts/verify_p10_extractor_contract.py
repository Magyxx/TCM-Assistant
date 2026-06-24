from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from p7_common import check, json_safe, status_from_checks, write_json
except ImportError:  # pragma: no cover
    from scripts.p7_common import check, json_safe, status_from_checks, write_json

from app.extractors.openai_compatible_client import OpenAICompatibleChatClient
from app.extractors.result import ExtractorResult
from app.extractors.router import get_extractor_backend
from app.graph.consultation_graph import run_consultation_graph
from app.memory.merge_policy import merge_fact
from app.memory.models import ConsultationMemory, MemoryFact
from app.schemas.report_schemas import RunState, TurnOutput
from app.storage.models import utc_now


DEFAULT_OUTPUT = ROOT_DIR / "artifacts" / "p10_extractor_contract_validation.json"


def _git_value(*args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except Exception:
        return "unknown"
    return completed.stdout.strip() if completed.returncode == 0 else "unknown"


def _git_lines(*args: str) -> list[str]:
    value = _git_value(*args)
    if value == "unknown":
        return []
    return [line.strip() for line in value.splitlines() if line.strip()]


def _backend_summary(result: ExtractorResult) -> dict[str, Any]:
    status = result.status
    return {
        "status": status,
        "schema_pass": result.schema_pass,
        "raw_json_valid": result.raw_json_valid,
        "fallback_used": result.fallback_used,
        "skip_reason": result.skip_reason,
        "latency_ms": result.latency_ms,
        "backend": result.backend,
        "model": result.model,
        "error_type": result.metadata.get("error_type"),
        "schema_guard": result.metadata.get("schema_guard"),
        "validated_output_schema_guard": result.metadata.get("validated_output_schema_guard"),
    }


def run_backend_checks() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    os.environ.setdefault("ENABLE_REAL_LLM", "false")
    os.environ.setdefault("LOCAL_LLM_TIMEOUT_SECONDS", "0.5")

    summaries: dict[str, Any] = {}
    checks: list[dict[str, Any]] = []
    for name in ["fake", "fallback", "openai_compatible", "local_lora"]:
        result = get_extractor_backend(name).extract("stomach discomfort for two days", state=RunState())
        summaries[name] = _backend_summary(result)
        expected = "passed" if name in {"fake", "fallback"} else {"passed", "skipped"}
        ok = result.status == expected if isinstance(expected, str) else result.status in expected
        checks.append(
            check(
                f"{name}_backend_contract",
                ok and ("fallback_used" in result.metadata) and ("raw_llm_json_valid" in result.metadata),
                status=result.status,
                skip_reason=result.skip_reason,
                metadata=result.metadata,
            )
        )

    mock_payload = json.dumps(
        {
            "chief_complaint": "stomach discomfort",
            "duration": "two days",
            "symptoms": [],
            "symptoms_status": "none",
            "risk_flags": [],
            "risk_flags_status": "none",
            "summary": "mock local_lora extraction",
        }
    )

    original = OpenAICompatibleChatClient.create_chat_completion

    def mock_completion(self, messages):
        return {"choices": [{"message": {"content": mock_payload}}]}

    OpenAICompatibleChatClient.create_chat_completion = mock_completion
    try:
        mock_result = get_extractor_backend("local_lora").extract("stomach discomfort for two days", state=RunState())
    finally:
        OpenAICompatibleChatClient.create_chat_completion = original
    summaries["local_lora_mock"] = _backend_summary(mock_result)
    checks.append(
        check(
            "local_lora_mock_contract",
            mock_result.status == "passed"
            and mock_result.turn_output is not None
            and mock_result.metadata.get("schema_guard") == "passed",
            metadata=mock_result.metadata,
        )
    )
    return summaries, checks


class BadContractBackend:
    mode = "bad_contract"

    def extract(self, user_input: str, *, state=None, memory=None, config=None, session_id=None, turn_id=None):
        return ExtractorResult.schema_failure(
            mode=self.mode,
            raw_output="not json",
            error="json_parse_failed",
            metadata={"error_type": "json_invalid"},
        )

    def extract_turn(self, user_input: str, state=None):
        return TurnOutput(summary="bad")


def run_schema_guard_check() -> dict[str, Any]:
    result = BadContractBackend().extract("bad", state=RunState())
    graph_state = run_consultation_graph(
        RunState(),
        "stomach discomfort for two days",
        use_langgraph=False,
        extractor_mode="bad_contract",
        rag_enabled=False,
    )
    ok = result.schema_pass is False and graph_state["schema_valid"] is False and graph_state["memory"].facts == {}
    return check(
        "invalid_output_blocked_from_memory",
        ok,
        result=result.model_dump(),
        graph_schema_valid=graph_state["schema_valid"],
        fact_count=len(graph_state["memory"].facts),
    )


def run_graph_integration_check() -> tuple[dict[str, Any], dict[str, Any]]:
    graph_state = run_consultation_graph(
        RunState(),
        "stomach discomfort for two days, no chest pain",
        use_langgraph=False,
        extractor_mode="fake",
        rag_enabled=False,
    )
    node_order = [event["node"] for event in graph_state["audit_events"] if "node" in event]
    run_state = graph_state["run_state"]
    graph_meta = run_state.metadata.get("p8_graph", {})
    payload = {
        "extract_turn_uses_router": graph_meta.get("extract_turn_uses_router") is True,
        "validate_turn_before_memory_update": node_order.index("validate_turn") < node_order.index("memory_update"),
        "memory_manager_invoked": graph_meta.get("memory_update_used") is True
        and any(event.action == "validate_turn_output" for event in graph_state["memory"].audit_events),
        "run_state_export": "p8_memory" in run_state.metadata,
        "audit_events": bool(graph_state["audit_events"]),
        "node_order": node_order,
    }
    return payload, check("graph_contract_integration", all(value is True for key, value in payload.items() if key != "node_order"), **payload)


def run_safety_checks() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    sticky_state = RunState(
        chief_complaint="chest tightness",
        duration="one day",
        risk_flags_status="present",
        risk_flags=["dyspnea"],
        triggered_rule_ids=["P0_RISK_DYSPNEA"],
    )
    sticky_graph = run_consultation_graph(
        sticky_state,
        "stomach discomfort for two days, no chest pain",
        use_langgraph=False,
        extractor_mode="fake",
        rag_enabled=False,
    )
    llm_blocked = sticky_graph["run_state"].risk_flags_status == "present" and any(
        event.reason == "llm_candidate_cannot_write_risk_authority"
        for event in sticky_graph["memory"].audit_events
    )

    original = OpenAICompatibleChatClient.create_chat_completion

    def clear_risk_mock(self, messages):
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "chief_complaint": "stomach discomfort",
                                "duration": "two days",
                                "risk_flags": [],
                                "risk_flags_status": "none",
                                "summary": "incorrectly clear risk",
                            }
                        )
                    }
                }
            ]
        }

    OpenAICompatibleChatClient.create_chat_completion = clear_risk_mock
    try:
        lora_graph = run_consultation_graph(
            RunState(),
            "chest pain with breathing difficulty",
            use_langgraph=False,
            extractor_mode="local_lora",
            rag_enabled=False,
        )
    finally:
        OpenAICompatibleChatClient.create_chat_completion = original
    local_lora_blocked = lora_graph["run_state"].risk_flags_status == "present"

    memory = ConsultationMemory()
    memory, rag_event = merge_fact(
        memory,
        MemoryFact(
            field_name="chief_complaint",
            value="retrieved evidence should not overwrite",
            source_turn_id="rag1",
            raw_text="retrieved evidence",
            extractor_mode="bm25",
            confidence=1.0,
            source_kind="rag_evidence",
        ),
    )
    rag_blocked = not rag_event.applied and rag_event.reason == "rag_evidence_forbidden_for_core_field"
    diagnosis_violation = bool(sticky_graph.get("safety_issues"))

    payload = {
        "llm_risk_overwrite_blocked": llm_blocked,
        "local_lora_risk_overwrite_blocked": local_lora_blocked,
        "high_risk_present_sticky": sticky_graph["run_state"].risk_flags_status == "present",
        "rag_core_field_overwrite_blocked": rag_blocked,
        "diagnosis_prescription_violation": diagnosis_violation,
    }
    checks = [
        check("llm_risk_overwrite_blocked", llm_blocked),
        check("local_lora_risk_overwrite_blocked", local_lora_blocked),
        check("high_risk_present_sticky", payload["high_risk_present_sticky"]),
        check("rag_core_field_overwrite_blocked", rag_blocked, event=rag_event.model_dump()),
        check("diagnosis_prescription_violation_absent", not diagnosis_violation),
    ]
    return payload, checks


def run_lora_artifact_check() -> tuple[dict[str, Any], dict[str, Any]]:
    tracked = _git_lines("ls-files")
    weight_pattern = re.compile(r"(adapter|checkpoint|lora|model).*\.(bin|safetensors|pt|pth|ckpt)$", re.I)
    tracked_weights = [path for path in tracked if weight_pattern.search(path)]
    payload = {
        "model_weights_committed": any(path.endswith((".bin", ".safetensors", ".pt", ".pth", ".ckpt")) for path in tracked_weights),
        "adapter_committed": any("adapter" in path.lower() for path in tracked_weights),
        "checkpoint_committed": any("checkpoint" in path.lower() or path.lower().endswith(".ckpt") for path in tracked_weights),
        "tracked_weight_paths": tracked_weights,
    }
    return payload, check(
        "lora_artifacts_not_committed",
        not payload["model_weights_committed"] and not payload["adapter_committed"] and not payload["checkpoint_committed"],
        **payload,
    )


def build_payload() -> dict[str, Any]:
    backends, backend_checks = run_backend_checks()
    schema_check = run_schema_guard_check()
    graph_integration, graph_check = run_graph_integration_check()
    safety, safety_checks = run_safety_checks()
    lora_artifacts, lora_check = run_lora_artifact_check()
    checks = [*backend_checks, schema_check, graph_check, *safety_checks, lora_check]
    return {
        "stage": "P10-M4A_EXTRACTOR_CONTRACT_RECONCILIATION",
        "status": status_from_checks(checks),
        "generated_at": utc_now(),
        "branch": _git_value("branch", "--show-current"),
        "commit": _git_value("rev-parse", "HEAD"),
        "backends": backends,
        "graph_integration": graph_integration,
        "schema_guard": {
            "raw_json_valid_recorded": all("raw_json_valid" in item for item in backends.values()),
            "schema_pass_recorded": all("schema_pass" in item for item in backends.values()),
            "fallback_used_recorded": all("fallback_used" in item for item in backends.values()),
            "skip_reason_recorded": all("skip_reason" in item for item in backends.values()),
            "invalid_output_blocked_from_memory": schema_check["ok"],
        },
        "safety": safety,
        "lora_artifacts": lora_artifacts,
        "checks": checks,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run P10-M4A extractor contract reconciliation validation.")
    parser.add_argument("--json", action="store_true", help="Print validation JSON.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT.relative_to(ROOT_DIR)), help="Artifact path.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args(argv)
    payload = build_payload()
    output = ROOT_DIR / args.output
    write_json(output, payload)
    if args.json:
        print(json.dumps(json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"P10 extractor contract validation: status={payload['status']} artifact={output.relative_to(ROOT_DIR)}")
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
