from __future__ import annotations

import argparse
import shutil
import unittest
from pathlib import Path

from scripts.device2.backend_eval_utils import compute_backend_metrics, load_eval_cases
from scripts.device2.eval_backend_compare import run


ROOT = Path(__file__).resolve().parents[1]


class Device2BackendCompareTests(unittest.TestCase):
    def test_builtin_cases_load(self) -> None:
        cases, metadata = load_eval_cases(limit=20)

        self.assertEqual(len(cases), 20)
        self.assertTrue(metadata["builtin_cases"] or metadata["case_source"].endswith(".jsonl"))

    def test_metrics_generate(self) -> None:
        records = [
            {
                "case_id": "c1",
                "backend": "local_lora",
                "input": "胸痛半小时",
                "parsed_json": {"chief_complaint": "胸痛", "risk_flags_status": "present", "risk_flags": ["胸痛"]},
                "json_valid": True,
                "schema_pass": True,
                "fallback_used": False,
                "latency_ms": 10,
                "error": None,
            }
        ]

        metrics = compute_backend_metrics("local_lora", records)

        self.assertEqual(metrics["case_count"], 1)
        self.assertEqual(metrics["json_valid_rate"], 1.0)
        self.assertEqual(metrics["schema_pass_rate"], 1.0)
        self.assertEqual(metrics["status"], "ok")

    def test_dry_run_skips_unavailable_backends_without_failure(self) -> None:
        tmpdir = ROOT / "artifacts" / "tmp" / "backend_compare_test"
        shutil.rmtree(tmpdir, ignore_errors=True)
        try:
            args = argparse.Namespace(
                base_url="http://127.0.0.1:9/v1",
                api_key="EMPTY",
                local_base_model="/tmp/base",
                local_lora_model="tcm-extractor-lora",
                cases=None,
                limit=2,
                dry_run=True,
                require_local_lora=False,
                output_predictions=tmpdir / "predictions.jsonl",
                output_metrics=tmpdir / "metrics.json",
                output_report=tmpdir / "report.md",
            )

            payload, exit_code = run(args)

            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["skipped"]["local_lora"], "dry_run")
            self.assertTrue((tmpdir / "predictions.jsonl").exists())
            self.assertTrue((tmpdir / "metrics.json").exists())
            self.assertTrue((tmpdir / "report.md").exists())
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_required_local_lora_failure_exits_nonzero(self) -> None:
        tmpdir = ROOT / "artifacts" / "tmp" / "backend_compare_required_test"
        shutil.rmtree(tmpdir, ignore_errors=True)
        try:
            args = argparse.Namespace(
                base_url="http://127.0.0.1:9/v1",
                api_key="EMPTY",
                local_base_model="/tmp/base",
                local_lora_model="tcm-extractor-lora",
                cases=None,
                limit=2,
                dry_run=True,
                require_local_lora=True,
                output_predictions=tmpdir / "predictions.jsonl",
                output_metrics=tmpdir / "metrics.json",
                output_report=tmpdir / "report.md",
            )

            payload, exit_code = run(args)

            self.assertEqual(payload["status"], "failed")
            self.assertEqual(exit_code, 1)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
