from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class Device2VLLMConfigTests(unittest.TestCase):
    def test_env_example_contains_local_lora_defaults(self) -> None:
        env_text = (ROOT / ".env.example").read_text(encoding="utf-8")

        self.assertIn("EXTRACTOR_BACKEND=local_lora", env_text)
        self.assertIn("LOCAL_LLM_BASE_URL=http://127.0.0.1:8000/v1", env_text)
        self.assertIn("LOCAL_LLM_MODEL=tcm-extractor-lora", env_text)
        self.assertIn("LOCAL_LLM_API_KEY=EMPTY", env_text)

    def test_check_vllm_runtime_writes_json_and_accepts_adapter_path(self) -> None:
        tmpdir = ROOT / "artifacts" / "tmp" / "vllm_config_test"
        shutil.rmtree(tmpdir, ignore_errors=True)
        try:
            adapter = tmpdir / "adapter"
            adapter.mkdir(parents=True)
            (adapter / "adapter_config.json").write_text(
                json.dumps(
                    {
                        "base_model_name_or_path": str(Path(tmpdir) / "base"),
                        "r": 16,
                        "lora_alpha": 32,
                        "target_modules": ["q_proj"],
                    }
                ),
                encoding="utf-8",
            )
            (adapter / "adapter_model.safetensors").write_bytes(b"placeholder")
            output = tmpdir / "vllm_repair_check.json"

            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "device2" / "check_vllm_runtime.py"),
                    "--adapter-path",
                    str(adapter),
                    "--json",
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
                timeout=60,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["adapter_path"], str(adapter))
            self.assertTrue(payload["adapter_path_exists"])
            self.assertTrue(payload["adapter_config_exists"])
            self.assertTrue(payload["adapter_model_exists"])
            self.assertEqual(payload["lora_r"], 16)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
