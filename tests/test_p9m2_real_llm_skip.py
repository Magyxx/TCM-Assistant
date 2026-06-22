from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def test_real_llm_validator_clean_skip_when_disabled(monkeypatch) -> None:
    monkeypatch.setenv("ENABLE_REAL_LLM", "false")
    completed = subprocess.run(
        [sys.executable, "scripts/validate_p9m2_real_llm.py"],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )

    assert completed.returncode == 0
    metrics = json.loads((ROOT_DIR / "artifacts/p9m2/real_llm_smoke_metrics.json").read_text(encoding="utf-8"))
    assert metrics["status"] == "skipped"
    assert metrics["skip_reason"] == "ENABLE_REAL_LLM=false"


def test_real_llm_validator_requires_live_allowance(monkeypatch) -> None:
    monkeypatch.setenv("ENABLE_REAL_LLM", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-testsecret1234567890")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.delenv("P9M2_ALLOW_REAL_LLM_LIVE", raising=False)

    completed = subprocess.run(
        [sys.executable, "scripts/validate_p9m2_real_llm.py"],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )

    assert completed.returncode == 0
    metrics = json.loads((ROOT_DIR / "artifacts/p9m2/real_llm_smoke_metrics.json").read_text(encoding="utf-8"))
    assert metrics["status"] == "skipped"
    assert metrics["skip_reason"] == "P9M2_ALLOW_REAL_LLM_LIVE=false"
