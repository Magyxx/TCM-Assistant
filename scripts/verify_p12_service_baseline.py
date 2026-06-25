from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

STAGE = "P12-M1_SERVICE_BASELINE"
DEFAULT_OUTPUT = ROOT_DIR / "artifacts" / "p12" / "service_baseline.json"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


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


def _module_exists(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _repo_path(path: Path) -> str:
    return path.relative_to(ROOT_DIR).as_posix()


def _route_inventory() -> list[dict[str, Any]]:
    from app.api.main import app

    routes: list[dict[str, Any]] = []
    for route in app.routes:
        methods = sorted(method for method in getattr(route, "methods", set()) if method not in {"HEAD", "OPTIONS"})
        path = getattr(route, "path", "")
        if not methods or not path:
            continue
        routes.append(
            {
                "path": path,
                "methods": methods,
                "name": getattr(route, "name", ""),
            }
        )
    return sorted(routes, key=lambda item: (item["path"], ",".join(item["methods"])))


def _has_route(routes: list[dict[str, Any]], method: str, path: str) -> bool:
    return any(route["path"] == path and method in route["methods"] for route in routes)


def _openapi_probe(routes: list[dict[str, Any]]) -> dict[str, Any]:
    from app.api.main import app

    schema = app.openapi()
    paths = sorted((schema.get("paths") or {}).keys())
    required = ["/health", "/sessions", "/sessions/{session_id}/turn"]
    return {
        "exportable": bool(schema.get("openapi") and paths),
        "path_count": len(paths),
        "required_paths_present": {path: path in paths for path in required},
        "route_count": len(routes),
    }


def _service_layer_inventory() -> dict[str, Any]:
    modules = {
        "consultation_service": "app.services.consultation_service",
        "report_service": "app.services.report_service",
        "eval_service": "app.services.eval_service",
        "export_service": "app.services.export_service",
        "p7_runtime": "app.services.p7_runtime",
    }
    return {name: _module_exists(module) for name, module in modules.items()}


def _storage_inventory() -> dict[str, Any]:
    from app.api.runtime_config import DEFAULT_DB_PATH
    from app.api.sqlite_store import STORE_SCHEMA_STAGE, STORE_SCHEMA_VERSION, STORE_TABLES
    from app.storage.postgres_store import schema_ready_status
    from app.storage.sqlite_store import P7_SQLITE_SCHEMA_STAGE, P7_SQLITE_SCHEMA_VERSION, P7_TABLES

    return {
        "default_storage": {
            "api_runtime": "sqlite",
            "api_db_path": DEFAULT_DB_PATH.as_posix(),
            "session_service": "sqlite",
        },
        "api_sqlite_store": {
            "present": _module_exists("app.api.sqlite_store"),
            "schema_stage": STORE_SCHEMA_STAGE,
            "schema_version": STORE_SCHEMA_VERSION,
            "tables": list(STORE_TABLES),
        },
        "p7_sqlite_store": {
            "present": _module_exists("app.storage.sqlite_store"),
            "schema_stage": P7_SQLITE_SCHEMA_STAGE,
            "schema_version": P7_SQLITE_SCHEMA_VERSION,
            "tables": list(P7_TABLES),
        },
        "session_sqlite_store": {
            "present": _module_exists("app.session.sqlite_store"),
        },
        "postgresql_ready": schema_ready_status(),
    }


def _filesystem_inventory() -> dict[str, Any]:
    checked = [
        "app/api",
        "app/services",
        "app/storage",
        "app/session",
        "app/graphs",
        "app/reports",
        "app/eval",
        "app/main.py",
        "README.md",
        ".env.example",
    ]
    return {path: (ROOT_DIR / path).exists() for path in checked}


def build_service_baseline() -> dict[str, Any]:
    routes = _route_inventory()
    route_checks = {
        "health": _has_route(routes, "GET", "/health"),
        "create_session": _has_route(routes, "POST", "/sessions"),
        "turn": _has_route(routes, "POST", "/sessions/{session_id}/turn"),
        "state": _has_route(routes, "GET", "/sessions/{session_id}/state"),
        "report_get": _has_route(routes, "GET", "/sessions/{session_id}/report"),
        "report_post": _has_route(routes, "POST", "/sessions/{session_id}/report"),
        "turns": _has_route(routes, "GET", "/sessions/{session_id}/turns"),
        "eval_final": _has_route(routes, "POST", "/eval/final"),
        "eval_p7": _has_route(routes, "POST", "/eval/p7"),
        "eval_p9m2": _has_route(routes, "POST", "/eval/p9m2-multiturn"),
        "version": _has_route(routes, "GET", "/version"),
    }
    service_layer = _service_layer_inventory()
    storage = _storage_inventory()
    openapi = _openapi_probe(routes)
    checks = {
        "fastapi_app_importable": _module_exists("app.api.main"),
        "route_inventory_nonempty": bool(routes),
        "service_layer_present": all(service_layer.values()),
        "storage_layer_present": storage["api_sqlite_store"]["present"]
        and storage["p7_sqlite_store"]["present"]
        and storage["session_sqlite_store"]["present"],
        "session_lifecycle_present": route_checks["create_session"] and route_checks["state"],
        "turn_endpoint_present": route_checks["turn"],
        "report_endpoint_present": route_checks["report_get"] and route_checks["report_post"],
        "eval_endpoint_present": route_checks["eval_final"] or route_checks["eval_p7"] or route_checks["eval_p9m2"],
        "health_endpoint_present": route_checks["health"],
        "openapi_exportable": openapi["exportable"] and all(openapi["required_paths_present"].values()),
        "sqlite_present": storage["api_sqlite_store"]["present"] and storage["p7_sqlite_store"]["present"],
        "postgresql_schema_ready": bool(storage["postgresql_ready"]["schema_ready"]),
    }
    gaps = [
        "PostgreSQL is schema-ready only; no runtime driver or live PostgreSQL service is required for P12.",
        "Live vLLM and LoRA backends remain optional and skipped unless explicitly enabled.",
        "No frontend or production deployment surface is in scope for P12.",
    ]
    status = "ok" if all(checks.values()) else "failed"
    return {
        "stage": STAGE,
        "status": status,
        "branch": _git(["branch", "--show-current"]),
        "head": _git(["rev-parse", "HEAD"]),
        "base_main": _git(["rev-parse", "origin/main"]),
        "fastapi_app_import_path": "app.api.main:app",
        "filesystem_inventory": _filesystem_inventory(),
        "endpoints": routes,
        "route_checks": route_checks,
        "service_layer": service_layer,
        "storage_backend": storage,
        "current_default_storage": storage["default_storage"],
        "session_lifecycle_exists": route_checks["create_session"] and route_checks["state"],
        "turn_endpoint_exists": route_checks["turn"],
        "report_endpoint_exists": route_checks["report_get"] or route_checks["report_post"],
        "eval_endpoint_exists": route_checks["eval_final"] or route_checks["eval_p7"] or route_checks["eval_p9m2"],
        "health_endpoint_exists": route_checks["health"],
        "openapi": openapi,
        "sqlite_exists": checks["sqlite_present"],
        "postgresql_ready_schema_exists": checks["postgresql_schema_ready"],
        "current_gaps": gaps,
        "p12_landing_plan": [
            "M2: lock session, turn, state, and health API smoke contracts.",
            "M3: lock SQLite persistence and replay contract with temporary test DBs.",
            "M4: lock report, eval, and extended health safety contracts.",
            "M5: aggregate P12 regression and export OpenAPI.",
            "M6: produce merge gate report without merging main.",
        ],
        "checks": checks,
        "git_status_short": _git(["status", "--short"]).splitlines(),
    }


def verify() -> dict[str, Any]:
    return build_service_baseline()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Verify P12 service readiness baseline.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Artifact output path.")
    args = parser.parse_args()
    payload = verify()
    if args.output:
        _write_json(Path(args.output), payload)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(
            json.dumps(
                {
                    "stage": payload["stage"],
                    "status": payload["status"],
                    "output": str(Path(args.output).relative_to(ROOT_DIR))
                    if Path(args.output).is_absolute()
                    else args.output,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
