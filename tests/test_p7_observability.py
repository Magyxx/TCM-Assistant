from __future__ import annotations

import unittest

from app.observability.trace import build_p7_trace_event, p7_trace_schema_pass
from app.schemas.report_schemas import RunState


class P7ObservabilityTests(unittest.TestCase):
    def test_p7_trace_schema_contains_required_fields(self) -> None:
        trace = build_p7_trace_event(
            session_id="s1",
            turn_id="t1",
            api_route="POST /sessions/{session_id}/turn",
            run_state=RunState(risk_flags_status="none"),
        )

        self.assertTrue(p7_trace_schema_pass([trace.model_dump()]))
        self.assertIn("fallback_used", trace.model_dump())
        self.assertIn("storage_write_pass", trace.model_dump())


if __name__ == "__main__":
    unittest.main()
