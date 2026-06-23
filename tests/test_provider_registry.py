from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from motionjson.backend.models import ALLOWED_EXTRACT_MASK_PROVIDERS, REJECTED_SEGMENTATION_ALIASES
from motionjson.capabilities import build_capability_report
from motionjson.config import DISCOVERY_MODES, DISCOVERY_PROVIDER_PREFERENCES, MASK_PROVIDERS
from motionjson.provider_registry import (
    PROVIDER_WORKFLOW_REGISTRY_FORMAT,
    normalize_provider_id,
    provider_by_id,
    registry_capability_ids,
    registry_has_provider_or_alias,
    registry_public_payload,
    worker_extract_provider_ids,
)
from motionjson.provider_settings import PROVIDER_DEFINITIONS, provider_catalog
from motionjson.ui.server import LocalUIApp

from tests.workflow_matrix import workflow_cases


REPO_ROOT = Path(__file__).resolve().parents[1]

_UI_REGISTRY_SCRIPT = """
import { WIZARD_PRESETS, buildRunConfig } from "./src/motionjson/ui/static/config_builder.js";
import "./src/motionjson/ui/static/app.js";
import { readFileSync } from "node:fs";

const matrix = JSON.parse(readFileSync("tests/fixtures/local_ui_workflow_matrix.v0.1.json", "utf8"));
const runConfigs = {};
for (const workflowCase of matrix.cases) {
  if (!workflowCase.builderInput) continue;
  runConfigs[workflowCase.id] = buildRunConfig({
    video: { id: "asset_1" },
    outputDir: "out/provider-registry-matrix",
    ...workflowCase.builderInput,
  });
}

console.log(JSON.stringify({
  apiRoutes: globalThis.MotionJSONUI.API_ROUTES,
  modelConnections: globalThis.MotionJSONUI.MODEL_CONNECTIONS,
  modelConnectionPriority: globalThis.MotionJSONUI.MODEL_CONNECTION_PRIORITY,
  wizardPresets: WIZARD_PRESETS,
  runConfigs,
}));
"""


def _decode(body: bytes) -> dict[str, Any]:
    return json.loads(body.decode("utf-8"))


def _ui_registry_snapshot() -> dict[str, Any]:
    result = subprocess.run(
        ["node", "--input-type=module", "-e", _UI_REGISTRY_SCRIPT],
        cwd=REPO_ROOT,
        env=os.environ.copy(),
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def _assert_public_safe(payload: dict[str, Any]) -> None:
    text = json.dumps(payload)
    assert "Authorization" not in text
    assert "[LOCAL_PATH_REDACTED]" not in text
    assert not re.search(r"(?<![\\w:])/(?:Users|private|var|tmp|Volumes|home)/", text)
    assert "sk-or-v1-" not in text
    assert not re.search(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9._~-]{8,}", text)


def test_provider_registry_api_is_public_safe_and_listed_in_health(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)

    status, _headers, body = app.handle("GET", "/api/provider-registry")
    payload = _decode(body)

    assert status == 200
    assert payload["format"] == PROVIDER_WORKFLOW_REGISTRY_FORMAT
    assert "providers" in payload
    assert "workflows" in payload
    assert provider_by_id("sam3-hosted:roboflow-sam3-pcs")["providerId"] == "sam3-hosted"
    assert provider_by_id("sam3-hosted:motionjson-colab-sam3-session")["providerId"] == "sam3-hosted"
    assert provider_by_id("sam2-hosted:replicate-sam2-video")["providerId"] == "sam2-hosted"
    assert provider_by_id("sam2-hosted:motionjson-colab-sam2-session")["providerId"] == "sam2-hosted"
    assert provider_by_id("openrouter-planner")["kind"] == "planning_provider"
    assert provider_by_id("openrouter-planner")["locality"] == "settings_only"
    _assert_public_safe(payload)

    status, _headers, body = app.handle("GET", "/api/health")
    health = _decode(body)
    assert status == 200
    assert "/api/provider-registry" in health["routes"]


def test_hosted_connection_aliases_preserve_settings_profile(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)

    status, _headers, body = app.handle(
        "POST",
        "/api/provider-settings",
        body=json.dumps({"providerId": "sam3-hosted:fal-sam3-image", "apiKey": "fal-test-token-123456"}).encode("utf-8"),
    )
    payload = _decode(body)
    sam3 = next(provider for provider in payload["providers"] if provider["id"] == "sam3-hosted")

    assert status == 200
    assert sam3["settings"]["hostedProfileId"] == "fal-sam3-image"
    assert "fal-test-token" not in json.dumps(payload)

    status, _headers, body = app.handle("POST", "/api/provider-settings/sam3-hosted:fal-sam3-image/test", body=b"{}")
    tested = _decode(body)
    assert status == 200
    assert tested["providerId"] == "sam3-hosted"
    assert tested["hostedProfileId"] == "fal-sam3-image"

    status, _headers, body = app.handle("POST", "/api/provider-settings/sam3-hosted:fal-sam3-image/diagnose", body=b"{}")
    diagnosis = _decode(body)
    assert status == 200
    assert diagnosis["providerId"] == "sam3-hosted"
    assert diagnosis["hostedProfileId"] == "fal-sam3-image"
    assert "FAL_KEY" in json.dumps(diagnosis)
    assert "fal-test-token" not in json.dumps(diagnosis)


def test_provider_settings_catalog_and_definitions_map_to_registry():
    catalog = provider_catalog()
    assert catalog["workflowRegistryFormat"] == PROVIDER_WORKFLOW_REGISTRY_FORMAT

    for definition in PROVIDER_DEFINITIONS:
        provider_id = definition["id"]
        entry = provider_by_id(provider_id)
        assert entry is not None, provider_id
        assert entry["providerId"] == provider_id
        assert entry["kind"] == definition["kind"]
        assert entry["locality"] == definition["locality"]
        assert entry["implemented"] == definition["implemented"]
        assert entry["settingsProviderId"] in {provider_id, "mock", "motion", "external", "sam2-local", "sam3-local"}
        assert definition["capabilityName"] in registry_capability_ids()

    for provider in catalog["providers"]:
        assert provider["registry"]["providerId"] == provider["id"]
        assert provider["registry"]["label"]


def test_capability_report_names_are_declared_by_registry():
    capability_ids = registry_capability_ids()
    report = build_capability_report()

    for provider in report["providers"]:
        name = provider["name"]
        assert name in capability_ids or registry_has_provider_or_alias(name), name

    assert provider_by_id("sam3-local")["capabilityId"] == "sam3-auto-masks"
    assert provider_by_id("sam3-concept")["settingsProviderId"] == "sam3-local"
    assert provider_by_id("sam3-exemplar")["settingsProviderId"] == "sam3-local"
    assert provider_by_id("sam3-auto-masks")["settingsProviderId"] == "sam3-local"


def test_sam3_product_paths_are_distinct_registry_entries_with_worker_mappings():
    expected = {
        "no_model_cpu_workflow": ("mock", ""),
        "sam2_prompt_tracking": ("sam2-local", "manual_prompt"),
        "sam2_hf_scene_fallback": ("sam2-hf-auto-masks", "sam2_hf_auto_masks"),
        "sam3_tracker_scene_sweep": ("sam3-local", "sam3_auto_masks"),
        "hosted_sam3_concept_text": ("sam3-hosted", "sam3_concept"),
        "advanced_local_sam3_concept_exemplar": ("sam3-local", "sam3_concept"),
    }

    for product_id, (run_provider, run_mode) in expected.items():
        entry = provider_by_id(product_id)
        assert entry is not None, product_id
        assert entry["providerId"] == product_id
        assert entry["kind"] == "product_workflow"
        assert entry["workerEligible"] is False
        assert product_id in registry_capability_ids()
        supports = [support for support in entry["workflowSupport"].values() if support["supported"] is not False]
        assert supports, product_id
        assert any(support["runConfigProviderName"] == run_provider for support in supports)
        if run_mode:
            assert any(support["runConfigDiscoveryMode"] == run_mode for support in supports)

    assert provider_by_id("sam3-local")["providerId"] == "sam3-local"
    assert provider_by_id("sam3-local")["capabilityId"] == "sam3-auto-masks"
    assert provider_by_id("sam3-scene-sweep")["providerId"] == "sam3-local"
    assert provider_by_id("sam3_tracker_scene_sweep")["providerId"] == "sam3_tracker_scene_sweep"
    assert provider_by_id("sam2_prompt_tracking")["settingsProviderId"] == "sam2-local"
    assert provider_by_id("sam2_hf_scene_fallback")["settingsProviderId"] == "sam2-hf-auto-masks"


def test_config_and_worker_policy_are_registry_backed():
    payload = registry_public_payload()

    assert ALLOWED_EXTRACT_MASK_PROVIDERS == worker_extract_provider_ids()
    assert payload["workerPolicy"]["allowedExtractMaskProviders"] == sorted(ALLOWED_EXTRACT_MASK_PROVIDERS)
    assert "evolink" in REJECTED_SEGMENTATION_ALIASES
    assert "openrouter" in REJECTED_SEGMENTATION_ALIASES
    assert "openai" in REJECTED_SEGMENTATION_ALIASES
    assert "sam2" in REJECTED_SEGMENTATION_ALIASES
    assert "evolink" not in ALLOWED_EXTRACT_MASK_PROVIDERS
    assert "evolink-planner" not in ALLOWED_EXTRACT_MASK_PROVIDERS
    assert "openrouter" not in ALLOWED_EXTRACT_MASK_PROVIDERS
    assert "openai" not in ALLOWED_EXTRACT_MASK_PROVIDERS
    assert "openrouter-planner" not in ALLOWED_EXTRACT_MASK_PROVIDERS
    assert "openai-planner" not in ALLOWED_EXTRACT_MASK_PROVIDERS

    for provider in MASK_PROVIDERS:
        assert registry_has_provider_or_alias(provider) or provider in REJECTED_SEGMENTATION_ALIASES, provider
    for preference in DISCOVERY_PROVIDER_PREFERENCES:
        assert preference == "auto" or registry_has_provider_or_alias(preference), preference
    for mode in DISCOVERY_MODES:
        assert registry_has_provider_or_alias(mode), mode


def test_ui_model_connections_and_config_builder_presets_map_to_registry():
    snapshot = _ui_registry_snapshot()

    assert "/api/provider-registry" in snapshot["apiRoutes"]
    assert snapshot["modelConnections"]
    for connection in snapshot["modelConnections"]:
        assert registry_has_provider_or_alias(connection["id"]), connection["id"]
        assert provider_by_id(connection["providerId"]) is not None, connection["providerId"]

    connection_ids = {connection["id"] for connection in snapshot["modelConnections"]}
    for preset_id, prioritized in snapshot["modelConnectionPriority"].items():
        for connection_id in prioritized:
            assert connection_id in connection_ids, f"{preset_id}: {connection_id}"
            assert registry_has_provider_or_alias(connection_id), connection_id

    for preset in snapshot["wizardPresets"]:
        assert registry_has_provider_or_alias(preset["id"]), preset["id"]
        assert registry_has_provider_or_alias(preset["discoveryMode"]), preset["discoveryMode"]
        assert registry_has_provider_or_alias(preset["defaultMaskProvider"]), preset["defaultMaskProvider"]


def test_phase1_workflow_matrix_provider_ids_map_to_registry():
    snapshot = _ui_registry_snapshot()
    run_configs = snapshot["runConfigs"]

    for workflow_case in workflow_cases():
        for key in ("providerName", "modelProviderId"):
            value = workflow_case.get(key)
            if value:
                assert registry_has_provider_or_alias(value), f"{workflow_case['id']}: {key}={value}"
        for provider in workflow_case.get("capabilityReport", {}).get("providers", []):
            name = provider.get("name")
            assert name in registry_capability_ids() or registry_has_provider_or_alias(name), f"{workflow_case['id']}: capability {name}"

    for case_id, run_config in run_configs.items():
        assert registry_has_provider_or_alias(run_config["provider"]["name"]), case_id
        discovery_mode = run_config.get("discovery", {}).get("mode")
        if discovery_mode:
            assert registry_has_provider_or_alias(discovery_mode), case_id
        provider_preference = run_config.get("discovery", {}).get("config", {}).get("providerPreference")
        if provider_preference:
            assert normalize_provider_id(provider_preference) == provider_preference or registry_has_provider_or_alias(provider_preference)


def test_hosted_and_settings_only_policy_is_explicit():
    sam2_hosted = provider_by_id("sam2-hosted")
    sam3_hosted = provider_by_id("sam3-hosted")
    openrouter = provider_by_id("openrouter-planner")
    evolink = provider_by_id("evolink-planner")
    openai = provider_by_id("openai-planner")
    text_detector = provider_by_id("text_detector")
    class_detector = provider_by_id("class_detector")

    for entry in (sam2_hosted, sam3_hosted, evolink, openai):
        assert entry["locality"] == "hosted"
        assert any(support["requiresHostedOptIn"] for support in entry["workflowSupport"].values())
        assert entry["providerId"] not in {"evolink", "evolink-planner", "openai", "openai-planner"} or entry["workerEligible"] is False

    assert evolink["settingsProviderId"] == "evolink"
    assert evolink["implemented"] is True
    assert evolink["workerEligible"] is False
    assert evolink["validationPolicy"] == "hosted_opt_in_required"
    assert openrouter["locality"] == "settings_only"
    assert openrouter["implemented"] is False
    assert openrouter["workerEligible"] is False
    assert openrouter["validationPolicy"] == "settings_only"
    assert provider_by_id("sam2-hf-auto-masks")["runtimeProofRequired"] is True
    assert provider_by_id("sam3-local")["runtimeProofRequired"] is True
    assert text_detector["implemented"] is False
    assert text_detector["validationPolicy"] == "mock_or_unavailable"
    assert class_detector["implemented"] is False
    assert class_detector["validationPolicy"] == "mock_or_unavailable"
