from __future__ import annotations

import json
import sqlite3
import sys
import types
from importlib.machinery import ModuleSpec

import pytest

from motionjson.backend.api import MotionJSONAPI
from motionjson.backend.api_keys import create_api_key
from motionjson.backend.auth import register_user
from motionjson.backend.db import initialize_database
from motionjson.backend.provider_setup_jobs import (
    cancel_provider_setup_job,
    create_provider_setup_job,
    provider_setup_actions,
)
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
    checklist_ids = {item["id"] for item in diagnosis["checklist"]}

    assert status == 200
    assert {"transformers_package", "sam3_tracker_auto_masks", "sam3_tracker_video"}.issubset(checklist_ids)
    assert model_row["ok"] is False
    assert "Use this file instead" in model_row["detail"]
    assert "[LOCAL_PATH_REDACTED]" in model_row["detail"]
    assert str(checkpoint) not in body.decode("utf-8")
    assert "SAM2 is not required" in body.decode("utf-8")


def test_provider_setup_job_api_allowlists_actions_redacts_and_persists_settings(tmp_path):
    checkpoint = tmp_path / "sam2.pt"
    config = tmp_path / "sam2.yaml"
    checkpoint.write_bytes(b"weights")
    config.write_text("model:\n  type: test\n", encoding="utf-8")
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=False)

    status, _headers, body = app.handle(
        "POST",
        "/api/provider-settings/sam2-local/setup/start",
        body=json.dumps(
            {
                "action": "diagnose",
                "runInline": True,
                "settings": {
                    "sam2CheckpointPath": str(checkpoint),
                    "sam2ModelConfigPath": str(config),
                    "sam2Device": "cpu",
                },
            }
        ).encode("utf-8"),
    )
    payload = decode(body)

    assert status == 200
    assert payload["setupJob"]["providerId"] == "sam2-local"
    assert payload["setupJob"]["action"] == "diagnose"
    assert payload["setupJob"]["status"] in {"blocked", "succeeded"}
    assert str(checkpoint) not in body.decode("utf-8")
    assert "[LOCAL_PATH_REDACTED]" in body.decode("utf-8")

    status, _headers, body = app.handle("GET", "/api/provider-settings")
    saved = decode(body)
    sam2 = provider_by_id(saved, "sam2-local")
    assert status == 200
    assert sam2["settings"]["sam2CheckpointPath"] == "[LOCAL_PATH_REDACTED]"
    assert sam2["settings"]["sam2ModelConfigPath"] == "[LOCAL_PATH_REDACTED]"

    status, _headers, body = app.handle(
        "POST",
        "/api/provider-settings/sam2-local/setup/start",
        body=json.dumps({"action": "shell", "runInline": True}).encode("utf-8"),
    )
    assert status == 400
    assert "setup action must be one of" in body.decode("utf-8")


def test_sam3_scene_sweep_setup_job_is_independent_from_sam2_and_has_actionable_blocks(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=False)
    actions = {action["id"]: action for action in provider_setup_actions("sam3-local")}

    assert actions["install"]["label"] == "Install scene sweep"
    assert "SAM2 is not required" in actions["install"]["description"]

    status, _headers, body = app.handle(
        "POST",
        "/api/provider-settings/sam3-local/setup/start",
        body=json.dumps({"action": "install", "runInline": True, "dryRun": True}).encode("utf-8"),
    )
    install = decode(body)

    assert status == 200
    assert install["setupJob"]["status"] == "succeeded"
    assert "sam3-transformers" in install["setupJob"]["result"]["command"]
    assert "sam2" not in install["setupJob"]["result"]["command"].lower()

    status, _headers, body = app.handle(
        "POST",
        "/api/provider-settings/sam3-local/setup/start",
        body=json.dumps({"action": "check_access", "runInline": True, "allowNetwork": False}).encode("utf-8"),
    )
    blocked = decode(body)["setupJob"]

    assert status == 200
    assert blocked["status"] == "blocked"
    assert blocked["result"]["networkAttempted"] is False
    assert "network confirmation" in blocked["result"]["message"]


def test_sam3_scene_sweep_diagnose_and_smoke_do_not_require_official_sam3_adapter(tmp_path, monkeypatch):
    monkeypatch.delenv("SAM3_LOCAL_MODEL", raising=False)
    model_dir = tmp_path / "facebook-sam3-cache"
    model_dir.mkdir()
    (model_dir / "config.json").write_text('{"model_type":"sam3"}\n', encoding="utf-8")
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=False)

    status, _headers, body = app.handle(
        "POST",
        "/api/provider-settings/sam3-local/setup/start",
        body=json.dumps(
            {
                "action": "cache_model",
                "runInline": True,
                "allowNetwork": True,
                "allowDisk": True,
                "model": str(model_dir),
            }
        ).encode("utf-8"),
    )
    assert status == 200
    assert decode(body)["setupJob"]["status"] == "succeeded"

    def fake_find_spec(name: str):
        if name in {"transformers", "torch"}:
            return ModuleSpec(name, loader=None)
        if name == "sam3":
            return None
        return None

    monkeypatch.setattr("motionjson.provider_settings.find_spec", fake_find_spec)
    monkeypatch.setattr("motionjson.provider_settings._sam3_tracker_auto_masks_importable", lambda: True)
    monkeypatch.setattr("motionjson.provider_settings._sam3_tracker_video_importable", lambda: True)

    status, _headers, body = app.handle(
        "POST",
        "/api/provider-settings/sam3-local/setup/start",
        body=json.dumps({"action": "diagnose", "runInline": True}).encode("utf-8"),
    )
    diagnosis = decode(body)["setupJob"]["result"]
    checklist = {item["id"]: item for item in diagnosis["checklist"]}

    assert status == 200
    assert diagnosis["ready"] is True
    assert diagnosis["setupState"]["runnable"] is True
    assert checklist["sam3_package"]["required"] is False
    assert checklist["sam3_package"]["ok"] is False
    assert checklist["model_path"]["required"] is False
    assert checklist["model_path"]["ok"] is False
    assert checklist["sam3_tracker_auto_masks"]["ok"] is True
    assert checklist["sam3_tracker_video"]["ok"] is True

    status, _headers, body = app.handle(
        "POST",
        "/api/provider-settings/sam3-local/setup/start",
        body=json.dumps({"action": "smoke", "runInline": True, "allowHeavyLocal": True, "sceneSweep": True}).encode("utf-8"),
    )
    smoke = decode(body)["setupJob"]

    assert status == 200
    assert smoke["status"] == "succeeded"
    assert smoke["result"]["ready"] is True
    assert smoke["result"]["smokeTest"]["sceneSweep"] is True
    assert smoke["result"]["smokeTest"]["sam2Required"] is False
    assert "SAM3_LOCAL_MODEL" not in smoke["result"]["message"]


def test_sam3_scene_sweep_diagnose_blocks_on_tracker_runtime_not_checkpoint_path(tmp_path, monkeypatch):
    monkeypatch.delenv("SAM3_LOCAL_MODEL", raising=False)
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=False)

    def fake_find_spec(name: str):
        if name in {"transformers", "torch"}:
            return ModuleSpec(name, loader=None)
        if name == "sam3":
            return None
        return None

    monkeypatch.setattr("motionjson.provider_settings.find_spec", fake_find_spec)
    monkeypatch.setattr("motionjson.provider_settings._sam3_tracker_auto_masks_importable", lambda: False)
    monkeypatch.setattr("motionjson.provider_settings._sam3_tracker_video_importable", lambda: False)

    status, _headers, body = app.handle(
        "POST",
        "/api/provider-settings/sam3-local/setup/start",
        body=json.dumps({"action": "diagnose", "runInline": True}).encode("utf-8"),
    )
    text = body.decode("utf-8")
    diagnosis = decode(body)["setupJob"]["result"]
    checklist = {item["id"]: item for item in diagnosis["checklist"]}

    assert status == 200
    assert diagnosis["ready"] is False
    assert checklist["sam3_tracker_auto_masks"]["ok"] is False
    assert checklist["sam3_tracker_auto_masks"]["required"] is True
    assert checklist["model_path"]["required"] is False
    assert "SAM3 Tracker automatic-mask" in text
    assert "SAM3 local adapter requires SAM3_LOCAL_MODEL" not in diagnosis["message"]


def test_sam3_setup_jobs_use_saved_hugging_face_token_without_echoing_it(tmp_path, monkeypatch):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=False)
    secret = "hf_saved_token_abcdef123456"
    seen: dict[str, tuple[str, str | None]] = {}
    cached_dir = tmp_path / "hf-cache" / "facebook-sam3"
    cached_dir.mkdir(parents=True)
    (cached_dir / "config.json").write_text('{"model_type":"sam3"}\n', encoding="utf-8")

    fake_hub = types.ModuleType("huggingface_hub")
    fake_hub.__spec__ = ModuleSpec("huggingface_hub", loader=None)

    class FakeHfApi:
        def model_info(self, repo_id: str, token: str | None = None) -> dict[str, str]:
            seen["model_info"] = (repo_id, token)
            return {"id": repo_id}

    def snapshot_download(repo_id: str, token: str | None = None) -> str:
        seen["snapshot_download"] = (repo_id, token)
        return str(cached_dir)

    fake_hub.HfApi = FakeHfApi
    fake_hub.snapshot_download = snapshot_download
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hub)
    monkeypatch.setattr("motionjson.backend.provider_setup_jobs.find_spec", lambda name: object() if name == "huggingface_hub" else None)

    status, _headers, body = app.handle(
        "POST",
        "/api/provider-settings/sam3-local/setup/start",
        body=json.dumps(
            {
                "action": "check_access",
                "runInline": True,
                "allowNetwork": True,
                "settings": {"selectedModel": "facebook/sam3", "hfToken": secret},
            }
        ).encode("utf-8"),
    )
    checked_text = body.decode("utf-8")
    checked = decode(body)["setupJob"]

    assert status == 200
    assert checked["status"] == "succeeded"
    assert checked["progress"] == {"known": True, "percent": 100, "label": "Access check complete"}
    assert any(event["metadata"].get("progress") for event in checked["events"])
    assert seen["model_info"] == ("facebook/sam3", secret)
    assert secret not in checked_text

    status, _headers, body = app.handle("GET", "/api/provider-settings")
    settings_text = body.decode("utf-8")
    settings = decode(body)
    sam3 = provider_by_id(settings, "sam3-local")
    hf_credential = next(item for item in sam3["credentials"] if item["name"] == "hf_token")

    assert status == 200
    assert hf_credential["configured"] is True
    assert hf_credential["source"] == "local_settings"
    assert secret not in settings_text

    status, _headers, body = app.handle(
        "POST",
        "/api/provider-settings/sam3-local/setup/start",
        body=json.dumps(
            {
                "action": "cache_model",
                "runInline": True,
                "allowNetwork": True,
                "allowDisk": True,
                "model": "facebook/sam3",
            }
        ).encode("utf-8"),
    )
    cached_text = body.decode("utf-8")
    cached = decode(body)["setupJob"]

    assert status == 200
    assert cached["status"] == "succeeded"
    assert cached["progress"] == {"known": True, "percent": 100, "label": "Model cached"}
    assert seen["snapshot_download"] == ("facebook/sam3", secret)
    assert secret not in cached_text
    assert str(cached_dir) not in cached_text
    progress_events = [event for event in cached["events"] if event["metadata"].get("progress")]
    progress_types = {event["type"] for event in progress_events}
    progress_text = json.dumps(progress_events)

    assert {"queued", "resolving_model", "downloading_cache", "verifying_cache", "cached", "succeeded"} <= progress_types
    assert "Downloading or resolving Hugging Face snapshot" in progress_text
    assert "Verifying cached model" in progress_text
    assert "Model cached" in progress_text
    assert secret not in progress_text
    assert str(cached_dir) not in progress_text


def test_sam_setup_jobs_cache_models_with_confirmation_and_redaction(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=False)

    status, _headers, body = app.handle(
        "POST",
        "/api/provider-settings/sam3-local/setup/start",
        body=json.dumps({"action": "cache_model", "runInline": True, "dryRun": True, "allowNetwork": False, "allowDisk": True}).encode("utf-8"),
    )
    blocked = decode(body)["setupJob"]

    assert status == 200
    assert blocked["status"] == "blocked"
    assert blocked["setupState"]["status"] == "failed_recoverable"
    assert blocked["result"]["networkAttempted"] is False
    assert blocked["progress"]["label"] == "Waiting for network confirmation"

    status, _headers, body = app.handle(
        "POST",
        "/api/provider-settings/sam2-hf-auto-masks/setup/start",
        body=json.dumps({"action": "cache_model", "runInline": True, "dryRun": True, "allowNetwork": True, "allowDisk": True}).encode("utf-8"),
    )
    cached = decode(body)["setupJob"]

    assert status == 200
    assert cached["status"] == "succeeded"
    assert cached["setupState"]["status"] == "ready"
    assert cached["result"]["model"] == "facebook/sam2.1-hiera-large"
    assert cached["progress"] == {"known": True, "percent": 100, "label": "Cache dry run accepted"}
    assert "cache_model" in {action["id"] for action in provider_setup_actions("sam2-hf-auto-masks")}


def test_local_model_cache_persists_and_survives_ui_reload_with_redaction(tmp_path):
    model_dir = tmp_path / "mock-sam2-from-pretrained"
    model_dir.mkdir()
    (model_dir / "config.json").write_text('{"model_type":"sam2"}\n', encoding="utf-8")
    (model_dir / "README.md").write_text("mock local model\n", encoding="utf-8")
    db_path = tmp_path / "backend.sqlite"
    storage_root = tmp_path / "storage"
    app = LocalUIApp(db_path=db_path, storage_root=storage_root, mock_mode=False)

    status, _headers, body = app.handle(
        "POST",
        "/api/provider-settings/sam2-hf-auto-masks/setup/start",
        body=json.dumps(
            {
                "action": "cache_model",
                "runInline": True,
                "allowNetwork": True,
                "allowDisk": True,
                "model": str(model_dir),
            }
        ).encode("utf-8"),
    )
    text = body.decode("utf-8")
    setup_job = decode(body)["setupJob"]

    assert status == 200
    assert setup_job["status"] == "succeeded"
    assert setup_job["result"]["networkAttempted"] is False
    assert str(model_dir) not in text

    reloaded = LocalUIApp(db_path=db_path, storage_root=storage_root, mock_mode=False)
    status, _headers, body = reloaded.handle("GET", "/api/provider-settings")
    text = body.decode("utf-8")
    provider = provider_by_id(decode(body), "sam2-hf-auto-masks")

    assert status == 200
    assert provider["modelCache"]["cached"] is True
    assert provider["modelCache"]["status"] == "cached"
    assert provider["modelCache"]["localPathDisplay"] == "[LOCAL_PATH_REDACTED]"
    assert str(model_dir) not in text


def test_hugging_face_cache_probe_uses_local_files_only_and_reports_cached(tmp_path, monkeypatch):
    model_dir = tmp_path / "hf-cache" / "snapshot"
    model_dir.mkdir(parents=True)
    (model_dir / "config.json").write_text('{"model_type":"sam3"}\n', encoding="utf-8")
    calls: dict[str, object] = {}
    fake_hub = types.ModuleType("huggingface_hub")
    fake_hub.__spec__ = ModuleSpec("huggingface_hub", loader=None)

    def snapshot_download(**kwargs):
        calls.update(kwargs)
        return str(model_dir)

    fake_hub.snapshot_download = snapshot_download
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hub)
    monkeypatch.setattr("motionjson.provider_settings.find_spec", lambda name: object() if name == "huggingface_hub" else None)
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=False)

    status, _headers, body = app.handle("GET", "/api/provider-settings")
    provider = provider_by_id(decode(body), "sam3-local")

    assert status == 200
    assert provider["modelCache"]["cached"] is True
    assert provider["modelCache"]["source"] == "hf_cache"
    assert calls["repo_id"] == "facebook/sam3"
    assert calls["local_files_only"] is True
    assert str(model_dir) not in body.decode("utf-8")


def test_hugging_face_cache_probe_reports_actionable_missing_cache(tmp_path, monkeypatch):
    class FakeLocalEntryNotFoundError(Exception):
        pass

    fake_hub = types.ModuleType("huggingface_hub")
    fake_hub.__spec__ = ModuleSpec("huggingface_hub", loader=None)

    def snapshot_download(**_kwargs):
        raise FakeLocalEntryNotFoundError("Local entry not found")

    fake_hub.snapshot_download = snapshot_download
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hub)
    monkeypatch.setattr("motionjson.provider_settings.find_spec", lambda name: object() if name == "huggingface_hub" else None)
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=False)

    status, _headers, body = app.handle("GET", "/api/provider-settings")
    provider = provider_by_id(decode(body), "sam3-local")

    assert status == 200
    assert provider["modelCache"]["cached"] is False
    assert provider["modelCache"]["status"] == "not_cached"
    assert "Cache model" in provider["modelCache"]["message"]
    assert provider["setupState"]["status"] in {"not_configured", "needs_access", "needs_download_confirmation"}


def test_sam2_hf_fallback_provider_is_distinct_from_official_sam2_setup(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=False)

    status, _headers, body = app.handle("GET", "/api/provider-settings")
    payload = decode(body)
    provider = provider_by_id(payload, "sam2-hf-auto-masks")

    assert status == 200
    assert provider["name"] == "SAM2 HF automatic masks"
    assert provider["supportsAutoMasks"] is True
    assert provider["supportedGoals"] == ["trace_all_objects"]
    assert "official SAM2 checkpoint/config" in provider["warning"]


def test_provider_setup_job_cancel_and_retry_are_public_and_terminal(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    conn = app.connection()
    try:
        user = app._local_user(conn)
        first = create_provider_setup_job(conn, user_id=user["id"], provider_id="sam3-local", payload={"action": "diagnose"})
        canceled = cancel_provider_setup_job(conn, user_id=user["id"], job_id=first["id"], reason="user_clicked_cancel")
        retry = create_provider_setup_job(conn, user_id=user["id"], provider_id="sam3-local", payload={"action": "diagnose"})
    finally:
        conn.close()

    assert canceled["status"] == "canceled"
    assert canceled["terminal"] is True
    assert retry["id"] != first["id"]
    assert retry["status"] == "queued"


def test_hosted_provider_setup_job_redacts_secrets(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=False)
    secret = "sk-hosted-sam3-redaction-secret-123456"

    status, _headers, body = app.handle(
        "POST",
        "/api/provider-settings/sam3-hosted/setup/start",
        body=json.dumps(
            {
                "action": "diagnose",
                "runInline": True,
                "settings": {
                    "hostedProfileId": "custom-sam3-compatible",
                    "endpoint": "https://provider.example.invalid/sam3",
                    "apiKey": secret,
                    "allowHosted": True,
                },
            }
        ).encode("utf-8"),
    )
    payload_text = body.decode("utf-8")
    payload = decode(body)

    assert status == 200
    assert payload["setupJob"]["providerId"] == "sam3-hosted"
    assert secret not in payload_text
    assert "[REDACTED]" in payload_text


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
