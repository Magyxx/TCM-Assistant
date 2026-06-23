from __future__ import annotations

import unittest

from scripts.device2.eval_compare_backends import (
    P6C_BUILTIN_CASES,
    classify_failure_types,
    compute_metrics,
    hallucinated_fields,
    predictions_are_sample_safe,
)


class Device2P6CMetricsTests(unittest.TestCase):
    def test_metrics_calculation_counts_rates_and_latency(self) -> None:
        cases = P6C_BUILTIN_CASES[:2]
        predictions = [
            {
                "case_id": cases[0]["case_id"],
                "backend": "local_lora",
                "final_turn_output": {
                    "chief_complaint": "胃胀",
                    "duration": "一周",
                    "risk_flags": [],
                    "risk_flags_status": "none",
                },
                "json_valid": True,
                "schema_pass": True,
                "fallback_used": False,
                "latency_ms": 10.0,
                "failure_types": [],
                "hallucinated_fields": [],
                "skipped": False,
            },
            {
                "case_id": cases[1]["case_id"],
                "backend": "local_lora",
                "final_turn_output": {
                    "chief_complaint": "咳嗽",
                    "duration": "三天",
                    "risk_flags": [],
                    "risk_flags_status": "none",
                },
                "json_valid": True,
                "schema_pass": True,
                "fallback_used": False,
                "latency_ms": 20.0,
                "failure_types": [],
                "hallucinated_fields": [],
                "skipped": False,
            },
        ]

        metrics = compute_metrics("local_lora", cases, predictions)

        self.assertEqual(metrics["case_count"], 2)
        self.assertEqual(metrics["json_valid_rate"], 1.0)
        self.assertEqual(metrics["schema_pass_rate"], 1.0)
        self.assertEqual(metrics["chief_complaint_match_rate"], 1.0)
        self.assertEqual(metrics["duration_match_rate"], 1.0)
        self.assertEqual(metrics["negation_accuracy"], 1.0)
        self.assertEqual(metrics["latency_ms_avg"], 15.0)

    def test_invalid_json_counts_as_structured_error(self) -> None:
        cases = [P6C_BUILTIN_CASES[5]]
        predictions = [
            {
                "case_id": cases[0]["case_id"],
                "backend": "local_base",
                "final_turn_output": None,
                "json_valid": False,
                "schema_pass": False,
                "fallback_used": False,
                "latency_ms": 5.0,
                "failure_types": ["invalid_json"],
                "hallucinated_fields": [],
                "skipped": False,
            }
        ]

        metrics = compute_metrics("local_base", cases, predictions)

        self.assertEqual(metrics["json_valid_rate"], 0.0)
        self.assertEqual(metrics["schema_pass_rate"], 0.0)
        self.assertEqual(metrics["structured_error_rate"], 1.0)
        self.assertEqual(metrics["failure_type_counts"]["invalid_json"], 1)

    def test_hallucination_detector_flags_unmentioned_risk_fields(self) -> None:
        case = P6C_BUILTIN_CASES[-1]

        fields = hallucinated_fields(
            case["user_input"],
            case["expected"],
            {"risk_flags": ["胸痛"], "risk_flags_status": "present"},
        )

        self.assertIn("risk_flags", fields)

    def test_failure_classifier_marks_negation_and_hallucination(self) -> None:
        case = P6C_BUILTIN_CASES[0]

        failures = classify_failure_types(
            case=case,
            json_valid=True,
            schema_pass=True,
            fallback_used=False,
            final_output={"risk_flags": ["胸痛"], "risk_flags_status": "present"},
            hallucinated=["risk_flags"],
            skipped=False,
        )

        self.assertIn("negation_error", failures)
        self.assertIn("risk_false_positive", failures)
        self.assertIn("hallucination", failures)

    def test_predictions_sample_rejects_weight_paths(self) -> None:
        self.assertFalse(
            predictions_are_sample_safe(
                [{"raw_output": "adapter_model.safetensors", "model_name": "mock"}]
            )
        )
        self.assertTrue(predictions_are_sample_safe([{"raw_output": "{}", "model_name": "mock"}]))


if __name__ == "__main__":
    unittest.main()
