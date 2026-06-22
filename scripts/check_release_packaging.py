from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_PATH = Path("artifacts") / "p3_3_release_packaging_check.json"
MANIFEST_PATH = Path("artifacts") / "p3_3_release_packaging.json"
RELEASE_DOC_PATH = Path("docs") / "RELEASE_PACKAGING.md"

SECRET_VALUE_PATTERN = re.compile(r"sk-[A-Za-z0-9_-]{20,}")
ABSOLUTE_PATH_PATTERN = re.compile(
    r"([A-Za-z]:[\\/]|\\\\|/Users/|/home/|/var/|C:[\\/]Users[\\/])",
    re.IGNORECASE,
)


def _read_text(path: Path) -> str:
    return (ROOT_DIR / path).read_text(encoding="utf-8")


def _path_exists(path: Path) -> bool:
    return (ROOT_DIR / path).exists()


def _check(name: str, ok: bool, detail: str = "") -> dict[str, Any]:
    return {
        "name": name,
        "status": "ok" if ok else "failed",
        "ok": bool(ok),
        "detail": detail,
    }


def _load_manifest() -> tuple[dict[str, Any], str, str]:
    path = ROOT_DIR / MANIFEST_PATH
    if not path.exists():
        return {}, "", "missing"
    text = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        return {}, text, f"invalid json: {exc}"
    if not isinstance(payload, dict):
        return {}, text, "manifest root is not an object"
    return payload, text, ""


def _env_example_has_no_secret(text: str) -> bool:
    if SECRET_VALUE_PATTERN.search(text):
        return False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("OPENAI_API_KEY="):
            _, value = stripped.split("=", 1)
            if value.strip() and value.strip().lower() not in {"example", "placeholder"}:
                return False
    return True


def _env_is_ignored() -> bool:
    gitignore = _read_text(Path(".gitignore")) if _path_exists(Path(".gitignore")) else ""
    has_env_rule = any(line.strip() == ".env" for line in gitignore.splitlines())
    keeps_example = any(line.strip() == "!.env.example" for line in gitignore.splitlines())
    if not (has_env_rule and keeps_example):
        return False

    try:
        tracked = subprocess.run(
            ["git", "ls-files", "--", ".env"],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return tracked.returncode == 0 and tracked.stdout.strip() == ""


def build_release_packaging_payload() -> dict[str, Any]:
    manifest, manifest_text, manifest_error = _load_manifest()
    release_doc = _read_text(RELEASE_DOC_PATH) if _path_exists(RELEASE_DOC_PATH) else ""
    env_example = _read_text(Path(".env.example")) if _path_exists(Path(".env.example")) else ""

    required_docs = [
        Path("docs/RUNTIME_CONFIG.md"),
        Path("docs/OBSERVABILITY.md"),
        RELEASE_DOC_PATH,
        Path("docs/P3_3_RELEASE_PACKAGING_REPORT.md"),
    ]
    required_artifacts = [MANIFEST_PATH]
    checks = [
        _check(
            "required_docs_exist",
            all(_path_exists(path) for path in required_docs),
            ", ".join(str(path).replace("\\", "/") for path in required_docs),
        ),
        _check(
            "required_manifest_artifact_exists",
            all(_path_exists(path) for path in required_artifacts),
            str(MANIFEST_PATH).replace("\\", "/"),
        ),
        _check(".env.example_exists_and_has_no_secret", bool(env_example) and _env_example_has_no_secret(env_example)),
        _check(".env_is_local_only", _env_is_ignored(), ".env ignored and not tracked in current index"),
        _check("manifest_json_parseable", bool(manifest) and not manifest_error, manifest_error),
        _check("manifest_has_no_absolute_local_paths", bool(manifest_text) and not ABSOLUTE_PATH_PATTERN.search(manifest_text)),
        _check(
            "manifest_has_no_secret_values",
            bool(manifest_text)
            and not SECRET_VALUE_PATTERN.search(manifest_text)
            and "OPENAI_API_KEY" not in manifest_text,
        ),
        _check("runtime_config_docs_exist", _path_exists(Path("docs/RUNTIME_CONFIG.md"))),
        _check("observability_docs_exist", _path_exists(Path("docs/OBSERVABILITY.md"))),
        _check(
            "recommended_unittest_command_documented",
            'python -m unittest discover -s tests -p "test*.py"' in release_doc,
        ),
        _check(
            "release_boundary_documents_no_diagnosis_or_prescription",
            all(term in release_doc for term in ["不诊断", "不开方", "不替代医生", "高风险提示线下就医"]),
        ),
        _check(
            "local_release_not_production",
            "local reproducible prototype / local engineering release candidate" in release_doc
            and "production medical product" in release_doc,
        ),
    ]
    errors = [check["name"] for check in checks if not check["ok"]]
    status = "ok" if not errors else "failed"
    return {
        "phase": "P3.3",
        "status": status,
        "checks_total": len(checks),
        "checks_passed": len(checks) - len(errors),
        "warnings": [],
        "errors": errors,
        "checks": checks,
        "manifest": {
            "path": str(MANIFEST_PATH).replace("\\", "/"),
            "phase": manifest.get("phase"),
            "release_type": manifest.get("release_type"),
            "contract_changed": manifest.get("contract_changed"),
            "sqlite_schema_changed": manifest.get("sqlite_schema_changed"),
            "boundary_violated": manifest.get("boundary_violated"),
        },
        "contract_changed": False,
        "sqlite_schema_changed": False,
        "boundary_violated": False,
        "recommend_next": "P3.4" if status == "ok" else "hold",
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def exit_code_for_payload(payload: dict[str, Any]) -> int:
    return 0 if payload.get("status") == "ok" else 1


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate P3.3 release packaging and reproducibility files.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help="JSON check artifact path. Defaults to artifacts/p3_3_release_packaging_check.json.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = _parse_args(argv)
    payload = build_release_packaging_payload()
    if args.output:
        write_json(Path(args.output), payload)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(
            json.dumps(
                {
                    "phase": payload["phase"],
                    "status": payload["status"],
                    "checks_total": payload["checks_total"],
                    "checks_passed": payload["checks_passed"],
                    "warnings": payload["warnings"],
                    "errors": payload["errors"],
                    "output": args.output,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
    return exit_code_for_payload(payload)


if __name__ == "__main__":
    raise SystemExit(main())
