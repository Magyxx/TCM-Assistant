from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_release_candidate_audit import (
    ArtifactSpec,
    build_boundary_summary,
    build_worktree_package,
    decide_status,
    parse_status_lines,
    summarize_artifacts,
)


class ReleaseCandidateAuditTests(unittest.TestCase):
    def test_parse_status_lines_groups_renames_and_untracked_paths(self) -> None:
        entries = parse_status_lines(
            [
                " M docs/PRODUCT_FINAL_DESIGN.md",
                "?? scripts/verify_release_candidate_audit.py",
                "R  old.py -> app/new.py",
            ]
        )

        self.assertEqual(entries[0]["top_level"], "docs")
        self.assertEqual(entries[1]["status"], "??")
        self.assertEqual(entries[2]["path"], "app/new.py")

    def test_worktree_package_accepts_required_groups_and_rejects_forbidden_paths(self) -> None:
        clean_package = build_worktree_package(
            [
                " M app/api/main.py",
                "?? scripts/verify_release_candidate_audit.py",
                "?? tests/test_release_candidate_audit.py",
                "?? docs/RELEASE_CANDIDATE_AUDIT.md",
                "?? artifacts/release_candidate_audit.json",
            ],
            [
                "app/api/main.py",
                "scripts/verify_release_candidate_audit.py",
                "tests/test_release_candidate_audit.py",
                "docs/RELEASE_CANDIDATE_AUDIT.md",
                "artifacts/release_candidate_audit.json",
            ],
        )
        forbidden_package = build_worktree_package(
            [
                "?? app/api/main.py",
                "?? scripts/verify.py",
                "?? tests/test_verify.py",
                "?? docs/RC.md",
                "?? artifacts/model-adapter.safetensors",
            ],
            ["artifacts/model-adapter.safetensors"],
        )

        self.assertTrue(clean_package["commit_package_ready"])
        self.assertEqual(clean_package["worktree_mode"], "commit_package")
        self.assertTrue(clean_package["forbidden_paths_ok"])
        self.assertFalse(forbidden_package["commit_package_ready"])
        self.assertFalse(forbidden_package["forbidden_paths_ok"])

    def test_worktree_package_accepts_clean_clone_validation_outputs_only(self) -> None:
        package = build_worktree_package(
            [
                " M artifacts/release_candidate_audit.json",
                " M knowledge/eval/p6_retrieval_safety_eval.json",
                "?? artifacts/p10m2/exports/example.md",
            ],
            [
                "artifacts/release_candidate_audit.json",
                "knowledge/eval/p6_retrieval_safety_eval.json",
                "artifacts/p10m2/exports/example.md",
            ],
        )
        app_only_package = build_worktree_package(
            [" M app/api/main.py"],
            ["app/api/main.py"],
        )

        self.assertTrue(package["clean_clone_reproducibility_ready"])
        self.assertEqual(package["worktree_mode"], "clean_clone_reproducibility")
        self.assertFalse(app_only_package["clean_clone_reproducibility_ready"])
        self.assertEqual(app_only_package["worktree_mode"], "not_ready")

    def test_artifact_summary_requires_release_hardening_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "hardening.json").write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "release_hardening_ready": True,
                        "failed_commands": [],
                        "failed_artifacts": [],
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
                    ArtifactSpec("p2_p10_release_hardening", Path("hardening.json")),
                    ArtifactSpec("secret_scan", Path("secret.json")),
                ],
            )

        self.assertTrue(all(item["ok"] for item in summaries))

    def test_decide_status_requires_package_and_boundary(self) -> None:
        commands = [{"name": "cmd", "status": "ok"}]
        artifacts = [{"name": "artifact", "ok": True}]
        package = {
            "commit_package_ready": True,
            "forbidden_paths_ok": True,
        }
        boundary = build_boundary_summary()

        self.assertEqual(decide_status(commands, artifacts, package, boundary), "ok")

        clean_clone_package = {
            "commit_package_ready": False,
            "clean_clone_reproducibility_ready": True,
            "forbidden_paths_ok": True,
        }
        self.assertEqual(decide_status(commands, artifacts, clean_clone_package, boundary), "ok")

        bad_boundary = dict(boundary)
        bad_boundary["git_commit_requires_explicit_user_approval"] = False
        self.assertEqual(decide_status(commands, artifacts, package, bad_boundary), "failed")


if __name__ == "__main__":
    unittest.main()
