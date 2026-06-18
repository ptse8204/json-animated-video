from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_normal_first_run_has_one_goal_picker_and_four_goal_cards():
    html = read("src/motionjson/ui/static/index.html")
    normal_start, advanced_panel = re.split(r'<details class="advanced-task-panel"', html, maxsplit=1)
    advanced_start = advanced_panel.split("</details>", 1)[0]

    assert 'class="goal-list"' not in html
    assert len(re.findall(r'<button class="goal-card(?:\s|")', normal_start)) == 4
    assert 'data-preset="trace_one_object"' in normal_start
    assert 'data-preset="pick_objects_from_frame"' in normal_start
    assert 'data-preset="text_detector"' in normal_start
    assert 'data-preset="review_existing"' in normal_start
    assert 'data-preset="trace_all_objects"' in advanced_start
    assert 'id="workflowDashboardToggle"' not in html
    assert 'id="detailsToggle"' not in html


def test_model_setup_normal_path_hides_raw_provider_controls_behind_advanced():
    js = read("src/motionjson/ui/static/app.js")
    detail_body = js.split("function renderModelSetupDetail", 1)[1].split("function currentModelPlanResult", 1)[0]
    rendered_markup = detail_body.split('return `\n        <form id="modelSetupForm"', 1)[1]
    before_advanced = rendered_markup.split('<details class="advanced-panel model-setup-advanced">', 1)[0]
    inside_advanced = detail_body.split('<details class="advanced-panel model-setup-advanced">', 1)[1]

    assert "model-setup-guided-card" in before_advanced
    assert "modelSetupRequiredNowMarkup" in detail_body
    assert "Hugging Face access" in detail_body
    assert "hfToken" in detail_body
    assert "HF_TOKEN" not in before_advanced
    assert '"cache-model"' in js
    for raw_control in ("sam3ModelPath", "endpoint", "apiKey", "View logs", "Diagnose"):
        assert raw_control not in before_advanced
    for advanced_binding in ("${localFields}", "${endpointField}", "${credentialField}", "View logs", "Diagnose"):
        assert advanced_binding in inside_advanced


def test_model_setup_renders_one_recommended_card_until_change_model():
    js = read("src/motionjson/ui/static/app.js")

    assert "modelSetupAlternativesOpen" in js
    assert "compatibleModelConnectionsForPreset(state.selectedPreset, { includeAdvanced: state.modelSetupAlternativesOpen })" in js
    assert "modelConnectionByConnectionId(state.selectedModelSetupProviderId) || modelConnectionByConnectionId(recommendedId)" in js


def test_model_setup_prioritizes_required_hf_token_in_normal_flow():
    js = read("src/motionjson/ui/static/app.js")
    detail_body = js.split("function renderModelSetupDetail", 1)[1].split("function currentModelPlanResult", 1)[0]

    assert "requiredInputPriority" in detail_body
    assert 'if (key === "hf_token") return 0;' in detail_body
    assert 'asArray(recommendation.requiredInputs).slice().sort((a, b) => requiredInputPriority(a) - requiredInputPriority(b))' in detail_body
    assert 'return credentialInputMarkup({ name: "hf_token", label: input.label || "Hugging Face token" }, { normal: true });' in detail_body


def test_pick_frame_workflow_has_explicit_scan_frame_gate():
    html = read("src/motionjson/ui/static/index.html")
    js = read("src/motionjson/ui/static/app.js")
    workflow = read("src/motionjson/ui/static/modules/workflow.js")

    assert 'id="keyframeScanChooser"' in html
    assert 'id="useCurrentFrameForScanButton"' in html
    assert 'id="clearScanFrameButton"' in html
    assert 'function fastFrameScanFrameError' in js
    assert js.count("blockFastFrameScanUntilConfirmed(formState)") >= 4
    assert "Choose the exact frame to scan before starting the keyframe scan." in js
    assert "snapshot.scanFrameConfirmed === true" in workflow
    assert "Choose the exact frame to scan." in workflow


def test_storyboard_shell_uses_project_drawer_and_in_flow_cta_in_normal_mode():
    css = read("src/motionjson/ui/static/app.css")
    html = read("src/motionjson/ui/static/index.html")
    final_overrides = css.rsplit("Final storyboard overrides", 1)[1]

    assert "id=\"projectDrawerToggle\"" in html
    assert "aria-controls=\"workspaceSidebar\"" in html
    assert "grid-template-columns: minmax(0, 1fr)" in final_overrides
    assert ".sidebar" in final_overrides
    assert "position: fixed" in final_overrides
    assert ".project-rail-list" in final_overrides
    assert ".sidebar-content > details" in final_overrides
    assert ".app-shell.is-sidebar-collapsed .sidebar" in final_overrides
    assert "display: none" in final_overrides
    assert "#workflowController" in final_overrides
    assert "position: static" in final_overrides
    assert "pointer-events: none" in final_overrides


def test_guided_parameters_show_auto_tuning_and_keyboard_help():
    html = read("src/motionjson/ui/static/index.html")
    css = read("src/motionjson/ui/static/app.css")
    js = read("src/motionjson/ui/static/app.js")
    selectors = read("src/motionjson/ui/static/ui_selectors.js")
    build_script = read("scripts/build_ui_shell.mjs")

    assert 'id="adaptiveParameterSummary"' in html
    assert 'id="resetAutoParametersButton"' in html
    assert 'id="sampleFpsAutoStatus"' in html
    assert 'id="maxFramesAutoStatus"' in html
    assert 'id="maxObjectsAutoStatus"' in html
    assert 'id="qualityPresetAutoStatus"' in html
    assert 'id="deviceAutoStatus"' in html
    assert 'id="guidedQualityControls"' in html
    assert 'data-quality-preset="maximum_recall"' in html
    assert 'data-device-preset="cuda"' in html
    assert 'data-tooltip="How many source frames per second are sampled before tracking.' in html
    assert 'data-tooltip="Maximum object candidates allowed into review.' in html
    assert 'data-tooltip="Controls package size and debug detail.' in html
    assert "Mask detail" in html
    assert "Runtime speed" in html
    assert 'tabindex="0" data-tooltip=' in html
    assert "adaptiveRunDefaultsFromSnapshot" in js
    assert 'from "./ui_selectors.js"' in js
    assert "export function adaptiveRunDefaultsFromSnapshot" in selectors
    assert "export function projectShellStateFromSnapshot" in selectors
    assert "export function reviewExportScreenStateFromSnapshot" in selectors
    assert '"ui_selectors.js"' in build_script
    assert "OPTION_HELP_TEXT" in js
    assert "parameterOverrides" in js
    assert ".adaptive-chip-grid" in css
    assert ".guided-quality-controls" in css
    assert ".segmented-control" in css
    assert ".parameter-source.is-override" in css


def test_review_export_workspace_has_distinct_review_and_export_hooks():
    html = read("src/motionjson/ui/static/index.html")
    css = read("src/motionjson/ui/static/app.css")
    js = read("src/motionjson/ui/static/app.js")
    selectors = read("src/motionjson/ui/static/ui_selectors.js")

    assert 'id="studioReviewTitle"' in html
    assert 'id="studioExportCard"' in html
    assert 'id="studioExportIncludedObjects"' in html
    assert 'id="studioPartialDiagnostic"' in html
    assert "is-review-export-screen-review" in css
    assert "is-review-export-screen-export" in css
    assert "reviewExportSubscreen" in js
    assert "reviewExportScreenStateFromSnapshot" in js
    assert "motionjson.local_ui_review_export_screen.v0.1" in selectors
    assert "Review partial objects" in js
    assert "workflow-partial-success" in js


def test_advanced_discover_objects_has_compatible_model_connections():
    js = read("src/motionjson/ui/static/app.js")
    provider_connections = read("src/motionjson/ui/static/modules/provider_connections.js")
    static_js = js + "\n" + provider_connections

    assert 'auto_object_proposals: ["sam2-hf-auto-masks", "sam2-local"]' in static_js
    assert 'pick_objects_from_frame: ["sam3-local", "sam3-hosted:motionjson-colab-sam3-session", "sam2-hf-auto-masks", "no_model_cpu_workflow", "sam3-hosted:custom-sam3-compatible"]' in static_js
    assert 'presetId === "auto_object_proposals"' in js
