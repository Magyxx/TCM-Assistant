import unittest

from app.agentic.workflow_adapter import P4WorkflowAdapter, run_p4_workflow
from app.schemas.report_schemas import RunState


class P41WorkflowAdapterTests(unittest.TestCase):
    def test_adapter_wraps_existing_flow_without_contract_flags(self) -> None:
        output = run_p4_workflow(
            RunState(),
            "我胃胀两天，没有胸痛",
            extractor_mode="fake",
            rag_enabled=False,
            use_langgraph=False,
        )

        state = output["run_state"]
        workflow = state.metadata["p4_workflow"]

        self.assertTrue(workflow["wrapped_existing_flow"])
        self.assertEqual(workflow["phase"], "P4.1")
        self.assertEqual(workflow["boundary"]["api_contract_changed"], False)
        self.assertEqual(workflow["boundary"]["response_body_schema_changed"], False)
        self.assertEqual(workflow["boundary"]["sqlite_schema_changed"], False)
        self.assertEqual(workflow["boundary"]["diagnosis_system"], False)
        self.assertTrue(output["p4_trace"])

    def test_adapter_keeps_existing_runtime_metadata(self) -> None:
        output = P4WorkflowAdapter().run(
            RunState(),
            "我不太舒服",
            extractor_mode="fake",
            rag_enabled=False,
            use_langgraph=False,
        )
        state = output["run_state"]

        self.assertEqual(state.metadata["graph_runtime"], "sequential_fallback")
        self.assertEqual(state.metadata["extractor_mode_requested"], "fake")
        self.assertIn("p4_memory", state.metadata)


if __name__ == "__main__":
    unittest.main()

