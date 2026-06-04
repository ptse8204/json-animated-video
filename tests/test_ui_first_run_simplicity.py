from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_normal_first_run_has_one_goal_picker_and_four_goal_cards():
    html = read("src/motionjson/ui/static/index.html")
    normal_start = html.split('<details class="advanced-panel advanced-task-panel">', 1)[0]

    assert 'class="goal-list"' not in html
    assert len(re.findall(r'<button class="goal-card(?:\s|")', normal_start)) == 4
    assert 'data-preset="trace_one_object"' in normal_start
    assert 'data-preset="text_detector"' in normal_start
    assert 'data-preset="trace_all_objects"' in normal_start
    assert 'data-preset="review_existing"' in normal_start


def test_model_setup_normal_path_hides_raw_provider_controls_behind_advanced():
    js = read("src/motionjson/ui/static/app.js")
    detail_body = js.split("function renderModelSetupDetail", 1)[1].split("function currentModelPlanResult", 1)[0]
    rendered_markup = detail_body.split('return `\n        <div class="model-setup-summary">', 1)[1]
    before_advanced = rendered_markup.split('<details class="advanced-panel model-setup-advanced">', 1)[0]
    inside_advanced = detail_body.split('<details class="advanced-panel model-setup-advanced">', 1)[1]

    assert "Change model" in before_advanced
    assert "primarySetupAction.label" in before_advanced
    assert "${normalAccessCard}" in before_advanced
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
    assert re.search(r"state\.modelSetupAlternativesOpen\s*\|\|\s*state\.workflowDashboard\s*\?\s*compatibleConnections", js)
    assert "compatibleConnections.filter((connection) => connection.id === state.selectedModelSetupProviderId" in js


def test_storyboard_shell_keeps_project_rail_and_in_flow_cta_in_normal_mode():
    css = read("src/motionjson/ui/static/app.css")
    final_overrides = css.rsplit("Final storyboard overrides", 1)[1]

    assert "grid-template-columns: 214px minmax(0, 1fr)" in final_overrides
    assert ".sidebar" in final_overrides
    assert ".project-rail-list" in final_overrides
    assert ".sidebar-content > details" in final_overrides
    assert "display: flex" in final_overrides
    assert "#workflowController" in final_overrides
    assert "position: static" in final_overrides
    assert "pointer-events: none" in final_overrides


def test_advanced_discover_objects_has_compatible_model_connections():
    js = read("src/motionjson/ui/static/app.js")

    assert 'auto_object_proposals: ["sam2-hf-auto-masks", "sam2-local"]' in js
    assert 'presetId === "auto_object_proposals"' in js
