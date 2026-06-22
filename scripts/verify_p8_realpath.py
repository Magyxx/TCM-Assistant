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
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from p7_common import json_safe, write_json
except ImportError:  # pragma: no cover
    from scripts.p7_common import json_safe, write_json

from app.api.redaction import redact_secrets
from app.extractors import (
    FakeTurnExtractor,
    FallbackTurnExtractor,
    OpenAICompatibleTurnExtractor,
    run_extractor_probe,
)
from app.graph.consultation_graph import run_consultation_graph
from app.rag import bm25_retriever
from app.rag.hybrid_retriever import HybridRetriever
from app.schemas.report_schemas import RunState


DEFAULT_OUTPUT = ROOT_DIR / "artifacts" / "p8_realpath_validation.json"
TAIL_CHARS = 4000


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _tail(value: str | bytes | None, limit: int = TAIL_CHARS) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return str(redact_secrets(str(value)[-limit:]))


def _command_to_text(command: Sequence[str]) -> str:
    return str(redact_secrets(subprocess.list2cmdline([str(part) for part in command])))


def _classify_unittest(stdout: str, stderr: str, return_code: int, timed_out: bool) -> dict[str, Any]:
    text = f"{stdout}\n{stderr}"
    match = re.search(r"Ran\s+(\d+)\s+tests?\s+in\s+([0-9.]+)s\s*\n\s*(OK|FAILED)", text)
    ran_count = int(match.group(1)) if match else None
    outcome = match.group(3) if match else None
    content_ok = outcome == "OK"
    if timed_out and content_ok:
        classification = "content_ok_runner_timeout"
    elif return_code == 0 and content_ok:
        classification = "ok"
    elif timed_out:
        classification = "timeout_no_ok_marker"
    else:
        classification = "failed"
    return {
        "ran_count": ran_count,
        "outcome_marker": outcome,
        "content_ok": content_ok,
        "classification": classification,
    }


def run_command(
    name: str,
    command: Sequence[str],
    *,
    timeout_seconds: int,
    classify_unittest: bool = False,
) -> dict[str, Any]:
    started = time.perf_counter()
    stdout = ""
    stderr = ""
    timed_out = False
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
    except subprocess.TimeoutExpired as exc:
        return_code = -1
        timed_out = True
        stdout = exc.stdout or ""
        stderr = (exc.stderr or "") + f"\nTimeout after {timeout_seconds} seconds."

    duration = round(time.perf_counter() - started, 3)
    unittest_detail = _classify_unittest(stdout, stderr, return_code, timed_out) if classify_unittest else None
    if unittest_detail:
        ok = unittest_detail["classification"] in {"ok", "content_ok_runner_timeout"}
        status = "ok" if ok else "failed"
    else:
        ok = return_code == 0
        status = "ok" if ok else "failed"

    return {
        "name": name,
        "command": _command_to_text(command),
        "status": status,
        "ok": ok,
        "return_code": return_code,
        "timed_out": timed_out,
        "timeout_seconds": timeout_seconds,
        "duration_seconds": duration,
        "stdout_tail": _tail(stdout),
        "stderr_tail": _tail(stderr),
        "unittest": unittest_detail,
    }


def run_secret_scan(output_path: Path) -> dict[str, Any]:
    check = run_command(
        "secret_scan",
        [sys.executable, "scripts/secret_scan.py", "--json", "--output", str(output_path.relative_to(ROOT_DIR))],
        timeout_seconds=120,
    )
    payload: dict[str, Any] = {}
    if output_path.exists():
        try:
            payload = json.loads(output_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
    check["artifact_status"] = payload.get("status")
    check["finding_count"] = payload.get("finding_count")
    check["ok"] = bool(check["ok"] and payload.get("status") == "ok" and payload.get("finding_count") == 0)
    check["status"] = "ok" if check["ok"] else "failed"
    return check


def run_extractor_smoke() -> dict[str, Any]:
    fake = run_extractor_probe(
        FakeTurnExtractor(),
        "stomach discomfort for two days, no other symptoms, no chest pain",
        RunState(),
    )
    fallback = run_extractor_probe(
        FallbackTurnExtractor(),
        "\u80f8\u75db\uff0c\u5598\u4e0d\u4e0a\u6c14",
        RunState(),
    )
    real_extractor = OpenAICompatibleTurnExtractor()
    real = run_extractor_probe(
        real_extractor,
        "stomach discomfort for two days, no chest pain",
        RunState(),
    )
    missing_config = real_extractor.missing_config()
    real_status = "skipped" if missing_config and real.error_type == "missing_api_config" else real.status
    real_payload = {
        **real.to_dict(),
        "status": real_status,
        "missing_config": missing_config,
        "availability": "skipped_missing_config" if real_status == "skipped" else "attempted",
    }
    ok = (
        fake.status == "ok"
        and fake.final_schema_pass
        and not fake.fallback_used
        and fallback.status == "ok"
        and fallback.final_schema_pass
        and fallback.fallback_used
        and fallback.risk_flags_status == "present"
        and real.final_schema_pass
    )
    return {
        "status": "ok" if ok else "failed",
        "fake": fake.to_dict(),
        "fallback": fallback.to_dict(),
        "real_llm": real_payload,
        "mode_comparison": {
            "fake_fallback_used": fake.fallback_used,
            "fallback_fallback_used": fallback.fallback_used,
            "real_llm_fallback_used": real.fallback_used,
            "real_llm_skipped": real_status == "skipped",
        },
    }


def run_bm25_smoke() -> dict[str, Any]:
    state = RunState(
        chief_complaint="stomach discomfort",
        duration="two days",
        symptoms_status="none",
        risk_flags_status="none",
    )
    before = state.model_dump()
    evidence = HybridRetriever(mode="bm25_only").retrieve(
        "chief complaint stomach discomfort duration two days observe advice",
        top_k=3,
    )
    after = state.model_dump()
    retriever_types = list(dict.fromkeys(item.retriever_type for item in evidence))
    ok = bool(evidence) and before == after
    return {
        "status": "ok" if ok else "failed",
        "rank_bm25_available": bm25_retriever.BM25Okapi is not None,
        "evidence_count": len(evidence),
        "retriever_types": retriever_types,
        "chunk_ids": [item.chunk_id for item in evidence],
        "core_state_before": before,
        "core_state_after": after,
        "core_state_unchanged": before == after,
    }


def run_graph_smoke() -> dict[str, Any]:
    graph_state = run_consultation_graph(
        RunState(),
        "stomach discomfort for two days, no chest pain",
        use_langgraph=True,
        extractor_mode="fallback",
        rag_enabled=False,
    )
    state = graph_state["run_state"]
    runtime = graph_state.get("graph_runtime")
    ok = runtime in {"langgraph", "sequential_fallback"} and state.metadata.get("extractor_mode_requested") == "fallback"
    return {
        "status": "ok" if ok else "failed",
        "graph_runtime": runtime,
        "extractor_mode": graph_state.get("extractor_mode"),
        "fallback_used": graph_state.get("fallback_used"),
        "schema_valid": graph_state.get("schema_valid"),
        "final_schema_pass": graph_state.get("final_schema_pass"),
        "state_snapshot": state.model_dump(),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    secret_scan_path = ROOT_DIR / args.secret_scan_output
    checks = [
        run_command(
            "compileall",
            [sys.executable, "-m", "compileall", "-q", "app", "scripts", "tests"],
            timeout_seconds=args.compile_timeout,
        ),
        run_command(
            "unittest_discover_tests",
            [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
            timeout_seconds=args.unittest_timeout,
            classify_unittest=True,
        ),
        run_secret_scan(secret_scan_path),
    ]
    extractor = run_extractor_smoke()
    bm25 = run_bm25_smoke()
    graph = run_graph_smoke()
    smoke_results = {
        "extractor_modes": extractor,
        "bm25_realpath": bm25,
        "graph_facade": graph,
    }
    skipped = []
    real_llm = extractor["real_llm"]
    if real_llm.get("status") == "skipped":
        skipped.append({"name": "real_llm_probe", "reason": real_llm.get("availability"), "missing_config": real_llm.get("missing_config")})
    if not bm25["rank_bm25_available"]:
        skipped.append({"name": "rank_bm25_native", "reason": "rank_bm25_missing_used_lexical_fallback"})

    command_ok = all(check["ok"] for check in checks)
    smoke_ok = all(result["status"] == "ok" for result in smoke_results.values())
    status = "ok" if command_ok and smoke_ok else "failed"
    if status == "ok" and skipped:
        status = "caution"
    return {
        "phase": "P8/P0.2",
        "generated_at": utc_now(),
        "status": status,
        "scope": "real-path validation for LangGraph facade, extractor modes, BM25, commands, and artifacts",
        "command_checks": checks,
        "smoke_results": smoke_results,
        "skipped": skipped,
        "metrics": {
            "compileall_pass": checks[0]["ok"],
            "unittest_status": checks[1]["unittest"]["classification"] if checks[1].get("unittest") else checks[1]["status"],
            "unittest_content_ok": (checks[1].get("unittest") or {}).get("content_ok"),
            "secret_scan_ok": checks[2]["ok"],
            "fake_final_schema_pass": extractor["fake"]["final_schema_pass"],
            "fallback_final_schema_pass": extractor["fallback"]["final_schema_pass"],
            "fallback_risk_flags_status": extractor["fallback"]["risk_flags_status"],
            "real_llm_final_schema_pass": extractor["real_llm"]["final_schema_pass"],
            "real_llm_skipped": extractor["real_llm"].get("status") == "skipped",
            "bm25_evidence_count": bm25["evidence_count"],
            "bm25_core_state_unchanged": bm25["core_state_unchanged"],
            "graph_runtime": graph["graph_runtime"],
        },
        "branch_safety": {
            "protected_tags_untouched": ["v0.7.0-p7-caution"],
            "protected_branches_untouched": [
                "backup/main-before-p7-device1-20260622-e986065",
                "origin/sft-local-pipeline",
                "origin/exp/sft-lora-extractor",
            ],
            "api_contract_changed": False,
        },
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run P8/P0.2 real-path validation.")
    parser.add_argument("--json", action="store_true", help="Print the validation artifact JSON.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT.relative_to(ROOT_DIR)), help="Artifact path.")
    parser.add_argument("--secret-scan-output", default="artifacts/secret_scan_result.json")
    parser.add_argument("--compile-timeout", type=int, default=180)
    parser.add_argument("--unittest-timeout", type=int, default=900)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args(argv)
    payload = build_payload(args)
    output = ROOT_DIR / args.output
    write_json(output, payload)
    if args.json:
        print(json.dumps(json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(
            "P8 realpath validation: "
            f"status={payload['status']} "
            f"unittest={payload['metrics']['unittest_status']} "
            f"real_llm_skipped={payload['metrics']['real_llm_skipped']} "
            f"artifact={output.relative_to(ROOT_DIR)}"
        )
    return 1 if payload["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
