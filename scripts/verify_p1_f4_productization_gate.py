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


DEFAULT_OUTPUT = Path("artifacts") / "p1_f4_productization_gate.json"
TAIL_CHARS = 3000


@dataclass(frozen=True)
class CommandSpec:
    name: str
    command: tuple[str, ...]
    timeout_seconds: int = 600


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
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def p1f_artifact_specs() -> list[ArtifactSpec]:
    return [
        ArtifactSpec("p1_f0_foundation", Path("artifacts/p1_foundation_validation.json")),
        ArtifactSpec("p1_f1_graph_integration", Path("artifacts/p1_f1_graph_integration_validation.json")),
        ArtifactSpec("p1_f2_api_exposure", Path("artifacts/p1_f2_api_exposure_validation.json")),
        ArtifactSpec("p1_f3_tool_audit_trace", Path("artifacts/p1_f3_tool_audit_trace_validation.json")),
        ArtifactSpec("p8_memory_validation", Path("artifacts/p8_memory_validation.json")),
        ArtifactSpec("p8_graph_validation", Path("artifacts/p8_graph_validation.json")),
        ArtifactSpec("p8_extractor_validation", Path("artifacts/p8_extractor_validation.json")),
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
            "tests.test_p1_foundation_no_external_dependencies",
            "tests.test_p1_f1_graph_integration",
            "tests.test_api_contract",
            "tests.test_rag_evidence_pack_contract",
            "tests.test_report_contract",
            "tests.test_storage_sqlite",
            "tests.test_tool_registry",
            "tests.test_p7_api",
            "tests.test_p1_f4_productization_gate",
        )
    )
    return [
        CommandSpec("compileall", (py, "-m", "compileall", "-q", "app", "scripts", "tests")),
        CommandSpec("p1_f0_foundation", (py, "scripts/verify_p1_foundation.py", "--json")),
        CommandSpec("p1_f1_graph_integration", (py, "scripts/verify_p1_f1_graph_integration.py", "--json")),
        CommandSpec("p1_f2_api_exposure", (py, "scripts/verify_p1_f2_api_exposure.py", "--json")),
        CommandSpec("p1_f3_tool_audit_trace", (py, "scripts/verify_p1_f3_tool_audit_trace.py", "--json")),
        CommandSpec("p8_memory_validation", (py, "scripts/verify_p8_memory.py")),
        CommandSpec("p8_graph_validation", (py, "scripts/verify_p8_graph.py")),
        CommandSpec("p8_extractor_validation", (py, "scripts/verify_p8_extractor.py")),
        CommandSpec("focused_unittest", unittest_command, timeout_seconds=900 if full_unittest else 300),
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


def summarize_artifacts(root: Path = ROOT, specs: Sequence[ArtifactSpec] | None = None) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for spec in specs or p1f_artifact_specs():
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
        if spec.name == "secret_scan":
            summary["finding_count"] = payload.get("finding_count")
            summary["ok"] = summary["ok"] and payload.get("finding_count") == 0
        if payload.get("stage"):
            summary["stage"] = payload.get("stage")
        summaries.append(summary)
    return summaries


def build_boundary_summary() -> dict[str, Any]:
    return {
        "legacy_p1_gate_authoritative": False,
        "legacy_p1_gate_reason": (
            "scripts/run_p1_gate.py belongs to the older P1.1-P1.6 line and treats "
            "MemoryManager/Tool Registry as non-goals; P1-F4 validates the post-P8 "
            "productization route instead."
        ),
        "p8_safety_boundaries_preserved": True,
        "memory_manager_allowed_from_p8": True,
        "tool_registry_allowed_from_p8": True,
        "no_real_llm_required": True,
        "no_local_lora_required": True,
        "no_embedding_required": True,
        "no_vectorstore_required": True,
        "no_device2_lora_merge": True,
        "no_diagnosis_prescription_or_treatment_plan": True,
    }


def decide_status(
    command_results: Sequence[dict[str, Any]],
    artifact_summaries: Sequence[dict[str, Any]],
    boundary: dict[str, Any],
) -> str:
    commands_ok = all(item.get("status") == "ok" for item in command_results)
    artifacts_ok = all(item.get("ok") is True for item in artifact_summaries)
    boundaries_ok = (
        boundary.get("legacy_p1_gate_authoritative") is False
        and boundary.get("p8_safety_boundaries_preserved") is True
        and boundary.get("no_diagnosis_prescription_or_treatment_plan") is True
        and boundary.get("no_device2_lora_merge") is True
    )
    return "ok" if commands_ok and artifacts_ok and boundaries_ok else "failed"


def build_gate_result(command_results: Sequence[dict[str, Any]]) -> dict[str, Any]:
    artifact_summaries = summarize_artifacts()
    boundary = build_boundary_summary()
    failed_commands = [item["name"] for item in command_results if item.get("status") != "ok"]
    failed_artifacts = [item["name"] for item in artifact_summaries if item.get("ok") is not True]
    status = decide_status(command_results, artifact_summaries, boundary)
    return {
        "stage": "P1-F4_PRODUCTIZATION_GATE",
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
        "recommend_next": "P1-F6 Post-P8 productization final report" if status == "ok" else "hold",
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Run the post-P8 P1-F productization gate.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--full-unittest", action="store_true")
    args = parser.parse_args()

    command_results = run_commands(default_command_specs(full_unittest=args.full_unittest), fail_fast=args.fail_fast)
    result = build_gate_result(command_results)
    _write_json(Path(args.output), result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(f"{result['stage']} {result['status']} -> {ROOT / args.output}")
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
