from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def json_safe(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, Path):
        try:
            return str(value.relative_to(ROOT_DIR)).replace("\\", "/")
        except ValueError:
            return str(value).replace("\\", "/")
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    return value


def write_json(path: Path | str, payload: dict[str, Any]) -> None:
    target = Path(path)
    if not target.is_absolute():
        target = ROOT_DIR / target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def read_json(path: Path | str) -> dict[str, Any]:
    target = Path(path)
    if not target.is_absolute():
        target = ROOT_DIR / target
    if not target.exists():
        return {}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def status_from_checks(checks: list[dict[str, Any]]) -> str:
    return "ok" if all(check.get("ok") is True for check in checks) else "failed"


def check(name: str, ok: bool, detail: str = "", **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": name,
        "ok": bool(ok),
        "status": "ok" if ok else "failed",
        "detail": detail,
    }
    if extra:
        payload["extra"] = extra
    return payload
