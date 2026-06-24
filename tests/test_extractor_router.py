from __future__ import annotations

import pytest

from app.extractors.router import get_extractor_backend
from app.schemas.report_schemas import RunState


def test_router_returns_fake_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXTRACTOR_BACKEND", "fake")
    backend = get_extractor_backend()
    output = backend.extract_turn("胃胀一周，没有发热", RunState())

    assert backend.mode == "fake"
    assert output.chief_complaint == "胃胀"
    assert output.duration == "一周"


def test_router_returns_rule_fallback_backend() -> None:
    backend = get_extractor_backend("rule_fallback")
    output = backend.extract_turn("胸痛伴呼吸困难", RunState())

    assert backend.mode == "rule_fallback"
    assert output.risk_flags_status == "present"
    assert "胸痛" in output.risk_flags


def test_unconfigured_real_llm_does_not_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_REAL_LLM", "false")
    backend = get_extractor_backend("real_llm")
    output = backend.extract_turn("胃胀两天", RunState())

    assert output.metadata["error_type"] == "real_llm_disabled"
    assert output.metadata["fallback_used"] is True


def test_local_lora_backend_falls_back_when_server_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOCAL_LLM_BASE_URL", "http://127.0.0.1:9/v1")
    monkeypatch.setenv("LOCAL_LLM_TIMEOUT_SECONDS", "0.1")
    backend = get_extractor_backend("local_lora")
    output = backend.extract_turn("胃胀一周", RunState())

    assert backend.mode == "local_lora"
    assert output.metadata["backend"] == "local_lora"
    assert output.metadata["fallback_used"] is True
    assert output.metadata["error_type"] in {"connection_error", "timeout"}


def test_local_vllm_backend_is_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXTRACTOR_BACKEND", "local_vllm")
    backend = get_extractor_backend()

    assert backend.mode == "local_vllm"
