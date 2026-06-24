from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_p2_p10_release_hardening import (
    ArtifactSpec,
    build_boundary_summary,
    decide_status,
    summarize_artifacts,
)


class P2P10ReleaseHardeningTests(unittest.TestCase):
    def test_artifact_summary_accepts_hardened_route(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "p1f6.json").write_text(
                json.dumps(
                    {"status": "ok", "completion": {"post_p8_productization_ready": True}},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (root / "p10m2.json").write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "knowledge_built": True,
                        "hybrid_rag_passed": True,
                        "citation_passed": True,
                        "rag_guard_passed": True,
                        "safety_redteam_passed": True,
                        "final_eval_passed": True,
                        "api_rag_passed": True,
                        "export_passed": True,
                        "docker_files_present": True,
                        "secret_scan_passed": True,
                        "p10m1_regression_passed": True,
                        "p9m2_regression_passed": True,
                        "lora_contract_present": True,
                        "failure_memory_built": True,
                        "safety_gates": {
                            "diagnosis_violation": 0,
                            "prescription_violation": 0,
                            "secret_log_leak_count": 0,
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (root / "p10m3.json").write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "checks": {"local_lora_mock_passed": True, "live_smoke_non_blocking": True},
                        "live_smoke": {"status": "skipped"},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (root / "m4a.json").write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "checks": [{"ok": True}],
                        "lora_artifacts": {"model_weights_committed": False},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (root / "packaging.json").write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "checks_total": 2,
                        "checks_passed": 2,
                        "errors": [],
                        "boundary_violated": False,
                        "contract_changed": False,
                        "sqlite_schema_changed": False,
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
                    ArtifactSpec("p1_f6_post_p8_productization_final", Path("p1f6.json")),
                    ArtifactSpec("p10m2_core_validation", Path("p10m2.json")),
                    ArtifactSpec("p10m3_local_lora_backend", Path("p10m3.json")),
                    ArtifactSpec("p10_m4a_extractor_contract", Path("m4a.json")),
                    ArtifactSpec("release_packaging_check", Path("packaging.json")),
                    ArtifactSpec("secret_scan", Path("secret.json")),
                ],
            )

        self.assertTrue(all(item["ok"] for item in summaries))
        self.assertEqual(
            decide_status([{"name": "cmd", "status": "ok"}], summaries, build_boundary_summary()),
            "ok",
        )

    def test_p10m2_safety_gate_or_lora_weights_block_release(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "p10m2.json").write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "knowledge_built": True,
                        "hybrid_rag_passed": True,
                        "citation_passed": True,
                        "rag_guard_passed": True,
                        "safety_redteam_passed": True,
                        "final_eval_passed": True,
                        "api_rag_passed": True,
                        "export_passed": True,
                        "docker_files_present": True,
                        "secret_scan_passed": True,
                        "p10m1_regression_passed": True,
                        "p9m2_regression_passed": True,
                        "lora_contract_present": True,
                        "failure_memory_built": True,
                        "safety_gates": {"diagnosis_violation": 1},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (root / "m4a.json").write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "checks": [{"ok": True}],
                        "lora_artifacts": {"model_weights_committed": True},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            summaries = summarize_artifacts(
                root,
                [
                    ArtifactSpec("p10m2_core_validation", Path("p10m2.json")),
                    ArtifactSpec("p10_m4a_extractor_contract", Path("m4a.json")),
                ],
            )

        self.assertFalse(summaries[0]["ok"])
        self.assertFalse(summaries[1]["ok"])
        self.assertEqual(
            decide_status([{"name": "cmd", "status": "ok"}], summaries, build_boundary_summary()),
            "failed",
        )

    def test_boundary_requires_local_release_and_no_device2_merge(self) -> None:
        boundary = build_boundary_summary()

        self.assertTrue(boundary["release_package_local_engineering_candidate"])
        self.assertTrue(boundary["not_production_medical_product"])
        self.assertFalse(boundary["legacy_p1_gate_authoritative"])
        self.assertTrue(boundary["no_device2_lora_merge"])
        self.assertTrue(boundary["real_llm_optional_and_disabled_by_default"])


if __name__ == "__main__":
    unittest.main()
