from __future__ import annotations

import sys
from typing import Any

try:
    from p7_common import ROOT_DIR, check, status_from_checks, write_json
except ImportError:  # pragma: no cover - package import path
    from scripts.p7_common import ROOT_DIR, check, status_from_checks, write_json

from app.storage.models import (  # noqa: E402
    AuditLogRecord,
    FinalReportRecord,
    MemorySnapshotRecord,
    RagEvidenceRecord,
    RiskEventRecord,
    RunStateSnapshot,
    StorageSession,
    StorageTurn,
    TraceEventRecord,
)
from app.storage.postgres_store import schema_ready_status  # noqa: E402
from app.storage.sqlite_store import P7_TABLES, P7SQLiteStore  # noqa: E402


ARTIFACT = ROOT_DIR / "artifacts" / "p7_storage_validation.json"


def run_p7_storage_validation(*, write_artifact: bool = True) -> dict[str, Any]:
    store = P7SQLiteStore(ROOT_DIR / ".runtime" / "p7_storage_validation.sqlite3")
    session_id = "p7-storage-session"
    turn_id = "1"
    store.create_session(StorageSession(session_id=session_id, mode="fake", rag_enabled=True))
    store.append_turn_bundle(
        turn=StorageTurn(
            turn_id=turn_id,
            session_id=session_id,
            turn_index=1,
            user_input="胃胀一周，没有胸痛",
            turn_output={"summary": "validated"},
        ),
        run_state=RunStateSnapshot(session_id=session_id, turn_id=turn_id, state={"turn_count": 1}),
        risk_events=[RiskEventRecord(session_id=session_id, turn_id=turn_id, risk_status="none")],
        rag_evidence=[
            RagEvidenceRecord(
                session_id=session_id,
                turn_id=turn_id,
                source_id="synthetic_p6_policy_001",
                chunk_id="chunk-1",
                chunk_hash="sha256:" + "a" * 64,
                index_version="kb.index.v0",
                score=1.0,
                retrieval_mode="p6b_runtime_bm25",
                is_used=False,
                evidence={"source_id": "synthetic_p6_policy_001"},
            )
        ],
        memory_snapshot=MemorySnapshotRecord(session_id=session_id, turn_id=turn_id, snapshot={"l4_privacy_pass": True}),
        trace_event=TraceEventRecord(session_id=session_id, turn_id=turn_id, trace_id="trace-1", event={"trace_id": "trace-1"}),
        audit_logs=[AuditLogRecord(session_id=session_id, turn_id=turn_id, event_type="turn.persisted", payload={"ok": True})],
    )
    store.save_final_report_bundle(
        report=FinalReportRecord(
            session_id=session_id,
            turn_id=turn_id,
            report={"summary": "ok", "advice": []},
            safety_check={"passed": True},
        ),
        evidence_updates=[
            RagEvidenceRecord(
                session_id=session_id,
                turn_id=turn_id,
                source_id="synthetic_p6_policy_001",
                chunk_id="chunk-1",
                chunk_hash="sha256:" + "a" * 64,
                index_version="kb.index.v0",
                score=1.0,
                retrieval_mode="p6b_runtime_bm25",
                is_used=True,
                used_in_report_section="report.metadata",
                evidence={"source_id": "synthetic_p6_policy_001"},
            )
        ],
    )
    bundle = store.fetch_session_bundle(session_id) or {}
    traces = store.fetch_trace_events(session_id)
    evidence = store.fetch_rag_evidence(session_id)
    used = store.fetch_rag_evidence(session_id, used_only=True)
    counts = store.table_counts()
    postgres = schema_ready_status()
    checks = [
        check("storage_tables_present", all(table in counts for table in P7_TABLES)),
        check("storage_roundtrip_pass", bool(bundle.get("session")) and len(bundle.get("turns") or []) >= 1),
        check("storage_trace_pass", len(traces) >= 1),
        check("rag_evidence_persistence_pass", len(evidence) >= 2 and len(used) >= 1),
        check("postgres_schema_ready", postgres.get("schema_ready") is True),
    ]
    payload = {
        "phase": "P7",
        "status": status_from_checks(checks),
        "storage_error_count": 0 if status_from_checks(checks) == "ok" else 1,
        "checks": checks,
        "metrics": {
            "storage_roundtrip_pass": checks[1]["ok"],
            "storage_error_count": 0 if status_from_checks(checks) == "ok" else 1,
            "rag_evidence_persistence_pass": checks[3]["ok"],
            "table_counts": counts,
            "postgres": postgres,
        },
    }
    if write_artifact:
        write_json(ARTIFACT, payload)
    return payload


def main() -> int:
    payload = run_p7_storage_validation()
    print(f"P7 storage validation: status={payload['status']} artifact={ARTIFACT.relative_to(ROOT_DIR)}")
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
