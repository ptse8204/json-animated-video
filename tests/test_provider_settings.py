from __future__ import annotations

import json
import sqlite3

import pytest

from motionjson.backend.api import MotionJSONAPI
from motionjson.backend.api_keys import create_api_key
from motionjson.backend.auth import register_user
from motionjson.backend.db import initialize_database
from motionjson.provider_settings import hosted_sam3_smoke_test, redact_secret_payload, redact_secret_text
from motionjson.ui.server import LocalUIApp


def decode(body: bytes) -> dict:
    return json.loads(body.decode("utf-8"))


def provider_by_id(payload: dict, provider_id: str) -> dict:
    return next(provider for provider in payload["providers"] if provider["id"] == provider_id)


def capability_by_name(payload: dict, name: str) -> dict:
    return next(provider for provider in payload["providers"] if provider["name"] == name)


class FakeHostedSAM3Transport:
    def __init__(self):
        self.calls = []

    def post_json(self, url, payload, *, headers=None, timeout_seconds=None):
        self.calls.append({"url": url, "payload": payload, "headers": headers or {}, "timeoutSeconds": timeout_seconds})
        return {
            "masks": [[[0, 0, 0], [0, 255, 0], [0, 0, 0]]],
            "boxes": [[1, 1, 1, 1]],
            "scores": [0.88],
            "labels": ["object"],
        }


def test_secret_redaction_helpers_cover_common_provider_shapes():
    secret = "sk-or-v1-motionjson-test-secret-123456"
    assert secret not in redact_secret_text(f"Authorization: Bearer {secret}")
    assert secret not in redact_secret_text(f"api_key={secret}")
    assert "sig=secret" not in redact_secret_text("https://provider.example.test/run?sig=secret&expires=1")
    assert redact_secret_payload({"apiKey": secret, "nested": {"message": f"token={secret}"}}) == {
        "apiKey": "[REDACTED]",
        "nested": {"message": "token=[REDACTED]"},
    }


def test_local_ui_provider_settings_defaults_are_redacted_and_mock_safe(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)

    status, _headers, body = app.handle("GET", "/api/provider-settings")
    payload = decode(body)

    assert status == 200
    assert payload["format"] == "motionjson.local_provider_settings.v0.1"
    assert payload["defaults"]["safeMaskProvider"] == "mock"
    mock = provider_by_id(payload, "mock")
    assert mock["credentialRequired"] is False
    assert mock["readiness"]["status"] == "ready"
    openrouter = provider_by_id(payload, "openrouter")
    assert openrouter["locality"] == "hosted"
    assert openrouter["readiness"]["status"] == "missing_key"
    assert "apiKey" not in json.dumps(payload)


def test_local_ui_provider_settings_persist_key_model_and_capability_source(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    secret = "sk-or-v1-phase03b-openrouter-secret-1234567890"

    status, _headers, body = app.handle(
        "POST",
        "/api/provider-settings",
        body=json.dumps(
            {
                "providerId": "openrouter",
                "apiKey": secret,
                "selectedModel": "__custom__",
                "customModelId": "example/custom-vlm",
                "allowHosted": True,
            }
        ).encode("utf-8"),
    )
    saved_text = body.decode("utf-8")
    saved = decode(body)

    assert status == 200
    assert secret not in saved_text
    openrouter = provider_by_id(saved, "openrouter")
    assert openrouter["credentials"][0]["configured"] is True
    assert openrouter["credentials"][0]["source"] == "local_settings"
    assert openrouter["credentials"][0]["display"].startswith("sk-...")
    assert openrouter["effectiveModel"] == "example/custom-vlm"

    status, _headers, body = app.handle("GET", "/api/capabilities")
    capabilities = decode(body)
    assert status == 200
    openrouter_capability = capability_by_name(capabilities, "openrouter")
    assert openrouter_capability["configured"] is True
    assert openrouter_capability["runnable"] is False
    assert openrouter_capability["status"] == "configured_settings_only"
    assert openrouter_capability["metadata"]["credentialSource"] == "local_settings"
    assert openrouter_capability["metadata"]["settingsOnly"] is True
    assert openrouter_capability["metadata"]["selectedModel"] == "example/custom-vlm"
    assert secret not in body.decode("utf-8")

    status, _headers, body = app.handle("POST", "/api/provider-settings/openrouter/test", body=b"{}")
    checked = decode(body)
    assert status == 200
    assert checked["status"] == "configured"
    assert checked["networkAttempted"] is False
    assert secret not in body.decode("utf-8")

    status, _headers, body = app.handle("DELETE", "/api/provider-settings/openrouter", body=b"{}")
    assert status == 200
    assert decode(body)["reset"] is True
    status, _headers, body = app.handle("GET", "/api/provider-settings")
    assert provider_by_id(decode(body), "openrouter")["readiness"]["status"] == "missing_key"


def test_local_ui_provider_settings_reject_invalid_key_without_echoing_it(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)

    status, _headers, body = app.handle(
        "POST",
        "/api/provider-settings",
        body=json.dumps({"providerId": "openrouter", "apiKey": "bad secret with spaces"}).encode("utf-8"),
    )

    assert status == 400
    text = body.decode("utf-8")
    assert "bad secret with spaces" not in text
    assert "invalid or too" in text


def test_local_ui_provider_settings_reject_invalid_hosted_urls(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)

    status, _headers, body = app.handle(
        "POST",
        "/api/provider-settings",
        body=json.dumps(
            {
                "providerId": "sam2-hosted",
                "apiKey": "hosted-sam2-secret-abcdef123456",
                "endpoint": "not a url",
                "allowHosted": True,
            }
        ).encode("utf-8"),
    )
    assert status == 400
    assert "expected an http:// or https:// URL" in body.decode("utf-8")

    status, _headers, body = app.handle(
        "POST",
        "/api/provider-settings",
        body=json.dumps(
            {
                "providerId": "openrouter",
                "apiKey": "sk-or-v1-valid-test-secret-abcdef123456",
                "baseUrl": "file:///tmp/router",
            }
        ).encode("utf-8"),
    )
    assert status == 400
    assert "expected an http:// or https:// URL" in body.decode("utf-8")


def test_provider_settings_environment_precedence_for_headless_users(tmp_path, monkeypatch):
    secret = "sk-or-v1-env-openrouter-secret-abcdef123456"
    monkeypatch.setenv("OPENROUTER_API_KEY", secret)
    monkeypatch.setenv("OPENROUTER_DEFAULT_MODEL", "env/model")
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)

    status, _headers, body = app.handle("GET", "/api/provider-settings")
    payload = decode(body)
    openrouter = provider_by_id(payload, "openrouter")

    assert status == 200
    assert openrouter["credentials"][0]["configured"] is True
    assert openrouter["credentials"][0]["source"] == "environment"
    assert openrouter["effectiveModel"] == "env/model"
    assert secret not in body.decode("utf-8")

    status, _headers, body = app.handle("GET", "/api/capabilities")
    capability = capability_by_name(decode(body), "openrouter")
    assert status == 200
    assert capability["metadata"]["credentialSource"] == "environment"
    assert capability["metadata"]["settingsOnly"] is False
    assert capability["metadata"]["selectedModel"] == "env/model"
    assert secret not in body.decode("utf-8")


def test_openai_provider_settings_are_redacted_and_use_env_model_precedence(tmp_path, monkeypatch):
    secret = "sk-openai-env-secret-abcdef123456"
    monkeypatch.setenv("OPENAI_API_KEY", secret)
    monkeypatch.setenv("OPENAI_DEFAULT_MODEL", "gpt-test-env")
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)

    status, _headers, body = app.handle("GET", "/api/provider-settings")
    payload = decode(body)
    openai = provider_by_id(payload, "openai")

    assert status == 200
    assert openai["locality"] == "hosted"
    assert openai["credentials"][0]["configured"] is True
    assert openai["credentials"][0]["source"] == "environment"
    assert openai["effectiveModel"] == "gpt-test-env"
    assert secret not in body.decode("utf-8")

    status, _headers, body = app.handle("POST", "/api/provider-settings/openai/test", body=b"{}")
    checked = decode(body)
    assert status == 200
    assert checked["status"] == "configured"
    assert checked["networkAttempted"] is False
    assert secret not in body.decode("utf-8")


def test_hosted_sam2_settings_require_endpoint_key_and_opt_in(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    secret = "hosted-sam2-secret-abcdef123456"

    status, _headers, body = app.handle(
        "POST",
        "/api/provider-settings",
        body=json.dumps(
            {
                "providerId": "sam2-hosted",
                "apiKey": secret,
                "endpoint": "https://provider.example.test/segment",
                "selectedModel": "auto",
                "allowHosted": True,
            }
        ).encode("utf-8"),
    )
    assert status == 200
    assert secret not in body.decode("utf-8")

    status, _headers, body = app.handle("GET", "/api/capabilities")
    capability = capability_by_name(decode(body), "sam2-hosted")
    assert status == 200
    assert capability["configured"] is True
    assert capability["runnable"] is False
    assert capability["status"] == "configured_settings_only"
    assert capability["networkRequired"] is True
    assert capability["metadata"]["credentialSource"] == "local_settings"
    assert capability["metadata"]["networkOptIn"] is True
    assert capability["metadata"]["settingsOnly"] is True
    assert secret not in body.decode("utf-8")


def test_hosted_sam3_settings_are_redacted_and_never_test_network(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    secret = "hosted-sam3-secret-abcdef123456"

    status, _headers, body = app.handle(
        "POST",
        "/api/provider-settings",
        body=json.dumps(
            {
                "providerId": "sam3-hosted",
                "apiKey": secret,
                "endpoint": "https://provider.example.test/sam3",
                "selectedModel": "auto",
                "allowHosted": True,
            }
        ).encode("utf-8"),
    )
    assert status == 200
    assert secret not in body.decode("utf-8")

    status, _headers, body = app.handle("POST", "/api/provider-settings/sam3-hosted/test", body=b"{}")
    checked = decode(body)
    assert status == 200
    assert checked["status"] == "configured"
    assert checked["networkAttempted"] is False
    assert secret not in body.decode("utf-8")

    status, _headers, body = app.handle("GET", "/api/capabilities")
    capability = capability_by_name(decode(body), "sam3-hosted")
    assert status == 200
    assert capability["configured"] is True
    assert capability["runnable"] is False
    assert capability["status"] == "configured_settings_only"
    assert capability["metadata"]["credentialSource"] == "local_settings"
    assert capability["metadata"]["settingsOnly"] is True
    assert secret not in body.decode("utf-8")


def test_hosted_sam3_smoke_requires_per_request_network_ack(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    secret = "hosted-sam3-secret-abcdef123456"

    status, _headers, body = app.handle(
        "POST",
        "/api/provider-settings",
        body=json.dumps(
            {
                "providerId": "sam3-hosted",
                "apiKey": secret,
                "endpoint": "https://provider.example.test/sam3",
                "allowHosted": True,
            }
        ).encode("utf-8"),
    )
    assert status == 200

    status, _headers, body = app.handle("POST", "/api/provider-settings/sam3-hosted/smoke-test", body=b"{}")

    assert status == 400
    text = body.decode("utf-8")
    assert "allowNetwork=true" in text
    assert secret not in text


def test_hosted_sam3_smoke_uses_server_saved_secret_and_redacts_response(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    secret = "hosted-sam3-secret-abcdef123456"
    status, _headers, body = app.handle(
        "POST",
        "/api/provider-settings",
        body=json.dumps(
            {
                "providerId": "sam3-hosted",
                "apiKey": secret,
                "endpoint": "https://provider.example.test/sam3",
                "selectedModel": "sam3/default",
                "allowHosted": True,
            }
        ).encode("utf-8"),
    )
    assert status == 200

    conn = app.connection()
    try:
        user = app._local_user(conn)
        transport = FakeHostedSAM3Transport()
        result = hosted_sam3_smoke_test(
            conn,
            user_id=user["id"],
            payload={"allowNetwork": True, "acknowledgeCostPrivacy": True, "prompt": "object"},
            transport=transport,
        )
    finally:
        conn.close()

    encoded = json.dumps(result, sort_keys=True)
    assert result["status"] == "ok"
    assert result["networkAttempted"] is True
    assert result["credentials"]["display"].startswith("hos...")
    assert result["model"] == "sam3/default"
    assert secret not in encoded
    assert transport.calls[0]["headers"]["Authorization"] == f"Bearer {secret}"
    assert transport.calls[0]["payload"]["model"] == "sam3/default"


def test_hosted_sam3_smoke_rejects_invalid_endpoint_before_network(tmp_path):
    conn = sqlite3.connect(tmp_path / "backend.sqlite")
    conn.row_factory = sqlite3.Row
    initialize_database(conn)
    user = register_user(conn, email="smoke@example.com", password="pw")
    transport = FakeHostedSAM3Transport()
    try:
        with pytest.raises(ValueError, match="invalid configuration"):
            hosted_sam3_smoke_test(
                conn,
                user_id=user["id"],
                payload={"allowNetwork": True, "allowHosted": True, "acknowledgeCostPrivacy": True},
                environ={"SAM3_HOSTED_URL": "file:///tmp/sam3", "SAM3_HOSTED_API_KEY": "hosted-sam3-secret-abcdef"},
                transport=transport,
            )
    finally:
        conn.close()

    assert transport.calls == []


def test_authenticated_api_exposes_hosted_sam3_smoke_route_without_client_secret(tmp_path, monkeypatch):
    conn = sqlite3.connect(tmp_path / "backend.sqlite")
    conn.row_factory = sqlite3.Row
    initialize_database(conn)
    user = register_user(conn, email="api-smoke@example.com", password="pw")
    api_key = create_api_key(conn, user_id=user["id"], name="API")["apiKey"]
    conn.close()

    def fake_smoke(conn, *, user_id, payload, environ=None, transport=None):
        assert payload["providerId"] == "sam3-hosted"
        assert payload["allowNetwork"] is True
        assert payload["acknowledgeCostPrivacy"] is True
        return {
            "format": "motionjson.provider_network_smoke_test.v0.1",
            "providerId": "sam3-hosted",
            "status": "ok",
            "networkAttempted": True,
            "message": "ok",
        }

    monkeypatch.setattr("motionjson.backend.api.hosted_sam3_smoke_test", fake_smoke)
    api = MotionJSONAPI(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage")

    status, _headers, body = api.handle(
        "POST",
        "/v1/providers/sam3-hosted/smoke-test",
        {"authorization": f"Bearer {api_key}"},
        json.dumps({"allowNetwork": True, "acknowledgeCostPrivacy": True}).encode("utf-8"),
    )

    assert status == 200
    payload = decode(body)
    assert payload["status"] == "ok"
    assert "apiKey" not in body.decode("utf-8")
