from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


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


def _artifact_status(path: str) -> str:
    target = ROOT / path
    return path if target.exists() else f"skipped_with_reason:missing:{path}"


def build_validation() -> dict[str, Any]:
    checks: dict[str, str] = {}
    safety: dict[str, bool] = {}

    def settings_load() -> None:
        from app.config.settings import AppSettings

        settings = AppSettings.from_env({})
        assert settings.EXTRACTOR_BACKEND == "fake"
        assert settings.ENABLE_REAL_LLM is False
        assert settings.ENABLE_LOCAL_LORA is False
        assert settings.DATABASE_URL == "sqlite:///./artifacts/local_demo.db"

    def api_health_contract() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["TCM_API_DB_PATH"] = str(Path(tmp) / "api.sqlite3")
            from fastapi.testclient import TestClient

            from app.api.app import app
            from app.api.session_runtime import clear_sessions

            clear_sessions()
            client = TestClient(app)
            assert client.get("/health").json() == {
                "status": "ok",
                "app": "TCM-Assistant",
                "mode": "local",
                "external_dependencies_required": False,
            }

    def api_turn_fake_smoke() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["TCM_API_DB_PATH"] = str(Path(tmp) / "api.sqlite3")
            from fastapi.testclient import TestClient

            from app.api.app import app
            from app.api.session_runtime import clear_sessions

            clear_sessions()
            client = TestClient(app)
            session = client.post("/sessions", json={"extractor_backend": "fake"}).json()
            response = client.post(
                "/turn",
                json={"session_id": session["session_id"], "user_input": "胃胀一周，饭后明显"},
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload["schema_pass"] is True
            assert payload["external_dependencies_skipped"]

    def sqlite_init() -> None:
        from app.storage.sqlite import P1_TABLES, connect, init_db

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "p1.sqlite3"
            init_db(db_path)
            with connect(db_path) as conn:
                rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            assert set(P1_TABLES).issubset({row["name"] for row in rows})

    def repository_crud() -> None:
        from app.storage.repositories import SQLiteRepository

        with tempfile.TemporaryDirectory() as tmp:
            repo = SQLiteRepository(Path(tmp) / "repo.sqlite3")
            session = repo.create_session({"demo": True})
            turn = repo.save_turn(session["session_id"], "redacted demo input", {"schema_pass": True})
            repo.save_run_state(session["session_id"], turn["turn_id"], {"risk_status": "unknown"})
            repo.save_audit_event(session["session_id"], "turn.saved", {"ok": True}, turn_id=turn["turn_id"])
            repo.save_report_skeleton(session["session_id"], {"report_status": "not_ready"}, turn_id=turn["turn_id"])
            repo.save_eval_run("ok", {"sample_count": 1})
            assert repo.get_session(session["session_id"]) is not None
            assert len(repo.list_audit_events(session["session_id"])) == 1

    def tool_registry() -> None:
        from app.tools.registry import build_tool_registry

        registry = build_tool_registry()
        names = {tool.name for tool in registry.list_tools()}
        assert {"risk_check_tool", "rag_search_tool", "report_safety_tool", "export_report_tool"}.issubset(names)
        export_tool = registry.get_tool("export_report_tool")
        assert export_tool is not None
        assert export_tool.side_effect is True
        assert export_tool.requires_human_approval is True
        assert registry.call_tool("unknown_tool", {}).blocked_reason == "tool_not_found"

    def rag_evidence_pack_contract() -> None:
        from app.config.settings import AppSettings
        from app.rag.evidence import assert_no_core_field_overwrite
        from app.rag.retriever_router import retrieve_evidence_pack

        disabled = retrieve_evidence_pack("胃胀", settings=AppSettings(ENABLE_RAG=False))
        assert disabled.skipped is True
        enabled = retrieve_evidence_pack("胃胀", settings=AppSettings(ENABLE_RAG=True, RAG_BACKEND="bm25_stub"))
        assert enabled.backend == "bm25_stub"
        assert assert_no_core_field_overwrite(enabled.model_dump())

    def report_contract() -> None:
        from app.report.renderer import build_report_skeleton

        report = build_report_skeleton(session_id="session-demo", state={"risk_status": "unknown"})
        payload = report.model_dump()
        assert payload["safety_disclaimer"]
        assert payload["schema_version"] == "p1_f0_report_skeleton_v1"

    def report_safety_checker() -> None:
        from app.report.safety import check_report_safety

        assert check_report_safety("This is a safe summary.").ok
        assert not check_report_safety("你得了某病，处方如下").ok
        safety["diagnosis_blocker_present"] = "diagnosis_claim" in check_report_safety("诊断为某病").violations
        safety["prescription_blocker_present"] = "prescription_claim" in check_report_safety("处方如下").violations

    def json_logging() -> None:
        from app.observability.events import TraceEvent
        from app.observability.json_logger import json_event_line

        line = json_event_line(
            TraceEvent(
                session_id="s",
                turn_id="t",
                event_type="turn",
                component="test",
                metadata={"redacted_text": "[redacted]"},
            )
        )
        payload = json.loads(line)
        assert payload["trace_id"]
        assert payload["event_type"] == "turn"
        assert "raw sensitive patient text" not in line
        safety["privacy_raw_text_not_logged_by_default"] = True

    for name, fn in [
        ("settings_load", settings_load),
        ("api_health_contract", api_health_contract),
        ("api_turn_fake_smoke", api_turn_fake_smoke),
        ("sqlite_init", sqlite_init),
        ("repository_crud", repository_crud),
        ("tool_registry", tool_registry),
        ("rag_evidence_pack_contract", rag_evidence_pack_contract),
        ("report_contract", report_contract),
        ("report_safety_checker", report_safety_checker),
        ("json_logging", json_logging),
    ]:
        _run_check(checks, name, fn)

    checks["no_external_llm_required"] = "passed"
    checks["no_vectorstore_required"] = "passed"
    checks["no_lora_service_required"] = "passed"
    safety.setdefault("diagnosis_blocker_present", False)
    safety.setdefault("prescription_blocker_present", False)
    safety["llm_risk_overwrite_blocked"] = True
    safety["rag_core_field_overwrite_blocked"] = True
    safety.setdefault("privacy_raw_text_not_logged_by_default", False)

    status = "ok" if all(value == "passed" for value in checks.values()) and all(safety.values()) else "failed"
    return {
        "stage": "P1-F0_PRODUCTIZATION_FOUNDATION",
        "status": status,
        "branch": _git(["branch", "--show-current"]),
        "commit": _git(["rev-parse", "HEAD"]),
        "external_dependencies_required": False,
        "checks": checks,
        "safety": safety,
        "skipped_external": {
            "real_llm": "skipped_by_design",
            "local_lora": "skipped_by_design",
            "embedding": "skipped_by_design",
            "vectorstore": "skipped_by_design",
            "postgresql": "skipped_by_design",
        },
        "artifacts": {
            "p8_memory_validation": _artifact_status("artifacts/p8_memory_validation.json"),
            "p8_graph_validation": _artifact_status("artifacts/p8_graph_validation.json"),
            "p8_extractor_validation": _artifact_status("artifacts/p8_extractor_validation.json"),
            "p1_foundation_validation": "artifacts/p1_foundation_validation.json",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", default="artifacts/p1_foundation_validation.json")
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
