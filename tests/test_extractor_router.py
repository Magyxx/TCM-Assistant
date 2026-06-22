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


def test_reserved_device2_backend_has_clear_error() -> None:
    backend = get_extractor_backend("local_lora")
    with pytest.raises(NotImplementedError, match="reserved for device2 integration"):
        backend.extract_turn("胃胀一周", RunState())
