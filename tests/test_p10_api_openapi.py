from __future__ import annotations

import json

from tests.p10_api_helpers import make_p10_client


def test_p10_openapi_contains_new_endpoints(tmp_path, monkeypatch) -> None:
    client, _paths = make_p10_client(tmp_path, monkeypatch)

    schema = client.get("/openapi.json")

    assert schema.status_code == 200, schema.text
    paths = schema.json()["paths"]
    assert "/turn" in paths
    assert "/sessions/{session_id}/turns" in paths
    assert "/sessions/{session_id}/replay" in paths
    assert "/eval/p9m2-multiturn" in paths
    serialized = json.dumps(schema.json(), ensure_ascii=False)
    assert "OPENAI_API_KEY" not in serialized
    assert "sk-" not in serialized
