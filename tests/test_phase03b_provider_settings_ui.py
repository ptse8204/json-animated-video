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
        "Provider settings",
        "Providers and models",
    ]:
        assert expected in html

    for expected in [
        "/api/provider-settings",
        "data-provider-field=\"apiKey\"",
        "allowHosted",
        "providerSettingsById",
        "saveProviderSettingsFromRow",
        "/api/provider-settings/${encodeURIComponent(providerId)}/test",
    ]:
        assert expected in js

    for expected in [
        "provider-settings-row",
        "provider-hosted-toggle",
        "provider-actions",
    ]:
        assert expected in css

    assert "provider-settings" in layout
