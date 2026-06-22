from __future__ import annotations

from tests.p10_api_helpers import create_session, make_p10_client


def test_p10_session_turn_runs_graph(tmp_path, monkeypatch) -> None:
    client, _paths = make_p10_client(tmp_path, monkeypatch)
    session_id = create_session(client)

    response = client.post(
        f"/sessions/{session_id}/turn",
        json={"user_input": "胃胀一周，没有发热，也不胸痛", "extractor_backend": "fake"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["session_id"] == session_id
    assert data["turn_id"] == "turn-1"
    assert data["trace_id"]
    assert data["graph_runtime"] in {"langgraph", "sequential_fallback"}
    assert data["risk_status"] == "none"
    assert "P0_RISK_CHEST_PAIN" not in data["risk_rule_ids"]
    assert data["retrieved_evidence_count"] >= 0


def test_p10_shortcut_turn_creates_session(tmp_path, monkeypatch) -> None:
    client, _paths = make_p10_client(tmp_path, monkeypatch)

    response = client.post("/turn", json={"user_input": "胃胀一周", "extractor_backend": "fake"})

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["session_id"]
    assert data["turn_id"] == "turn-1"


def test_p10_multiturn_keeps_chief_complaint_and_duration(tmp_path, monkeypatch) -> None:
    client, _paths = make_p10_client(tmp_path, monkeypatch)
    session_id = create_session(client)

    for text in ["胃胀", "一周", "没有其他症状", "睡眠一般，食欲一般，大便正常，小便正常，没有胸痛"]:
        response = client.post(
            f"/sessions/{session_id}/turn",
            json={"user_input": text, "extractor_backend": "fake"},
        )
        assert response.status_code == 200, response.text

    state = client.get(f"/sessions/{session_id}/state").json()["state"]
    assert state["chief_complaint"] == "胃胀"
    assert state["duration"] == "一周"


def test_p10_high_risk_stays_sticky_after_improvement(tmp_path, monkeypatch) -> None:
    client, _paths = make_p10_client(tmp_path, monkeypatch)
    session_id = create_session(client)

    first = client.post(
        f"/sessions/{session_id}/turn",
        json={"user_input": "胸痛伴呼吸困难", "extractor_backend": "fake"},
    )
    assert first.status_code == 200, first.text
    assert first.json()["risk_status"] == "present"

    second = client.post(
        f"/sessions/{session_id}/turn",
        json={"user_input": "现在好点了", "extractor_backend": "fake"},
    )
    assert second.status_code == 200, second.text
    assert second.json()["risk_status"] == "present"


def test_p10_answered_fields_are_not_repeatedly_asked(tmp_path, monkeypatch) -> None:
    client, _paths = make_p10_client(tmp_path, monkeypatch)
    session_id = create_session(client)

    for text in ["胃胀", "一周", "大便正常，小便正常", "睡眠一般，食欲一般，没有发热"]:
        response = client.post(
            f"/sessions/{session_id}/turn",
            json={"user_input": text, "extractor_backend": "fake"},
        )
        assert response.status_code == 200, response.text

    replay = client.post(f"/sessions/{session_id}/replay", json={"allow_write": False}).json()
    asked = [
        item["payload"].get("metadata", {}).get("field")
        for item in replay["graph_events"]
        if item.get("event_type") == "graph_event" and item.get("payload", {}).get("node") == "ask_followup"
    ]
    asked = [field for field in asked if field]
    assert len(asked) == len(set(asked))
