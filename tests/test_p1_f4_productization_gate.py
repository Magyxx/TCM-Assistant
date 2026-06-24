from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_p1_f4_productization_gate import (
    ArtifactSpec,
    build_boundary_summary,
    decide_status,
    summarize_artifacts,
)


class P1F4ProductizationGateTests(unittest.TestCase):
    def test_artifact_summary_requires_ok_status_and_zero_secret_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ok.json").write_text(
                json.dumps({"status": "ok", "stage": "P1-FX"}, ensure_ascii=False),
                encoding="utf-8",
            )
            (root / "secret.json").write_text(
                json.dumps({"status": "ok", "finding_count": 0}, ensure_ascii=False),
                encoding="utf-8",
            )

            summaries = summarize_artifacts(
                root,
                [
                    ArtifactSpec("stage", Path("ok.json")),
                    ArtifactSpec("secret_scan", Path("secret.json")),
                ],
            )

        self.assertTrue(all(item["ok"] for item in summaries))
        self.assertEqual(summaries[0]["stage"], "P1-FX")
        self.assertEqual(summaries[1]["finding_count"], 0)

    def test_secret_scan_findings_fail_artifact_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "secret.json").write_text(
                json.dumps({"status": "ok", "finding_count": 1}, ensure_ascii=False),
                encoding="utf-8",
            )

            summaries = summarize_artifacts(root, [ArtifactSpec("secret_scan", Path("secret.json"))])

        self.assertFalse(summaries[0]["ok"])

    def test_decide_status_requires_commands_artifacts_and_post_p8_boundary(self) -> None:
        commands = [{"name": "compileall", "status": "ok"}]
        artifacts = [{"name": "p1_f0", "ok": True}]
        boundary = build_boundary_summary()

        self.assertEqual(decide_status(commands, artifacts, boundary), "ok")

        drifted_boundary = dict(boundary)
        drifted_boundary["legacy_p1_gate_authoritative"] = True
        self.assertEqual(decide_status(commands, artifacts, drifted_boundary), "failed")

        failed_artifacts = [{"name": "p1_f0", "ok": False}]
        self.assertEqual(decide_status(commands, failed_artifacts, boundary), "failed")


if __name__ == "__main__":
    unittest.main()
