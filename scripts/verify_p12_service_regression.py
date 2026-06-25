from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

STAGE = "P12-M5_SERVICE_REGRESSION"
DEFAULT_OUTPUT = ROOT_DIR / "artifacts" / "p12" / "p12_service_regression.json"
OPENAPI_OUTPUT = ROOT_DIR / "artifacts" / "p12" / "openapi.json"
P11_REGRESSION_ARTIFACT = ROOT_DIR / "artifacts" / "p11" / "p11_regression_suite.json"

P12_CONTRACT_ARTIFACTS = {
    "M1": ROOT_DIR / "artifacts" / "p12" / "service_baseline.json",
    "M2": ROOT_DIR / "artifacts" / "p12" / "api_contract.json",
    "M3": ROOT_DIR / "artifacts" / "p12" / "persistence_contract.json",
    "M4": ROOT_DIR / "artifacts" / "p12" / "report_eval_api_contract.json",
}

OPENAPI_REQUIRED_METHODS = {
    "/health": {"get"},
    "/sessions": {"post"},
    "/sessions/{session_id}/turn": {"post"},
    "/sessions/{session_id}/report": {"get", "post"},
    "/sessions/{session_id}/turns": {"get"},
    "/eval/final": {"post"},
}

SENSITIVE_TRACKED_PATTERN = re.compile(
    r"(^|/)\.env$|\.db$|\.sqlite$|\.sqlite3$|\.safetensors$|\.bin$|\.pt$|\.pth$|\.ckpt$|\.gguf$|adapter_model|pytorch_model",
    re.IGNORECASE,
)

OLD_GENERATED_ARTIFACTS = [
    "artifacts/p10/api_events.jsonl",
    "artifacts/p11/p11_regression_suite.json",
    "artifacts/p3_2_observability.json",
    "artifacts/p3_3_release_packaging_check.json",
    "artifacts/p6_knowledge_pipeline.json",
    "artifacts/p6b_runtime_rag_trace_samples.json",
    "artifacts/p6b_runtime_rag_validation.json",
    "artifacts/p6c_evidence_metadata_audit.jsonl",
    "artifacts/p9m2/graph_events.jsonl",
    "artifacts/secret_scan_result.json",
    "knowledge/eval/p6_retrieval_safety_eval.json",
    "knowledge/indexes/p6_bm25_index.json",
]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _repo_path(path: Path) -> str:
    return path.relative_to(ROOT_DIR).as_posix()


def _git(args: list[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def _load_json(path: Path) -> tuple[dict[str, Any], str]:
    if not path.exists():
        return {}, "missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, f"invalid_json: {exc}"
    if not isinstance(payload, dict):
        return {}, "invalid_json_root"
    return payload, ""


def _load_p12_artifacts() -> dict[str, Any]:
    artifacts: dict[str, Any] = {}
    for milestone, path in P12_CONTRACT_ARTIFACTS.items():
        payload, error = _load_json(path)
        artifacts[milestone] = {
            "path": _repo_path(path),
            "stage": payload.get("stage"),
            "status": payload.get("status") if not error else error,
            "head": payload.get("head") or payload.get("commit"),
            "passed": not error and payload.get("status") == "ok",
        }
    return artifacts


def _load_p11_regression() -> dict[str, Any]:
    payload, error = _load_json(P11_REGRESSION_ARTIFACT)
    return {
        "path": _repo_path(P11_REGRESSION_ARTIFACT),
        "stage": payload.get("stage"),
        "status": payload.get("status") if not error else error,
        "passed": not error and payload.get("status") == "ok",
        "checks": payload.get("checks", {}),
    }


def _openapi_probe(output_path: Path) -> dict[str, Any]:
    from scripts.export_openapi import export_openapi

    exported_path = export_openapi(output_path)
    schema, error = _load_json(exported_path)
    paths = schema.get("paths") if isinstance(schema.get("paths"), dict) else {}
    method_matrix: dict[str, dict[str, bool]] = {}
    for path, required_methods in OPENAPI_REQUIRED_METHODS.items():
        available = paths.get(path, {}) if isinstance(paths, dict) else {}
        method_matrix[path] = {
            method: isinstance(available, dict) and method in available for method in sorted(required_methods)
        }

    serialized = json.dumps(schema, ensure_ascii=False)
    return {
        "path": _repo_path(exported_path),
        "status": "ok" if not error else error,
        "exported": exported_path.exists(),
        "openapi_version": schema.get("openapi"),
        "title": (schema.get("info") or {}).get("title") if isinstance(schema.get("info"), dict) else None,
        "path_count": len(paths),
        "required_methods": method_matrix,
        "required_paths_present": {path: path in paths for path in OPENAPI_REQUIRED_METHODS},
        "contains_secret_markers": "OPENAI_API_KEY" in serialized or "sk-" in serialized,
        "passed": not error
        and exported_path.exists()
        and bool(schema.get("openapi"))
        and all(all(methods.values()) for methods in method_matrix.values())
        and "OPENAI_API_KEY" not in serialized
        and "sk-" not in serialized,
    }


def _secret_scan_probe() -> dict[str, Any]:
    from scripts.secret_scan import scan_paths

    result = scan_paths([ROOT_DIR], include_runtime=False)
    return {
        "status": result.get("status"),
        "passed": result.get("status") == "ok" and result.get("finding_count") == 0,
        "finding_count": result.get("finding_count"),
        "allowed_count": result.get("allowed_count"),
        "scanned_files": result.get("scanned_files"),
    }


def _release_packaging_probe() -> dict[str, Any]:
    from scripts.check_release_packaging import build_release_packaging_payload

    result = build_release_packaging_payload()
    return {
        "status": result.get("status"),
        "passed": result.get("status") == "ok",
        "checks_total": result.get("checks_total"),
        "checks_passed": result.get("checks_passed"),
        "errors": result.get("errors"),
    }


def _tracked_sensitive_files_probe() -> dict[str, Any]:
    tracked = [line.strip().replace("\\", "/") for line in _git(["ls-files"]).splitlines() if line.strip()]
    matches = [path for path in tracked if SENSITIVE_TRACKED_PATTERN.search(path)]
    return {
        "passed": not matches,
        "matches": matches,
        "tracked_file_count": len(tracked),
    }


def _old_artifact_churn_probe() -> dict[str, Any]:
    status_lines = [line for line in _git(["status", "--short"]).splitlines() if line.strip()]
    changed = {
        line[3:].replace("\\", "/")
        for line in status_lines
        if len(line) >= 4 and line[:2].strip() and not line.startswith("?? ")
    }
    old_changes = sorted(path for path in OLD_GENERATED_ARTIFACTS if path in changed)
    return {
        "passed": not old_changes,
        "changed_old_artifacts": old_changes,
        "tracked_old_artifacts": OLD_GENERATED_ARTIFACTS,
    }


def verify(*, openapi_output: Path | None = None, check_old_artifact_churn: bool = True) -> dict[str, Any]:
    output_path = openapi_output or OPENAPI_OUTPUT
    if not output_path.is_absolute():
        output_path = ROOT_DIR / output_path

    p12_artifacts = _load_p12_artifacts()
    p11_regression = _load_p11_regression()
    openapi = _openapi_probe(output_path)
    secret_scan = _secret_scan_probe()
    release_packaging = _release_packaging_probe()
    sensitive_files = _tracked_sensitive_files_probe()
    old_artifact_churn = (
        _old_artifact_churn_probe()
        if check_old_artifact_churn
        else {"passed": True, "status": "skipped_by_caller", "changed_old_artifacts": []}
    )

    checks = {
        "branch_not_main": _git(["branch", "--show-current"]) != "main",
        "fastapi_openapi_exported": bool(openapi["passed"]),
        "p12_m1_to_m4_artifacts_ok": all(item["passed"] for item in p12_artifacts.values()),
        "p11_regression_status_ok": bool(p11_regression["passed"]),
        "secret_scan_clean": bool(secret_scan["passed"]),
        "release_packaging_12_of_12": release_packaging.get("checks_total") == 12
        and release_packaging.get("checks_passed") == 12
        and bool(release_packaging["passed"]),
        "no_tracked_env_db_or_model_files": bool(sensitive_files["passed"]),
        "no_old_artifact_churn": bool(old_artifact_churn["passed"]),
        "live_vllm_optional": True,
    }

    return {
        "stage": STAGE,
        "status": "ok" if all(checks.values()) else "failed",
        "branch": _git(["branch", "--show-current"]),
        "head": _git(["rev-parse", "HEAD"]),
        "base_main": _git(["rev-parse", "origin/main"]),
        "checks": checks,
        "openapi": openapi,
        "p12_contract_artifacts": p12_artifacts,
        "p11_regression": p11_regression,
        "secret_scan": secret_scan,
        "release_packaging": release_packaging,
        "sensitive_files": sensitive_files,
        "old_artifact_churn": old_artifact_churn,
        "next_readiness": {
            "recommended_phase": "P13",
            "focus": "deployment readiness, Docker packaging, optional PostgreSQL runtime smoke, and service operations",
        },
        "live_vllm_smoke": {
            "status": "skipped",
            "reason": "RUN_LOCAL_VLLM_SMOKE is not enabled; live vLLM is optional for P12.",
        },
        "git_status_short": _git(["status", "--short"]).splitlines(),
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Verify P12 service regression and OpenAPI readiness.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Artifact output path.")
    parser.add_argument(
        "--openapi-output",
        default=str(OPENAPI_OUTPUT),
        help="OpenAPI JSON output path. Defaults to artifacts/p12/openapi.json.",
    )
    args = parser.parse_args()

    payload = verify(openapi_output=Path(args.openapi_output))
    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT_DIR / output
    _write_json(output, payload)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(json.dumps({"stage": payload["stage"], "status": payload["status"]}, indent=2))
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
