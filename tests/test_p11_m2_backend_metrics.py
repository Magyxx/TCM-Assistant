from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app.extractors.router import get_extractor_backend
from app.schemas.report_schemas import RunState


class P11M2BackendMetricsTests(unittest.TestCase):
    def test_backend_summaries_record_metrics_and_error_boundaries(self) -> None:
        env = {
            "ENABLE_REAL_LLM": "false",
            "TCM_ALLOW_REAL_LLM": "false",
        }
        with patch.dict(os.environ, env, clear=False):
            results = {
                "fake": get_extractor_backend("fake").extract("stomach discomfort", state=RunState()),
                "fallback": get_extractor_backend("fallback").extract("stomach discomfort", state=RunState()),
                "real_llm": get_extractor_backend("real_llm").extract("stomach discomfort", state=RunState()),
            }

        for mode, result in results.items():
            with self.subTest(mode=mode):
                summary = result.contract_summary()
                self.assertIsNotNone(summary["latency_ms"])
                self.assertGreaterEqual(float(summary["latency_ms"]), 0.0)
                self.assertIn(summary["fallback_used"], {True, False})
                self.assertIn(summary["schema_pass"], {True, False})
                self.assertIn("skip_reason", summary)
                self.assertIn("error_type", summary)

        self.assertFalse(results["fake"].contract_summary()["fallback_used"])
        self.assertTrue(results["fallback"].contract_summary()["fallback_used"])
        self.assertTrue(results["real_llm"].contract_summary()["fallback_used"])
        self.assertEqual(results["real_llm"].contract_summary()["skip_reason"], "ENABLE_REAL_LLM=false")


if __name__ == "__main__":
    unittest.main()
