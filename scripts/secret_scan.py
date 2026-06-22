from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.api.redaction import redact_secrets


SECRET_PATTERN = re.compile(r"sk-[A-Za-z0-9_-]{20,}")
DEFAULT_EXCLUDED_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".runtime",
    "__pycache__",
    "hf_cache",
    "models",
    "outputs",
    "venv",
}
DEFAULT_EXCLUDED_SUFFIXES = {
    ".db",
    ".db-shm",
    ".db-wal",
    ".bin",
    ".ckpt",
    ".log",
    ".pyd",
    ".pyc",
    ".pyo",
    ".safetensors",
    ".sqlite",
    ".sqlite-shm",
    ".sqlite-wal",
    ".sqlite3",
    ".sqlite3-shm",
    ".sqlite3-wal",
}
RUNTIME_DB_SUFFIXES = {
    ".db",
    ".db-shm",
    ".db-wal",
    ".sqlite",
    ".sqlite-shm",
    ".sqlite-wal",
    ".sqlite3",
    ".sqlite3-shm",
    ".sqlite3-wal",
}
DEFAULT_EXCLUDED_FILE_NAMES = {
    ".env",
}
SYNTHETIC_SECRET_MARKERS = (
    "auditsecret",
    "boundarysecret",
    "compatsecret",
    "contractsecret",
    "errorsecret",
    "inspectsecret",
    "nestedsecret",
    "snapshotsecret",
    "testsecret",
)
P2_CASE_SYNTHETIC_SECRETS = {
    ("artifacts", "eval_cases", "secret_injection_input.json"): (
        "sk-" + "testsecret-p2-case-0001"
    ),
    ("artifacts", "eval_cases", "report_secret_injection_case.json"): (
        "sk-" + "reportsecret-p2-case-0001"
    ),
}


def _is_under(path: Path, parent_name: str) -> bool:
    return parent_name in {part.lower() for part in path.parts}


def _iter_files(root: Path, *, include_runtime: bool) -> Iterable[Path]:
    if root.is_file():
        yield root
        return

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        parts = {part.lower() for part in path.relative_to(root).parts}
        excluded_dirs = set(DEFAULT_EXCLUDED_DIRS)
        if include_runtime:
            excluded_dirs.discard(".runtime")
        if parts & excluded_dirs:
            continue
        if path.name in DEFAULT_EXCLUDED_FILE_NAMES or (
            path.name.startswith(".env.") and path.name != ".env.example"
        ):
            continue
        suffix = path.suffix.lower()
        if suffix in DEFAULT_EXCLUDED_SUFFIXES and not (
            include_runtime and suffix in RUNTIME_DB_SUFFIXES
        ):
            continue
        yield path


def _safe_read_text(path: Path) -> str:
    return path.read_bytes().decode("utf-8", errors="ignore")


def is_allowlisted(path: Path, match_text: str) -> bool:
    lowered = match_text.lower()
    if "[redacted-secret]" in lowered:
        return True
    lowered_parts = tuple(part.lower() for part in path.parts)
    for fixture_path, synthetic_secret in P2_CASE_SYNTHETIC_SECRETS.items():
        if (
            match_text == synthetic_secret
            and len(lowered_parts) >= len(fixture_path)
            and lowered_parts[-len(fixture_path):] == fixture_path
        ):
            return True
    if _is_under(path, "tests") and any(marker in lowered for marker in SYNTHETIC_SECRET_MARKERS):
        return True
    return False


def _line_number(text: str, start: int) -> int:
    return text.count("\n", 0, start) + 1


def _finding(path: Path, root: Path, text: str, match: re.Match[str]) -> dict[str, Any]:
    start = max(0, match.start() - 48)
    end = min(len(text), match.end() + 48)
    preview = text[start:end].replace("\r", " ").replace("\n", " ")
    preview = str(redact_secrets(preview)).replace("\\", "/")
    try:
        display_path = str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        display_path = str(path)
    return {
        "path": str(redact_secrets(display_path)),
        "line": _line_number(text, match.start()),
        "kind": "sk_high_entropy",
        "preview": preview,
    }


def scan_paths(paths: list[Path], *, include_runtime: bool = False) -> dict[str, Any]:
    scanned_files = 0
    findings: list[dict[str, Any]] = []
    allowed_findings: list[dict[str, Any]] = []

    for root in paths:
        root = root.resolve()
        for path in _iter_files(root, include_runtime=include_runtime):
            scanned_files += 1
            text = _safe_read_text(path)
            for match in SECRET_PATTERN.finditer(text):
                item = _finding(path, root if root.is_dir() else root.parent, text, match)
                if is_allowlisted(path, match.group(0)):
                    allowed_findings.append(item)
                else:
                    findings.append(item)

    status = "ok" if not findings else "failed"
    return {
        "phase": "P1.6",
        "status": status,
        "scanned_files": scanned_files,
        "finding_count": len(findings),
        "allowed_count": len(allowed_findings),
        "findings": findings,
        "allowed_findings": allowed_findings,
        "allowlist": {
            "test_synthetic_secret_markers": list(SYNTHETIC_SECRET_MARKERS),
            "p2_case_corpus_synthetic_secret": [
                {
                    "path": "/".join(fixture_path),
                    "scope": "exact synthetic P2 eval fixture only",
                }
                for fixture_path in P2_CASE_SYNTHETIC_SECRETS
            ],
            "redacted_secret_literal": "[redacted-secret]",
        },
        "include_runtime": include_runtime,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Scan repository files for secret-like values.")
    parser.add_argument("--path", action="append", help="Path to scan. Defaults to repository root.")
    parser.add_argument("--include-runtime", action="store_true", help="Include .runtime files.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--output", help="Optional JSON artifact path.")
    args = parser.parse_args()

    paths = [Path(value) for value in args.path] if args.path else [ROOT_DIR]
    result = scan_paths(paths, include_runtime=args.include_runtime)
    if args.output:
        _write_json(Path(args.output), result)

    if args.json or not args.output:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    raise SystemExit(0 if result["status"] == "ok" else 1)


if __name__ == "__main__":
    main()
