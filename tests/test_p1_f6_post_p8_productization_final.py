from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.report.audit import REPORT_AUDIT_SCHEMA_VERSION
from scripts.verify_p1_f6_post_p8_productization_final import (
    ArtifactSpec,
    build_boundary_summary,
    build_completion_decision,
    decide_status,
    summarize_artifacts,
)


class P1F6PostP8ProductizationFinalTests(unittest.TestCase):
    def test_artifact_summary_requires_all_post_p8_stages_and_f5_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "f4.json").write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "stage": "P1-F4_PRODUCTIZATION_GATE",
                        "commands_failed": 0,
                        "failed_artifacts": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (root / "f5.json").write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "stage": "P1-F5_REPORT_SAFETY_REDACTION_AUDIT",
                        "report_audit_schema_version": REPORT_AUDIT_SCHEMA_VERSION,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (root / "secret.json").write_text(
                json.dumps({"status": "ok", "finding_count": 0}, ensure_ascii=False),
                encoding="utf-8",
            )

            summaries = summarize_artifacts(
                root,
                [
                    ArtifactSpec("p1_f4_productization_gate", Path("f4.json")),
                    ArtifactSpec("p1_f5_report_audit", Path("f5.json")),
                    ArtifactSpec("secret_scan", Path("secret.json")),
                ],
            )

        self.assertTrue(all(item["ok"] for item in summaries))
        self.assertEqual(summaries[1]["report_audit_schema_version"], REPORT_AUDIT_SCHEMA_VERSION)
        self.assertEqual(summaries[2]["finding_count"], 0)

    def test_failed_f5_schema_or_secret_scan_blocks_final_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "f5.json").write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "report_audit_schema_version": "old_schema",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (root / "secret.json").write_text(
                json.dumps({"status": "ok", "finding_count": 1}, ensure_ascii=False),
                encoding="utf-8",
            )

            summaries = summarize_artifacts(
                root,
                [
                    ArtifactSpec("p1_f5_report_audit", Path("f5.json")),
                    ArtifactSpec("secret_scan", Path("secret.json")),
                ],
            )

        self.assertFalse(summaries[0]["ok"])
        self.assertFalse(summaries[1]["ok"])
        self.assertEqual(decide_status([{"name": "cmd", "status": "ok"}], summaries, build_boundary_summary()), "failed")

    def test_boundary_marks_post_p8_route_as_authoritative(self) -> None:
        boundary = build_boundary_summary()

        self.assertTrue(boundary["post_p8_route_authoritative"])
        self.assertFalse(boundary["legacy_p1_gate_authoritative"])
        self.assertTrue(boundary["p8_m3_follow_up_project_started"])
        self.assertTrue(boundary["no_device2_lora_merge"])
        self.assertEqual(boundary["report_audit_schema_version"], REPORT_AUDIT_SCHEMA_VERSION)

    def test_completion_decision_recommends_next_only_when_ready(self) -> None:
        ready = build_completion_decision(
            "ok",
            [{"name": "cmd", "status": "ok"}],
            [{"name": "artifact", "ok": True}],
        )
        held = build_completion_decision(
            "failed",
            [{"name": "cmd", "status": "failed"}],
            [{"name": "artifact", "ok": False}],
        )

        self.assertTrue(ready["post_p8_productization_ready"])
        self.assertEqual(ready["recommend_next"], "P2/P10 release hardening and packaging")
        self.assertFalse(held["post_p8_productization_ready"])
        self.assertEqual(held["recommend_next"], "hold")
        self.assertEqual(held["failed_commands"], ["cmd"])
        self.assertEqual(held["failed_artifacts"], ["artifact"])


if __name__ == "__main__":
    unittest.main()
