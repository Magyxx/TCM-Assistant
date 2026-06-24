from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from app.graph.consultation_graph import run_consultation_graph
from app.graph.runner import run_p9m1_graph
from app.schemas.report_schemas import RunState


COMPLETE_FAKE_INPUT = "胃胀一周，没有其他症状，睡眠一般，食欲一般，大便正常，小便正常，没有胸痛，没有呼吸困难，没有便血"


class P1F1GraphIntegrationTests(unittest.TestCase):
    def test_p8_graph_records_p1_evidence_pack_and_report_skeleton(self) -> None:
        state = RunState(
            chief_complaint="stomach discomfort",
            duration="two days",
            symptoms_status="none",
            risk_flags_status="none",
        )
        before = state.model_dump()
        result = run_consultation_graph(
            state,
            "sleep is not good",
            use_langgraph=False,
            extractor_mode="fake",
            rag_enabled=True,
        )
        metadata = result["run_state"].metadata
        pack = metadata["p1_f1_evidence_pack"]
        skeleton = metadata["p1_f1_report_skeleton"]
        self.assertEqual(pack["backend"], "bm25_realpath")
        self.assertTrue(pack["chunks"])
        self.assertEqual(skeleton["evidence_pack"]["backend"], "bm25_realpath")
        self.assertTrue(skeleton["safety_disclaimer"])
        self.assertTrue(metadata["p1_f1_rag_core_field_overwrite_blocked"])
        after = result["run_state"].model_dump()
        for field in ["chief_complaint", "duration", "risk_flags_status", "triggered_rule_ids"]:
            self.assertEqual(before[field], after[field])

    def test_p9_graph_exports_p1_pack_and_skeleton_in_final_report(self) -> None:
        result = run_p9m1_graph(
            COMPLETE_FAKE_INPUT,
            extractor_backend="fake",
            use_langgraph=False,
        )
        self.assertEqual(result["p1_evidence_pack"]["backend"], "bm25_realpath")
        self.assertTrue(result["p1_evidence_pack"]["chunks"])
        self.assertEqual(result["p1_report_skeleton"]["evidence_pack"]["backend"], "bm25_realpath")
        self.assertEqual(
            result["final_report"]["metadata"]["p1_f1_evidence_pack"]["backend"],
            "bm25_realpath",
        )
        self.assertTrue(result["final_report"]["metadata"]["rag_core_fields_read_only"])

    def test_verify_script_writes_p1_f1_artifact(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "p1_f1.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/verify_p1_f1_graph_integration.py",
                    "--json",
                    "--output",
                    str(output),
                ],
                cwd=root,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=120,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "ok")
            self.assertFalse(payload["external_dependencies_required"])
            self.assertEqual(payload["checks"]["no_embedding_required"], "passed")


if __name__ == "__main__":
    unittest.main()
