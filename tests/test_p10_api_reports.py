from __future__ import annotations

from tests.p10_api_helpers import create_session, make_p10_client


def test_p10_report_not_available_returns_200(tmp_path, monkeypatch) -> None:
    client, _paths = make_p10_client(tmp_path, monkeypatch)
    session_id = create_session(client)

    response = client.get(f"/sessions/{session_id}/report")

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["session_id"] == session_id
    assert data["report_available"] is False
    assert data["missing_core_fields"]
    assert data["safety_disclaimer"]


def test_p10_report_available_after_complete_turns(tmp_path, monkeypatch) -> None:
    client, _paths = make_p10_client(tmp_path, monkeypatch)
    session_id = create_session(client)
    for text in [
        "胃胀一周",
        "没有其他症状",
        "睡眠一般，食欲一般，大便正常，小便正常，没有发热，也不胸痛",
    ]:
        response = client.post(
            f"/sessions/{session_id}/turn",
            json={"user_input": text, "extractor_backend": "fake"},
        )
        assert response.status_code == 200, response.text

    report = client.get(f"/sessions/{session_id}/report")

    assert report.status_code == 200, report.text
    data = report.json()
    assert data["report_available"] is True
    assert data["final_report"]
    assert data["safety_disclaimer"]
