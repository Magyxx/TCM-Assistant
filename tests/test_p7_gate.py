from __future__ import annotations

import unittest
from unittest.mock import patch

from scripts.run_p7_gate import run_p7_gate


def _ok(name: str = "ok") -> dict:
    return {"status": "ok", "metrics": {}, "checks": [], "name": name}


class P7GateTests(unittest.TestCase):
    def test_gate_aggregates_ok_metrics(self) -> None:
        api = {"status": "ok", "metrics": {"api_health_ok": True, "api_session_create_ok": True, "api_turn_ok": True, "api_report_ok": True, "api_state_restore_ok": True}}
        storage = {"status": "ok", "metrics": {"storage_roundtrip_pass": True, "storage_error_count": 0, "rag_evidence_persistence_pass": True}}
        memory = {"status": "ok", "metrics": {"memory_l1_pass": True, "memory_l2_fact_write_pass": True, "memory_l3_summary_pass": True, "memory_l4_privacy_pass": True, "memory_source_traceability_pass": True}}
        tools = {"status": "ok", "metrics": {"tool_registry_schema_pass": True, "tool_permission_violation_count": 0, "tool_audit_log_pass": True}}
        observability = {"status": "ok", "metrics": {"trace_schema_pass": True, "trace_storage_pass": True, "fallback_used_rate": 0.0}}
        safety = {"status": "ok", "metrics": {"rag_boundary_pass": True, "core_state_mutation_count_by_rag": 0, "report_safety_violation_count": 0, "diagnosis_or_prescription_violation_count": 0, "high_risk_false_negative_count": 0, "negation_accuracy": 1.0}}
        docker = {"status": "ok", "metrics": {"docker_smoke_pass": True}}
        with patch("scripts.run_p7_gate.run_p7_api_validation", return_value=api), \
            patch("scripts.run_p7_gate.run_p7_storage_validation", return_value=storage), \
            patch("scripts.run_p7_gate.run_p7_memory_validation", return_value=memory), \
            patch("scripts.run_p7_gate.run_p7_tool_registry_validation", return_value=tools), \
            patch("scripts.run_p7_gate.run_p7_observability_validation", return_value=observability), \
            patch("scripts.run_p7_gate.run_p7_safety_validation", return_value=safety), \
            patch("scripts.run_p7_gate.run_p7_docker_smoke", return_value=docker), \
            patch("scripts.run_p7_gate.run_p7_failure_analysis", return_value={"status": "ok", "cautions": []}), \
            patch("scripts.run_p7_gate.run_p5_validation", return_value={"validation": {"status": "ok", "metrics_table": {}}}), \
            patch("scripts.run_p7_gate.run_p5_demo_cases", return_value={"status": "ok"}), \
            patch("scripts.run_p7_gate.run_p6_pipeline", return_value={"status": "ok"}), \
            patch("scripts.run_p7_gate.run_p6b_runtime_rag_validation", return_value={"status": "ok"}), \
            patch("scripts.run_p7_gate.run_p6c_gate", return_value={"status": "ok"}), \
            patch("scripts.run_p7_gate._command_checks", return_value=[]), \
            patch("scripts.run_p7_gate._json_checks", return_value=[]), \
            patch("scripts.run_p7_gate.read_json", return_value={"hard_gate_status": "ok"}):
            result = run_p7_gate(write_artifact=False, run_unittest=False, run_compileall=False, run_docker=True)

        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["metrics"]["api_turn_ok"])
        self.assertTrue(result["metrics"]["docker_smoke_pass"])


if __name__ == "__main__":
    unittest.main()
