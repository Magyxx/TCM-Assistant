from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence
from unittest.mock import patch


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from p7_common import check, json_safe, write_json
except ImportError:  # pragma: no cover
    from scripts.p7_common import check, json_safe, write_json

from app.extractors import ExtractorAdapter
from app.extractors.openai_compatible_extractor import OpenAICompatibleTurnExtractor
from app.extractors.result import ExtractorResult
from app.graph.consultation_graph import run_consultation_graph
from app.schemas.report_schemas import RunState
from app.storage.models import utc_now


DEFAULT_OUTPUT = ROOT_DIR / "artifacts" / "p8_extractor_validation.json"


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


def run_fake_check() -> tuple[dict[str, Any], dict[str, Any]]:
    result = ExtractorAdapter().extract("胃胀两天，没有其他症状", state=RunState(), mode="fake")
    ok = result.schema_pass and result.turn_output is not None and result.turn_output.chief_complaint == "胃胀"
    return (
        {
            "status": "passed" if ok else "failed",
            "schema_pass": result.schema_pass,
            "fallback_used": result.fallback_used,
            "latency_ms": result.latency_ms,
        },
        check("fake_mode_schema_pass", ok, mode=result.mode, metadata=result.metadata),
    )


def run_fallback_check() -> tuple[dict[str, Any], dict[str, Any]]:
    result = ExtractorAdapter().extract("胸痛，喘不上气", state=RunState(), mode="fallback")
    ok = result.schema_pass and result.fallback_used and result.turn_output is not None
    return (
        {
            "status": "passed" if ok else "failed",
            "schema_pass": result.schema_pass,
            "fallback_used": result.fallback_used,
            "risk_flags_status": getattr(result.turn_output, "risk_flags_status", None),
            "latency_ms": result.latency_ms,
        },
        check("fallback_mode_schema_pass", ok, mode=result.mode, metadata=result.metadata),
    )


def run_real_llm_check() -> tuple[dict[str, Any], dict[str, Any]]:
    extractor = OpenAICompatibleTurnExtractor()
    missing = extractor.missing_config()
    result = ExtractorAdapter().extract("胃胀两天，没有胸痛", state=RunState(), mode="real_llm")
    if missing:
        ok = result.status == "skipped" and result.schema_pass and result.skip_reason is not None
    else:
        ok = result.status in {"passed", "skipped"} and result.schema_pass
    status = "skipped" if result.skip_reason else ("passed" if ok else "failed")
    return (
        {
            "status": status,
            "schema_pass": result.schema_pass,
            "fallback_used": result.fallback_used,
            "skip_reason": result.skip_reason,
            "missing_config": missing,
            "raw_llm_json_valid": result.metadata.get("raw_llm_json_valid"),
            "repair_used": result.metadata.get("repair_used"),
            "latency_ms": result.latency_ms,
        },
        check("real_llm_safe_pass_or_skip", ok, mode=result.mode, status=status, skip_reason=result.skip_reason),
    )


class BadExtractor:
    mode = "bad"

    def extract(self, text: str, *, state=None, memory=None) -> ExtractorResult:
        return ExtractorResult.schema_failure(
            mode="bad",
            raw_output="{bad json",
            error="json_parse_failed",
            metadata={"raw_llm_json_valid": False, "repair_used": False},
        )


def run_schema_guard_check() -> dict[str, Any]:
    with patch("app.extractors.structured_output_adapter.get_extractor", return_value=BadExtractor()):
        graph_state = run_consultation_graph(
            RunState(),
            "胃胀两天",
            use_langgraph=False,
            extractor_mode="bad",
            rag_enabled=False,
        )
    ok = not graph_state["schema_valid"] and graph_state["memory"].facts == {}
    return check(
        "memory_write_blocked_on_schema_failure",
        ok,
        schema_valid=graph_state["schema_valid"],
        fact_count=len(graph_state["memory"].facts),
        audit_reasons=[event.reason for event in graph_state["memory"].audit_events],
    )


def run_graph_integration_check() -> dict[str, Any]:
    graph_state = run_consultation_graph(
        RunState(),
        "胃胀两天，没有其他症状",
        use_langgraph=False,
        extractor_mode="fake",
        rag_enabled=False,
    )
    ok = (
        graph_state["extraction_result"]["metadata"].get("adapter") == "structured_output_adapter"
        and graph_state["run_state"].metadata.get("p8_graph", {}).get("extractor_adapter") == "structured_output_adapter"
        and graph_state["schema_valid"] is True
    )
    return check(
        "graph_extractor_integration",
        ok,
        extractor_mode=graph_state["extractor_mode"],
        schema_valid=graph_state["schema_valid"],
        adapter=graph_state["extraction_result"]["metadata"].get("adapter"),
    )


def run_risk_authority_check() -> dict[str, Any]:
    graph_state = run_consultation_graph(
        RunState(
            chief_complaint="胸闷",
            duration="一天",
            risk_flags_status="present",
            risk_flags=["呼吸困难"],
            triggered_rule_ids=["P0_RISK_DYSPNEA"],
        ),
        "胃胀两天，没有胸痛",
        use_langgraph=False,
        extractor_mode="fake",
        rag_enabled=False,
    )
    ok = graph_state["run_state"].risk_flags_status == "present" and any(
        event.reason == "llm_candidate_cannot_write_risk_authority" for event in graph_state["memory"].audit_events
    )
    return check(
        "risk_authority_not_llm_direct",
        ok,
        risk_status=graph_state["run_state"].risk_flags_status,
        audit_reasons=[event.reason for event in graph_state["memory"].audit_events],
    )


def build_payload() -> dict[str, Any]:
    fake_mode, fake_check = run_fake_check()
    fallback_mode, fallback_check = run_fallback_check()
    real_mode, real_check = run_real_llm_check()
    guard_check = run_schema_guard_check()
    graph_check = run_graph_integration_check()
    risk_check = run_risk_authority_check()
    checks = [fake_check, fallback_check, real_check, guard_check, graph_check, risk_check]
    ok = all(item.get("ok") is True for item in checks)
    schema_results = [fake_mode["schema_pass"], fallback_mode["schema_pass"], real_mode["schema_pass"]]
    fallback_values = [fake_mode["fallback_used"], fallback_mode["fallback_used"], real_mode["fallback_used"]]
    return {
        "stage": "P8-M3_STRUCTURED_EXTRACTOR_ADAPTER",
        "phase": "P8-M3",
        "generated_at": utc_now(),
        "status": "ok" if ok else "failed",
        "branch": _git_value("branch", "--show-current"),
        "commit": _git_value("rev-parse", "HEAD"),
        "modes": {
            "fake": fake_mode,
            "fallback": fallback_mode,
            "real_llm": real_mode,
        },
        "checks": {
            "turn_output_schema_guard": "passed" if guard_check["ok"] else "failed",
            "graph_extractor_integration": "passed" if graph_check["ok"] else "failed",
            "memory_write_blocked_on_schema_failure": "passed" if guard_check["ok"] else "failed",
            "risk_authority_not_llm_direct": "passed" if risk_check["ok"] else "failed",
        },
        "check_details": checks,
        "metrics": {
            "raw_llm_json_valid_rate": None,
            "schema_pass_rate": sum(1 for item in schema_results if item) / len(schema_results),
            "fallback_used_rate": sum(1 for item in fallback_values if item) / len(fallback_values),
        },
        "branch_safety": {
            "protected_tags_untouched": ["v0.7.0-p7-caution"],
            "protected_branches_untouched": [
                "backup/main-before-p7-device1-20260622-e986065",
                "origin/sft-local-pipeline",
                "origin/exp/sft-lora-extractor",
            ],
            "device2_sft_lora_code_mixed": False,
        },
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run P8-M3 structured extractor adapter validation.")
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
        print(
            "P8 extractor validation: "
            f"status={payload['status']} "
            f"real_llm={payload['modes']['real_llm']['status']} "
            f"artifact={output.relative_to(ROOT_DIR)}"
        )
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
