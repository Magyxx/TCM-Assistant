from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.extractors.openai_compatible_client import OpenAICompatibleChatClient
from app.graph.runner import run_p9m1_graph


class P11M3MemoryStateUpdatePathTests(unittest.TestCase):
    def test_merge_state_updates_authoritative_run_state_after_schema_guard(self) -> None:
        def mock_completion(self, messages):
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "chief_complaint": "stomach discomfort",
                                    "duration": "two days",
                                    "symptoms": [],
                                    "symptoms_status": "none",
                                    "risk_flags": [],
                                    "risk_flags_status": "none",
                                    "summary": "mock candidate",
                                }
                            )
                        }
                    }
                ]
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(OpenAICompatibleChatClient, "create_chat_completion", mock_completion):
                result = run_p9m1_graph(
                    "stomach discomfort for two days, no other symptoms",
                    extractor_backend="local_lora",
                    use_langgraph=False,
                    graph_events_path=Path(temp_dir) / "graph_events.jsonl",
                )

        nodes = [item["node"] for item in result["trace"]]
        run_state = result["run_state"]

        self.assertLess(nodes.index("validate_turn"), nodes.index("merge_state"))
        self.assertEqual(run_state["chief_complaint"], "stomach discomfort")
        self.assertEqual(run_state["duration"], "two days")
        self.assertEqual(run_state["metadata"]["extractor_backend"], "local_lora")
        self.assertEqual(run_state["turn_count"], 1)


if __name__ == "__main__":
    unittest.main()
