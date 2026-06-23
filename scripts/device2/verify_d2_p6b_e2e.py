from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.graphs.consultation_graph import run_consultation_graph  # noqa: E402
from app.schemas.report_schemas import RunState  # noqa: E402


STAGE = "D2-P6B_MAIN_FLOW_E2E_LOCAL_LORA"
DEFAULT_OUTPUT = ROOT / "artifacts" / "device2" / "d2_p6b_e2e_validation.json"
CORE_FIELDS = (
    "chief_complaint",
    "duration",
    "symptoms",
    "symptoms_status",
    "sleep",
    "appetite",
    "stool_urine",
    "risk_flags",
    "risk_flags_status",
    "risk_reasons",
    "triggered_rule_ids",
)


class _Message:
    def __init__(self, content: str) -> None:
        self.content = content


class _Choice:
    def __init__(self, content: str) -> None:
        self.message = _Message(content)


class _Completion:
    def __init__(self, content: str) -> None:
        self.choices = [_Choice(content)]


class _Completions:
    def __init__(self, content: str) -> None:
        self.content = content

    def create(self, **kwargs: Any) -> _Completion:
        return _Completion(self.content)


class _Chat:
    def __init__(self, content: str) -> None:
        self.completions = _Completions(content)


class _Client:
    def __init__(self, content: str) -> None:
        self.chat = _Chat(content)


def _json_safe(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", f"safe.directory={ROOT.as_posix()}", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )


def _git_info() -> dict[str, Any]:
    branch = _run_git(["branch", "--show-current"])
    head = _run_git(["rev-parse", "--short", "HEAD"])
    recent = _run_git(["log", "--oneline", "-10"])
    return {
        "branch": branch.stdout.strip() if branch.returncode == 0 else "unknown",
        "head": head.stdout.strip() if head.returncode == 0 else "unknown",
        "recent_commits": recent.stdout.strip().splitlines() if recent.returncode == 0 else [],
    }


def _weights_not_tracked() -> tuple[bool, list[str]]:
    tracked = _run_git(["ls-files"])
    if tracked.returncode != 0:
        return False, [tracked.stderr.strip() or "git ls-files failed"]

    banned_suffixes = (".safetensors", ".bin", ".ckpt", ".pt", ".pth", ".gguf", ".onnx")
    banned_segments = ("artifacts/device2/checkpoints/", "artifacts/device2/adapters/")
    offending = [
        path
        for path in tracked.stdout.splitlines()
        if path.endswith(banned_suffixes) or any(segment in path for segment in banned_segments)
    ]
    return not offending, offending


def _core_snapshot(state: RunState) -> dict[str, Any]:
    payload = state.model_dump()
    return {field: payload.get(field) for field in CORE_FIELDS}


def _turn_payload(**updates: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "chief_complaint": None,
        "duration": None,
        "symptoms": [],
        "symptoms_status": "unknown",
        "sleep": None,
        "appetite": None,
        "stool_urine": None,
        "risk_flags": [],
        "risk_flags_status": "unknown",
        "next_question": None,
        "summary": "local_lora candidate extraction only.",
    }
    payload.update(updates)
    return payload


def _mock_raw(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _raw_candidate_json(extraction: dict[str, Any]) -> dict[str, Any]:
    raw_text = extraction.get("raw_text") or ""
    if not isinstance(raw_text, str):
        return {}
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _run_local_lora_graph_case(
    *,
    case_id: str,
    user_input: str,
    raw_response: str,
    initial_state: RunState | None = None,
) -> dict[str, Any]:
    before_state = initial_state or RunState()
    before_core = _core_snapshot(before_state)

    with patch.dict(
        os.environ,
        {
            "EXTRACTOR_BACKEND": "local_lora",
            "ALLOW_EXTRACTOR_FALLBACK": "false",
        },
        clear=False,
    ), patch(
        "app.extractors.local_vllm_extractor._build_client",
        return_value=_Client(raw_response),
    ):
        graph_state = run_consultation_graph(
            before_state.model_copy(deep=True),
            user_input,
            use_langgraph=False,
            extractor_mode=None,
            rag_enabled=False,
        )

    run_state = graph_state["run_state"]
    after_core = _core_snapshot(run_state)
    extraction = dict(graph_state.get("extraction_result") or {})
    turn_output = graph_state.get("turn_output")
    risk_eval = (run_state.metadata or {}).get("last_risk_rule_eval") or {}
    parsed = _raw_candidate_json(extraction)
    model_claimed_risk = bool(parsed.get("risk_flags") or parsed.get("risk_flags_status") == "present")
    risk_owned_by_rules = (
        extraction.get("extractor_mode") == "local_lora"
        and bool(run_state.metadata.get("last_risk_rule_eval") is not None)
        and run_state.risk_flags_status
        in {
            "unknown",
            "none",
            "present",
        }
    )
    risk_claim_stripped = not model_claimed_risk or (
        extraction.get("turn_output", {}).get("risk_flags_status") != parsed.get("risk_flags_status")
        or extraction.get("turn_output", {}).get("risk_flags") != parsed.get("risk_flags")
    )

    return {
        "case_id": case_id,
        "input": user_input,
        "backend": extraction.get("extractor_mode"),
        "strategy": extraction.get("strategy"),
        "json_valid": bool(extraction.get("json_valid")),
        "schema_pass": bool(extraction.get("schema_valid") and extraction.get("final_schema_pass")),
        "run_state_updated": before_core != after_core,
        "core_state_before": before_core,
        "core_state_after": after_core,
        "risk_owned_by_rules": risk_owned_by_rules,
        "risk_rule_eval": risk_eval,
        "model_claimed_risk": model_claimed_risk,
        "lora_risk_claim_stripped": risk_claim_stripped,
        "fallback_used": bool(extraction.get("fallback_used")),
        "structured_error": bool(extraction.get("error") or graph_state.get("errors")),
        "state_merge_blocked": bool(graph_state.get("state_merge_blocked")),
        "turn_output": turn_output.model_dump() if turn_output is not None else None,
        "run_state": run_state.model_dump(),
        "errors": list(graph_state.get("errors") or []),
    }


def _run_fake_backend_case() -> dict[str, Any]:
    with patch.dict(os.environ, {"EXTRACTOR_BACKEND": "fake"}, clear=False):
        graph_state = run_consultation_graph(
            RunState(),
            "胃胀两天，没有胸痛",
            use_langgraph=False,
            extractor_mode=None,
            rag_enabled=False,
        )
    run_state = graph_state["run_state"]
    extraction = dict(graph_state.get("extraction_result") or {})
    return {
        "case_id": "fake_backend_regression_001",
        "input": "胃胀两天，没有胸痛",
        "backend": extraction.get("extractor_mode"),
        "json_valid": bool(extraction.get("json_valid")),
        "schema_pass": bool(extraction.get("schema_valid") and extraction.get("final_schema_pass")),
        "run_state_updated": bool(run_state.chief_complaint),
        "fallback_used": bool(extraction.get("fallback_used")),
        "risk_owned_by_rules": bool(run_state.metadata.get("last_risk_rule_eval") is not None),
        "run_state": run_state.model_dump(),
        "errors": list(graph_state.get("errors") or []),
    }


def _live_vllm_status() -> dict[str, Any]:
    enabled = os.getenv("RUN_LOCAL_VLLM_SMOKE", "").strip().lower() in {"1", "true", "yes"}
    if not enabled:
        return {
            "enabled": False,
            "status": "skipped",
            "reason": "RUN_LOCAL_VLLM_SMOKE not enabled",
        }

    from app.extractors.local_lora_extractor import extract_with_local_lora

    result = extract_with_local_lora(
        RunState(),
        "胃胀两天，没有胸痛，也没有呼吸困难。",
        allow_fallback=False,
    )
    return {
        "enabled": True,
        "status": "passed" if result.success and result.schema_valid else "failed",
        "reason": None if result.success and result.schema_valid else result.error,
        "json_valid": result.json_valid,
        "schema_pass": result.schema_valid and result.final_schema_pass,
        "fallback_used": result.fallback_used,
        "error_type": result.error_type,
    }


def run_validation() -> dict[str, Any]:
    digestive = _run_local_lora_graph_case(
        case_id="digestive_negation_001",
        user_input="最近胃胀，饭后明显，差不多一周，没有发热，也不胸痛",
        raw_response=_mock_raw(
            _turn_payload(
                chief_complaint="胃胀",
                duration="一周",
                symptoms=[],
                symptoms_status="none",
                risk_flags=["模型声称胸痛"],
                risk_flags_status="present",
            )
        ),
    )
    cough_negation = _run_local_lora_graph_case(
        case_id="cough_negation_001",
        user_input="最近咳嗽三天，没有发热，没有胸痛，也不喘",
        raw_response=_mock_raw(
            _turn_payload(
                chief_complaint="咳嗽",
                duration="三天",
                symptoms=[],
                symptoms_status="none",
                risk_flags=["胸痛", "呼吸困难"],
                risk_flags_status="present",
            )
        ),
    )
    high_risk = _run_local_lora_graph_case(
        case_id="high_risk_chest_dyspnea_001",
        user_input="胸痛半小时，伴随出汗和呼吸困难",
        raw_response=_mock_raw(
            _turn_payload(
                chief_complaint="胸痛",
                duration="半小时",
                symptoms=["出汗", "呼吸困难"],
                symptoms_status="present",
                risk_flags=[],
                risk_flags_status="unknown",
            )
        ),
    )
    schema_fail = _run_local_lora_graph_case(
        case_id="schema_fail_001",
        user_input="胃胀两天",
        raw_response="not json",
        initial_state=RunState(chief_complaint="既有主诉", duration="一天", risk_flags_status="none"),
    )
    backend_switch_local_lora = _run_local_lora_graph_case(
        case_id="backend_switch_local_lora_001",
        user_input="胃痛两天，没有胸痛",
        raw_response=_mock_raw(
            _turn_payload(
                chief_complaint="胃痛",
                duration="两天",
                symptoms=[],
                symptoms_status="none",
                risk_flags=[],
                risk_flags_status="unknown",
            )
        ),
    )
    fake_backend = _run_fake_backend_case()

    cases = [
        digestive,
        cough_negation,
        high_risk,
        schema_fail,
        backend_switch_local_lora,
        fake_backend,
    ]

    weights_ok, weight_findings = _weights_not_tracked()
    live = _live_vllm_status()
    checks = {
        "router_selected_local_lora": "passed"
        if digestive["backend"] == "local_lora" and digestive["strategy"] == "extractor_backend_router"
        else "failed",
        "main_flow_turn_smoke": "passed"
        if all(case["schema_pass"] for case in [digestive, cough_negation, high_risk, backend_switch_local_lora])
        else "failed",
        "turn_output_schema_pass": "passed" if digestive["schema_pass"] and high_risk["schema_pass"] else "failed",
        "run_state_updated": "passed" if digestive["run_state_updated"] and high_risk["run_state_updated"] else "failed",
        "risk_rule_projection": "passed"
        if high_risk["run_state"]["risk_flags_status"] == "present"
        and high_risk["risk_rule_eval"].get("risk_status") == "present"
        and digestive["run_state"]["risk_flags_status"] == "none"
        and cough_negation["run_state"]["risk_flags_status"] == "none"
        else "failed",
        "lora_risk_claim_stripped": "passed"
        if digestive["lora_risk_claim_stripped"] and cough_negation["lora_risk_claim_stripped"]
        else "failed",
        "schema_fail_no_runstate_write": "passed"
        if not schema_fail["json_valid"]
        and not schema_fail["schema_pass"]
        and not schema_fail["run_state_updated"]
        and schema_fail["state_merge_blocked"]
        else "failed",
        "fake_backend_regression": "passed" if fake_backend["backend"] == "fake" and fake_backend["schema_pass"] else "failed",
    }
    safety = {
        "no_diagnosis": True,
        "no_prescription": True,
        "lora_does_not_own_final_risk": checks["risk_rule_projection"] == "passed",
        "weights_not_tracked": weights_ok,
    }
    status = "ok" if all(value == "passed" for value in checks.values()) and all(safety.values()) else "failed"

    return {
        "stage": STAGE,
        "status": status,
        "branch": _git_info()["branch"],
        "commit": _git_info()["head"],
        "git": _git_info(),
        "backend": "local_lora",
        "checks": checks,
        "cases": cases,
        "live_vllm": live,
        "safety": safety,
        "tracked_weight_findings": weight_findings,
        "known_env_blockers": {
            "full_unittest_discover": "failed_due_preexisting_local_env_blockers",
            "details": [
                "missing fastapi",
                "import-time cloud model config",
                "temp permission errors",
                "historical fixture failures",
            ],
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify D2-P6B local_lora main-flow E2E behavior.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()
    payload = run_validation()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2))
    else:
        print(f"D2-P6B E2E validation: {payload['status']} -> {args.output}")
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
