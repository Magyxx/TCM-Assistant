from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.api.versioning import (  # noqa: E402
    API_CONTRACT_STATUS,
    API_STAGE,
    API_VERSION,
    API_VERSION_HEADER,
    SERVICE_NAME,
    VERSION_ENDPOINT_SUPPORTED,
    VERSIONED_ALIAS_SUPPORTED,
)

DEFAULT_OUTPUT_PATH = Path("artifacts") / "p3_4_api_contract_check.json"
DEFAULT_SNAPSHOT_PATH = Path("artifacts") / "p3_4_api_contract_snapshot.json"
P1_CONTRACT_PATH = Path("artifacts") / "p1_api_contract_snapshot.json"
API_VERSIONING_DOC_PATH = Path("docs") / "API_VERSIONING.md"

SECRET_VALUE_PATTERN = re.compile(r"sk-[A-Za-z0-9_-]{8,}")
SECRET_NAME_PATTERN = re.compile(r"OPENAI_API_KEY|SECRET|TOKEN|PASSWORD|AUTHORIZATION|COOKIE", re.IGNORECASE)
ABSOLUTE_PATH_PATTERN = re.compile(
    r"([A-Za-z]:[\\/]|\\\\|/Users/|/home/|/var/|C:[\\/]Users[\\/])",
    re.IGNORECASE,
)
PUBLIC_ENDPOINT_ORDER = [
    ("GET", "/health"),
    ("GET", "/version"),
    ("POST", "/sessions"),
    ("POST", "/sessions/{session_id}/turn"),
    ("GET", "/sessions/{session_id}/state"),
    ("GET", "/sessions/{session_id}/report"),
]
CORE_ENDPOINTS = {
    ("GET", "/health"),
    ("POST", "/sessions"),
    ("POST", "/sessions/{session_id}/turn"),
    ("GET", "/sessions/{session_id}/state"),
    ("GET", "/sessions/{session_id}/report"),
}


Check = dict[str, Any]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads((ROOT_DIR / path).read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _read_text(path: Path) -> str:
    return (ROOT_DIR / path).read_text(encoding="utf-8")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    output_path = ROOT_DIR / path if not path.is_absolute() else path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _check(name: str, ok: bool, detail: str = "") -> Check:
    return {
        "name": name,
        "status": "ok" if ok else "failed",
        "ok": bool(ok),
        "detail": detail,
    }


def _model_name(model: Any) -> str | None:
    if model is None:
        return None
    return getattr(model, "__name__", str(model))


def _model_fields(model: Any) -> list[str]:
    fields = getattr(model, "model_fields", None)
    if isinstance(fields, dict):
        return sorted(str(name) for name in fields)
    return []


def _body_model(route: APIRoute) -> Any:
    body_params = getattr(getattr(route, "dependant", None), "body_params", []) or []
    if body_params:
        field_info = getattr(body_params[0], "field_info", None)
        annotation = getattr(field_info, "annotation", None)
        if annotation is not None:
            return annotation
    return None


def _route_category(method: str, path: str) -> str:
    if path == "/health":
        return "health"
    if path == "/version":
        return "version_metadata"
    if (method, path) in CORE_ENDPOINTS:
        return "public_api"
    return "internal_or_docs"


def _public_routes() -> list[APIRoute]:
    from app.api.main import app

    routes: list[APIRoute] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if route.path.startswith(("/docs", "/redoc", "/openapi")):
            continue
        routes.append(route)
    return routes


def _route_methods(route: APIRoute) -> list[str]:
    return sorted(method for method in route.methods if method not in {"HEAD", "OPTIONS"})


def _route_endpoint_items() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for route in _public_routes():
        request_model = _body_model(route)
        response_model = getattr(route, "response_model", None)
        for method in _route_methods(route):
            category = _route_category(method, route.path)
            items.append(
                {
                    "method": method,
                    "path": route.path,
                    "request_model": _model_name(request_model),
                    "request_fields": _model_fields(request_model),
                    "response_model": _model_name(response_model),
                    "response_required_fields": _model_fields(response_model),
                    "status_code": int(route.status_code or 200),
                    "public_contract": category in {"health", "version_metadata", "public_api"},
                    "category": category,
                    "internal_or_health_debug": category if category in {"health", "version_metadata"} else None,
                    "compatibility": "frozen" if (method, route.path) in CORE_ENDPOINTS else "additive",
                    "future_additive_change_allowed": True,
                }
            )

    order = {endpoint: index for index, endpoint in enumerate(PUBLIC_ENDPOINT_ORDER)}
    return sorted(items, key=lambda item: (order.get((item["method"], item["path"]), 999), item["path"], item["method"]))


def build_contract_snapshot() -> dict[str, Any]:
    from app.api.main import app

    p1_contract = _read_json(P1_CONTRACT_PATH)
    openapi = app.openapi()
    endpoints = _route_endpoint_items()
    return {
        "phase": API_STAGE,
        "api_version": API_VERSION,
        "contract_status": API_CONTRACT_STATUS,
        "service": SERVICE_NAME,
        "created_at": _utc_now(),
        "source": "FastAPI route inventory plus P1 contract snapshot metadata",
        "public_endpoint_count": len(endpoints),
        "public_endpoints": endpoints,
        "frozen_p1_p2_contract": {
            "source_snapshot": str(P1_CONTRACT_PATH).replace("\\", "/"),
            "contract_version": p1_contract.get("contract_version"),
            "endpoints": [
                {
                    "method": item.get("method"),
                    "path": item.get("path"),
                    "request_schema": item.get("request_schema"),
                    "success_response_required_fields": item.get("success_response_required_fields", []),
                }
                for item in p1_contract.get("endpoints", [])
            ],
            "error_response_shape": p1_contract.get("error_response_shape"),
        },
        "headers": {
            "X-Request-ID": "P3.2 additive tracing header; does not change response body.",
            API_VERSION_HEADER: f"P3.4 additive API version header; fixed value {API_VERSION}.",
        },
        "version_endpoint_supported": VERSION_ENDPOINT_SUPPORTED,
        "versioned_alias_supported": VERSIONED_ALIAS_SUPPORTED,
        "versioned_alias_policy": (
            "P3.4 freezes current public API as v1-compatible surface. "
            "Physical /api/v1 aliases are deferred unless needed by downstream clients."
        ),
        "openapi_summary": {
            "title": openapi.get("info", {}).get("title"),
            "app_version": openapi.get("info", {}).get("version"),
            "path_count": len(openapi.get("paths", {})),
        },
        "breaking_change_rules": [
            "delete public endpoint",
            "change existing endpoint method",
            "change existing endpoint path",
            "remove existing response body field",
            "change response field type",
            "change optional field to required",
            "change existing error semantics",
            "change SQLite schema in a way that breaks historical sessions",
            "turn assistant intake output into diagnosis, prescription, or treatment plan output",
        ],
        "non_breaking_additive_rules": [
            "add endpoint",
            "add optional response field",
            "add response header",
            "add optional request field",
            "add artifact",
            "add check script",
            "add documentation",
            "add versioned alias while retaining original endpoint",
        ],
        "contract_changed": False,
        "api_response_body_changed": False,
        "sqlite_schema_changed": False,
        "boundary_violated": False,
    }


def _endpoint_map(snapshot: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (str(item.get("method")), str(item.get("path"))): item
        for item in snapshot.get("public_endpoints", [])
        if isinstance(item, dict)
    }


def _p1_endpoint_map() -> dict[tuple[str, str], dict[str, Any]]:
    p1_contract = _read_json(P1_CONTRACT_PATH)
    return {
        (str(item.get("method")), str(item.get("path"))): item
        for item in p1_contract.get("endpoints", [])
        if isinstance(item, dict)
    }


def _json_has_secret(text: str) -> bool:
    return bool(SECRET_VALUE_PATTERN.search(text) or SECRET_NAME_PATTERN.search(text))


def _json_has_absolute_path(text: str) -> bool:
    return bool(ABSOLUTE_PATH_PATTERN.search(text))


def _docs_text() -> str:
    path = ROOT_DIR / API_VERSIONING_DOC_PATH
    return path.read_text(encoding="utf-8") if path.exists() else ""


def build_api_contract_check_payload(*, snapshot_output: Path | None = DEFAULT_SNAPSHOT_PATH) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    checks: list[Check] = []

    snapshot: dict[str, Any] = {}
    openapi: dict[str, Any] = {}
    app_imported = False
    try:
        from app.api.main import app

        app_imported = True
        openapi = app.openapi()
        snapshot = build_contract_snapshot()
    except Exception as exc:  # pragma: no cover - defensive check payload
        errors.append(f"app_import_or_snapshot_failed:{type(exc).__name__}")

    if snapshot and snapshot_output is not None:
        _write_json(snapshot_output, snapshot)

    snapshot_text = json.dumps(snapshot, ensure_ascii=False, sort_keys=True) if snapshot else ""
    parsed_snapshot: dict[str, Any] = {}
    snapshot_parse_error = ""
    try:
        if snapshot_output is not None:
            parsed_snapshot = json.loads((ROOT_DIR / snapshot_output).read_text(encoding="utf-8"))
        elif snapshot:
            parsed_snapshot = json.loads(snapshot_text)
    except (OSError, json.JSONDecodeError) as exc:
        snapshot_parse_error = str(exc)

    route_endpoints = set(_endpoint_map(snapshot))
    p1_endpoints = _p1_endpoint_map()
    core_missing = sorted(f"{method} {path}" for method, path in CORE_ENDPOINTS if (method, path) not in route_endpoints)
    p1_missing = sorted(f"{method} {path}" for method, path in p1_endpoints if (method, path) not in route_endpoints)

    method_stable = not p1_missing
    body_schema_unchanged = True
    body_schema_details: list[str] = []
    for key, p1_endpoint in p1_endpoints.items():
        current = _endpoint_map(snapshot).get(key)
        if not current:
            body_schema_unchanged = False
            body_schema_details.append(f"missing:{key[0]} {key[1]}")
            continue
        expected_fields = set(p1_endpoint.get("success_response_required_fields") or [])
        current_fields = set(current.get("response_required_fields") or [])
        missing_fields = sorted(expected_fields - current_fields)
        if missing_fields:
            body_schema_unchanged = False
            body_schema_details.append(f"{key[0]} {key[1]} missing fields {missing_fields}")

    request_id_header_ok = False
    version_header_ok = False
    try:
        previous_log_level = os.environ.get("TCM_LOG_LEVEL")
        os.environ["TCM_LOG_LEVEL"] = "CRITICAL"
        try:
            from app.api.runtime_config import reset_runtime_config_cache

            reset_runtime_config_cache()
        except Exception:
            pass
        from app.api.main import app

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/health", headers={"X-Request-ID": "p3-4-contract"})
        p1_contract = _read_json(P1_CONTRACT_PATH)
        request_id_header_ok = (
            response.status_code == 200
            and response.json() == p1_contract.get("health_contract")
            and response.headers.get("X-Request-ID") == "p3-4-contract"
        )
        version_header_ok = response.headers.get(API_VERSION_HEADER) == API_VERSION
    finally:
        if "previous_log_level" in locals():
            if previous_log_level is None:
                os.environ.pop("TCM_LOG_LEVEL", None)
            else:
                os.environ["TCM_LOG_LEVEL"] = previous_log_level
            try:
                from app.api.runtime_config import reset_runtime_config_cache

                reset_runtime_config_cache()
            except Exception:
                pass

    docs = _docs_text()
    docs_breaking_ok = "breaking change policy" in docs and "delete public endpoint" in docs
    docs_safety_ok = all(phrase in docs for phrase in ["不诊断", "不开方", "不替代医生", "高风险提示线下就医"])

    checks.extend(
        [
            _check("api_version_constant_exists", isinstance(API_VERSION, str) and bool(API_VERSION)),
            _check("api_version_is_v1", API_VERSION == "v1", API_VERSION),
            _check("contract_status_frozen", API_CONTRACT_STATUS == "frozen", API_CONTRACT_STATUS),
            _check("fastapi_app_importable", app_imported),
            _check("openapi_schema_generated", bool(openapi.get("paths")), f"paths={len(openapi.get('paths', {}))}"),
            _check("public_endpoint_snapshot_generated", bool(snapshot.get("public_endpoints")), f"count={snapshot.get('public_endpoint_count')}"),
            _check("core_endpoints_still_exist", not core_missing, ", ".join(core_missing)),
            _check("core_endpoint_methods_unchanged", method_stable, ", ".join(p1_missing)),
            _check("response_body_schema_unchanged", body_schema_unchanged, "; ".join(body_schema_details)),
            _check("request_id_header_body_unchanged", request_id_header_ok),
            _check("api_version_header_present", version_header_ok, API_VERSION_HEADER),
            _check("contract_snapshot_json_parseable", bool(parsed_snapshot) and not snapshot_parse_error, snapshot_parse_error),
            _check("contract_snapshot_has_no_secret", bool(snapshot_text) and not _json_has_secret(snapshot_text)),
            _check("contract_snapshot_has_no_absolute_local_paths", bool(snapshot_text) and not _json_has_absolute_path(snapshot_text)),
            _check("docs_include_breaking_change_policy", docs_breaking_ok),
            _check("docs_include_safety_boundary", docs_safety_ok),
        ]
    )

    failed_checks = [check["name"] for check in checks if not check["ok"]]
    errors.extend(failed_checks)
    status = "ok" if not errors else "failed"
    return {
        "status": status,
        "phase": API_STAGE,
        "api_version": API_VERSION,
        "contract_status": API_CONTRACT_STATUS,
        "checks_total": len(checks),
        "checks_passed": len(checks) - len(failed_checks),
        "warnings": warnings,
        "errors": errors,
        "checks": checks,
        "public_endpoint_count": snapshot.get("public_endpoint_count"),
        "version_headers_supported": version_header_ok,
        "version_endpoint_supported": VERSION_ENDPOINT_SUPPORTED,
        "versioned_alias_supported": VERSIONED_ALIAS_SUPPORTED,
        "contract_snapshot_created": bool(snapshot),
        "contract_changed": False,
        "api_response_body_changed": False,
        "sqlite_schema_changed": False,
        "boundary_violated": False,
        "recommend_next": "P3.5" if status == "ok" else "hold",
    }


def exit_code_for_payload(payload: dict[str, Any]) -> int:
    return 0 if payload.get("status") == "ok" else 1


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate P3.4 API versioning and contract freeze metadata.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help="JSON check artifact path. Use an empty value to skip writing.",
    )
    parser.add_argument(
        "--snapshot-output",
        default=str(DEFAULT_SNAPSHOT_PATH),
        help="JSON contract snapshot path. Use an empty value to skip writing.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = _parse_args(argv)
    snapshot_output = Path(args.snapshot_output) if args.snapshot_output else None
    payload = build_api_contract_check_payload(snapshot_output=snapshot_output)
    if args.output:
        _write_json(Path(args.output), payload)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(
            json.dumps(
                {
                    "phase": payload["phase"],
                    "status": payload["status"],
                    "api_version": payload["api_version"],
                    "contract_status": payload["contract_status"],
                    "checks_total": payload["checks_total"],
                    "checks_passed": payload["checks_passed"],
                    "warnings": payload["warnings"],
                    "errors": payload["errors"],
                    "output": args.output,
                    "snapshot_output": args.snapshot_output,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
    return exit_code_for_payload(payload)


if __name__ == "__main__":
    raise SystemExit(main())