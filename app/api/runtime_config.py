from __future__ import annotations

import os
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from app.api.redaction import redact_secret_text


SUPPORTED_RUNTIME_MODES = frozenset({"local", "test", "demo", "eval"})
VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})

DEFAULT_RUNTIME_MODE = "local"
DEFAULT_RUNTIME_DIR = Path(".runtime")
DEFAULT_ARTIFACTS_DIR = Path("artifacts")
DEFAULT_DB_PATH = DEFAULT_RUNTIME_DIR / "tcm_assistant.sqlite3"
DEFAULT_LOG_LEVEL = "INFO"

ENV_RUNTIME_MODE = "TCM_RUNTIME_MODE"
ENV_DB_PATH = "TCM_API_DB_PATH"
ENV_RUNTIME_DIR = "TCM_RUNTIME_DIR"
ENV_ARTIFACTS_DIR = "TCM_ARTIFACTS_DIR"
ENV_ALLOW_REAL_LLM = "TCM_ALLOW_REAL_LLM"
ENV_LOG_LEVEL = "TCM_LOG_LEVEL"
ENV_REDACT_LOGS = "TCM_REDACT_LOGS"
ENV_CONFIG_STRICT = "TCM_CONFIG_STRICT"
ENV_OPENAI_API_KEY = "OPENAI_API_KEY"

TRUE_VALUES = frozenset({"1", "true", "yes", "y", "on"})
FALSE_VALUES = frozenset({"0", "false", "no", "n", "off"})


@dataclass(frozen=True)
class RuntimeConfig:
    runtime_mode: str
    db_path: str
    db_path_source: str
    runtime_dir: str
    artifacts_dir: str
    allow_real_llm: bool
    openai_api_key_present: bool
    log_level: str
    redact_logs: bool
    config_strict: bool
    loaded_at: str
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


_CONFIG_CACHE: RuntimeConfig | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _env_value(env: Mapping[str, str], key: str) -> str | None:
    value = env.get(key)
    if value is None:
        return None
    return str(value)


def _parse_bool(
    env: Mapping[str, str],
    key: str,
    *,
    default: bool,
    errors: list[str],
) -> bool:
    raw_value = _env_value(env, key)
    if raw_value is None:
        return default
    normalized = raw_value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    errors.append(
        f"Invalid boolean env {key}={raw_value!r}; expected one of "
        "true/false, yes/no, on/off, or 1/0."
    )
    return default


def _path_from_env(
    env: Mapping[str, str],
    key: str,
    *,
    default: Path,
    errors: list[str],
) -> str:
    raw_value = _env_value(env, key)
    if raw_value is None:
        return default.as_posix()
    if not raw_value.strip():
        errors.append(f"Invalid path env {key}: value must not be empty.")
        return str(default)
    if "\x00" in raw_value:
        errors.append(f"Invalid path env {key}: value contains a NUL byte.")
        return str(default)
    return raw_value


def _clean_runtime_mode(env: Mapping[str, str], errors: list[str]) -> str:
    runtime_mode = (_env_value(env, ENV_RUNTIME_MODE) or DEFAULT_RUNTIME_MODE).strip().lower()
    if runtime_mode not in SUPPORTED_RUNTIME_MODES:
        errors.append(
            f"Invalid runtime_mode {runtime_mode!r}; expected one of "
            f"{', '.join(sorted(SUPPORTED_RUNTIME_MODES))}."
        )
    return runtime_mode


def _clean_log_level(env: Mapping[str, str], errors: list[str]) -> str:
    log_level = (_env_value(env, ENV_LOG_LEVEL) or DEFAULT_LOG_LEVEL).strip().upper()
    if log_level not in VALID_LOG_LEVELS:
        errors.append(
            f"Invalid log_level {log_level!r}; expected one of "
            f"{', '.join(sorted(VALID_LOG_LEVELS))}."
        )
    return log_level


def load_runtime_config(env: Mapping[str, str] | None = None) -> RuntimeConfig:
    source_env = os.environ if env is None else env
    errors: list[str] = []
    warnings: list[str] = []

    runtime_mode = _clean_runtime_mode(source_env, errors)
    runtime_dir = _path_from_env(
        source_env,
        ENV_RUNTIME_DIR,
        default=DEFAULT_RUNTIME_DIR,
        errors=errors,
    )
    artifacts_dir = _path_from_env(
        source_env,
        ENV_ARTIFACTS_DIR,
        default=DEFAULT_ARTIFACTS_DIR,
        errors=errors,
    )
    db_path = _path_from_env(
        source_env,
        ENV_DB_PATH,
        default=DEFAULT_DB_PATH,
        errors=errors,
    )
    db_path_source = f"env:{ENV_DB_PATH}" if _env_value(source_env, ENV_DB_PATH) is not None else "default"

    allow_real_llm = _parse_bool(
        source_env,
        ENV_ALLOW_REAL_LLM,
        default=False,
        errors=errors,
    )
    redact_logs = _parse_bool(
        source_env,
        ENV_REDACT_LOGS,
        default=True,
        errors=errors,
    )
    config_strict = _parse_bool(
        source_env,
        ENV_CONFIG_STRICT,
        default=False,
        errors=errors,
    )
    log_level = _clean_log_level(source_env, errors)
    openai_api_key_present = bool(_env_value(source_env, ENV_OPENAI_API_KEY))

    if runtime_mode in {"test", "eval"} and db_path_source == "default":
        warnings.append(
            f"{runtime_mode} mode should use a temporary database or an explicit {ENV_DB_PATH}/--db path."
        )
    if not redact_logs:
        warnings.append(f"{ENV_REDACT_LOGS}=false is not recommended; emitted summaries remain redacted.")
    if allow_real_llm:
        warnings.append(f"{ENV_ALLOW_REAL_LLM}=true is explicit; default gates must not require it.")
    if allow_real_llm and not openai_api_key_present:
        warnings.append(f"{ENV_ALLOW_REAL_LLM}=true but {ENV_OPENAI_API_KEY} is not present.")

    if config_strict and warnings:
        errors.extend(f"Strict config warning promoted to error: {warning}" for warning in warnings)

    return RuntimeConfig(
        runtime_mode=runtime_mode,
        db_path=db_path,
        db_path_source=db_path_source,
        runtime_dir=runtime_dir,
        artifacts_dir=artifacts_dir,
        allow_real_llm=allow_real_llm,
        openai_api_key_present=openai_api_key_present,
        log_level=log_level,
        redact_logs=redact_logs,
        config_strict=config_strict,
        loaded_at=_now_iso(),
        warnings=tuple(redact_secret_text(warning) for warning in warnings),
        errors=tuple(redact_secret_text(error) for error in errors),
    )


def get_runtime_config() -> RuntimeConfig:
    global _CONFIG_CACHE
    if _CONFIG_CACHE is None:
        _CONFIG_CACHE = load_runtime_config()
    return _CONFIG_CACHE


def reset_runtime_config_cache() -> None:
    global _CONFIG_CACHE
    _CONFIG_CACHE = None


def config_with_db_override(config: RuntimeConfig, db_path: str | Path, *, source: str = "cli:--db") -> RuntimeConfig:
    return replace(config, db_path=str(db_path), db_path_source=source)


def _nearest_existing_parent(path: Path) -> Path | None:
    candidate = path if path.is_dir() else path.parent
    if str(candidate) in {"", "."}:
        return Path(".")
    while not candidate.exists():
        parent = candidate.parent
        if parent == candidate:
            return None
        candidate = parent
    return candidate


def _check_file_parent(path_text: str, name: str) -> tuple[dict[str, Any], list[str], list[str]]:
    warnings: list[str] = []
    errors: list[str] = []
    if not path_text.strip() or "\x00" in path_text:
        errors.append(f"{name} is not a valid path.")
        return {"name": name, "status": "failed", "detail": errors[-1]}, warnings, errors

    path = Path(path_text)
    parent = path.parent if str(path.parent) not in {"", "."} else Path(".")
    if parent.exists() and not parent.is_dir():
        errors.append(f"{name} parent is not a directory: {parent}")
    elif not parent.exists():
        ancestor = _nearest_existing_parent(parent)
        if ancestor is None or not ancestor.is_dir():
            errors.append(f"{name} parent cannot be resolved: {parent}")
        else:
            warnings.append(f"{name} parent does not exist yet but can be created: {parent}")

    status = "failed" if errors else "warning" if warnings else "ok"
    detail = errors[-1] if errors else warnings[-1] if warnings else ""
    return {"name": name, "status": status, "detail": redact_secret_text(detail)}, warnings, errors


def _check_directory(path_text: str, name: str) -> tuple[dict[str, Any], list[str], list[str]]:
    warnings: list[str] = []
    errors: list[str] = []
    if not path_text.strip() or "\x00" in path_text:
        errors.append(f"{name} is not a valid path.")
        return {"name": name, "status": "failed", "detail": errors[-1]}, warnings, errors

    path = Path(path_text)
    if path.exists() and not path.is_dir():
        errors.append(f"{name} exists but is not a directory: {path}")
    elif not path.exists():
        ancestor = _nearest_existing_parent(path)
        if ancestor is None or not ancestor.is_dir():
            errors.append(f"{name} cannot be resolved: {path}")
        else:
            warnings.append(f"{name} does not exist yet but can be created: {path}")

    status = "failed" if errors else "warning" if warnings else "ok"
    detail = errors[-1] if errors else warnings[-1] if warnings else ""
    return {"name": name, "status": status, "detail": redact_secret_text(detail)}, warnings, errors


def validate_runtime_config(config: RuntimeConfig) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    warnings = list(config.warnings)
    errors = list(config.errors)

    checks.append(
        {
            "name": "runtime_mode",
            "status": "ok" if config.runtime_mode in SUPPORTED_RUNTIME_MODES else "failed",
            "detail": "" if config.runtime_mode in SUPPORTED_RUNTIME_MODES else "unsupported runtime mode",
        }
    )
    checks.append(
        {
            "name": "log_level",
            "status": "ok" if config.log_level in VALID_LOG_LEVELS else "failed",
            "detail": "" if config.log_level in VALID_LOG_LEVELS else "unsupported log level",
        }
    )
    for check_name, path_text, is_dir in (
        ("db_path", config.db_path, False),
        ("runtime_dir", config.runtime_dir, True),
        ("artifacts_dir", config.artifacts_dir, True),
    ):
        check, path_warnings, path_errors = (
            _check_directory(path_text, check_name)
            if is_dir
            else _check_file_parent(path_text, check_name)
        )
        checks.append(check)
        warnings.extend(path_warnings)
        errors.extend(path_errors)

    checks.append(
        {
            "name": "redaction_enabled",
            "status": "ok" if config.redact_logs else "warning",
            "detail": "" if config.redact_logs else "summaries are still forcibly redacted",
        }
    )
    checks.append(
        {
            "name": "openai_api_key_present",
            "status": "ok",
            "detail": f"present={str(config.openai_api_key_present).lower()}",
        }
    )
    checks.append(
        {
            "name": "allow_real_llm",
            "status": "warning" if config.allow_real_llm else "ok",
            "detail": "explicitly enabled" if config.allow_real_llm else "disabled",
        }
    )

    failed_checks = [check for check in checks if check.get("status") == "failed"]
    status = "failed" if failed_checks or errors else "ok"
    return {
        "status": status,
        "checks": checks,
        "warnings": [redact_secret_text(str(warning)) for warning in warnings],
        "errors": [redact_secret_text(str(error)) for error in errors],
    }


def runtime_config_summary(config: RuntimeConfig, redacted: bool = True) -> dict[str, Any]:
    def clean(value: str) -> str:
        return redact_secret_text(value) if redacted else value

    return {
        "runtime_mode": config.runtime_mode,
        "db_path": clean(config.db_path),
        "db_path_source": config.db_path_source,
        "runtime_dir": clean(config.runtime_dir),
        "artifacts_dir": clean(config.artifacts_dir),
        "allow_real_llm": config.allow_real_llm,
        "openai_api_key_present": config.openai_api_key_present,
        "log_level": config.log_level,
        "redact_logs": config.redact_logs,
        "config_strict": config.config_strict,
        "loaded_at": config.loaded_at,
    }
