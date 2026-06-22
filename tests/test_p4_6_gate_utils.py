from __future__ import annotations

import json
import unittest

from scripts.gate_utils import redact_preserving_schema


class GateUtilsTests(unittest.TestCase):
    def test_redact_preserving_schema_recurses_through_gate_payloads(self) -> None:
        secret = "sk-" + "p46gateutils1234567890"
        payload = {
            f"secret_key={secret}": secret,
            "nested": [
                {"token": f"TOKEN={secret}"},
                ("safe", secret),
            ],
            7: secret,
        }

        redacted = redact_preserving_schema(payload)
        serialized = json.dumps(redacted, ensure_ascii=False)

        self.assertNotIn(secret, serialized)
        self.assertNotIn("TOKEN=", serialized)
        self.assertNotIn("secret_key=", serialized)
        self.assertIn("[redacted-secret]", serialized)
        self.assertEqual(redacted["nested"][1][0], "safe")
        self.assertEqual(redacted[7], "[redacted-secret]")


if __name__ == "__main__":
    unittest.main()
