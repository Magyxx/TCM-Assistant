from __future__ import annotations

from typing import Any

try:
    from p7_common import ROOT_DIR, check, status_from_checks, write_json
except ImportError:  # pragma: no cover - package import path
    from scripts.p7_common import ROOT_DIR, check, status_from_checks, write_json

from app.memory.manager import MemoryManager  # noqa: E402
from app.memory.privacy import contains_pii  # noqa: E402
from app.schemas.report_schemas import RunState  # noqa: E402


ARTIFACT = ROOT_DIR / "artifacts" / "p7_memory_validation.json"


def run_p7_memory_validation(*, write_artifact: bool = True) -> dict[str, Any]:
    previous = RunState()
    current = RunState(
        chief_complaint="胃胀",
        duration="一周",
        symptoms_status="none",
        risk_flags_status="none",
        turn_count=1,
    )
    snapshot = MemoryManager().build_snapshot(
        session_id="p7-memory-session",
        turn_id="1",
        turn_index=1,
        previous_state=previous,
        current_state=current,
        user_input="胃胀一周，没有胸痛，手机号13800138000",
    )
    checks = [
        check("memory_l1_pass", len(snapshot.recent_turns) == 1 and "13800138000" in snapshot.recent_turns[0].user_input_preview),
        check("memory_l2_fact_write_pass", any(fact.field_name == "chief_complaint" for fact in snapshot.structured_facts)),
        check("memory_l3_summary_pass", snapshot.case_summary.generated_from_fact_count >= 4),
        check("memory_l4_privacy_pass", snapshot.l4_privacy_pass and not contains_pii([item.model_dump() for item in snapshot.experience_retrieval])),
        check("memory_source_traceability_pass", snapshot.source_traceability_pass),
    ]
    payload = {
        "phase": "P7",
        "status": status_from_checks(checks),
        "checks": checks,
        "metrics": {item["name"]: item["ok"] for item in checks},
        "snapshot": snapshot.model_dump(),
    }
    if write_artifact:
        write_json(ARTIFACT, payload)
    return payload


def main() -> int:
    payload = run_p7_memory_validation()
    print(f"P7 memory validation: status={payload['status']} artifact={ARTIFACT.relative_to(ROOT_DIR)}")
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
