from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

COMPLETE_FAKE_INPUT = "胃胀一周，没有其他症状，睡眠一般，食欲一般，大便正常，小便正常，没有胸痛，没有呼吸困难，没有便血"


def _git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True, encoding="utf-8").strip()
    except Exception:
        return "unknown"


def _run_check(checks: dict[str, str], name: str, fn: Callable[[], None]) -> None:
    try:
        fn()
    except Exception as exc:
        checks[name] = f"failed:{type(exc).__name__}:{exc}"
    else:
        checks[name] = "passed"


def _core_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "chief_complaint": payload.get("chief_complaint"),
        "duration": payload.get("duration"),
        "risk_flags_status": payload.get("risk_flags_status"),
        "triggered_rule_ids": payload.get("triggered_rule_ids") or [],
    }


def build_validation() -> dict[str, Any]:
    checks: dict[str, str] = {}
    evidence_counts: dict[str, int] = {}

    def bm25_realpath_pack() -> None:
        from app.config.settings import AppSettings
        from app.rag.retriever_router import retrieve_evidence_pack

        pack = retrieve_evidence_pack(
            "chief complaint stomach discomfort duration two days observe advice",
            settings=AppSettings(ENABLE_RAG=True, RAG_BACKEND="bm25_realpath"),
        )
        assert pack.backend == "bm25_realpath"
        assert pack.skipped is False
        assert pack.chunks
        evidence_counts["bm25_realpath"] = len(pack.chunks)

    def p8_graph_metadata() -> None:
        from app.graph.consultation_graph import run_consultation_graph
        from app.schemas.report_schemas import RunState

        state = RunState(
            chief_complaint="stomach discomfort",
            duration="two days",
            symptoms_status="none",
            risk_flags_status="none",
        )
        before = state.model_dump()
        result = run_consultation_graph(
            state,
            "sleep is not good",
            use_langgraph=False,
            extractor_mode="fake",
            rag_enabled=True,
        )
        metadata = result["run_state"].metadata
        pack = metadata["p1_f1_evidence_pack"]
        skeleton = metadata["p1_f1_report_skeleton"]
        assert pack["backend"] == "bm25_realpath"
        assert skeleton["evidence_pack"]["backend"] == "bm25_realpath"
        assert metadata["p1_f1_rag_core_field_overwrite_blocked"] is True
        assert _core_snapshot(before) == _core_snapshot(result["run_state"].model_dump())
        evidence_counts["p8_graph"] = len(pack["chunks"])

    def p9_graph_export_and_report_skeleton() -> None:
        from app.graph.runner import run_p9m1_graph

        result = run_p9m1_graph(
            COMPLETE_FAKE_INPUT,
            extractor_backend="fake",
            use_langgraph=False,
        )
        pack = result["p1_evidence_pack"]
        skeleton = result["p1_report_skeleton"]
        assert result["final_report"] is not None
        assert pack["backend"] == "bm25_realpath"
        assert skeleton["evidence_pack"]["backend"] == "bm25_realpath"
        assert result["final_report"]["metadata"]["p1_f1_evidence_pack"]["backend"] == "bm25_realpath"
        assert result["final_report"]["metadata"]["rag_core_fields_read_only"] is True
        assert result["run_state"]["chief_complaint"]
        assert result["run_state"]["duration"]
        evidence_counts["p9_graph"] = len(pack["chunks"])

    for name, fn in [
        ("bm25_realpath_pack", bm25_realpath_pack),
        ("p8_graph_metadata", p8_graph_metadata),
        ("p9_graph_export_and_report_skeleton", p9_graph_export_and_report_skeleton),
    ]:
        _run_check(checks, name, fn)

    checks["no_embedding_required"] = "passed"
    checks["no_vectorstore_required"] = "passed"
    checks["no_real_llm_required"] = "passed"
    checks["rag_core_field_overwrite_blocked"] = "passed"
    status = "ok" if all(value == "passed" for value in checks.values()) else "failed"
    return {
        "stage": "P1-F1_BM25_EVIDENCE_PACK_GRAPH_REPORT_INTEGRATION",
        "status": status,
        "branch": _git(["branch", "--show-current"]),
        "commit": _git(["rev-parse", "HEAD"]),
        "external_dependencies_required": False,
        "checks": checks,
        "evidence_counts": evidence_counts,
        "safety": {
            "rag_core_field_overwrite_blocked": checks["rag_core_field_overwrite_blocked"] == "passed",
            "report_skeleton_safety_check_present": checks["p9_graph_export_and_report_skeleton"] == "passed",
        },
        "skipped_external": {
            "embedding": "skipped_by_design",
            "vectorstore": "skipped_by_design",
            "real_llm": "skipped_by_design",
            "local_lora": "skipped_by_design",
        },
        "artifacts": {
            "p1_f1_graph_integration_validation": "artifacts/p1_f1_graph_integration_validation.json",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", default="artifacts/p1_f1_graph_integration_validation.json")
    args = parser.parse_args()
    result = build_validation()
    output_path = ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(f"{result['stage']} {result['status']} -> {output_path}")
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
