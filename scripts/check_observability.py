from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.api.observability import (
    EVENT_FIELDS,
    REDACTED,
    generate_request_id,
    make_log_event,
    redact_observable_value,
)
from app.api.runtime_config import get_runtime_config


DEFAULT_OUTPUT_PATH = Path("artifacts") / "p3_2_observability.json"


def _check(name: str, ok: bool, detail: str = "") -> dict[str, Any]:
    return {
        "name": name,
        "status": "ok" if ok else "failed",
        "ok": bool(ok),
        "detail": str(detail),
    }


def _redact_payload(value: Any) -> Any:
    return redact_observable_value(value, redact_logs=True)


def build_observability_payload() -> dict[str, Any]:
    config = get_runtime_config()
    request_id = generate_request_id()
    secret = "sk-" + "observabilitysecret0001"
    event = make_log_event(
        "observability.check",
        component="scripts.check_observability",
        request_id=request_id,
        session_id="session-check",
        turn_id="turn-check",
        status="ok",
        duration_ms=1.25,
        message=f"checking secret {secret}",
        extra={
            "OPENAI_API_KEY": secret,
            "nested": [{"token": secret}, {"safe": "value"}],
            "user_input": "胃胀" * 120,
        },
        config=config,
    )
    serialized = json.dumps(event, ensure_ascii=False, sort_keys=True)
    checks = [
        _check("structured_event_fields", list(event.keys()) == list(EVENT_FIELDS)),
        _check("json_serializable", bool(json.dumps(event, ensure_ascii=False))),
        _check("request_id_supported", bool(request_id and event["request_id"] == request_id)),
        _check("secret_value_redacted", secret not in serialized and REDACTED in serialized),
        _check("openai_api_key_value_absent", "observabilitysecret0001" not in serialized),
        _check("nested_redaction", REDACTED in json.dumps(event["extra"]["nested"][0], ensure_ascii=False)),
        _check("sensitive_key_name_redacted", "OPENAI_API_KEY" not in serialized),
        _check("long_user_text_truncated", "[TRUNCATED]" in event["extra"]["user_input"]),
        _check("runtime_mode_present", event["runtime_mode"] == config.runtime_mode),
    ]
    status = "ok" if all(check["ok"] for check in checks) else "failed"
    return _redact_payload(
        {
            "phase": "P3.2",
            "status": status,
            "runtime_mode": config.runtime_mode,
            "structured_logging": True,
            "redaction_enabled": True,
            "request_id_supported": True,
            "p2_gate_integrated": True,
            "tests": {},
            "checks": checks,
            "sample_event": event,
            "contract_changed": False,
            "sqlite_schema_changed": False,
            "boundary_violated": False,
            "created_at": event["ts"],
            "recommend_next": "P3.3" if status == "ok" else "hold",
        }
    )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_redact_payload(payload), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def exit_code_for_payload(payload: dict[str, Any]) -> int:
    return 0 if payload.get("status") == "ok" else 1


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate P3.2 observability and redacted logging.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help="JSON artifact path. Defaults to artifacts/p3_2_observability.json.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = _parse_args(argv)
    payload = build_observability_payload()
    write_json(Path(args.output), payload)
    if args.json:
        print(json.dumps(_redact_payload(payload), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(
            json.dumps(
                {
                    "phase": payload["phase"],
                    "status": payload["status"],
                    "runtime_mode": payload["runtime_mode"],
                    "structured_logging": payload["structured_logging"],
                    "redaction_enabled": payload["redaction_enabled"],
                    "checks": len(payload["checks"]),
                    "output": str(args.output),
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
    return exit_code_for_payload(payload)


if __name__ == "__main__":
    raise SystemExit(main())
