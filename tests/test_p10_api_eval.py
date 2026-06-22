from __future__ import annotations

from tests.p10_api_helpers import make_p10_client


def test_p10_eval_endpoint_returns_metrics_or_clean_skip(tmp_path, monkeypatch) -> None:
    client, _paths = make_p10_client(tmp_path, monkeypatch)

    response = client.post("/eval/p9m2-multiturn", json={"run": False})

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] in {"ok", "skipped"}
    assert isinstance(data["metrics"], dict)
    assert isinstance(data["artifacts"], dict)
    if data["skipped"]:
        assert data["skip_reason"]
    else:
        assert data["metrics"].get("dialogue_count", 0) >= 50
