from __future__ import annotations

import json
import sqlite3

import pytest

from motionjson.backend.api import MotionJSONAPI
from motionjson.backend.api_keys import create_api_key
from motionjson.backend.auth import register_user
from motionjson.backend.db import initialize_database
from motionjson.provider_settings import provider_catalog, hosted_sam3_smoke_test, redact_secret_payload, redact_secret_text
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


def test_local_ui_provider_settings_defaults_are_redacted_and_sam_first(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)

    status, _headers, body = app.handle("GET", "/api/provider-settings")
    payload = decode(body)

    assert status == 200
    assert payload["format"] == "motionjson.local_provider_settings.v0.1"
    assert payload["defaults"]["safeMaskProvider"] == "sam2-local"
    assert payload["defaults"]["debugMaskProvider"] == "mock"
    mock = provider_by_id(payload, "mock")
    assert mock["credentialRequired"] is False
    assert mock["readiness"]["status"] == "ready"
    openrouter = provider_by_id(payload, "openrouter")
    assert openrouter["locality"] == "hosted"
    assert openrouter["readiness"]["status"] == "missing_key"
    sam2_hosted = provider_by_id(payload, "sam2-hosted")
    assert sam2_hosted["settings"]["hostedProfileId"] == "replicate-sam2-video"
    assert {profile["id"] for profile in sam2_hosted["hostedProfiles"]} >= {"replicate-sam2-video", "custom-sam2-compatible"}
    sam3_hosted = provider_by_id(payload, "sam3-hosted")
    assert sam3_hosted["settings"]["hostedProfileId"] == "roboflow-sam3-pcs"
    assert {profile["id"] for profile in sam3_hosted["hostedProfiles"]} >= {"roboflow-sam3-pcs", "fal-sam3-image", "custom-sam3-compatible"}
    assert "apiKey" not in json.dumps(payload)


def test_sam3_local_setup_guide_distinguishes_source_repo_from_checkpoint_path():
    catalog = provider_catalog()
    sam3_local = provider_by_id(catalog, "sam3-local")
    guide_text = json.dumps(sam3_local["setupGuide"])

    assert "SAM3_LOCAL_MODEL" in guide_text
    assert "sam3.pt" in guide_text
    assert "facebook/sam3" in guide_text
    assert "/content/sam3" in guide_text
    assert "checkpoint file path" in sam3_local["localConfigFields"][0]["label"]
    assert "Do not enter /content/sam3 or facebook/sam3" in sam3_local["localConfigFields"][0]["helpText"]
    assert "sam3.pt" in sam3_local["localConfigFields"][0]["placeholder"]
    assert sam3_local["docs"] == "docs/sam3_local.md"
    assert "sk-" not in guide_text
    assert "HF_TOKEN=" not in guide_text
    assert "<token>" not in guide_text
    assert "api_key" not in guide_text


def test_sam_goal_capabilities_are_declared_for_guided_ui():
    catalog = provider_catalog()
    sam2_local = provider_by_id(catalog, "sam2-local")
    sam3_local = provider_by_id(catalog, "sam3-local")
    sam3_hosted = provider_by_id(catalog, "sam3-hosted")
    roboflow = next(profile for profile in sam3_hosted["hostedProfiles"] if profile["id"] == "roboflow-sam3-pcs")
    custom = next(profile for profile in sam3_hosted["hostedProfiles"] if profile["id"] == "custom-sam3-compatible")

    assert "trace_one_object" in sam2_local["supportedGoals"]
    assert sam2_local["supportsTracking"] is True
    assert sam3_local["supportedPromptTypes"] == ["box"]
    assert {"trace_one_object", "trace_all_objects", "text_detector"} <= set(sam3_local["supportedGoals"])
    assert roboflow["supportedGoals"] == ["text_detector"]
    assert roboflow["supportsExemplar"] is False
    assert roboflow["supportsAutoMasks"] is False
    assert custom["supportsExemplar"] is True
    assert custom["supportsTracking"] is True


def test_local_sam_settings_persist_and_diagnose_without_raw_values(tmp_path):
    checkpoint = tmp_path / "sam2.pt"
    config = tmp_path / "sam2.yaml"
    checkpoint.write_bytes(b"weights")
    config.write_text("model:\n  type: test\n", encoding="utf-8")
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=False)

    status, _headers, body = app.handle(
        "POST",
        "/api/provider-settings",
        body=json.dumps(
            {
                "providerId": "sam2-local",
                "sam2CheckpointPath": str(checkpoint),
                "sam2ModelConfigPath": str(config),
                "sam2Device": "cpu",
            }
        ).encode("utf-8"),
    )
    payload = decode(body)

    assert status == 200
    sam2 = provider_by_id(payload, "sam2-local")
    assert sam2["settings"]["sam2CheckpointPath"] == "[LOCAL_PATH_REDACTED]"
    assert sam2["settings"]["sam2ModelConfigPath"] == "[LOCAL_PATH_REDACTED]"
    assert sam2["settings"]["sam2Device"] == "cpu"
    assert "apiKey" not in body.decode("utf-8")

    status, _headers, body = app.handle("POST", "/api/provider-settings/sam2-local/diagnose", body=b"{}")
    diagnosis = decode(body)

    assert status == 200
    assert diagnosis["providerId"] == "sam2-local"
    assert diagnosis["networkAttempted"] is False
    assert {item["id"] for item in diagnosis["checklist"]} >= {"sam2_package", "checkpoint", "model_config", "device"}
    checkpoint_row = next(item for item in diagnosis["checklist"] if item["id"] == "checkpoint")
    assert checkpoint_row["ok"] is True
    assert "apiKey" not in body.decode("utf-8")


def test_sam3_local_diagnose_explains_invalid_model_paths(tmp_path, monkeypatch):
    monkeypatch.delenv("SAM3_LOCAL_MODEL", raising=False)
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=False)

    for value, expected in [
        ("facebook/sam3", "Hugging Face repo id"),
        ("/content/sam3", "source/package directory"),
    ]:
        status, _headers, body = app.handle(
            "POST",
            "/api/provider-settings/sam3-local/diagnose",
            body=json.dumps({"sam3ModelPath": value}).encode("utf-8"),
        )
        diagnosis = decode(body)
        model_row = next(item for item in diagnosis["checklist"] if item["id"] == "model_path")

        assert status == 200
        assert model_row["ok"] is False
        assert expected in model_row["detail"]

    model_dir = tmp_path / "sam3-cache"
    checkpoint = model_dir / "snapshot" / "sam3.pt"
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_text("placeholder")
    status, _headers, body = app.handle(
        "POST",
        "/api/provider-settings/sam3-local/diagnose",
        body=json.dumps({"sam3ModelPath": str(model_dir)}).encode("utf-8"),
    )
    diagnosis = decode(body)
    model_row = next(item for item in diagnosis["checklist"] if item["id"] == "model_path")

    assert status == 200
    assert model_row["ok"] is False
    assert "Use this file instead" in model_row["detail"]
    assert "[LOCAL_PATH_REDACTED]" in model_row["detail"]
    assert str(checkpoint) not in body.decode("utf-8")


def test_local_sam_smoke_requires_explicit_heavy_local_ack(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=False)

    status, _headers, body = app.handle("POST", "/api/provider-settings/sam2-local/smoke-test", body=b"{}")
    assert status == 400
    assert "allowHeavyLocal=true" in body.decode("utf-8")

    status, _headers, body = app.handle(
        "POST",
        "/api/provider-settings/sam2-local/smoke-test",
        body=json.dumps({"allowHeavyLocal": True}).encode("utf-8"),
    )
    payload = decode(body)
    assert status == 200
    assert payload["providerId"] == "sam2-local"
    assert payload["networkAttempted"] is False
    assert payload["heavyLocalAttempted"] is True
    assert payload["status"] == "blocked"


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


def test_hosted_profile_persistence_is_redacted_and_updates_capabilities(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    secret = "fal-profile-secret-abcdef123456"

    status, _headers, body = app.handle(
        "POST",
        "/api/provider-settings",
        body=json.dumps(
            {
                "providerId": "sam3-hosted",
                "hostedProfileId": "fal-sam3-image",
                "apiKey": secret,
                "selectedModel": "fal-ai/sam-3/image",
                "allowHosted": True,
            }
        ).encode("utf-8"),
    )
    payload = decode(body)

    assert status == 200
    assert secret not in body.decode("utf-8")
    provider = provider_by_id(payload, "sam3-hosted")
    assert provider["settings"]["hostedProfileId"] == "fal-sam3-image"
    assert provider["effectiveProfile"]["id"] == "fal-sam3-image"
    assert provider["credentials"][0]["env"] == "FAL_KEY"
    assert provider["credentials"][0]["display"].startswith("fal...")

    status, _headers, body = app.handle("GET", "/api/capabilities")
    capability = capability_by_name(decode(body), "sam3-hosted")
    assert status == 200
    assert capability["metadata"]["hostedProfileId"] == "fal-sam3-image"
    assert capability["metadata"]["effectiveProfile"]["id"] == "fal-sam3-image"
    assert secret not in body.decode("utf-8")


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
    assert capability["runnable"] is True
    assert capability["status"] == "ready"
    assert capability["networkRequired"] is True
    assert capability["metadata"]["credentialSource"] == "local_settings"
    assert capability["metadata"]["networkOptIn"] is True
    assert capability["metadata"]["settingsOnly"] is False
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
    assert capability["runnable"] is True
    assert capability["status"] == "ready"
    assert capability["metadata"]["credentialSource"] == "local_settings"
    assert capability["metadata"]["settingsOnly"] is False
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


def test_hosted_sam2_smoke_supports_replicate_profile_without_raw_secret(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    secret = "replicate-profile-secret-abcdef123456"
    status, _headers, body = app.handle(
        "POST",
        "/api/provider-settings",
        body=json.dumps(
            {
                "providerId": "sam2-hosted",
                "hostedProfileId": "replicate-sam2-video",
                "apiKey": secret,
                "selectedModel": "meta/sam-2-video",
                "allowHosted": True,
            }
        ).encode("utf-8"),
    )
    assert status == 200

    conn = app.connection()
    try:
        user = app._local_user(conn)
        result = hosted_sam3_smoke_test(
            conn,
            user_id=user["id"],
            payload={"providerId": "sam2-hosted", "allowNetwork": True, "allowHosted": True, "acknowledgeCostPrivacy": True},
        )
    finally:
        conn.close()

    encoded = json.dumps(result, sort_keys=True)
    assert result["providerId"] == "sam2-hosted"
    assert result["hostedProfileId"] == "replicate-sam2-video"
    assert result["smokeTest"]["providerName"] == "replicate-sam2-video"
    assert secret not in encoded


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
