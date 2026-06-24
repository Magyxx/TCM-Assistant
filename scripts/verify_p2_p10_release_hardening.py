from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.api.redaction import redact_secrets


DEFAULT_OUTPUT = Path("artifacts") / "p2_p10_release_hardening.json"
TAIL_CHARS = 3000


@dataclass(frozen=True)
class CommandSpec:
    name: str
    command: tuple[str, ...]
    timeout_seconds: int = 900


@dataclass(frozen=True)
class ArtifactSpec:
    name: str
    path: Path
    expected_status: str = "ok"


def _git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True, encoding="utf-8").strip()
    except Exception:
        return "unknown"


def _command_to_text(command: Sequence[str]) -> str:
    return str(redact_secrets(subprocess.list2cmdline([str(part) for part in command])))


def _tail(value: str, limit: int = TAIL_CHARS) -> str:
    return str(redact_secrets((value or "")[-limit:]))


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def release_hardening_artifact_specs() -> list[ArtifactSpec]:
    return [
        ArtifactSpec("p1_f6_post_p8_productization_final", Path("artifacts/p1_f6_post_p8_productization_final.json")),
        ArtifactSpec("p10m2_core_validation", Path("artifacts/p10m2/core_validation.json")),
        ArtifactSpec("p10m3_local_lora_backend", Path("artifacts/p10m3/local_lora_backend_validation.json")),
        ArtifactSpec("p10_m4a_extractor_contract", Path("artifacts/p10_extractor_contract_validation.json")),
        ArtifactSpec("release_packaging_check", Path("artifacts/p3_3_release_packaging_check.json")),
        ArtifactSpec("secret_scan", Path("artifacts/secret_scan_result.json")),
    ]


def default_command_specs(*, full_unittest: bool = False) -> list[CommandSpec]:
    py = sys.executable
    unittest_command = (
        (py, "-m", "unittest", "discover", "-s", "tests")
        if full_unittest
        else (
            py,
            "-m",
            "unittest",
            "tests.test_p1_f4_productization_gate",
            "tests.test_p1_f5_report_audit",
            "tests.test_p1_f6_post_p8_productization_final",
            "tests.test_extractor_contract",
            "tests.test_local_lora_backend_skip",
            "tests.test_api_contract",
            "tests.test_p7_api",
        )
    )
    return [
        CommandSpec("compileall", (py, "-m", "compileall", "-q", "app", "scripts", "tests")),
        CommandSpec(
            "p1_f6_post_p8_productization_final",
            (
                py,
                "scripts/verify_p1_f6_post_p8_productization_final.py",
                "--json",
                "--output",
                "artifacts/p1_f6_post_p8_productization_final.json",
            ),
        ),
        CommandSpec("p10m2_core_validation", (py, "scripts/verify_p10m2_core.py")),
        CommandSpec(
            "p10m3_local_lora_backend",
            (
                py,
                "scripts/verify_p10m3_local_lora_backend.py",
                "--json",
                "--output",
                "artifacts/p10m3/local_lora_backend_validation.json",
            ),
        ),
        CommandSpec(
            "p10_m4a_extractor_contract",
            (
                py,
                "scripts/verify_p10_extractor_contract.py",
                "--json",
                "--output",
                "artifacts/p10_extractor_contract_validation.json",
            ),
        ),
        CommandSpec(
            "release_packaging_check",
            (
                py,
                "scripts/check_release_packaging.py",
                "--json",
                "--output",
                "artifacts/p3_3_release_packaging_check.json",
            ),
        ),
        CommandSpec("focused_release_unittest", unittest_command, timeout_seconds=1200 if full_unittest else 420),
        CommandSpec(
            "secret_scan",
            (py, "scripts/secret_scan.py", "--json", "--output", "artifacts/secret_scan_result.json"),
        ),
        CommandSpec("git_diff_check", ("git", "diff", "--check")),
    ]


def run_command(spec: CommandSpec) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            [str(part) for part in spec.command],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=spec.timeout_seconds,
        )
        return_code = int(completed.returncode)
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        status = "ok" if return_code == 0 else "failed"
    except subprocess.TimeoutExpired as exc:
        return_code = -1
        stdout = exc.stdout or ""
        stderr = (exc.stderr or "") + f"\nTimeout after {spec.timeout_seconds} seconds."
        status = "failed"

    return {
        "name": spec.name,
        "command": _command_to_text(spec.command),
        "status": status,
        "return_code": return_code,
        "duration_seconds": round(time.perf_counter() - started, 3),
        "stdout_tail": _tail(stdout),
        "stderr_tail": _tail(stderr),
    }


def run_commands(specs: Sequence[CommandSpec], *, fail_fast: bool = False) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for spec in specs:
        result = run_command(spec)
        results.append(result)
        if fail_fast and result["status"] != "ok":
            break
    return results


def _all_checks_ok(checks: Any) -> bool:
    if isinstance(checks, dict):
        return all(value is True or value == "passed" for value in checks.values())
    if isinstance(checks, list):
        return all(bool(item.get("ok")) for item in checks if isinstance(item, dict))
    return False


def _p10m2_required_ok(payload: dict[str, Any]) -> bool:
    required = [
        "knowledge_built",
        "hybrid_rag_passed",
        "citation_passed",
        "rag_guard_passed",
        "safety_redteam_passed",
        "final_eval_passed",
        "api_rag_passed",
        "export_passed",
        "docker_files_present",
        "secret_scan_passed",
        "p10m1_regression_passed",
        "p9m2_regression_passed",
        "lora_contract_present",
        "failure_memory_built",
    ]
    safety = payload.get("safety_gates") if isinstance(payload.get("safety_gates"), dict) else {}
    return all(bool(payload.get(name)) for name in required) and all(value == 0 for value in safety.values())


def summarize_artifacts(root: Path = ROOT, specs: Sequence[ArtifactSpec] | None = None) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for spec in specs or release_hardening_artifact_specs():
        target = root / spec.path
        payload = _load_json(target)
        status = payload.get("status") if payload else None
        summary: dict[str, Any] = {
            "name": spec.name,
            "path": str(spec.path).replace("\\", "/"),
            "exists": target.exists(),
            "status": status,
            "expected_status": spec.expected_status,
            "ok": target.exists() and status == spec.expected_status,
        }
        if payload.get("stage"):
            summary["stage"] = payload.get("stage")
        if spec.name == "p1_f6_post_p8_productization_final":
            completion = payload.get("completion") if isinstance(payload.get("completion"), dict) else {}
            summary["post_p8_productization_ready"] = completion.get("post_p8_productization_ready")
            summary["ok"] = summary["ok"] and completion.get("post_p8_productization_ready") is True
        elif spec.name == "p10m2_core_validation":
            summary["p10m2_required_ok"] = _p10m2_required_ok(payload)
            summary["ok"] = summary["ok"] and summary["p10m2_required_ok"]
        elif spec.name == "p10m3_local_lora_backend":
            live_smoke = payload.get("live_smoke") if isinstance(payload.get("live_smoke"), dict) else {}
            summary["checks_ok"] = _all_checks_ok(payload.get("checks"))
            summary["live_smoke_status"] = live_smoke.get("status")
            summary["ok"] = summary["ok"] and summary["checks_ok"] and live_smoke.get("status") in {"passed", "skipped"}
        elif spec.name == "p10_m4a_extractor_contract":
            lora_artifacts = payload.get("lora_artifacts") if isinstance(payload.get("lora_artifacts"), dict) else {}
            summary["checks_ok"] = _all_checks_ok(payload.get("checks"))
            summary["model_weights_committed"] = lora_artifacts.get("model_weights_committed")
            summary["ok"] = summary["ok"] and summary["checks_ok"] and lora_artifacts.get("model_weights_committed") is False
        elif spec.name == "release_packaging_check":
            summary["checks_total"] = payload.get("checks_total")
            summary["checks_passed"] = payload.get("checks_passed")
            summary["errors"] = payload.get("errors")
            summary["boundary_violated"] = payload.get("boundary_violated")
            summary["ok"] = (
                summary["ok"]
                and payload.get("checks_total") == payload.get("checks_passed")
                and not payload.get("errors")
                and payload.get("boundary_violated") is False
                and payload.get("contract_changed") is False
                and payload.get("sqlite_schema_changed") is False
            )
        elif spec.name == "secret_scan":
            summary["finding_count"] = payload.get("finding_count")
            summary["ok"] = summary["ok"] and payload.get("finding_count") == 0
        summaries.append(summary)
    return summaries


def build_boundary_summary() -> dict[str, Any]:
    return {
        "post_p8_p1_route_accepted": True,
        "p10m2_core_accepted": True,
        "p10m3_local_lora_device1_extractor_only": True,
        "p10_m4a_extractor_contract_accepted": True,
        "legacy_p1_gate_authoritative": False,
        "release_package_local_engineering_candidate": True,
        "not_production_medical_product": True,
        "no_diagnosis_prescription_or_treatment_plan": True,
        "no_device2_lora_merge": True,
        "no_model_weights_or_adapters_committed": True,
        "real_llm_optional_and_disabled_by_default": True,
        "local_lora_runtime_optional": True,
        "no_vectorstore_or_postgres_required": True,
        "secret_scan_required": True,
    }


def decide_status(
    command_results: Sequence[dict[str, Any]],
    artifact_summaries: Sequence[dict[str, Any]],
    boundary: dict[str, Any],
) -> str:
    commands_ok = all(item.get("status") == "ok" for item in command_results)
    artifacts_ok = all(item.get("ok") is True for item in artifact_summaries)
    boundaries_ok = (
        boundary.get("post_p8_p1_route_accepted") is True
        and boundary.get("p10m2_core_accepted") is True
        and boundary.get("p10m3_local_lora_device1_extractor_only") is True
        and boundary.get("p10_m4a_extractor_contract_accepted") is True
        and boundary.get("legacy_p1_gate_authoritative") is False
        and boundary.get("not_production_medical_product") is True
        and boundary.get("no_diagnosis_prescription_or_treatment_plan") is True
        and boundary.get("no_device2_lora_merge") is True
        and boundary.get("no_model_weights_or_adapters_committed") is True
    )
    return "ok" if commands_ok and artifacts_ok and boundaries_ok else "failed"


def build_hardening_result(command_results: Sequence[dict[str, Any]]) -> dict[str, Any]:
    artifact_summaries = summarize_artifacts()
    boundary = build_boundary_summary()
    failed_commands = [item["name"] for item in command_results if item.get("status") != "ok"]
    failed_artifacts = [item["name"] for item in artifact_summaries if item.get("ok") is not True]
    status = decide_status(command_results, artifact_summaries, boundary)
    return {
        "stage": "P2_P10_RELEASE_HARDENING_PACKAGING",
        "status": status,
        "branch": _git(["branch", "--show-current"]),
        "commit": _git(["rev-parse", "HEAD"]),
        "external_dependencies_required": False,
        "commands_total": len(command_results),
        "commands_passed": len(command_results) - len(failed_commands),
        "commands_failed": len(failed_commands),
        "failed_commands": failed_commands,
        "failed_artifacts": failed_artifacts,
        "commands": list(command_results),
        "artifacts": artifact_summaries,
        "boundary": boundary,
        "release_hardening_ready": status == "ok",
        "recommend_next": "release candidate audit and commit packaging" if status == "ok" else "hold",
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Run P2/P10 release hardening and packaging validation.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--full-unittest", action="store_true")
    args = parser.parse_args()

    command_results = run_commands(default_command_specs(full_unittest=args.full_unittest), fail_fast=args.fail_fast)
    result = build_hardening_result(command_results)
    _write_json(Path(args.output), result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(f"{result['stage']} {result['status']} -> {ROOT / args.output}")
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
