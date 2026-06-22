from __future__ import annotations

from tests.p10_api_helpers import create_session, make_p10_client


def test_p10_create_and_get_session(tmp_path, monkeypatch) -> None:
    client, _paths = make_p10_client(tmp_path, monkeypatch)

    session_id = create_session(client)
    detail = client.get(f"/sessions/{session_id}")

    assert detail.status_code == 200, detail.text
    data = detail.json()
    assert data["session_id"] == session_id
    assert data["store_backend"] == "sqlite"
    assert data["has_final_report"] is False


def test_p10_list_turns_after_turn(tmp_path, monkeypatch) -> None:
    client, _paths = make_p10_client(tmp_path, monkeypatch)
    session_id = create_session(client)

    turn = client.post(
        f"/sessions/{session_id}/turn",
        json={"user_input": "胃胀一周，没有发热，也不胸痛", "extractor_backend": "fake"},
    )
    assert turn.status_code == 200, turn.text

    response = client.get(f"/sessions/{session_id}/turns")
    assert response.status_code == 200, response.text
    turns = response.json()["turns"]
    assert any(item["role"] == "user" for item in turns)
    assert any(item["role"] == "assistant" for item in turns)
