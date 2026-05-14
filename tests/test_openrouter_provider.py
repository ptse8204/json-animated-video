import subprocess
import sys

import pytest

from motionjson.providers import LLMProvider, OpenRouterLLMProvider, ProviderConfigError


def test_openrouter_provider_builds_openai_compatible_request_without_network():
    captured = {}

    def transport(url, payload, headers, timeout):
        captured["url"] = url
        captured["payload"] = payload
        captured["headers"] = headers
        captured["timeout"] = timeout
        return {"choices": [{"message": {"content": "ok"}}]}

    provider = OpenRouterLLMProvider(
        api_key="test-key",
        base_url="https://openrouter.ai/api/v1/",
        default_model="openai/test-model",
        transport=transport,
        timeout=7,
        app_name="MotionJSON Tests",
        site_url="https://example.test",
    )

    assert isinstance(provider, LLMProvider)
    result = provider.complete(
        [{"role": "user", "content": "Describe the layer"}],
        response_format={"type": "json_object"},
        provider={"order": ["mock"]},
    )

    assert result["choices"][0]["message"]["content"] == "ok"
    assert captured["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert captured["payload"]["model"] == "openai/test-model"
    assert captured["payload"]["messages"] == [{"role": "user", "content": "Describe the layer"}]
    assert captured["payload"]["response_format"] == {"type": "json_object"}
    assert captured["payload"]["provider"] == {"order": ["mock"]}
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["headers"]["Content-Type"] == "application/json"
    assert captured["headers"]["HTTP-Referer"] == "https://example.test"
    assert captured["headers"]["X-Title"] == "MotionJSON Tests"
    assert captured["timeout"] == 7


def test_openrouter_provider_requires_api_key_before_transport_call(monkeypatch):
    called = False

    def transport(url, payload, headers, timeout):
        nonlocal called
        called = True
        return {}

    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    provider = OpenRouterLLMProvider(api_key=None, transport=transport)

    with pytest.raises(ProviderConfigError, match="OPENROUTER_API_KEY"):
        provider.complete([{"role": "user", "content": "hello"}])

    assert not called


def test_openrouter_provider_uses_env_fallbacks(monkeypatch):
    captured = {}

    def transport(url, payload, headers, timeout):
        captured["url"] = url
        captured["payload"] = payload
        captured["headers"] = headers
        return {"id": "env"}

    monkeypatch.setenv("OPENROUTER_API_KEY", "env-key")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://router.test/api/v1")
    monkeypatch.setenv("OPENROUTER_DEFAULT_MODEL", "openai/env-model")
    provider = OpenRouterLLMProvider(transport=transport)

    result = provider.complete([{"role": "user", "content": "hello"}])

    assert result == {"id": "env"}
    assert captured["url"] == "https://router.test/api/v1/chat/completions"
    assert captured["payload"]["model"] == "openai/env-model"
    assert captured["headers"]["Authorization"] == "Bearer env-key"


def test_segmentation_and_cli_imports_do_not_eagerly_load_openrouter():
    script = """
import sys
import motionjson.providers.segmentation
assert 'motionjson.providers.openrouter' not in sys.modules
import motionjson.cli
assert 'motionjson.providers.openrouter' not in sys.modules
"""
    subprocess.run([sys.executable, "-c", script], check=True)
