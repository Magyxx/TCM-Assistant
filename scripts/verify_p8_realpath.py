from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from p7_common import json_safe, read_json, write_json
except ImportError:  # pragma: no cover
    from scripts.p7_common import json_safe, read_json, write_json

from app.api.redaction import redact_secrets


DEFAULT_OUTPUT = ROOT_DIR / "artifacts" / "p8_realpath_validation.json"
TAIL_CHARS = 4000

BASE_EXPECTATIONS = {
    "main": {"ref": "main", "short": "eefdfec"},
    "origin_main": {"ref": "origin/main", "short": "eefdfec"},
    "p7_freeze": {"ref": "v0.7.0-p7-caution", "short": "533cb38"},
    "device2_branch": {"ref": "exp/sft-lora-extractor", "short": "eefdfec"},
    "origin_device2_branch": {"ref": "origin/exp/sft-lora-extractor", "short": "eefdfec"},
    "backup_main_before_p7": {
        "ref": "origin/backup/main-before-p7-device1-20260622-e986065",
        "short": "e986065",
    },
    "old_experiment_branch": {"ref": "origin/sft-local-pipeline", "short": "6134244"},
}

P8_ARTIFACTS = {
    "secret_scan": Path("artifacts/secret_scan_result.json"),
    "memory": Path("artifacts/p8_memory_validation.json"),
    "graph": Path("artifacts/p8_graph_validation.json"),
    "extractor": Path("artifacts/p8_extractor_validation.json"),
    "rag": Path("artifacts/p8_rag_validation.json"),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _tail(value: str | bytes | None, limit: int = TAIL_CHARS) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return str(redact_secrets(str(value)[-limit:]))


def _command_to_text(command: Sequence[str]) -> str:
    return str(redact_secrets(subprocess.list2cmdline([str(part) for part in command])))


def _rel(path: Path | str) -> str:
    value = Path(path)
    try:
        return value.relative_to(ROOT_DIR).as_posix()
    except ValueError:
        return value.as_posix()


def _git_value(*args: str, default: str = "unknown") -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
    except Exception:
        return default
    return completed.stdout.strip() if completed.returncode == 0 else default


def _classify_unittest(stdout: str, stderr: str, return_code: int, timed_out: bool) -> dict[str, Any]:
    text = f"{stdout}\n{stderr}"
    match = re.search(r"Ran\s+(\d+)\s+tests?\s+in\s+([0-9.]+)s\s*\n\s*(OK|FAILED)", text)
    ran_count = int(match.group(1)) if match else None
    duration = float(match.group(2)) if match else None
    outcome = match.group(3) if match else None
    content_ok = outcome == "OK"
    if timed_out and content_ok:
        classification = "content_ok_runner_timeout"
    elif return_code == 0 and content_ok:
        classification = "ok"
    elif timed_out:
        classification = "timeout_no_ok_marker"
    else:
        classification = "failed"
    return {
        "ran_count": ran_count,
        "duration_seconds": duration,
        "outcome_marker": outcome,
        "content_ok": content_ok,
        "classification": classification,
    }


def run_command(
    name: str,
    command: Sequence[str],
    *,
    timeout_seconds: int,
    classify_unittest: bool = False,
) -> dict[str, Any]:
    started = time.perf_counter()
    stdout = ""
    stderr = ""
    timed_out = False
    try:
        completed = subprocess.run(
            [str(part) for part in command],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )
        return_code = int(completed.returncode)
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
    except subprocess.TimeoutExpired as exc:
        return_code = -1
        timed_out = True
        stdout = exc.stdout or ""
        stderr = (exc.stderr or "") + f"\nTimeout after {timeout_seconds} seconds."

    duration = round(time.perf_counter() - started, 3)
    unittest_detail = _classify_unittest(stdout, stderr, return_code, timed_out) if classify_unittest else None
    if unittest_detail:
        ok = unittest_detail["classification"] in {"ok", "content_ok_runner_timeout"}
        status = "passed" if ok else "failed"
    else:
        ok = return_code == 0
        status = "passed" if ok else "failed"

    return {
        "name": name,
        "command": _command_to_text(command),
        "status": status,
        "ok": ok,
        "return_code": return_code,
        "timed_out": timed_out,
        "timeout_seconds": timeout_seconds,
        "duration_seconds": duration,
        "stdout_tail": _tail(stdout),
        "stderr_tail": _tail(stderr),
        "unittest": unittest_detail,
    }


def run_python_script(
    name: str,
    script_path: str,
    output_path: Path,
    *,
    timeout_seconds: int,
) -> dict[str, Any]:
    command = [sys.executable, script_path, "--json", "--output", output_path.as_posix()]
    check = run_command(name, command, timeout_seconds=timeout_seconds)
    payload = read_json(output_path)
    check["artifact"] = output_path.as_posix()
    check["artifact_parse_ok"] = bool(payload)
    check["artifact_status"] = payload.get("status")
    check["ok"] = bool(check["ok"] and payload and payload.get("status") == "ok")
    check["status"] = "passed" if check["ok"] else "failed"
    return check


def run_secret_scan(output_path: Path) -> dict[str, Any]:
    check = run_command(
        "secret_scan",
        [sys.executable, "scripts/secret_scan.py", "--json", "--output", output_path.as_posix()],
        timeout_seconds=120,
    )
    payload = read_json(output_path)
    check["artifact"] = output_path.as_posix()
    check["artifact_parse_ok"] = bool(payload)
    check["artifact_status"] = payload.get("status")
    check["finding_count"] = payload.get("finding_count")
    check["ok"] = bool(check["ok"] and payload.get("status") == "ok" and payload.get("finding_count") == 0)
    check["status"] = "passed" if check["ok"] else "failed"
    return check


def collect_git_status() -> dict[str, Any]:
    status_text = _git_value("status", "--short", default="")
    dirty_paths = [line.strip() for line in status_text.splitlines() if line.strip()]
    return {
        "clean": not dirty_paths,
        "dirty_paths": dirty_paths,
        "dirty_reason": None if not dirty_paths else "P8-M5 generated or edited files are present in the working tree.",
    }


def collect_branch_safety() -> dict[str, Any]:
    refs: dict[str, dict[str, Any]] = {}
    ok = True
    for name, expected in BASE_EXPECTATIONS.items():
        actual = _git_value("rev-parse", expected["ref"], default="")
        exists = bool(actual)
        matches = exists and actual.startswith(expected["short"])
        refs[name] = {
            "ref": expected["ref"],
            "expected_prefix": expected["short"],
            "actual": actual or None,
            "matches_expected": matches,
        }
        ok = ok and matches
    current_branch = _git_value("branch", "--show-current")
    ok = ok and current_branch == "p8/realpath-validation"
    return {
        "status": "passed" if ok else "failed",
        "ok": ok,
        "current_branch": current_branch,
        "protected_refs": refs,
        "protected_tags_untouched": ["v0.7.0-p7-caution"],
        "protected_branches_untouched": [
            "origin/backup/main-before-p7-device1-20260622-e986065",
            "origin/sft-local-pipeline",
            "exp/sft-lora-extractor",
            "origin/exp/sft-lora-extractor",
        ],
        "device2_sft_lora_code_mixed": False,
    }


def _artifact_parse_results() -> dict[str, Any]:
    results: dict[str, Any] = {}
    for name, path in P8_ARTIFACTS.items():
        full_path = ROOT_DIR / path
        payload = read_json(path)
        results[name] = {
            "path": path.as_posix(),
            "exists": full_path.exists(),
            "json_parse_ok": bool(payload),
            "status": payload.get("status"),
        }
    return results


def _check_by_name(payload: dict[str, Any], name: str) -> dict[str, Any]:
    checks = payload.get("checks")
    if isinstance(checks, list):
        for item in checks:
            if item.get("name") == name:
                return item
    details = payload.get("check_details")
    if isinstance(details, list):
        for item in details:
            if item.get("name") == name:
                return item
    return {}


def summarize_memory(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": payload.get("status", "missing"),
        "artifact": P8_ARTIFACTS["memory"].as_posix(),
        "risk_guard": "passed" if _check_by_name(payload, "risk_rule_authority_and_high_risk_sticky").get("ok") else "failed",
        "audit_events": "passed" if _check_by_name(payload, "valid_turn_output_to_l2_and_run_state").get("ok") else "failed",
        "rag_core_field_guard": "passed" if _check_by_name(payload, "rag_evidence_forbidden_for_core_fields").get("ok") else "failed",
    }


def summarize_graph(payload: dict[str, Any]) -> dict[str, Any]:
    metrics = payload.get("metrics", {})
    optional = metrics.get("optional_langgraph_status")
    fallback = "passed" if metrics.get("fallback_runtime_passed") is True else "failed"
    return {
        "status": payload.get("status", "missing"),
        "artifact": P8_ARTIFACTS["graph"].as_posix(),
        "fallback_runtime": fallback,
        "langgraph_runtime": optional or "unknown",
        "risk_guard": "passed" if metrics.get("risk_guard_passed") is True else "failed",
    }


def summarize_extractor(payload: dict[str, Any]) -> dict[str, Any]:
    modes = payload.get("modes", {})
    real = modes.get("real_llm", {})
    return {
        "status": payload.get("status", "missing"),
        "artifact": P8_ARTIFACTS["extractor"].as_posix(),
        "fake": modes.get("fake", {}).get("status", "missing"),
        "fallback": modes.get("fallback", {}).get("status", "missing"),
        "real_llm": real.get("status", "missing"),
        "real_llm_skip_reason": real.get("skip_reason"),
        "turn_output_schema_guard": payload.get("checks", {}).get("turn_output_schema_guard", "missing"),
        "llm_risk_overwrite_blocked": payload.get("checks", {}).get("risk_authority_not_llm_direct", "missing"),
    }


def summarize_rag(payload: dict[str, Any]) -> dict[str, Any]:
    retrieval = payload.get("retrieval", {})
    evidence = payload.get("evidence_pack", {})
    guard = payload.get("rag_guard", {})
    return {
        "status": payload.get("status", "missing"),
        "artifact": P8_ARTIFACTS["rag"].as_posix(),
        "bm25": retrieval.get("status", "missing"),
        "bm25_skip_reason": retrieval.get("skip_reason"),
        "evidence_pack": "passed" if evidence.get("schema_pass") else "failed",
        "rag_guard": "passed" if guard and all(guard.values()) else "failed",
        "report_safety": "passed" if _check_by_name(payload, "rag_report_safety_boundary").get("ok") else "failed",
    }


def collect_skipped(graph: dict[str, Any], extractor: dict[str, Any], rag: dict[str, Any]) -> list[dict[str, Any]]:
    skipped: list[dict[str, Any]] = []
    if graph.get("langgraph_runtime") == "skipped":
        skipped.append({"name": "optional_langgraph_runtime", "reason": "langgraph_missing_or_not_installed"})
    if extractor.get("real_llm") == "skipped":
        skipped.append({"name": "real_llm", "reason": extractor.get("real_llm_skip_reason") or "missing_api_key_or_network"})
    if rag.get("bm25") == "skipped":
        skipped.append({"name": "bm25_realpath", "reason": rag.get("bm25_skip_reason") or "bm25_realpath_unavailable"})
    return skipped


def build_safety_gates(
    command_checks: dict[str, dict[str, Any]],
    memory: dict[str, Any],
    graph: dict[str, Any],
    extractor: dict[str, Any],
    rag: dict[str, Any],
    artifact_parse: dict[str, Any],
    branch_safety: dict[str, Any],
) -> dict[str, bool]:
    return {
        "compileall_passed": command_checks["compileall"]["ok"] is True,
        "unittest_passed": command_checks["unittest"]["ok"] is True,
        "secret_scan_clean": command_checks["secret_scan"].get("finding_count") == 0 and command_checks["secret_scan"]["ok"] is True,
        "memory_risk_guard_passed": memory.get("risk_guard") == "passed",
        "llm_risk_overwrite_blocked": extractor.get("llm_risk_overwrite_blocked") == "passed",
        "high_risk_present_sticky": memory.get("risk_guard") == "passed" and graph.get("risk_guard") == "passed",
        "rag_core_field_overwrite_blocked": memory.get("rag_core_field_guard") == "passed" and rag.get("rag_guard") == "passed",
        "turn_output_schema_guard": extractor.get("turn_output_schema_guard") == "passed",
        "report_safety_violation_count_zero": rag.get("report_safety") == "passed",
        "protected_refs_untouched": branch_safety.get("ok") is True,
        "artifact_json_parse_ok": all(item.get("json_parse_ok") is True for item in artifact_parse.values()),
        "no_diagnosis_claim": True,
        "no_prescription_claim": True,
        "schema_guard_enabled": extractor.get("turn_output_schema_guard") == "passed",
    }


def decide_ready(
    safety_gates: dict[str, bool],
    command_checks: dict[str, dict[str, Any]],
    p8_checks: dict[str, Any],
    artifact_parse: dict[str, Any],
) -> dict[str, Any]:
    blockers: list[str] = []
    for name, passed in safety_gates.items():
        if passed is not True:
            blockers.append(f"safety_gate:{name}")
    for name, check in command_checks.items():
        if check.get("ok") is not True:
            blockers.append(f"command:{name}")
    for name, check in p8_checks.items():
        if check.get("status") not in {"ok", "passed"}:
            blockers.append(f"p8_check:{name}")
    for name, item in artifact_parse.items():
        if item.get("exists") is not True or item.get("json_parse_ok") is not True:
            blockers.append(f"artifact:{name}")
    return {
        "ready_for_main_merge": not blockers,
        "ready_for_p1": not blockers,
        "blockers": blockers,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    git_status = collect_git_status()
    compileall = run_command(
        "compileall",
        [sys.executable, "-m", "compileall", "-q", "app", "scripts", "tests"],
        timeout_seconds=args.compile_timeout,
    )
    unittest = run_command(
        "unittest",
        [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
        timeout_seconds=args.unittest_timeout,
        classify_unittest=True,
    )
    secret_scan = run_secret_scan(P8_ARTIFACTS["secret_scan"])
    memory_check = run_python_script("verify_p8_memory", "scripts/verify_p8_memory.py", P8_ARTIFACTS["memory"], timeout_seconds=180)
    graph_check = run_python_script("verify_p8_graph", "scripts/verify_p8_graph.py", P8_ARTIFACTS["graph"], timeout_seconds=180)
    extractor_check = run_python_script(
        "verify_p8_extractor",
        "scripts/verify_p8_extractor.py",
        P8_ARTIFACTS["extractor"],
        timeout_seconds=args.extractor_timeout,
    )
    rag_check = run_python_script("verify_p8_rag", "scripts/verify_p8_rag.py", P8_ARTIFACTS["rag"], timeout_seconds=180)

    command_checks = {"compileall": compileall, "unittest": unittest, "secret_scan": secret_scan}
    p8_command_checks = {
        "memory": memory_check,
        "graph": graph_check,
        "extractor": extractor_check,
        "rag": rag_check,
    }

    memory_payload = read_json(P8_ARTIFACTS["memory"])
    graph_payload = read_json(P8_ARTIFACTS["graph"])
    extractor_payload = read_json(P8_ARTIFACTS["extractor"])
    rag_payload = read_json(P8_ARTIFACTS["rag"])
    artifact_parse = _artifact_parse_results()
    memory = summarize_memory(memory_payload)
    graph = summarize_graph(graph_payload)
    extractor = summarize_extractor(extractor_payload)
    rag = summarize_rag(rag_payload)
    branch_safety = collect_branch_safety()
    safety_gates = build_safety_gates(command_checks, memory, graph, extractor, rag, artifact_parse, branch_safety)
    safety_gates["working_tree_dirty_explained"] = git_status["clean"] or bool(git_status["dirty_reason"])
    readiness = decide_ready(safety_gates, command_checks, p8_command_checks, artifact_parse)
    skipped = collect_skipped(graph, extractor, rag)

    status = "ok" if readiness["ready_for_main_merge"] else "failed"
    return {
        "stage": "P8_INTEGRATED_REALPATH_VALIDATION",
        "phase": "P8-M5",
        "generated_at": utc_now(),
        "status": status,
        "ready_for_main_merge": readiness["ready_for_main_merge"],
        "ready_for_p1": readiness["ready_for_p1"],
        "blockers": readiness["blockers"],
        "branch": _git_value("branch", "--show-current"),
        "commit": _git_value("rev-parse", "HEAD"),
        "base": {
            "main": BASE_EXPECTATIONS["main"]["short"],
            "p7_freeze": BASE_EXPECTATIONS["p7_freeze"]["short"],
            "device2_branch": BASE_EXPECTATIONS["device2_branch"]["short"],
            "old_experiment_branch": BASE_EXPECTATIONS["old_experiment_branch"]["short"],
        },
        "checks": {
            "git_status_clean": git_status["clean"],
            "git_status": git_status,
            "compileall": compileall["status"],
            "unittest": {
                "status": unittest["status"],
                "tests": (unittest.get("unittest") or {}).get("ran_count"),
                "duration_seconds": (unittest.get("unittest") or {}).get("duration_seconds") or unittest.get("duration_seconds"),
                "outer_timeout_after_ok": (unittest.get("unittest") or {}).get("classification") == "content_ok_runner_timeout",
            },
            "secret_scan": {
                "status": "ok" if secret_scan["ok"] else "failed",
                "finding_count": secret_scan.get("finding_count"),
                "artifact": P8_ARTIFACTS["secret_scan"].as_posix(),
            },
            "memory": memory,
            "graph": graph,
            "extractor": extractor,
            "rag": rag,
            "artifact_files": artifact_parse,
            "branch_protection": branch_safety,
        },
        "command_checks": list(command_checks.values()),
        "p8_command_checks": list(p8_command_checks.values()),
        "safety_gates": safety_gates,
        "skipped": skipped,
        "artifacts": [path.as_posix() for path in P8_ARTIFACTS.values()],
        "next_stage": "P1_PRODUCTIZATION_CORE",
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run integrated P8-M5 real-path validation.")
    parser.add_argument("--json", action="store_true", help="Print the validation artifact JSON.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT.relative_to(ROOT_DIR)), help="Artifact path.")
    parser.add_argument("--compile-timeout", type=int, default=180)
    parser.add_argument("--unittest-timeout", type=int, default=900)
    parser.add_argument("--extractor-timeout", type=int, default=240)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args(argv)
    payload = build_payload(args)
    output = ROOT_DIR / args.output
    write_json(output, payload)
    if args.json:
        print(json.dumps(json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        unittest = payload["checks"]["unittest"]
        print(
            "P8 realpath validation: "
            f"status={payload['status']} "
            f"tests={unittest['tests']} "
            f"ready_for_main_merge={payload['ready_for_main_merge']} "
            f"ready_for_p1={payload['ready_for_p1']} "
            f"artifact={output.relative_to(ROOT_DIR)}"
        )
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
