from __future__ import annotations

import json
import unittest

from app.api.redaction import (
    REDACTED_SECRET,
    REDACTED_SECRET_KEY,
    dumps_redacted_json,
    redact_secrets,
)
from app.api.sqlite_store import redact_secrets as sqlite_redact_secrets


class P13RedactionTests(unittest.TestCase):
    def test_redacts_secret_assignments_and_key_values(self) -> None:
        value = "hello OPENAI_API_KEY=sk-testsecret1234567890 goodbye"

        redacted = redact_secrets(value)

        self.assertIn(REDACTED_SECRET, redacted)
        self.assertNotIn("OPENAI_API_KEY", redacted)
        self.assertNotIn("sk-testsecret1234567890", redacted)

    def test_redacts_nested_secret_keys_and_values(self) -> None:
        payload = {
            "metadata": {
                "OPENAI_API_KEY": "sk-nestedsecret1234567890",
                "notes": ["safe", "TOKEN=abc123456789"],
            },
            "turn_count": 1,
        }

        redacted = redact_secrets(payload)
        serialized = json.dumps(redacted, ensure_ascii=False)

        self.assertIn(REDACTED_SECRET_KEY, redacted["metadata"])
        self.assertEqual(redacted["turn_count"], 1)
        self.assertIn("safe", serialized)
        self.assertNotIn("OPENAI_API_KEY", serialized)
        self.assertNotIn("sk-nestedsecret1234567890", serialized)
        self.assertNotIn("TOKEN=abc123456789", serialized)

    def test_dumps_redacted_json_sorts_keys_and_redacts(self) -> None:
        serialized = dumps_redacted_json(
            {"b": "safe", "a": "AUTH_TOKEN=abc123456789"}
        )

        self.assertTrue(serialized.startswith('{"a":'))
        self.assertIn(REDACTED_SECRET, serialized)
        self.assertNotIn("AUTH_TOKEN", serialized)

    def test_sqlite_store_keeps_redaction_import_compatibility(self) -> None:
        redacted = sqlite_redact_secrets("sk-compatsecret1234567890")

        self.assertEqual(redacted, REDACTED_SECRET)


if __name__ == "__main__":
    unittest.main()
