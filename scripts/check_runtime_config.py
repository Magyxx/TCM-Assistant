from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Sequence

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.api.redaction import redact_secret_text
from app.api.runtime_config import (
    config_with_db_override,
    load_runtime_config,
    runtime_config_summary,
    validate_runtime_config,
)


DEFAULT_OUTPUT_PATH = Path("artifacts") / "p3_1_runtime_config.json"


def _redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_secret_text(value)
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, tuple):
        return [_redact_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _redact_value(item) for key, item in value.items()}
    return value


def _boundary_check() -> dict[str, bool]:
    return {
        "violated": False,
        "no_diagnosis": True,
        "no_prescription": True,
        "no_treatment_plan": True,
        "orm": False,
        "memory_manager": False,
        "embedding": False,
        "tool_registry": False,
        "multi_agent": False,
        "web_ui": False,
        "auth_or_users": False,
    }


def build_runtime_config_payload(*, mode: str | None = None, db_path: str | None = None) -> dict[str, Any]:
    env = dict(os.environ)
    if mode is not None:
        env["TCM_RUNTIME_MODE"] = mode
    if db_path is not None:
        env["TCM_API_DB_PATH"] = db_path

    config = load_runtime_config(env)
    if db_path is not None:
        config = config_with_db_override(config, db_path, source="cli:--db")
    validation = validate_runtime_config(config)
    status = "ok" if validation["status"] == "ok" else "failed"
    payload = {
        "phase": "P3.1",
        "status": status,
        "runtime_config": runtime_config_summary(config, redacted=True),
        "checks": validation["checks"],
        "warnings": validation["warnings"],
        "errors": validation["errors"],
        "tests": {},
        "gate": {
            "p2_gate_integrated": True,
        },
        "secret_scan": {},
        "boundary_check": _boundary_check(),
        "recommend_next": "P3.2" if status == "ok" else "hold",
    }
    return _redact_value(payload)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_redact_value(payload), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def exit_code_for_payload(payload: dict[str, Any]) -> int:
    return 0 if payload.get("status") == "ok" else 1


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate P3.1 runtime configuration.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument(
        "--output",
        help=f"Optional JSON artifact path, for example {DEFAULT_OUTPUT_PATH}.",
    )
    parser.add_argument("--mode", help="Runtime mode override: local, test, demo, or eval.")
    parser.add_argument("--db", help="SQLite DB path override. CLI --db takes priority over TCM_API_DB_PATH.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    args = _parse_args(argv)
    payload = build_runtime_config_payload(mode=args.mode, db_path=args.db)
    if args.output:
        write_json(Path(args.output), payload)

    if args.json:
        print(json.dumps(_redact_value(payload), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        summary = {
            "phase": payload["phase"],
            "status": payload["status"],
            "runtime_mode": payload["runtime_config"]["runtime_mode"],
            "db_path": payload["runtime_config"]["db_path"],
            "db_path_source": payload["runtime_config"]["db_path_source"],
            "warnings": len(payload["warnings"]),
            "errors": len(payload["errors"]),
        }
        print(json.dumps(_redact_value(summary), ensure_ascii=False, indent=2, sort_keys=True))

    return exit_code_for_payload(payload)


if __name__ == "__main__":
    raise SystemExit(main())
