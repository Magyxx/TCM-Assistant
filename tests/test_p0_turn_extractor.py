import json
import os
import unittest

from app.chains.turn_extractor import (
    _json_prompt_loads_turn_output,
    extract_turn,
    extract_with_fake_structured_output,
    extract_with_rule_fallback,
)
import app.chains.turn_extractor as turn_extractor
from app.schemas.report_schemas import RunState, TurnOutput


class P0TurnExtractorTest(unittest.TestCase):
    def test_normal_json_output_passes_schema(self):
        raw = json.dumps(
            {
                "chief_complaint": "胃胀",
                "duration": "两天",
                "symptoms": [],
                "symptoms_status": "none",
                "sleep": None,
                "appetite": None,
                "stool_urine": None,
                "risk_flags": [],
                "risk_flags_status": "none",
                "next_question": None,
                "summary": "已整理问诊信息。",
            },
            ensure_ascii=False,
        )

        result = extract_with_fake_structured_output(RunState(), "我胃胀两天", raw_text=raw)

        self.assertTrue(result.raw_llm_json_valid)
        self.assertTrue(result.final_schema_pass)
        self.assertFalse(result.fallback_used)
        self.assertIsInstance(result.turn_output, TurnOutput)

    def test_non_json_output_enters_fallback(self):
        result = extract_with_fake_structured_output(RunState(), "我胃胀", raw_text="not json")

        self.assertEqual(result.mode, "rule_fallback")
        self.assertFalse(result.raw_llm_json_valid)
        self.assertTrue(result.final_schema_pass)
        self.assertTrue(result.fallback_used)

    def test_high_fever_sets_risk_fields(self):
        result = extract_with_fake_structured_output(RunState(), "我持续高烧三天")

        self.assertTrue(result.raw_llm_json_valid)
        self.assertEqual(result.turn_output.risk_flags_status, "present")
        self.assertIn("持续高热", result.turn_output.risk_flags)

    def test_negated_fever_and_chest_pain_not_present(self):
        result = extract_with_fake_structured_output(RunState(), "没有发热，也不胸痛")

        self.assertNotEqual(result.turn_output.risk_flags_status, "present")
        self.assertNotIn("胸痛", result.turn_output.risk_flags)

    def test_schema_metrics_do_not_depend_on_real_llm(self):
        fake = extract_with_fake_structured_output(RunState(), "我咳嗽两天，没有其他症状，也没有胸痛")
        fallback = extract_with_rule_fallback(RunState(), "我咳嗽")

        self.assertTrue(fake.raw_llm_json_valid)
        self.assertTrue(fake.final_schema_pass)
        self.assertFalse(fake.fallback_used)
        self.assertFalse(fallback.raw_llm_json_valid)
        self.assertTrue(fallback.final_schema_pass)
        self.assertTrue(fallback.fallback_used)

    def test_real_llm_missing_api_config_falls_back(self):
        old_values = {
            "OPENAI_API_KEY": os.environ.pop("OPENAI_API_KEY", None),
            "OPENAI_BASE_URL": os.environ.pop("OPENAI_BASE_URL", None),
            "OPENAI_MODEL": os.environ.pop("OPENAI_MODEL", None),
        }
        try:
            result = extract_turn(RunState(), "我胃胀两天", extractor_mode="real_llm")
        finally:
            for key, value in old_values.items():
                if value is not None:
                    os.environ[key] = value

        self.assertEqual(result.extractor_mode, "real_llm")
        self.assertTrue(result.fallback_used)
        self.assertEqual(result.error_type, "missing_api_config")
        self.assertEqual(result.strategy, "rule_fallback")

    def test_real_llm_runtime_failure_keeps_real_llm_mode_with_fallback(self):
        old_values = {
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
            "OPENAI_BASE_URL": os.environ.get("OPENAI_BASE_URL"),
            "OPENAI_MODEL": os.environ.get("OPENAI_MODEL"),
        }
        original_provider = turn_extractor.extract_with_provider_native_structured_output
        original_tool = turn_extractor.extract_with_tool_calling_structured_output
        original_json = turn_extractor.extract_with_json_prompt_fallback

        os.environ["OPENAI_API_KEY"] = "test-key"
        os.environ["OPENAI_BASE_URL"] = "https://example.test/v1"
        os.environ["OPENAI_MODEL"] = "test-model"
        turn_extractor.extract_with_provider_native_structured_output = lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("AuthenticationError: api key: sk-secret is invalid")
        )
        turn_extractor.extract_with_tool_calling_structured_output = lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("should_not_run")
        )
        turn_extractor.extract_with_json_prompt_fallback = lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("should_not_run")
        )

        try:
            result = extract_turn(RunState(), "我胃胀两天", extractor_mode="real_llm")
        finally:
            turn_extractor.extract_with_provider_native_structured_output = original_provider
            turn_extractor.extract_with_tool_calling_structured_output = original_tool
            turn_extractor.extract_with_json_prompt_fallback = original_json
            for key, value in old_values.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        self.assertEqual(result.extractor_mode, "real_llm")
        self.assertEqual(result.strategy, "rule_fallback")
        self.assertTrue(result.fallback_used)
        self.assertEqual(result.error_type, "authentication_error")
        self.assertNotIn("sk-secret", result.error or "")

    def test_json_prompt_parser_accepts_valid_json(self):
        raw = json.dumps(
            {
                "chief_complaint": "胃胀",
                "duration": "两天",
                "symptoms": [],
                "symptoms_status": "unknown",
                "risk_flags": [],
                "risk_flags_status": "none",
            },
            ensure_ascii=False,
        )

        parsed = _json_prompt_loads_turn_output(raw)

        self.assertEqual(parsed.chief_complaint, "胃胀")
        self.assertEqual(parsed.duration, "两天")

    def test_extra_diagnosis_fields_do_not_enter_schema(self):
        raw = json.dumps(
            {
                "chief_complaint": "胃胀",
                "duration": None,
                "symptoms": [],
                "symptoms_status": "unknown",
                "risk_flags": [],
                "risk_flags_status": "unknown",
                "diagnosis": "不应进入 schema",
                "prescription": "不应进入 schema",
            },
            ensure_ascii=False,
        )

        result = extract_with_fake_structured_output(RunState(), "胃胀", raw_text=raw)

        dumped = result.turn_output.model_dump()
        self.assertNotIn("diagnosis", dumped)
        self.assertNotIn("prescription", dumped)


if __name__ == "__main__":
    unittest.main()
