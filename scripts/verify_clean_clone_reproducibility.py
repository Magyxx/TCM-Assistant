from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.knowledge.source_registry import DEFAULT_SOURCE_REGISTRY_PATH, load_source_registry, source_file_hash


DEFAULT_OUTPUT = ROOT_DIR / "artifacts" / "clean_clone_reproducibility_validation.json"
ALLOWED_ENV_SAMPLE_NAMES = {".env.example"}
FORBIDDEN_PREFIXES = (
    ".env.",
    "adapter_model",
    "checkpoint",
    "model.safetensors",
    "pytorch_model",
)
FORBIDDEN_SUFFIXES = (".safetensors", ".bin", ".pt", ".pth", ".ckpt")


def _git(args: list[str]) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except Exception:
        return ""
    return completed.stdout.strip() if completed.returncode == 0 else ""


def _status(ok: bool) -> str:
    return "passed" if ok else "failed"


def _source_hash_checks() -> list[dict[str, Any]]:
    registry = load_source_registry(DEFAULT_SOURCE_REGISTRY_PATH)
    checks: list[dict[str, Any]] = []
    for source in registry.get("sources", []):
        if not isinstance(source, dict):
            continue
        if not source.get("content_path"):
            continue
        expected = source.get("hash")
        actual = source_file_hash(source, DEFAULT_SOURCE_REGISTRY_PATH)
        checks.append(
            {
                "source_id": source.get("source_id"),
                "expected_hash": expected,
                "actual_hash": actual,
                "status": _status(actual == expected),
            }
        )
    return checks


def _report_chain_import_check() -> dict[str, Any]:
    import app.chains.report_chain as report_chain_module

    return {
        "status": _status(report_chain_module.report_chain is None),
        "lazy_report_chain": report_chain_module.report_chain is None,
        "lazy_structured_llm": report_chain_module.structured_llm is None,
    }


def _forbidden_git_files() -> list[str]:
    files = _git(["ls-files"]).splitlines()
    forbidden: list[str] = []
    for path in files:
        normalized = path.replace("\\", "/")
        lower = normalized.lower()
        name = Path(normalized).name.lower()
        if name in ALLOWED_ENV_SAMPLE_NAMES:
            continue
        if name == ".env" or any(name.startswith(pattern) for pattern in FORBIDDEN_PREFIXES):
            forbidden.append(normalized)
        elif lower.endswith(FORBIDDEN_SUFFIXES):
            forbidden.append(normalized)
    return sorted(set(forbidden))


def build_payload() -> dict[str, Any]:
    source_checks = _source_hash_checks()
    report_chain_check = _report_chain_import_check()
    forbidden_files = _forbidden_git_files()
    checks = {
        "source_registry_hashes": _status(bool(source_checks) and all(item["status"] == "passed" for item in source_checks)),
        "report_chain_import_is_lazy": report_chain_check["status"],
        "forbidden_git_files": _status(not forbidden_files),
    }
    status = "ok" if all(value == "passed" for value in checks.values()) else "failed"
    return {
        "stage": "RC-S2R_CLEAN_CLONE_REPRODUCIBILITY_REPAIR",
        "status": status,
        "branch": _git(["branch", "--show-current"]),
        "commit": _git(["rev-parse", "HEAD"]),
        "checks": checks,
        "source_hashes": source_checks,
        "report_chain_import": report_chain_check,
        "forbidden_git_files": forbidden_files,
        "external_dependencies_required": False,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate clean clone reproducibility repair guards.")
    parser.add_argument("--json", action="store_true", help="Print validation JSON.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT.relative_to(ROOT_DIR)), help="Artifact path.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args(argv)
    payload = build_payload()
    output = ROOT_DIR / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"status={payload['status']} output={output.relative_to(ROOT_DIR)}")
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
