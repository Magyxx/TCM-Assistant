from __future__ import annotations

from tests.p10_api_helpers import create_session, make_p10_client


def test_p10_replay_returns_session_state(tmp_path, monkeypatch) -> None:
    client, _paths = make_p10_client(tmp_path, monkeypatch)
    session_id = create_session(client)
    turn = client.post(
        f"/sessions/{session_id}/turn",
        json={"user_input": "胃胀一周，没有发热，也不胸痛", "extractor_backend": "fake"},
    )
    assert turn.status_code == 200, turn.text

    response = client.post(f"/sessions/{session_id}/replay", json={"allow_write": False})

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["session_id"] == session_id
    assert data["replay_status"] == "ok_read_only"
    assert data["final_state"]["chief_complaint"] == "胃胀"
    assert data["graph_events"]
