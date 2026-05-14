from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from .base import ProviderConfigError, ProviderExecutionError


Transport = Callable[[str, Mapping[str, Any], Mapping[str, str], float], Mapping[str, Any]]


def _clean_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def _urllib_transport(url: str, payload: Mapping[str, Any], headers: Mapping[str, str], timeout: float) -> Mapping[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=dict(headers), method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise ProviderExecutionError(f"OpenRouter request failed with HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise ProviderExecutionError(f"OpenRouter request failed: {exc.reason}") from exc


@dataclass
class OpenRouterLLMProvider:
    """OpenAI-compatible OpenRouter client for LLM/VLM reasoning only."""

    api_key: str | None = None
    base_url: str | None = None
    default_model: str | None = None
    transport: Transport | None = None
    timeout: float = 30.0
    app_name: str | None = None
    site_url: str | None = None

    def __post_init__(self) -> None:
        self.api_key = self.api_key if self.api_key is not None else os.getenv("OPENROUTER_API_KEY")
        self.base_url = _clean_base_url(self.base_url or os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"))
        self.default_model = self.default_model if self.default_model is not None else os.getenv("OPENROUTER_DEFAULT_MODEL")
        self.transport = self.transport or _urllib_transport
        self.app_name = self.app_name if self.app_name is not None else os.getenv("OPENROUTER_APP_NAME", "MotionJSON")
        self.site_url = self.site_url if self.site_url is not None else os.getenv("OPENROUTER_SITE_URL")

    def complete(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        tools: Sequence[Mapping[str, Any]] | None = None,
        response_format: Mapping[str, Any] | None = None,
        **routing: Any,
    ) -> Mapping[str, Any]:
        if not self.api_key:
            raise ProviderConfigError("OPENROUTER_API_KEY is required to call OpenRouterLLMProvider.complete().")
        if not messages:
            raise ValueError("messages must contain at least one chat message")

        payload: dict[str, Any] = {"messages": list(messages)}
        selected_model = model or self.default_model
        if selected_model:
            payload["model"] = selected_model
        if tools is not None:
            payload["tools"] = list(tools)
        if response_format is not None:
            payload["response_format"] = dict(response_format)
        payload.update({key: value for key, value in routing.items() if value is not None})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.site_url:
            headers["HTTP-Referer"] = self.site_url
        if self.app_name:
            headers["X-Title"] = self.app_name

        assert self.transport is not None
        return self.transport(f"{self.base_url}/chat/completions", payload, headers, self.timeout)
