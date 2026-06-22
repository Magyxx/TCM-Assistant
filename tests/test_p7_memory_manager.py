from __future__ import annotations

import unittest

from app.memory.manager import MemoryManager
from app.schemas.report_schemas import RunState


class P7MemoryManagerTests(unittest.TestCase):
    def test_snapshot_has_four_layers_and_traceable_facts(self) -> None:
        snapshot = MemoryManager().build_snapshot(
            session_id="s1",
            turn_id="t1",
            turn_index=1,
            previous_state=RunState(),
            current_state=RunState(
                chief_complaint="胃胀",
                duration="一周",
                symptoms_status="none",
                risk_flags_status="none",
            ),
            user_input="胃胀一周，没有胸痛",
        )

        self.assertEqual(len(snapshot.recent_turns), 1)
        self.assertTrue(snapshot.structured_facts)
        self.assertTrue(snapshot.case_summary.summary)
        self.assertTrue(snapshot.experience_retrieval)
        self.assertTrue(snapshot.source_traceability_pass)


if __name__ == "__main__":
    unittest.main()
