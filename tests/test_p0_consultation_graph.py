import unittest

from app.chains.report_chain import merge_turn_fields
from app.graphs.consultation_graph import run_consultation_graph
from app.schemas.report_schemas import RunState, TurnOutput


class P0ConsultationGraphTest(unittest.TestCase):
    def test_single_ordinary_symptom_enters_followup(self):
        graph_state = run_consultation_graph(RunState(), "我咳嗽", use_langgraph=False, extractor_mode="fake")
        state = graph_state["run_state"]

        self.assertEqual(state.chief_complaint, "咳嗽")
        self.assertIsNotNone(state.next_question)
        self.assertIn("多久", state.next_question)

    def test_incomplete_core_fields_generate_next_question(self):
        graph_state = run_consultation_graph(RunState(), "我咳嗽两天", use_langgraph=False, extractor_mode="fake")
        state = graph_state["run_state"]

        self.assertEqual(state.chief_complaint, "咳嗽")
        self.assertEqual(state.duration, "两天")
        self.assertIsNotNone(state.next_question)

    def test_high_risk_stops_routine_followup(self):
        graph_state = run_consultation_graph(RunState(), "我持续高烧三天", use_langgraph=False, extractor_mode="rule_fallback")
        state = graph_state["run_state"]

        self.assertEqual(state.risk_flags_status, "present")
        self.assertIsNone(state.next_question)
        self.assertIsNotNone(state.final_report)
        self.assertEqual(state.final_report.triage_level, "urgent_visit")

    def test_multi_turn_state_is_not_cleared(self):
        state = RunState()
        first = run_consultation_graph(
            state,
            "我胃胀两天，没有其他症状，也没有胸痛",
            use_langgraph=False,
            extractor_mode="fake",
        )["run_state"]
        second = run_consultation_graph(
            first,
            "今天稍微好一点",
            use_langgraph=False,
            extractor_mode="fake",
        )["run_state"]

        self.assertEqual(second.chief_complaint, "胃胀")
        self.assertEqual(second.duration, "两天")
        self.assertEqual(second.symptoms_status, "none")
        self.assertEqual(second.risk_flags_status, "none")

    def test_fallback_only_environment_does_not_crash(self):
        graph_state = run_consultation_graph(RunState(), "我不太舒服", use_langgraph=False, extractor_mode="rule_fallback")
        state = graph_state["run_state"]

        self.assertIsNotNone(state.next_question)
        self.assertEqual(graph_state["extraction_mode"], "rule_fallback")

    def test_fake_structured_extractor_completes_report(self):
        graph_state = run_consultation_graph(
            RunState(),
            "我胃胀两天，没有其他症状，也没有胸痛",
            use_langgraph=False,
            extractor_mode="fake",
        )
        state = graph_state["run_state"]

        self.assertEqual(graph_state["extraction_mode"], "fake_structured_output")
        self.assertEqual(graph_state["extractor_mode"], "fake")
        self.assertTrue(graph_state["raw_llm_json_valid"])
        self.assertFalse(graph_state["fallback_used"])
        self.assertEqual(state.metadata["graph_runtime"], "sequential_fallback")
        self.assertEqual(state.metadata["extractor_mode_requested"], "fake")
        self.assertEqual(state.metadata["last_extractor_mode"], "fake")
        self.assertIsNotNone(state.final_report)
        self.assertEqual(state.final_report.triage_level, "observe")

    def test_langgraph_runtime_metadata_is_recorded(self):
        graph_state = run_consultation_graph(
            RunState(),
            "我持续高烧三天",
            use_langgraph=True,
            extractor_mode="fallback",
        )
        state = graph_state["run_state"]

        self.assertIn(graph_state["graph_runtime"], {"langgraph", "sequential_fallback"})
        self.assertEqual(state.metadata["extractor_mode_requested"], "fallback")
        self.assertEqual(state.metadata["last_extractor_mode"], "fallback")
        self.assertTrue(state.metadata["last_fallback_used"])

    def test_confirmed_no_risk_survives_ordinary_symptom_update(self):
        state = RunState(
            chief_complaint="咳嗽",
            duration="三天",
            symptoms_status="none",
            risk_flags_status="none",
        )
        turn_output = TurnOutput(
            symptoms=["乏力"],
            symptoms_status="present",
            risk_flags_status="unknown",
            summary="补充普通伴随症状。",
        )

        merged = merge_turn_fields(state, turn_output, "后来还有点乏力")

        self.assertEqual(merged.symptoms_status, "present")
        self.assertEqual(merged.risk_flags_status, "none")

    def test_risk_recheck_symptom_update_resets_confirmed_no_risk(self):
        state = RunState(
            chief_complaint="咳嗽",
            duration="三天",
            symptoms_status="none",
            risk_flags_status="none",
        )
        turn_output = TurnOutput(
            symptoms=["头晕"],
            symptoms_status="present",
            risk_flags_status="unknown",
            summary="补充需要重新确认风险的伴随症状。",
        )

        merged = merge_turn_fields(state, turn_output, "今天又开始头晕了")

        self.assertEqual(merged.symptoms_status, "present")
        self.assertEqual(merged.risk_flags_status, "unknown")

    def test_unmentioned_symptoms_do_not_accept_model_none(self):
        state = RunState(chief_complaint="胃胀", duration="三天")
        turn_output = TurnOutput(
            symptoms=[],
            symptoms_status="none",
            risk_flags_status="unknown",
            summary="未提伴随症状。",
        )

        merged = merge_turn_fields(state, turn_output, "胃胀三天了")

        self.assertEqual(merged.symptoms_status, "unknown")

    def test_explicit_symptom_negation_accepts_none(self):
        state = RunState(chief_complaint="胃胀", duration="三天")
        turn_output = TurnOutput(
            symptoms=[],
            symptoms_status="none",
            risk_flags_status="unknown",
            summary="否认腹痛。",
        )

        merged = merge_turn_fields(state, turn_output, "胃胀三天，没有腹痛")

        self.assertEqual(merged.symptoms_status, "none")

    def test_unmentioned_risks_do_not_accept_model_none(self):
        state = RunState(chief_complaint="胃胀", duration="三天")
        turn_output = TurnOutput(
            symptoms_status="unknown",
            risk_flags=[],
            risk_flags_status="none",
            summary="未提风险。",
        )

        merged = merge_turn_fields(state, turn_output, "胃胀三天了")

        self.assertEqual(merged.risk_flags_status, "unknown")

    def test_explicit_risk_negation_accepts_none(self):
        state = RunState(chief_complaint="胃胀", duration="三天")
        turn_output = TurnOutput(
            symptoms_status="unknown",
            risk_flags=[],
            risk_flags_status="none",
            summary="否认胸痛。",
        )

        merged = merge_turn_fields(state, turn_output, "胃胀三天，没有胸痛")

        self.assertEqual(merged.risk_flags_status, "none")


if __name__ == "__main__":
    unittest.main()
