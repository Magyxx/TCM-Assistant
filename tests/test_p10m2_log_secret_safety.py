from __future__ import annotations

from app.services.consultation_service import append_api_event


def test_p10m2_api_logs_do_not_store_secret_like_raw_text(tmp_path) -> None:
    log_path = tmp_path / "api_events.jsonl"
    append_api_event(
        {
            "method": "POST",
            "path": "/turn",
            "status_code": 200,
            "input_length": 26,
            "redacted_input_hash": "hash-only",
            "error_code": "Authorization: Bearer local-demo-token sk-test-short",
        },
        log_path,
    )

    text = log_path.read_text(encoding="utf-8")
    assert "local-demo-token" not in text
    assert "sk-test-short" not in text
    assert "input_length" in text

