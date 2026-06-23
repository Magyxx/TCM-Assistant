from __future__ import annotations

import os
from dataclasses import dataclass

from app.extractors.base import BackendResult, ExtractorBackend, backend_result_from_local_vllm
from app.extractors.cloud_llm_extractor import extract_with_cloud_llm
from app.extractors.fake_extractor import extract_with_fake_backend
from app.extractors.local_lora_extractor import (
    DEFAULT_LOCAL_LORA_MODEL,
    extract_with_local_lora,
)
from app.extractors.local_vllm_extractor import (
    DEFAULT_LOCAL_BASE_LLM_MODEL,
    get_local_llm_api_key,
    get_local_llm_base_url,
    get_local_llm_max_tokens,
    get_local_llm_temperature,
    extract_with_local_vllm,
)
from app.schemas.report_schemas import RunState


SUPPORTED_EXTRACTOR_BACKENDS = ("fake", "local_base", "local_lora", "cloud_llm")


def normalize_backend_name(value: str | None) -> str:
    name = (value or os.getenv("EXTRACTOR_BACKEND") or "fake").strip().lower()
    aliases = {
        "local-vllm": "local_base",
        "local_vllm": "local_base",
        "lora": "local_lora",
        "local-lora": "local_lora",
        "cloud": "cloud_llm",
        "real_llm": "cloud_llm",
    }
    return aliases.get(name, name)


@dataclass
class FakeExtractorBackend:
    name: str = "fake"

    def extract_turn(self, state: RunState, user_input: str) -> BackendResult:
        return extract_with_fake_backend(state, user_input)


@dataclass
class LocalBaseExtractorBackend:
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    max_tokens: int | None = None
    temperature: float | None = None
    name: str = "local_base"

    def extract_turn(self, state: RunState, user_input: str) -> BackendResult:
        result = extract_with_local_vllm(
            state,
            user_input,
            base_url=self.base_url or get_local_llm_base_url(),
            model=(
                self.model
                or os.getenv("LOCAL_BASE_LLM_MODEL")
                or os.getenv("LOCAL_LLM_MODEL")
                or DEFAULT_LOCAL_BASE_LLM_MODEL
            ),
            api_key=self.api_key or get_local_llm_api_key(),
            max_tokens=self.max_tokens or get_local_llm_max_tokens(),
            temperature=get_local_llm_temperature() if self.temperature is None else self.temperature,
            response_format_enabled=False,
        )
        return backend_result_from_local_vllm(self.name, result)


@dataclass
class LocalLoraExtractorBackend:
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    max_tokens: int | None = None
    temperature: float | None = None
    allow_fallback: bool | None = None
    name: str = "local_lora"

    def extract_turn(self, state: RunState, user_input: str) -> BackendResult:
        result = extract_with_local_lora(
            state,
            user_input,
            base_url=self.base_url or get_local_llm_base_url(),
            model=self.model or os.getenv("LOCAL_LORA_MODEL") or os.getenv("LOCAL_LLM_MODEL") or DEFAULT_LOCAL_LORA_MODEL,
            api_key=self.api_key or get_local_llm_api_key(),
            max_tokens=self.max_tokens or get_local_llm_max_tokens(),
            temperature=get_local_llm_temperature() if self.temperature is None else self.temperature,
            response_format_enabled=False,
            allow_fallback=self.allow_fallback,
        )
        return backend_result_from_local_vllm(self.name, result)


@dataclass
class CloudLLMExtractorBackend:
    name: str = "cloud_llm"

    def extract_turn(self, state: RunState, user_input: str) -> BackendResult:
        return extract_with_cloud_llm(state, user_input)


def get_extractor_backend(
    backend_name: str | None = None,
    *,
    base_url: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    allow_fallback: bool | None = None,
) -> ExtractorBackend:
    name = normalize_backend_name(backend_name)
    if name == "fake":
        return FakeExtractorBackend()
    if name == "local_base":
        return LocalBaseExtractorBackend(
            base_url=base_url,
            model=model,
            api_key=api_key,
            max_tokens=max_tokens,
            temperature=temperature,
        )
    if name == "local_lora":
        return LocalLoraExtractorBackend(
            base_url=base_url,
            model=model,
            api_key=api_key,
            max_tokens=max_tokens,
            temperature=temperature,
            allow_fallback=allow_fallback,
        )
    if name == "cloud_llm":
        return CloudLLMExtractorBackend()
    allowed = ", ".join(SUPPORTED_EXTRACTOR_BACKENDS)
    raise ValueError(f"Unknown EXTRACTOR_BACKEND '{backend_name or name}'. Expected one of: {allowed}.")


def extract_with_backend_router(
    state: RunState,
    user_input: str,
    *,
    backend_name: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    allow_fallback: bool | None = None,
) -> BackendResult:
    backend = get_extractor_backend(
        backend_name,
        base_url=base_url,
        model=model,
        api_key=api_key,
        max_tokens=max_tokens,
        temperature=temperature,
        allow_fallback=allow_fallback,
    )
    return backend.extract_turn(state, user_input)
