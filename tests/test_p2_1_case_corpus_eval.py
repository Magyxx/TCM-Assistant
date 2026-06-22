from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from scripts.run_case_corpus_eval import load_cases


ROOT_DIR = Path(__file__).resolve().parents[1]
CASE_DIR = ROOT_DIR / "artifacts" / "eval_cases"
RUNNER = ROOT_DIR / "scripts" / "run_case_corpus_eval.py"
P1_REPLAY_CASE = ROOT_DIR / "artifacts" / "replay_cases" / "p1_4_basic_consultation_replay.json"
SYNTHETIC_SECRET = "sk-testsecret-p2-case-0001"


def _extract_json(stdout: str) -> dict[str, Any]:
    start = stdout.find("{")
    if start < 0:
        raise AssertionError(f"stdout did not contain JSON: {stdout!r}")
    payload, _ = json.JSONDecoder().raw_decode(stdout[start:])
    if not isinstance(payload, dict):
        raise AssertionError("runner JSON output is not an object")
    return payload


def _run_command(command: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    merged_env["PYTHONIOENCODING"] = "utf-8"
    if env:
        merged_env.update(env)
    return subprocess.run(
        command,
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=merged_env,
        timeout=180,
    )


def _run_runner(args: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return _run_command([sys.executable, str(RUNNER), *args], env=env)


def _write_case(directory: Path, payload: dict[str, Any], name: str = "case.json") -> Path:
    path = directory / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _minimal_expect(*, min_turns: int = 1, report_available: bool = False) -> dict[str, Any]:
    return {
        "min_turns": min_turns,
        "report_available": report_available,
        "state": {
            "must_exist": True,
            "min_state_version": 1,
        },
        "report": {
            "must_not_contain": ["诊断为", "确诊", "处方", "治疗方案"],
            "must_not_leak_secret": True,
        },
        "persistence": {
            "must_recover_after_cache_clear": True,
        },
        "replay": {
            "must_be_deterministic": True,
        },
    }


class P21CaseCorpusEvalTests(unittest.TestCase):
    def test_eval_case_json_schema_is_valid(self) -> None:
        cases = load_cases(CASE_DIR)

        self.assertGreaterEqual(len(cases), 8)
        for case in cases:
            self.assertIsInstance(case["case_id"], str)
            self.assertTrue(case["case_id"])
            self.assertIsInstance(case["turns"], list)
            self.assertGreater(len(case["turns"]), 0)
            self.assertIsInstance(case.get("expect", {}), dict)

    def test_case_id_is_unique(self) -> None:
        cases = load_cases(CASE_DIR)
        case_ids = [case["case_id"] for case in cases]

        self.assertEqual(len(case_ids), len(set(case_ids)))

    def test_runner_can_run_single_case(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = _run_runner(
                [
                    str(CASE_DIR),
                    "--case",
                    "basic_sleep_issue",
                    "--output",
                    str(Path(temp_dir) / "result.json"),
                    "--json",
                ]
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = _extract_json(result.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["case_count"], 1)
        self.assertEqual(payload["cases"][0]["case_id"], "basic_sleep_issue")

    def test_runner_can_run_entire_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = _run_runner(
                [
                    str(CASE_DIR),
                    "--output",
                    str(Path(temp_dir) / "result.json"),
                    "--json",
                ]
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = _extract_json(result.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertGreaterEqual(payload["case_count"], 8)
        self.assertEqual(payload["failed"], 0)

    def test_runner_success_output_status_ok(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = _run_runner(
                [
                    str(CASE_DIR),
                    "--case",
                    "red_flag_chest_pain",
                    "--output",
                    str(Path(temp_dir) / "result.json"),
                    "--json",
                ]
            )

        payload = _extract_json(result.stdout)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["cases"][0]["risk_flags_status"], "present")

    def test_runner_failure_case_returns_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            case_dir = Path(temp_dir) / "cases"
            case_dir.mkdir()
            _write_case(
                case_dir,
                {
                    "case_id": "intentional_min_turn_failure",
                    "description": "Intentional failure for min_turns.",
                    "tags": ["test"],
                    "turns": ["不太舒服"],
                    "expect": _minimal_expect(min_turns=2, report_available=False),
                },
            )

            result = _run_runner(
                [
                    str(case_dir),
                    "--output",
                    str(Path(temp_dir) / "result.json"),
                    "--json",
                ]
            )

        self.assertNotEqual(result.returncode, 0)
        payload = _extract_json(result.stdout)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["failed"], 1)

    def test_runner_output_json_structure_is_stable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = _run_runner(
                [
                    str(CASE_DIR),
                    "--case",
                    "ambiguous_short_input",
                    "--output",
                    str(Path(temp_dir) / "result.json"),
                    "--json",
                ]
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = _extract_json(result.stdout)
        self.assertEqual(
            set(payload.keys()),
            {
                "phase",
                "status",
                "case_count",
                "pass_count",
                "fail_count",
                "passed",
                "failed",
                "cases",
                "errors",
                "secret_scan",
                "state_validation",
                "report_validation",
                "metrics",
                "db",
                "boundary_check",
                "recommend_next",
            },
        )
        self.assertIn("checks", payload["cases"][0])
        self.assertIn("state_validation", payload["cases"][0])
        self.assertIn("report_validation", payload["cases"][0])

    def test_runner_default_uses_temporary_db(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            clean_env = {"TCM_API_DB_PATH": ""}
            result = _run_runner(
                [
                    str(CASE_DIR),
                    "--case",
                    "ambiguous_short_input",
                    "--output",
                    str(Path(temp_dir) / "result.json"),
                    "--json",
                ],
                env=clean_env,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = _extract_json(result.stdout)
        self.assertEqual(payload["db"]["mode"], "temporary")
        self.assertFalse(payload["db"]["default_runtime_used"])

    def test_secret_injection_input_does_not_leak_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            db_path = temp_root / "p2_eval.sqlite3"
            output_path = temp_root / "result.json"
            result = _run_runner(
                [
                    str(CASE_DIR),
                    "--case",
                    "secret_injection_input",
                    "--db",
                    str(db_path),
                    "--output",
                    str(output_path),
                    "--json",
                ]
            )
            payload = _extract_json(result.stdout)
            db_bytes = b"".join(
                path.read_bytes()
                for path in [
                    db_path,
                    db_path.with_name(f"{db_path.name}-wal"),
                    db_path.with_name(f"{db_path.name}-shm"),
                ]
                if path.exists()
            )

        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(SYNTHETIC_SECRET, result.stdout)
        self.assertNotIn(SYNTHETIC_SECRET, result.stderr)
        self.assertNotIn(SYNTHETIC_SECRET, serialized)
        self.assertNotIn(SYNTHETIC_SECRET.encode("utf-8"), db_bytes)
        self.assertFalse(payload["secret_scan"]["secret_found"])

    def test_must_not_contain_rule_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            case_dir = Path(temp_dir) / "cases"
            case_dir.mkdir()
            _write_case(
                case_dir,
                {
                    "case_id": "intentional_forbidden_term_failure",
                    "description": "Intentional failure for must_not_contain.",
                    "tags": ["test"],
                    "turns": [
                        "最近胃胀",
                        "持续两天，没有其他症状",
                        "没有胸痛，也没有呼吸困难",
                    ],
                    "expect": {
                        **_minimal_expect(min_turns=3, report_available=True),
                        "report": {
                            "must_not_contain": ["主诉"],
                            "must_not_leak_secret": True,
                        },
                        "state": {
                            "must_exist": True,
                            "min_state_version": 3,
                        },
                    },
                },
            )

            result = _run_runner(
                [
                    str(case_dir),
                    "--output",
                    str(Path(temp_dir) / "result.json"),
                    "--json",
                ]
            )

        payload = _extract_json(result.stdout)
        checks = payload["cases"][0]["checks"]
        must_not_contain = [check for check in checks if check["name"] == "must_not_contain"][0]
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(must_not_contain["ok"])

    def test_nonexistent_case_directory_error_is_clear(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "missing"
            result = _run_runner(
                [
                    str(missing),
                    "--output",
                    str(Path(temp_dir) / "result.json"),
                    "--json",
                ]
            )

        payload = _extract_json(result.stdout)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(payload["status"], "failed")
        self.assertIn("does not exist", payload["errors"][0])

    def test_empty_case_directory_error_is_clear(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            case_dir = Path(temp_dir) / "empty"
            case_dir.mkdir()
            result = _run_runner(
                [
                    str(case_dir),
                    "--output",
                    str(Path(temp_dir) / "result.json"),
                    "--json",
                ]
            )

        payload = _extract_json(result.stdout)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(payload["status"], "failed")
        self.assertIn("contains no JSON files", payload["errors"][0])

    def test_malformed_json_error_is_clear(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            case_dir = Path(temp_dir) / "cases"
            case_dir.mkdir()
            (case_dir / "bad.json").write_text("{bad", encoding="utf-8")
            result = _run_runner(
                [
                    str(case_dir),
                    "--output",
                    str(Path(temp_dir) / "result.json"),
                    "--json",
                ]
            )

        payload = _extract_json(result.stdout)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(payload["status"], "failed")
        self.assertIn("Malformed JSON", payload["errors"][0])

    def test_p1_replay_script_still_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "p1_replay.sqlite3"
            result = _run_command(
                [
                    sys.executable,
                    "scripts/replay_api_case.py",
                    str(P1_REPLAY_CASE),
                    "--db",
                    str(db_path),
                    "--json",
                ]
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = _extract_json(result.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["phase"], "P1.4")


if __name__ == "__main__":
    unittest.main()
