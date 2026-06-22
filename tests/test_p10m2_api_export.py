from __future__ import annotations

from pathlib import Path

from tests.p10_api_helpers import create_session, make_p10_client


def test_p10m2_report_export_api_writes_markdown(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("REPORT_EXPORT_DIR", str(tmp_path / "exports"))
    client, _paths = make_p10_client(tmp_path, monkeypatch)
    session_id = create_session(client)

    response = client.post(f"/sessions/{session_id}/report/export", json={"format": "markdown"})

    assert response.status_code == 200, response.text
    path = Path(response.json()["path"])
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[1] / path
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "Safety Disclaimer" in text
    assert "Evidence Citations" in text

