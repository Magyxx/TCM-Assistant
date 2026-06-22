from __future__ import annotations

import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.observability import (
    EVENT_FIELDS,
    REDACTED,
    REDACTED_KEY,
    generate_request_id,
    make_log_event,
    redact_observable_value,
)
from app.api.runtime_config import load_runtime_config, reset_runtime_config_cache
from app.api.sqlite_store import STORE_SCHEMA_VERSION, STORE_TABLES, fetch_schema_meta


TCM_ENV_KEYS = [
    "TCM_RUNTIME_MODE",
    "TCM_API_DB_PATH",
    "TCM_LOG_LEVEL",
    "TCM_REDACT_LOGS",
    "OPENAI_API_KEY",
]


@contextmanager
def _isolated_env(**values: str):
    previous = {key: os.environ.get(key) for key in TCM_ENV_KEYS}
    for key in TCM_ENV_KEYS:
        os.environ.pop(key, None)
    os.environ.update(values)
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


class P32ObservabilityTests(unittest.TestCase):
    def test_structured_log_event_fields_are_stable(self) -> None:
        event = make_log_event(
            "unit.test",
            component="tests",
            request_id="req-1",
            session_id="session-1",
            turn_id="turn-1",
            status="ok",
            duration_ms=12.3456,
            message="hello",
            extra={"safe": "value"},
            config=load_runtime_config({}),
        )

        self.assertEqual(list(event.keys()), list(EVENT_FIELDS))
        self.assertEqual(event["event"], "unit.test")
        self.assertEqual(event["duration_ms"], 12.346)
        json.dumps(event, ensure_ascii=False)

    def test_redaction_handles_plain_dict(self) -> None:
        secret = "sk-" + "plainsecret0001"
        redacted = redact_observable_value({"api_key": secret, "safe": "value"})
        serialized = json.dumps(redacted, ensure_ascii=False)

        self.assertIn(REDACTED_KEY, redacted)
        self.assertEqual(redacted["safe"], "value")
        self.assertNotIn("api_key", serialized)
        self.assertNotIn(secret, serialized)

    def test_redaction_handles_nested_dict_and_list(self) -> None:
        secret = "sk-" + "nestedsecret0001"
        redacted = redact_observable_value({"outer": [{"token": secret}, {"item": "ok"}]})
        serialized = json.dumps(redacted, ensure_ascii=False)

        self.assertIn(REDACTED_KEY, redacted["outer"][0])
        self.assertNotIn("token", serialized)
        self.assertNotIn(secret, serialized)

    def test_openai_api_key_is_never_output(self) -> None:
        secret = "sk-" + "openaisecret0001"
        event = make_log_event(
            "secret.test",
            message=f"OPENAI_API_KEY={secret}",
            extra={"OPENAI_API_KEY": secret},
            config=load_runtime_config({"OPENAI_API_KEY": secret}),
        )
        serialized = json.dumps(event, ensure_ascii=False)

        self.assertNotIn(secret, serialized)
        self.assertNotIn("OPENAI_API_KEY", serialized)
        self.assertIn(REDACTED, serialized)

    def test_sk_style_string_is_redacted(self) -> None:
        secret = "sk-" + "stylesecret0001"
        redacted = redact_observable_value(f"value={secret}")

        self.assertNotIn(secret, redacted)
        self.assertIn(REDACTED, redacted)

    def test_long_user_text_is_truncated(self) -> None:
        value = {"user_input": "胃胀" * 200}
        redacted = redact_observable_value(value)

        self.assertLess(len(redacted["user_input"]), len(value["user_input"]))
        self.assertIn("[TRUNCATED]", redacted["user_input"])

    def test_redact_logs_true_and_false_do_not_leak_secret(self) -> None:
        secret = "sk-" + "redactflagsecret0001"
        for redact_logs in [True, False]:
            with self.subTest(redact_logs=redact_logs):
                config = load_runtime_config({"TCM_REDACT_LOGS": str(redact_logs).lower()})
                event = make_log_event(
                    "redact.flag",
                    extra={"secret": secret, "user_input": "胃胀" * 200},
                    config=config,
                )
                serialized = json.dumps(event, ensure_ascii=False)

                self.assertNotIn(secret, serialized)
                self.assertIn(REDACTED, serialized)

    def test_request_id_can_be_generated(self) -> None:
        request_id = generate_request_id()

        self.assertIsInstance(request_id, str)
        self.assertGreater(len(request_id), 20)

    def test_api_response_body_contract_is_unchanged_and_header_is_added(self) -> None:
        from app.api.main import app

        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = str(Path(temp_dir) / "api.sqlite3")
            with _isolated_env(TCM_API_DB_PATH=db_path, TCM_LOG_LEVEL="CRITICAL"):
                client = TestClient(app, raise_server_exceptions=False)
                response = client.get("/health", headers={"X-Request-ID": "req-contract"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "status": "ok",
                "service": "TCM-Assistant",
                "stage": "P1.1",
                "mode": "agentic_workflow",
                "diagnosis_system": False,
            },
        )
        self.assertEqual(response.headers.get("X-Request-ID"), "req-contract")

    def test_sqlite_schema_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "schema.sqlite3"
            meta = fetch_schema_meta(db_path)

        self.assertEqual(meta["schema_version"], str(STORE_SCHEMA_VERSION))
        self.assertIn("sessions", STORE_TABLES)
        self.assertIn("reports", STORE_TABLES)


if __name__ == "__main__":
    unittest.main()
