from __future__ import annotations

from tests.p10_api_helpers import create_session, make_p10_client


def test_p10m2_rag_api_endpoints(tmp_path, monkeypatch) -> None:
    client, _paths = make_p10_client(tmp_path, monkeypatch)
    health = client.get("/rag/health")
    assert health.status_code == 200, health.text
    assert health.json()["chunks_count"] > 0

    search = client.post("/rag/search", json={"query": "chest pain breathing difficulty red flag", "top_k": 3})
    assert search.status_code == 200, search.text
    assert search.json()["results"]
    assert search.json()["citations"]

    session_id = create_session(client)
    turn = client.post(
        f"/sessions/{session_id}/turn",
        json={"user_input": "stomach bloating for one week, no fever, no chest pain", "extractor_backend": "fake"},
    )
    assert turn.status_code == 200, turn.text
    session_search = client.post(f"/sessions/{session_id}/rag/search", json={"top_k": 3})
    assert session_search.status_code == 200, session_search.text
    assert session_search.json()["session_id"] == session_id
    assert session_search.json()["query"]

