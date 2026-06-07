from __future__ import annotations

import copy
import json
import os
import subprocess
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

import pytest

from motionjson.backend.assets import list_assets_for_job
from motionjson.config import ExtractionRunConfig
from motionjson.model_connectors import (
    FakeModelConnector,
    ModelConnectorError,
    ModelPlanRequest,
    OpenAIPlanningConnector,
    OpenRouterSettingsModelConnector,
)
from motionjson.ui import server as ui_server
from motionjson.ui.server import LocalUIApp

from tests.workflow_matrix import get_path, load_workflow_matrix, workflow_case, workflow_cases


REPO_ROOT = Path(__file__).resolve().parents[1]

_JS_MATRIX_CONFIG_SCRIPT = """
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { buildRunConfig } from "./src/motionjson/ui/static/config_builder.js";

const matrix = JSON.parse(readFileSync(resolve("tests/fixtures/local_ui_workflow_matrix.v0.1.json"), "utf8"));
const assetId = process.env.MOTIONJSON_MATRIX_ASSET_ID || "asset_1";
const outputDir = process.env.MOTIONJSON_MATRIX_OUTPUT_DIR || "out/ui-workflow-matrix";
const configs = {};
for (const workflowCase of matrix.cases) {
  if (!workflowCase.builderInput) continue;
  configs[workflowCase.id] = buildRunConfig({
    video: { id: assetId },
    outputDir,
    ...workflowCase.builderInput,
  });
}
console.log(JSON.stringify(configs));
"""


def _decode(body: bytes) -> dict[str, Any]:
    return json.loads(body.decode("utf-8"))


def _demo_video() -> Path:
    return Path(__file__).resolve().parents[1] / "examples" / "demo_red_ball.mp4"


def _wait_for_job(app: LocalUIApp, job_id: str, *, timeout: float = 10.0) -> dict[str, Any]:
    deadline = time.time() + timeout
    last_job: dict[str, Any] = {}
    while time.time() < deadline:
        status, _headers, body = app.handle("GET", f"/api/jobs/{job_id}")
        assert status == 200
        last_job = _decode(body)["job"]
        if last_job["status"] in {"succeeded", "failed", "canceled"}:
            return last_job
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish; last status: {last_job}")


def _capability_report_for_case(case: dict[str, Any]) -> dict[str, Any]:
    report = copy.deepcopy(case.get("capabilityReport") or {})
    providers = report.setdefault("providers", [])
    ready = sum(1 for provider in providers if provider.get("available") is not False and provider.get("runnable") is not False)
    report.setdefault("schema", "motionjson.provider_diagnostics.v0.1")
    report.setdefault("summary", {"providersReady": ready, "providersTotal": len(providers)})
    report.setdefault("environment", {})
    return report


@lru_cache(maxsize=None)
def _js_matrix_run_configs(asset_id: str = "asset_1", output_dir: str = "out/ui-workflow-matrix") -> dict[str, Any]:
    env = os.environ.copy()
    env["MOTIONJSON_MATRIX_ASSET_ID"] = asset_id
    env["MOTIONJSON_MATRIX_OUTPUT_DIR"] = output_dir
    result = subprocess.run(
        ["node", "--input-type=module", "-e", _JS_MATRIX_CONFIG_SCRIPT],
        cwd=REPO_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def _js_run_config_for_case(case: dict[str, Any], tmp_path: Path, *, asset_id: str = "asset_1") -> dict[str, Any]:
    return copy.deepcopy(_js_matrix_run_configs(asset_id, str(tmp_path / "matrix-output"))[case["id"]])


def test_workflow_matrix_schema_and_required_cases():
    matrix = load_workflow_matrix()
    cases = matrix["cases"]
    ids = [case["id"] for case in cases]
    assert len(cases) >= 20
    assert len(ids) == len(set(ids))
    assert {case["status"] for case in cases} <= {"runnable", "blocked", "conditional", "mocked"}
    for required in {
        "trace_one_mock_prompt",
        "threshold_cpu_local",
        "motion_foreground_cpu",
        "sam_auto_masks_mock_proposals",
        "sam_auto_masks_unavailable",
        "external_masks_missing_dir",
        "sam2_local_unavailable",
        "sam2_local_available_mocked",
        "sam2_hf_auto_masks_unavailable",
        "sam2_hf_auto_masks_available_mocked",
        "sam3_scene_sweep_unavailable",
        "sam3_scene_sweep_available_mocked",
        "sam3_local_concept_blocked",
        "sam2_hosted_blocked_without_opt_in",
        "sam3_hosted_blocked_without_opt_in",
        "hosted_configured_no_network",
        "fake_local_planner",
        "openai_planner_mocked",
        "openrouter_planner_not_runnable",
        "review_existing_import",
    }:
        assert required in ids


@pytest.mark.parametrize(
    "case",
    [case for case in workflow_cases() if "expectedValidation" in case],
    ids=lambda case: case["id"],
)
def test_local_ui_run_config_validation_matrix(tmp_path, monkeypatch, case):
    report = _capability_report_for_case(case)

    def fake_capability_report(*_args, **_kwargs):
        return report

    monkeypatch.setattr(ui_server, "build_capability_report", fake_capability_report)
    app = LocalUIApp(db_path=tmp_path / f"{case['id']}.sqlite", storage_root=tmp_path / f"{case['id']}-storage", mock_mode=True)
    run_config = _js_run_config_for_case(case, tmp_path)

    for path, expected_value in case.get("expectedRunConfig", {}).items():
        assert get_path(run_config, path) == expected_value

    status, _headers, body = app.handle(
        "POST",
        "/api/run-config/validate",
        body=json.dumps({"runConfig": run_config}).encode("utf-8"),
    )
    payload = _decode(body)
    expected = case["expectedValidation"]
    public_text = json.dumps(payload)

    assert status == 200
    assert payload["valid"] is expected["valid"]
    if expected.get("errorCodes") is not None:
        assert [error.get("code") for error in payload["errors"]] == expected["errorCodes"]
    if expected.get("warningCodes") is not None:
        assert [warning.get("code") for warning in payload["warnings"]] == expected["warningCodes"]
    if expected.get("errorCodesAnyOf"):
        assert set(expected["errorCodesAnyOf"]) & {error.get("code") for error in payload["errors"]}
    if expected.get("blockingWarningCodesAnyOf"):
        assert set(expected["blockingWarningCodesAnyOf"]) & {warning.get("code") for warning in payload["warnings"]}
        assert any(warning.get("severity") == "error" for warning in payload["warnings"])
    if expected.get("blockingProvidersAnyOf"):
        providers = {item.get("provider") for item in payload["warnings"] + payload["errors"]}
        assert set(expected["blockingProvidersAnyOf"]) & providers
    if expected.get("messageContainsAnyOf"):
        assert any(fragment in public_text for fragment in expected["messageContainsAnyOf"])
    if expected.get("mustNotMentionAnyOf"):
        for fragment in expected["mustNotMentionAnyOf"]:
            assert fragment not in public_text
    if payload["valid"]:
        ExtractionRunConfig.from_dict(payload["runConfig"])


def test_workflow_matrix_mock_job_review_and_export_surfaces(tmp_path, monkeypatch):
    case = workflow_case("trace_one_mock_prompt")
    report = _capability_report_for_case(case)

    def fake_capability_report(*_args, **_kwargs):
        return report

    monkeypatch.setattr(ui_server, "build_capability_report", fake_capability_report)
    app = LocalUIApp(db_path=tmp_path / "matrix-job.sqlite", storage_root=tmp_path / "matrix-job-storage", mock_mode=True)

    status, _headers, body = app.handle("POST", "/api/projects", body=json.dumps({"name": "Matrix Mock Project"}).encode("utf-8"))
    assert status == 200
    project = _decode(body)["project"]

    status, _headers, body = app.handle(
        "POST",
        "/api/videos",
        body=json.dumps({"projectId": project["id"], "path": str(_demo_video())}).encode("utf-8"),
    )
    assert status == 200
    video = _decode(body)["video"]
    run_config = _js_run_config_for_case(case, tmp_path, asset_id=video["id"])

    status, _headers, body = app.handle("POST", "/api/run-config/validate", body=json.dumps({"runConfig": run_config}).encode("utf-8"))
    validation = _decode(body)
    assert status == 200
    assert validation["valid"] is True
    assert validation["warnings"] == []

    status, _headers, body = app.handle(
        "POST",
        "/api/jobs",
        body=json.dumps({"projectId": project["id"], "runConfig": run_config, "run": True}).encode("utf-8"),
    )
    assert status == 200
    job = _wait_for_job(app, _decode(body)["job"]["id"])
    assert job["status"] == case["expectedJob"]["terminalStatus"]

    status, _headers, body = app.handle("GET", f"/api/jobs/{job['id']}/artifacts")
    artifacts_payload = _decode(body)
    artifact_kinds = {artifact["kind"] for artifact in artifacts_payload["artifacts"]}
    assert status == 200
    assert artifact_kinds & set(case["expectedArtifacts"]["kindsAnyOf"])
    assert "storage_key" not in body.decode("utf-8")

    status, _headers, body = app.handle("GET", f"/api/jobs/{job['id']}/review")
    review = _decode(body)["review"]
    assert status == 200
    assert review["tracks"] or review["diagnostics"]

    status, _headers, body = app.handle("GET", f"/api/jobs/{job['id']}/review-tools")
    tools = _decode(body)
    assert status == 200
    assert tools["readiness"]["readyForReview"] is case["expectedReview"]["readyForReview"]
    assert tools["readiness"]["previewToolsReady"] is case["expectedReview"]["reviewToolsReady"]

    status, _headers, body = app.handle(
        "POST",
        f"/api/jobs/{job['id']}/validate",
        body=json.dumps({"preset": "compact", "includePreview": False}).encode("utf-8"),
    )
    export_validation = _decode(body)
    assert status == 200
    assert export_validation["validation"]["ok"] is case["expectedExport"]["validationOk"]

    status, _headers, body = app.handle(
        "POST",
        f"/api/jobs/{job['id']}/exports/motionjson",
        body=json.dumps({"preset": "compact", "includePreview": False}).encode("utf-8"),
    )
    exported = _decode(body)
    exported_kinds = {artifact["kind"] for artifact in exported["artifacts"]}
    assert status == 200
    assert exported_kinds & set(case["expectedExport"]["kindsAnyOf"])
    assert "storage_key" not in body.decode("utf-8")


@pytest.mark.parametrize(
    "case",
    [case for case in workflow_cases() if "expectedModelRun" in case],
    ids=lambda case: case["id"],
)
def test_model_planner_matrix_cases(case):
    request = ModelPlanRequest.from_dict(case.get("modelInput") or {})
    expected = case["expectedModelRun"]
    if case["modelProviderId"] == "fake-local-planner":
        connector = FakeModelConnector()
        result = connector.plan(request)
        assert connector.readiness()["networkAttempted"] is expected["networkAttempted"]
        assert result.validation["valid"] is expected["runConfigValid"]
        assert result.requires_user_confirmation is expected["requiresUserConfirmation"]
        assert get_path(result.run_config, "provider.name") == expected["provider.name"]
        ExtractionRunConfig.from_dict(result.run_config)
        return

    if case["modelProviderId"] == "openai-planner":
        captured: dict[str, Any] = {}

        def transport(url, payload, headers, timeout):
            captured["url"] = url
            captured["payload"] = payload
            captured["headers"] = headers
            captured["timeout"] = timeout
            return {
                "output_text": (
                    '{"goal":"find_objects_from_text","objectLabels":["red ball"],'
                    '"objectId":"red_ball","textPrompt":"red ball",'
                    '"suggestedKeyframes":[0,3],'
                    '"providerPlan":{"discoveryProvider":"text_detector","maskProvider":"mock",'
                    '"trackingMode":"selected_only","rationale":"Use text candidates first."},'
                    '"troubleshooting":["If candidates are broad, lower max area."]}'
                )
            }

        connector = OpenAIPlanningConnector(api_key="sk-openai-test-secret-123456", model="gpt-test-planner", transport=transport, allow_network=True)
        result = connector.plan(request)
        encoded_payload = json.dumps(captured["payload"])
        for forbidden in expected["payloadMustNotContain"]:
            assert forbidden not in encoded_payload
        assert captured["url"] == "https://api.openai.com/v1/responses"
        assert result.validation["valid"] is expected["runConfigValid"]
        assert result.requires_user_confirmation is expected["requiresUserConfirmation"]
        assert get_path(result.run_config, "provider.name") == expected["provider.name"]
        ExtractionRunConfig.from_dict(result.run_config)
        return

    if case["modelProviderId"] == "openrouter-planner":
        connector = OpenRouterSettingsModelConnector()
        readiness = connector.readiness()
        assert readiness["runnable"] is expected["readinessRunnable"]
        with pytest.raises(ModelConnectorError, match="|".join(expected["messageContainsAnyOf"])):
            connector.plan(request)
        return

    raise AssertionError(f"Unhandled model provider case: {case['modelProviderId']}")


def test_workflow_matrix_review_existing_import_path(tmp_path):
    case = workflow_case("review_existing_import")
    app = LocalUIApp(db_path=tmp_path / "matrix-import.sqlite", storage_root=tmp_path / "matrix-import-storage", mock_mode=True)

    status, _headers, body = app.handle("POST", "/api/projects", body=json.dumps({"name": "Matrix Import Project"}).encode("utf-8"))
    assert status == 200
    project = _decode(body)["project"]
    status, _headers, body = app.handle(
        "POST",
        "/api/videos",
        body=json.dumps({"projectId": project["id"], "path": str(_demo_video())}).encode("utf-8"),
    )
    assert status == 200
    video = _decode(body)["video"]
    status, _headers, body = app.handle(
        "POST",
        "/api/jobs",
        body=json.dumps({"projectId": project["id"], "videoId": video["id"], "maskProvider": "mock", "maxFrames": 2, "run": True}).encode("utf-8"),
    )
    assert status == 200
    job = _wait_for_job(app, _decode(body)["job"]["id"])
    assert job["status"] == "succeeded"

    conn = app.connection()
    try:
        assets = list_assets_for_job(conn, project_id=job["project_id"], source_job_id=job["id"])
    finally:
        conn.close()

    import_dir = tmp_path / "matrix-importable-result"
    storage = app.storage()
    for asset in assets:
        metadata = json.loads(asset.get("metadata_json") or "{}")
        rel_path = metadata.get("rel_path")
        if not isinstance(rel_path, str) or not rel_path:
            continue
        target = import_dir / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(storage.load_bytes(asset["storage_key"]))

    status, _headers, body = app.handle(
        "POST",
        case["expectedImport"]["endpoint"].replace("{projectId}", project["id"]),
        body=json.dumps({"path": str(import_dir)}).encode("utf-8"),
    )
    imported = _decode(body)["import"]
    assert status == 200
    assert imported["validation"]["ok"] is case["expectedImport"]["validationOk"]

    imported_job_id = imported["job"]["id"]
    for rel_path in case["expectedImport"]["previewFilesAnyOf"]:
        status, _headers, body = app.handle("GET", f"/api/jobs/{imported_job_id}/preview-files/{rel_path}")
        if status == 200:
            break
    else:
        raise AssertionError(f"none of the expected preview files were available: {case['expectedImport']['previewFilesAnyOf']}")

    status, _headers, body = app.handle("GET", f"/api/jobs/{imported_job_id}/review-tools")
    tools = _decode(body)
    assert status == 200
    assert tools["readiness"]["previewToolsReady"] is case["expectedImport"]["reviewToolsReady"]
