from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient


def make_p10_client(tmp_path: Path, monkeypatch: Any) -> tuple[TestClient, dict[str, Path]]:
    paths = {
        "session_db": tmp_path / "p10_sessions.sqlite3",
        "api_log": tmp_path / "api_events.jsonl",
        "legacy_db": tmp_path / "legacy_api.sqlite3",
        "p7_db": tmp_path / "p7.sqlite3",
    }
    monkeypatch.setenv("EXTRACTOR_BACKEND", "fake")
    monkeypatch.setenv("ENABLE_REAL_LLM", "false")
    monkeypatch.setenv("SESSION_STORE_BACKEND", "sqlite")
    monkeypatch.setenv("SESSION_SQLITE_PATH", str(paths["session_db"]))
    monkeypatch.setenv("API_LOG_PATH", str(paths["api_log"]))
    monkeypatch.setenv("TCM_API_DB_PATH", str(paths["legacy_db"]))
    monkeypatch.setenv("TCM_SQLITE_PATH", str(paths["p7_db"]))

    from app.api.deps import set_consultation_service_override
    from app.api.main import app
    from app.api.session_runtime import clear_sessions
    from app.services.consultation_service import ConsultationService

    clear_sessions()
    set_consultation_service_override(
        ConsultationService(sqlite_path=paths["session_db"], api_log_path=paths["api_log"])
    )
    return TestClient(app, raise_server_exceptions=False), paths


def create_session(client: TestClient) -> str:
    response = client.post("/sessions", json={"backend": "fake", "metadata": {"test": "p10"}})
    assert response.status_code == 200, response.text
    session_id = response.json()["session_id"]
    assert session_id
    return session_id
