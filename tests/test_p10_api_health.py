from __future__ import annotations

from tests.p10_api_helpers import make_p10_client


def test_p10_health_extended_returns_service_status(tmp_path, monkeypatch) -> None:
    client, paths = make_p10_client(tmp_path, monkeypatch)

    response = client.get("/health?extended=true")

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "ok"
    assert data["api_version"] == "p10m1"
    assert data["graph_available"] is True
    assert data["session_store_backend"] == "sqlite"
    assert data["sqlite_path"] == str(paths["session_db"])
    assert data["extractor_backend"] == "fake"
