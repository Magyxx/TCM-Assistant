from __future__ import annotations

import unittest

from pydantic import ValidationError

from app.graph.state import ConsultationGraphState
from app.memory.models import ConsultationMemory
from app.schemas.report_schemas import RunState


class GraphStateTests(unittest.TestCase):
    def test_graph_state_is_pydantic_and_has_lightweight_defaults(self) -> None:
        state = ConsultationGraphState(
            session_id="session-1",
            turn_id="turn-1",
            user_input="  stomach discomfort  ",
        )

        self.assertIsInstance(state.run_state, RunState)
        self.assertIsInstance(state.memory, ConsultationMemory)
        self.assertEqual(state.graph_runtime, "fallback")
        self.assertEqual(state.extractor_mode, "")
        self.assertEqual(state.extractor_mode_requested, "auto")
        self.assertEqual(state.audit_events, [])

    def test_required_fields_are_enforced(self) -> None:
        with self.assertRaises(ValidationError):
            ConsultationGraphState.model_validate({"session_id": "session-1", "user_input": "x"})

    def test_model_dump_and_validate_can_replay_state(self) -> None:
        state = ConsultationGraphState(
            session_id="session-1",
            turn_id="turn-1",
            user_input="stomach discomfort",
            run_state=RunState(chief_complaint="stomach discomfort"),
        )

        replayed = ConsultationGraphState.model_validate(state.model_dump())
        self.assertEqual(replayed.session_id, "session-1")
        self.assertEqual(replayed.run_state.chief_complaint, "stomach discomfort")

    def test_legacy_dict_preserves_run_state_object(self) -> None:
        state = ConsultationGraphState(
            session_id="session-1",
            turn_id="turn-1",
            user_input="x",
            run_state=RunState(chief_complaint="cough"),
        )
        payload = state.to_legacy_dict()

        self.assertIsInstance(payload["run_state"], RunState)
        self.assertEqual(payload["run_state"].chief_complaint, "cough")


if __name__ == "__main__":
    unittest.main()
