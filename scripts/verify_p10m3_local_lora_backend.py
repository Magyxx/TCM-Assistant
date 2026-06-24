from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

ARTIFACT_DIR = ROOT_DIR / "artifacts" / "p10m3"
DEFAULT_OUTPUT = ARTIFACT_DIR / "local_lora_backend_validation.json"


class MockClient:
    def __init__(self, content: str) -> None:
        self.content = content

    def create_chat_completion(self, messages):
        return {"choices": [{"message": {"content": self.content}}]}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _git(args: list[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def verify() -> dict[str, Any]:
    from app.extractors.local_lora_extractor import LocalLoRAExtractorBackend
    from app.extractors.router import get_extractor_backend
    from app.graph.runner import run_p9m1_graph
    from app.schemas.report_schemas import RunState

    ok_json = json.dumps(
        {
            "chief_complaint": "胃胀",
            "duration": "一周",
            "symptoms": [],
            "symptoms_status": "none",
            "risk_flags": [],
            "risk_flags_status": "none",
            "summary": "mock local_lora",
        },
        ensure_ascii=False,
    )
    fake_output = get_extractor_backend("fake").extract_turn("胃胀一周，没有发热", RunState())
    fallback_output = get_extractor_backend("fallback").extract_turn("胸痛伴呼吸困难", RunState())
    local_output = LocalLoRAExtractorBackend(client=MockClient(ok_json)).extract_turn("胃胀一周", RunState())
    invalid_output = LocalLoRAExtractorBackend(client=MockClient("not json")).extract_turn("胃胀一周", RunState())
    bad_schema_output = LocalLoRAExtractorBackend(
        client=MockClient(json.dumps({"risk_flags_status": "clear"}, ensure_ascii=False))
    ).extract_turn("胃胀一周", RunState())

    from app.extractors.openai_compatible_client import OpenAICompatibleChatClient

    original = OpenAICompatibleChatClient.create_chat_completion

    def high_risk_mock(self, messages):
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "chief_complaint": "胸痛",
                                "duration": "半天",
                                "risk_flags": [],
                                "risk_flags_status": "none",
                                "summary": "incorrectly clear risk",
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }

    OpenAICompatibleChatClient.create_chat_completion = high_risk_mock
    try:
        high_risk_graph = run_p9m1_graph("胸痛伴呼吸困难半天", extractor_backend="local_lora", use_langgraph=False)
    finally:
        OpenAICompatibleChatClient.create_chat_completion = original

    def negation_mock(self, messages):
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "chief_complaint": "胃胀",
                                "duration": "一周",
                                "symptoms": [],
                                "symptoms_status": "none",
                                "risk_flags": [],
                                "risk_flags_status": "none",
                                "summary": "negation preserved",
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }

    OpenAICompatibleChatClient.create_chat_completion = negation_mock
    try:
        negation_graph = run_p9m1_graph("胃胀一周，没有发热，也不胸痛", extractor_backend="local_lora", use_langgraph=False)
    finally:
        OpenAICompatibleChatClient.create_chat_completion = original

    os.environ.setdefault("LOCAL_LLM_TIMEOUT_SECONDS", "0.5")
    live_output = get_extractor_backend("local_lora").extract_turn("胃胀一周", RunState())
    live_meta = live_output.metadata
    if live_meta.get("fallback_used") and live_meta.get("error_type") in {"connection_error", "timeout", "http_error"}:
        live_smoke = {"status": "skipped", "skip_reason": str(live_meta.get("error_type"))}
    else:
        live_smoke = {
            "status": "passed" if live_meta.get("schema_guard") == "passed" else "failed",
            "skip_reason": "",
        }

    checks = {
        "fake_backend_passed": fake_output.chief_complaint == "胃胀",
        "fallback_backend_passed": fallback_output.risk_flags_status == "present",
        "local_lora_mock_passed": local_output.metadata.get("schema_guard") == "passed",
        "invalid_json_fallback_passed": invalid_output.metadata.get("error_type") == "json_invalid"
        and invalid_output.metadata.get("fallback_used") is True,
        "schema_guard_passed": bad_schema_output.metadata.get("error_type") == "schema_mismatch"
        and bad_schema_output.metadata.get("fallback_used") is True,
        "high_risk_rules_authority_passed": high_risk_graph.get("risk_status") == "present"
        and "P0_RISK_CHEST_PAIN" in high_risk_graph.get("risk_rule_ids", []),
        "negation_regression_passed": negation_graph.get("risk_status") == "none"
        and not negation_graph.get("risk_rule_ids"),
        "live_smoke_non_blocking": live_smoke["status"] in {"passed", "skipped"},
    }
    result = {
        "status": "ok" if all(checks.values()) else "failed",
        "branch": _git(["branch", "--show-current"]),
        "commit": _git(["rev-parse", "--short", "HEAD"]),
        "checks": checks,
        "live_smoke": live_smoke,
        "mock_metadata": local_output.metadata,
        "invalid_json_metadata": invalid_output.metadata,
        "schema_guard_metadata": bad_schema_output.metadata,
        "artifacts": {
            "local_lora_backend_validation": str(DEFAULT_OUTPUT.relative_to(ROOT_DIR)).replace("\\", "/"),
        },
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify P10M3 local_lora backend integration.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Artifact output path.")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    result = verify()
    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT_DIR / output
    _write_json(output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) if args.json else result["status"])
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
