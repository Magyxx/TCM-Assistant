from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ADAPTER = (
    "/mnt/e/ai_artifacts/tcm_assistant_device2/"
    "d2t1r2/risk_repair_20260623T060605Z/adapter/final_adapter"
)


class Device2VLLMScriptTests(unittest.TestCase):
    def test_base_script_defaults_and_requires_base_model(self) -> None:
        script = ROOT / "scripts" / "device2" / "serve_vllm_base.sh"
        text = script.read_text(encoding="utf-8")

        self.assertTrue(text.startswith("#!/usr/bin/env bash"))
        self.assertIn("set -euo pipefail", text)
        self.assertIn(": \"${HOST:=127.0.0.1}\"", text)
        self.assertIn(": \"${PORT:=8000}\"", text)
        self.assertIn(": \"${MAX_MODEL_LEN:=2048}\"", text)
        self.assertIn(": \"${GPU_MEMORY_UTILIZATION:=0.75}\"", text)
        self.assertIn(": \"${DTYPE:=auto}\"", text)
        self.assertIn(": \"${GENERATION_CONFIG:=vllm}\"", text)
        self.assertIn(": \"${CHAT_TEMPLATE:=}\"", text)
        self.assertIn("BASE_MODEL is required", text)
        self.assertIn("vllm serve", text)
        self.assertIn("--generation-config \"${GENERATION_CONFIG}\"", text)
        self.assertIn("--chat-template", text)

    def test_lora_script_defaults_and_infers_base_model(self) -> None:
        script = ROOT / "scripts" / "device2" / "serve_vllm_lora.sh"
        text = script.read_text(encoding="utf-8")

        self.assertTrue(text.startswith("#!/usr/bin/env bash"))
        self.assertIn("set -euo pipefail", text)
        self.assertIn(": \"${LORA_NAME:=tcm-extractor-lora}\"", text)
        self.assertIn(DEFAULT_ADAPTER, text)
        self.assertIn("adapter_config.json", text)
        self.assertIn("base_model_name_or_path", text)
        self.assertIn(": \"${GENERATION_CONFIG:=vllm}\"", text)
        self.assertIn(": \"${CHAT_TEMPLATE:=}\"", text)
        self.assertIn("chat_template.jinja", text)
        self.assertIn("--enable-lora", text)
        self.assertIn("--max-lora-rank", text)
        self.assertIn("--lora-modules", text)
        self.assertNotIn("VLLM_ALLOW_RUNTIME_LORA_UPDATING", text)

    def test_api_smoke_script_has_expected_defaults(self) -> None:
        script = ROOT / "scripts" / "device2" / "test_vllm_api.py"
        text = script.read_text(encoding="utf-8")

        self.assertIn("DEFAULT_BASE_URL = \"http://127.0.0.1:8000/v1\"", text)
        self.assertIn("DEFAULT_MODEL = \"tcm-extractor-lora\"", text)
        self.assertIn("chat.completions.create", text)
        self.assertIn("TurnOutput.model_validate", text)
        self.assertIn("temperature=0", text)
        self.assertIn("max_tokens=args.max_tokens", text)


if __name__ == "__main__":
    unittest.main()
