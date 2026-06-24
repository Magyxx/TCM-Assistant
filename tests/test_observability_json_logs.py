from __future__ import annotations

import json
import unittest

from app.observability.events import TraceEvent
from app.observability.json_logger import json_event_line


class P1F0ObservabilityTests(unittest.TestCase):
    def test_trace_event_json_line_is_parseable_and_redacted(self) -> None:
        line = json_event_line(
            TraceEvent(
                session_id="session",
                turn_id="turn",
                event_type="api",
                component="test",
                latency_ms=1,
                metadata={"redacted_text": "[redacted]"},
            )
        )
        payload = json.loads(line)
        self.assertTrue(payload["trace_id"])
        self.assertEqual(payload["event_type"], "api")
        self.assertEqual(payload["component"], "test")
        self.assertNotIn("raw sensitive patient text", line)


if __name__ == "__main__":
    unittest.main()
