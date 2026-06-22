from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


def _safe_preview(value: Any, limit: int = 240) -> str:
    text = str(value)
    text = re.sub(r"Bearer\s+\S+", "Bearer [redacted-secret]", text, flags=re.I)
    text = re.sub(r"sk-[A-Za-z0-9_\-]+", "[redacted-secret]", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


@dataclass(frozen=True)
class LocalLLMConfig:
    base_url: str
    model: str
    timeout_seconds: float = 10.0
    api_key: str | None = None
    temperature: float = 0.0

    @classmethod
    def from_env(cls) -> "LocalLLMConfig":
        raw_timeout = os.getenv("LOCAL_LLM_TIMEOUT_SECONDS") or "10"
        try:
            timeout = max(0.1, float(raw_timeout))
        except ValueError:
            timeout = 10.0
        return cls(
            base_url=(os.getenv("LOCAL_LLM_BASE_URL") or "http://127.0.0.1:8000/v1").strip(),
            model=(os.getenv("LOCAL_LLM_MODEL") or "tcm-extractor-lora").strip(),
            timeout_seconds=timeout,
            api_key=(os.getenv("LOCAL_LLM_API_KEY") or "").strip() or None,
            temperature=0.0,
        )


class LocalLLMClientError(RuntimeError):
    def __init__(self, error_type: str, message: str) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.message = message


class OpenAICompatibleChatClient:
    def __init__(self, config: LocalLLMConfig | None = None) -> None:
        self.config = config or LocalLLMConfig.from_env()

    @property
    def chat_completions_url(self) -> str:
        base = self.config.base_url.rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        return f"{base}/chat/completions"

    def create_chat_completion(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "response_format": {"type": "json_object"},
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        request = urllib.request.Request(self.chat_completions_url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                body = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise LocalLLMClientError("http_error", f"HTTP {exc.code}: {_safe_preview(body)}") from exc
        except TimeoutError as exc:
            raise LocalLLMClientError("timeout", f"local_lora request timed out after {self.config.timeout_seconds}s") from exc
        except urllib.error.URLError as exc:
            raise LocalLLMClientError("connection_error", _safe_preview(exc.reason)) from exc
        except OSError as exc:
            raise LocalLLMClientError("connection_error", _safe_preview(exc)) from exc

        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            raise LocalLLMClientError("provider_json_invalid", _safe_preview(exc)) from exc
        if not isinstance(parsed, dict):
            raise LocalLLMClientError("provider_json_invalid", "chat completion response was not a JSON object")
        return parsed


def extract_message_content(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise LocalLLMClientError("provider_response_invalid", "missing choices in chat completion response")
    first = choices[0]
    if not isinstance(first, dict):
        raise LocalLLMClientError("provider_response_invalid", "first choice was not an object")
    message = first.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
            if parts:
                return "".join(parts)
    text = first.get("text")
    if isinstance(text, str):
        return text
    raise LocalLLMClientError("provider_response_invalid", "missing assistant message content")


__all__ = [
    "LocalLLMClientError",
    "LocalLLMConfig",
    "OpenAICompatibleChatClient",
    "extract_message_content",
]
