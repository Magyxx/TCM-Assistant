from __future__ import annotations

import unittest
from unittest.mock import patch

from app.extractors.result import ExtractorResult
from app.graph.consultation_graph import run_consultation_graph
from app.schemas.report_schemas import RunState


class BadExtractor:
    mode = "bad"

    def extract(self, text: str, *, state=None, memory=None) -> ExtractorResult:
        return ExtractorResult.schema_failure(
            mode="bad",
            raw_output="{bad json",
            error="json_parse_failed",
            metadata={"raw_llm_json_valid": False, "repair_used": False},
        )


class ExtractorSchemaGuardTests(unittest.TestCase):
    def test_schema_failure_does_not_enter_memory_l2(self) -> None:
        with patch("app.extractors.structured_output_adapter.get_extractor", return_value=BadExtractor()):
            graph_state = run_consultation_graph(
                RunState(),
                "胃胀两天",
                use_langgraph=False,
                extractor_mode="bad",
                rag_enabled=False,
            )

        self.assertFalse(graph_state["schema_valid"])
        self.assertEqual(graph_state["memory"].facts, {})
        self.assertTrue(
            any(event.reason.startswith("schema_validation_failed") for event in graph_state["memory"].audit_events)
        )


if __name__ == "__main__":
    unittest.main()
