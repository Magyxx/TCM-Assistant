from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.api.redaction import redact_secrets
from app.api.runtime_config import reset_runtime_config_cache


SECRET_MARKERS = ("OPENAI_API_KEY", "sk-")


def _check(name: str, ok: bool, detail: str = "") -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def _contains_any(payload: Any, terms: list[str]) -> list[str]:
    text = json.dumps(payload, ensure_ascii=False).lower()
    return [term for term in terms if term.lower() in text]


def _load_case(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _report_snapshot_count(db_path: Path, session_id: str) -> int:
    if not db_path.exists() or not session_id:
        return 0
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM reports WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def replay_case(case_path: Path, db_path: Path) -> dict[str, Any]:
    os.environ["TCM_API_DB_PATH"] = str(db_path)
    reset_runtime_config_cache()

    from fastapi.testclient import TestClient

    from app.api.main import app
    from app.api.session_runtime import clear_session_cache, clear_sessions

    case = _load_case(case_path)
    expect = case.get("expect") or {}
    turns = list(case.get("turns") or [])

    clear_sessions()
    client = TestClient(app)
    checks: list[dict[str, Any]] = []

    session_response = client.post(
        "/sessions",
        json={"extractor_mode": "fake", "rag_enabled": True},
    )
    session_ok = session_response.status_code == 200
    session = session_response.json() if session_ok else {}
    session_id = str(session.get("session_id") or "")
    checks.append(_check("create_session", session_ok and bool(session_id)))

    turn_payloads: list[dict[str, Any]] = []
    for index, turn_text in enumerate(turns, start=1):
        response = client.post(
            f"/sessions/{session_id}/turn",
            json={"user_input": turn_text},
        )
        payload = response.json()
        turn_payloads.append(payload)
        checks.append(
            _check(
                f"turn_{index}",
                response.status_code == 200 and payload.get("turn_count") == index,
                f"status={response.status_code} turn_count={payload.get('turn_count')!r}",
            )
        )

    clear_session_cache()
    state_response = client.get(f"/sessions/{session_id}/state")
    state = state_response.json()
    report_response = client.get(f"/sessions/{session_id}/report")
    report = report_response.json()

    turn_count = int(state.get("turn_count") or 0) if isinstance(state, dict) else 0
    report_available = bool(report.get("ready")) if isinstance(report, dict) else False
    report_snapshot_count = _report_snapshot_count(db_path, session_id)
    min_turns = int(expect.get("min_turns") or 0)
    checks.append(
        _check(
            "min_turns",
            turn_count >= min_turns,
            f"turn_count={turn_count} min_turns={min_turns}",
        )
    )
    if "report_available" in expect:
        checks.append(
            _check(
                "report_available",
                report_available is bool(expect["report_available"]),
                f"report_available={report_available}",
            )
        )
    if report_available or expect.get("report_snapshot_generated"):
        checks.append(
            _check(
                "report_snapshot_generated",
                report_snapshot_count >= 1,
                f"report_snapshot_count={report_snapshot_count}",
            )
        )

    must_not_contain = list(expect.get("must_not_contain") or [])
    forbidden_terms = _contains_any(
        {
            "session": session,
            "turns": turn_payloads,
            "state": state,
            "report": report,
        },
        must_not_contain,
    )
    checks.append(
        _check(
            "must_not_contain",
            not forbidden_terms,
            f"forbidden_terms={forbidden_terms}",
        )
    )

    secret_terms = _contains_any(
        {
            "session": session,
            "turns": turn_payloads,
            "state": state,
            "report": report,
        },
        list(SECRET_MARKERS),
    )
    checks.append(
        _check(
            "secret_redaction",
            not secret_terms,
            f"markers={secret_terms}",
        )
    )

    status = "ok" if all(check["ok"] for check in checks) else "failed"
    result = {
        "phase": "P1.4",
        "case_id": case.get("case_id"),
        "status": status,
        "checks": checks,
        "session_id": session_id,
        "turn_count": turn_count,
        "report_available": report_available,
        "report_snapshot_count": report_snapshot_count,
        "must_not_contain_passed": not forbidden_terms,
    }
    return redact_secrets(result)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay an API consultation case locally.")
    parser.add_argument("case_path", help="Path to a replay case JSON file.")
    parser.add_argument("--db", help="SQLite DB path. Defaults to a temporary DB.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--output", help="Optional path to write replay result JSON.")
    args = parser.parse_args()

    previous_db_path = os.environ.get("TCM_API_DB_PATH")
    try:
        if args.db:
            result = replay_case(Path(args.case_path), Path(args.db))
        else:
            with tempfile.TemporaryDirectory() as temp_dir:
                result = replay_case(
                    Path(args.case_path),
                    Path(temp_dir) / "replay.sqlite3",
                )

        if args.output:
            _write_json(Path(args.output), result)
        if args.json or not args.output:
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(0 if result["status"] == "ok" else 1)
    finally:
        if previous_db_path is None:
            os.environ.pop("TCM_API_DB_PATH", None)
        else:
            os.environ["TCM_API_DB_PATH"] = previous_db_path
        reset_runtime_config_cache()


if __name__ == "__main__":
    main()
