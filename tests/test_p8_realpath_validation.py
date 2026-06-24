from __future__ import annotations

import unittest

from scripts.verify_p8_realpath import _classify_unittest, build_safety_gates, decide_ready


class P8RealpathValidationTests(unittest.TestCase):
    def test_classifies_unittest_ok_marker(self) -> None:
        detail = _classify_unittest(
            stdout="",
            stderr="Ran 42 tests in 1.234s\n\nOK\n",
            return_code=0,
            timed_out=False,
        )

        self.assertEqual(detail["classification"], "ok")
        self.assertEqual(detail["ran_count"], 42)
        self.assertEqual(detail["duration_seconds"], 1.234)
        self.assertTrue(detail["content_ok"])

    def test_failed_gate_blocks_merge_and_p1_readiness(self) -> None:
        command_checks = {
            "compileall": {"ok": True},
            "unittest": {"ok": True},
            "secret_scan": {"ok": True, "finding_count": 0},
        }
        memory = {
            "risk_guard": "passed",
            "rag_core_field_guard": "passed",
        }
        graph = {"risk_guard": "passed"}
        extractor = {
            "llm_risk_overwrite_blocked": "failed",
            "turn_output_schema_guard": "passed",
        }
        rag = {"rag_guard": "passed", "report_safety": "passed"}
        artifact_parse = {
            "memory": {"exists": True, "json_parse_ok": True},
            "graph": {"exists": True, "json_parse_ok": True},
        }
        branch_safety = {"ok": True}

        safety_gates = build_safety_gates(
            command_checks,
            memory,
            graph,
            extractor,
            rag,
            artifact_parse,
            branch_safety,
        )
        readiness = decide_ready(safety_gates, command_checks, {}, artifact_parse)

        self.assertFalse(safety_gates["llm_risk_overwrite_blocked"])
        self.assertFalse(readiness["ready_for_main_merge"])
        self.assertFalse(readiness["ready_for_p1"])
        self.assertIn("safety_gate:llm_risk_overwrite_blocked", readiness["blockers"])

    def test_skipped_is_only_allowed_when_summary_remains_ok(self) -> None:
        command_checks = {
            "compileall": {"ok": True},
            "unittest": {"ok": True},
            "secret_scan": {"ok": True, "finding_count": 0},
        }
        p8_checks = {
            "graph": {"status": "passed"},
            "extractor": {"status": "passed"},
            "memory": {"status": "passed"},
            "rag": {"status": "failed"},
        }
        safety_gates = {
            "compileall_passed": True,
            "unittest_passed": True,
            "secret_scan_clean": True,
            "memory_risk_guard_passed": True,
        }
        artifact_parse = {"rag": {"exists": True, "json_parse_ok": True}}

        readiness = decide_ready(safety_gates, command_checks, p8_checks, artifact_parse)

        self.assertFalse(readiness["ready_for_main_merge"])
        self.assertIn("p8_check:rag", readiness["blockers"])


if __name__ == "__main__":
    unittest.main()
