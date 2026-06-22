from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

from app.api.runtime_config import (
    load_runtime_config,
    reset_runtime_config_cache,
    runtime_config_summary,
    get_runtime_config,
    validate_runtime_config,
)


ROOT_DIR = Path(__file__).resolve().parents[1]
TCM_ENV_KEYS = [
    "TCM_RUNTIME_MODE",
    "TCM_API_DB_PATH",
    "TCM_RUNTIME_DIR",
    "TCM_ARTIFACTS_DIR",
    "TCM_ALLOW_REAL_LLM",
    "TCM_LOG_LEVEL",
    "TCM_REDACT_LOGS",
    "TCM_CONFIG_STRICT",
    "OPENAI_API_KEY",
]


@contextmanager
def _clean_process_env() -> None:
    previous = {key: os.environ.get(key) for key in TCM_ENV_KEYS}
    for key in TCM_ENV_KEYS:
        os.environ.pop(key, None)
    reset_runtime_config_cache()
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        reset_runtime_config_cache()


class P31RuntimeConfigTests(unittest.TestCase):
    def test_default_config_is_local_with_default_db(self) -> None:
        config = load_runtime_config({})

        self.assertEqual(config.runtime_mode, "local")
        self.assertEqual(config.db_path, ".runtime/tcm_assistant.sqlite3")
        self.assertEqual(config.db_path_source, "default")
        self.assertEqual(config.runtime_dir, ".runtime")
        self.assertEqual(config.artifacts_dir, "artifacts")
        self.assertFalse(config.allow_real_llm)
        self.assertTrue(config.redact_logs)
        self.assertFalse(config.config_strict)

    def test_env_overrides_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            config = load_runtime_config(
                {
                    "TCM_API_DB_PATH": str(temp_root / "runtime.sqlite3"),
                    "TCM_RUNTIME_DIR": str(temp_root / "runtime"),
                    "TCM_ARTIFACTS_DIR": str(temp_root / "artifacts"),
                }
            )

        self.assertEqual(config.db_path_source, "env:TCM_API_DB_PATH")
        self.assertTrue(config.db_path.endswith("runtime.sqlite3"))
        self.assertTrue(config.runtime_dir.endswith("runtime"))
        self.assertTrue(config.artifacts_dir.endswith("artifacts"))

    def test_runtime_modes_are_supported(self) -> None:
        for mode in ["local", "test", "demo", "eval"]:
            with self.subTest(mode=mode):
                config = load_runtime_config({"TCM_RUNTIME_MODE": mode, "TCM_API_DB_PATH": "temp.sqlite3"})
                self.assertEqual(config.runtime_mode, mode)
                self.assertEqual(validate_runtime_config(config)["status"], "ok")

    def test_invalid_runtime_mode_reports_error(self) -> None:
        config = load_runtime_config({"TCM_RUNTIME_MODE": "bad-mode"})
        validation = validate_runtime_config(config)

        self.assertEqual(validation["status"], "failed")
        self.assertTrue(any("Invalid runtime_mode" in error for error in validation["errors"]))

    def test_boolean_parsing_and_invalid_boolean_errors(self) -> None:
        truthy = load_runtime_config({"TCM_ALLOW_REAL_LLM": "yes"})
        falsy = load_runtime_config({"TCM_ALLOW_REAL_LLM": "0"})
        invalid = load_runtime_config({"TCM_ALLOW_REAL_LLM": "maybe"})

        self.assertTrue(truthy.allow_real_llm)
        self.assertFalse(falsy.allow_real_llm)
        self.assertFalse(invalid.allow_real_llm)
        self.assertTrue(any("Invalid boolean env TCM_ALLOW_REAL_LLM" in error for error in invalid.errors))

    def test_openai_api_key_records_presence_without_value(self) -> None:
        secret = "sk-" + "runtimeconfigsecret0001"
        config = load_runtime_config({"OPENAI_API_KEY": secret})
        summary_text = json.dumps(runtime_config_summary(config), ensure_ascii=False)

        self.assertTrue(config.openai_api_key_present)
        self.assertIn('"openai_api_key_present": true', summary_text)
        self.assertNotIn(secret, summary_text)
        self.assertNotIn("OPENAI_API_KEY", summary_text)

    def test_summary_redacts_secret_like_paths(self) -> None:
        secret = "sk-" + "pathsecret0001"
        config = load_runtime_config({"TCM_API_DB_PATH": f".runtime/{secret}.sqlite3"})
        redacted = runtime_config_summary(config, redacted=True)

        self.assertNotIn(secret, json.dumps(redacted, ensure_ascii=False))
        self.assertIn("[redacted-secret]", redacted["db_path"])

    def test_reset_runtime_config_cache(self) -> None:
        with _clean_process_env():
            os.environ["TCM_RUNTIME_MODE"] = "demo"
            self.assertEqual(get_runtime_config().runtime_mode, "demo")
            os.environ["TCM_RUNTIME_MODE"] = "eval"
            self.assertEqual(get_runtime_config().runtime_mode, "demo")
            reset_runtime_config_cache()
            self.assertEqual(get_runtime_config().runtime_mode, "eval")

    def test_config_summary_is_json_serializable(self) -> None:
        config = load_runtime_config({"TCM_RUNTIME_MODE": "local"})

        json.dumps(runtime_config_summary(config), ensure_ascii=False)
        json.dumps(config.__dict__, ensure_ascii=False)

    def test_import_has_no_runtime_file_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env = os.environ.copy()
            for key in TCM_ENV_KEYS:
                env.pop(key, None)
            env["PYTHONPATH"] = str(ROOT_DIR) + os.pathsep + env.get("PYTHONPATH", "")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "from pathlib import Path; "
                        "import app.api.runtime_config; "
                        "print(Path('.runtime').exists()); "
                        "print(Path('artifacts').exists())"
                    ),
                ],
                cwd=temp_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
                timeout=30,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.strip().splitlines(), ["False", "False"])


if __name__ == "__main__":
    unittest.main()
