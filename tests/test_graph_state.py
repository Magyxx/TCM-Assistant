from __future__ import annotations

import unittest

from app.graph.state import ConsultationGraphState
from app.memory.models import ConsultationMemory
from app.schemas.report_schemas import RunState


class GraphStateTests(unittest.TestCase):
    def test_graph_state_is_pydantic_and_has_defaults(self) -> None:
        state = ConsultationGraphState(user_input="  stomach discomfort  ")

        self.assertIsInstance(state.run_state, RunState)
        self.assertIsInstance(state.memory, ConsultationMemory)
        self.assertEqual(state.graph_runtime, "pending")
        self.assertEqual(state.extractor_mode_requested, "auto")

    def test_legacy_dict_preserves_run_state_object(self) -> None:
        state = ConsultationGraphState(run_state=RunState(chief_complaint="cough"))
        payload = state.to_legacy_dict()

        self.assertIsInstance(payload["run_state"], RunState)
        self.assertEqual(payload["run_state"].chief_complaint, "cough")


if __name__ == "__main__":
    unittest.main()
