from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from pydantic import BaseModel, Field


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class AppSettings(BaseModel):
    APP_ENV: str = Field(default="local")
    APP_NAME: str = Field(default="TCM-Assistant")
    DATABASE_URL: str = Field(default="sqlite:///./artifacts/local_demo.db")
    EXTRACTOR_BACKEND: str = Field(default="fake")
    ENABLE_REAL_LLM: bool = Field(default=False)
    ENABLE_LOCAL_LORA: bool = Field(default=False)
    LOCAL_LLM_BASE_URL: str = Field(default="")
    LOCAL_LLM_MODEL: str = Field(default="")
    ENABLE_RAG: bool = Field(default=False)
    RAG_BACKEND: str = Field(default="bm25_stub")
    LOG_JSON: bool = Field(default=True)
    ARTIFACTS_DIR: str = Field(default="./artifacts")

    external_dependencies_required: bool = False

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> "AppSettings":
        env: dict[str, str] | os._Environ[str] = environ if environ is not None else os.environ

        def value(name: str, default: str) -> str:
            return str(env.get(name, default))

        def boolean(name: str, default: bool) -> bool:
            if environ is None:
                return _env_bool(name, default)
            raw = env.get(name)
            return default if raw is None else raw.strip().lower() in {"1", "true", "yes", "on"}

        return cls(
            APP_ENV=value("APP_ENV", "local"),
            APP_NAME=value("APP_NAME", "TCM-Assistant"),
            DATABASE_URL=value("DATABASE_URL", "sqlite:///./artifacts/local_demo.db"),
            EXTRACTOR_BACKEND=value("EXTRACTOR_BACKEND", "fake"),
            ENABLE_REAL_LLM=boolean("ENABLE_REAL_LLM", False),
            ENABLE_LOCAL_LORA=boolean("ENABLE_LOCAL_LORA", False),
            LOCAL_LLM_BASE_URL=value("LOCAL_LLM_BASE_URL", ""),
            LOCAL_LLM_MODEL=value("LOCAL_LLM_MODEL", ""),
            ENABLE_RAG=boolean("ENABLE_RAG", False),
            RAG_BACKEND=value("RAG_BACKEND", "bm25_stub"),
            LOG_JSON=boolean("LOG_JSON", True),
            ARTIFACTS_DIR=value("ARTIFACTS_DIR", "./artifacts"),
        )

    def safe_external_summary(self) -> dict[str, Any]:
        return {
            "real_llm": "enabled" if self.ENABLE_REAL_LLM else "skipped_by_design",
            "local_lora": "enabled" if self.ENABLE_LOCAL_LORA else "skipped_by_design",
            "rag": self.RAG_BACKEND if self.ENABLE_RAG else "skipped_by_design",
            "vectorstore": "skipped_by_design",
            "postgresql": "skipped_by_design",
        }


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings.from_env()
