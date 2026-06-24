from __future__ import annotations

from pathlib import Path


def test_p10m2_lora_contract_documents_backend_only_boundary() -> None:
    text = (Path(__file__).resolve().parents[1] / "docs" / "LORA_INTEGRATION_CONTRACT.md").read_text(encoding="utf-8")

    assert "local_lora" in text
    assert "only replace `ExtractorBackend`" in text
    assert "TurnOutput.model_validate" in text
    assert "cannot decide final `risk_status`" in text
    assert "cannot overwrite `risk_rule_ids`" in text

