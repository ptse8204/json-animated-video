from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_phase03b_local_ui_has_provider_settings_surface():
    html = read("src/motionjson/ui/static/index.html")
    js = read("src/motionjson/ui/static/app.js")
    css = read("src/motionjson/ui/static/app.css")
    layout = read("scripts/check_local_ui_layout.mjs")

    for expected in [
        "providerSettingsPanel",
        "providerSettingsList",
        "modelSetupPanel",
        "modelSetupChoices",
        "Provider settings",
        "Providers and models",
        "Connect SAM for extraction",
        "textDiscoveryProviderSelect",
    ]:
        assert expected in html

    for expected in [
        "/api/provider-settings",
        "/api/model-providers",
        "modelSetupProviderSummary",
        "modelSetupPayloadFromValues",
        "renderModelSetup",
        "data-provider-field=\"apiKey\"",
        "data-provider-field=\"hostedProfileId\"",
        "data-model-setup-field=\"apiKey\"",
        "allowHosted",
        "hostedProfileId",
        "sam2CheckpointPath",
        "sam3ModelPath",
        "textDiscoveryProvider",
        "providerSettingsById",
        "saveProviderSettingsFromRow",
        "/api/provider-settings/${encodeURIComponent(providerId)}/test",
        "/api/provider-settings/${encodeURIComponent(providerId)}/diagnose",
        "/api/provider-settings/${encodeURIComponent(providerId)}/smoke-test",
        "Run local smoke",
        "Run hosted smoke",
        'state.health?.mockMode || provider.id !== "mock"',
    ]:
        assert expected in js

    for expected in [
        "model-setup-panel",
        "model-choice-card",
        "model-hosted-toggle",
        "provider-settings-row",
        "provider-hosted-toggle",
        "provider-actions",
    ]:
        assert expected in css

    assert "provider-settings" in layout
    assert "model-setup-hosted-warning" in layout
