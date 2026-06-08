from __future__ import annotations

import io
import copy
import json
import sqlite3
import time
import zipfile
from pathlib import Path
from urllib.parse import quote

from motionjson.backend.assets import list_assets_for_job, register_generated_asset, register_upload
from motionjson.backend.rights import list_asset_lineage, list_asset_rights
from motionjson.backend.jobs import record_job_event
from motionjson.capabilities import gpu_model_recommendation, local_environment_profile
from motionjson.ui import server as ui_server
from motionjson.ui.server import LOCAL_UI_EMAIL
from motionjson.ui.server import LocalUIApp, _track_review_summary
from motionjson.validation import validate_document


def demo_video() -> Path:
    return Path(__file__).resolve().parents[1] / "examples" / "demo_red_ball.mp4"


def approved_creator_pack_rights() -> dict:
    return {
        "source_uri": "local://approved-library-layer.mp4",
        "display_text": "Approved local library layer",
        "license": "creator_pack_license",
        "license_name": "Creator Pack License",
        "license_scope": "commercial",
        "creator_approved": True,
        "creator_approval_status": "approved",
        "commercial_use": True,
        "commercial_use_status": "approved",
    }


def decode(body: bytes) -> dict:
    return json.loads(body.decode("utf-8"))


def multipart_body(fields: dict[str, str], files: dict[str, tuple[str, str, bytes]]) -> tuple[dict[str, str], bytes]:
    boundary = "----motionjson-test-boundary"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"),
                str(value).encode("utf-8"),
                b"\r\n",
            ]
        )
    for name, (filename, content_type, data) in files.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode("utf-8"),
                f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"),
                data,
                b"\r\n",
            ]
        )
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return {"content-type": f"multipart/form-data; boundary={boundary}"}, b"".join(chunks)


def wait_for_job(app: LocalUIApp, job_id: str, *, timeout: float = 10.0) -> dict:
    deadline = time.time() + timeout
    last_job = {}
    while time.time() < deadline:
        status, _headers, body = app.handle("GET", f"/api/jobs/{job_id}")
        assert status == 200
        last_job = decode(body)["job"]
        if last_job["status"] in {"succeeded", "failed", "canceled"}:
            return last_job
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish; last status: {last_job}")


def create_completed_mock_job(app: LocalUIApp, project_name: str = "Export Project") -> tuple[dict, dict, dict]:
    status, _headers, body = app.handle("POST", "/api/projects", body=json.dumps({"name": project_name}).encode("utf-8"))
    assert status == 200
    project = decode(body)["project"]
    status, _headers, body = app.handle(
        "POST",
        "/api/videos",
        body=json.dumps({"projectId": project["id"], "path": str(demo_video())}).encode("utf-8"),
    )
    assert status == 200
    video = decode(body)["video"]
    status, _headers, body = app.handle(
        "POST",
        "/api/jobs",
        body=json.dumps({"projectId": project["id"], "videoId": video["id"], "maskProvider": "mock", "maxFrames": 2, "run": True}).encode("utf-8"),
    )
    assert status == 200
    job = wait_for_job(app, decode(body)["job"]["id"])
    assert job["status"] == "succeeded"
    return project, video, job


def scene_asset_for_job(app: LocalUIApp, job: dict) -> dict:
    conn = app.connection()
    try:
        assets = list_assets_for_job(conn, project_id=job["project_id"], source_job_id=job["id"])
    finally:
        conn.close()
    return next(asset for asset in assets if asset["kind"] == "scene_graph")


def test_track_review_summary_classifies_static_fallback_and_mask_quality():
    moving = _track_review_summary(
        {
            "objectId": "ball",
            "label": "ball",
            "source": "track_summary",
            "providerName": "sam3_tracker_video",
            "exportStatus": "accepted",
            "frames": [
                {
                    "frame": 0,
                    "visible": True,
                    "bbox": {"x": 10, "y": 10, "w": 20, "h": 20},
                    "maskArea": 240,
                    "maskShape": [100, 100],
                    "contourPoints": 18,
                    "polygon": [[10, 10], [28, 12], [30, 28], [12, 30]],
                },
                {
                    "frame": 1,
                    "visible": True,
                    "bbox": {"x": 18, "y": 10, "w": 20, "h": 20},
                    "maskArea": 230,
                    "maskShape": [100, 100],
                    "contourPoints": 16,
                    "polygon": [[18, 10], [36, 12], [38, 28], [20, 30]],
                },
            ],
        }
    )
    static = _track_review_summary(
        {
            "objectId": "static_ball",
            "label": "static ball",
            "source": "track_summary",
            "providerName": "keyframe_seed_sequence",
            "exportStatus": "accepted",
            "metadata": {"discovery": {"trackingProvider": "keyframe_seed_sequence"}},
            "frames": [
                {"frame": 0, "visible": True, "bbox": {"x": 10, "y": 10, "w": 20, "h": 20}, "maskArea": 400},
                {"frame": 1, "visible": True, "bbox": {"x": 10, "y": 10, "w": 20, "h": 20}, "maskArea": 400},
            ],
        }
    )

    assert moving["trackClass"] == "moving_track"
    assert moving["exportEligibility"] == "eligible"
    assert moving["maskQuality"]["qualityStatus"] == "good"
    assert moving["maskQuality"]["trackingMotionPx"] > 0
    assert static["trackClass"] == "static_fallback"
    assert static["exportEligibility"] == "blocked"
    assert static["exportBlockReason"] == "static_keyframe_mask_sequence"
    assert static["exportIncluded"] is False
    assert static["maskQuality"]["qualityStatus"] == "needs_refinement"


def test_local_ui_api_health_capabilities_and_defaults_are_public(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)

    status, headers, body = app.handle("GET", "/api/health")
    health = decode(body)
    assert status == 200
    assert headers["cache-control"] == "no-store"
    assert health["format"] == "motionjson.local_ui.v0.1"
    assert health["status"] == "ok"
    assert health["localFirst"] is True
    assert health["mockModeAvailable"] is True
    assert health["mockMode"] is True
    assert health["deployment"]["format"] == "motionjson.deployment_readiness.v0.1"
    assert health["deployment"]["mode"] == "local_single_user"
    assert health["deployment"]["hostedReady"] is False
    assert health["deployment"]["components"]["modelRuns"]["kind"] == "persistent_sqlite"
    assert "/api/deployment-readiness" in health["routes"]
    assert "/api/capabilities" in health["routes"]
    assert "/api/progress" in health["routes"]
    assert "/api/artifacts" in health["routes"]
    assert "/api/videos/upload" in health["routes"]
    assert "/api/videos/{videoId}/content" in health["routes"]
    assert "/api/run-config/validate" in health["routes"]
    assert "/api/provider-settings/{providerId}/diagnose" in health["routes"]
    assert "/api/provider-settings/{providerId}/advanced-local-paths" in health["routes"]
    assert "/api/provider-settings/{providerId}/setup/start" in health["routes"]
    assert "/api/provider-settings/setup-jobs/{jobId}" in health["routes"]
    assert "/api/provider-settings/setup-jobs/{jobId}/cancel" in health["routes"]
    assert "/api/jobs/{jobId}/run" in health["routes"]
    assert "/api/jobs/{jobId}/review" in health["routes"]
    assert "/api/jobs/{jobId}/exports" in health["routes"]
    assert "/api/jobs/{jobId}/exports/motionjson" in health["routes"]
    assert "/api/jobs/{jobId}/cancel" in health["routes"]
    assert "/api/jobs/{jobId}/review-tools" in health["routes"]
    assert "/api/jobs/{jobId}/preview-files/{relPath}" in health["routes"]
    assert "/api/projects/{projectId}/imports/motionjson" in health["routes"]
    assert "/api/videos/{videoId}/prepare-browser-preview" in health["routes"]
    assert "/api/assets/{assetId}/content" in health["routes"]
    assert "/api/library/assets" in health["routes"]
    assert "/api/library/assets/{libraryAssetId}" in health["routes"]
    assert "/api/library/collections" in health["routes"]
    assert "/api/library/packs" in health["routes"]
    assert "/api/projects/{projectId}/library-assets" in health["routes"]

    status, _headers, body = app.handle("GET", "/api/capabilities")
    capabilities = decode(body)
    assert status == 200
    assert capabilities["schema"] == "motionjson.provider_diagnostics.v0.1"
    assert any(provider["name"] == "mock" and provider["noModelSafe"] for provider in capabilities["providers"])
    assert capabilities["summary"]["canRunNoModelSmoke"] is True
    assert "mock" in capabilities["summary"]["readyNoModelProviders"]
    assert "mock" in capabilities["summary"]["runnableProviders"]
    assert "mock" in capabilities["summary"]["localFreeRunnableProviders"]
    assert capabilities["environment"]["profile"]["format"] == "motionjson.local_environment_profile.v0.1"
    assert capabilities["environment"]["runtimeEnvironment"]["format"] == "motionjson.runtime_environment.v0.2"
    assert capabilities["environment"]["runtimeEnvironment"]["classification"] in {
        "cuda_ready",
        "cuda_hardware_runtime_missing",
        "mps_ready",
        "mps_hardware_runtime_missing",
        "xpu_ready",
        "xpu_hardware_runtime_missing",
        "rocm_ready",
        "rocm_hardware_runtime_missing",
        "cpu_only",
        "unknown",
    }
    assert capabilities["summary"]["gpuModelRecommendation"]["format"] == "motionjson.gpu_model_recommendation.v0.1"
    assert capabilities["summary"]["firstRun"]["recommendedCommand"] == "python3 -m motionjson.cli ui --no-open"

    status, _headers, body = app.handle(
        "GET",
        f"/api/capabilities?video={quote(str(demo_video()))}&outputDir={quote(str(tmp_path / 'exports'))}",
    )
    probed = decode(body)
    assert status == 200
    assert probed["environment"]["videoIO"]["checkedVideo"] is True
    assert probed["environment"]["output"]["checked"] is True
    if probed["environment"]["videoIO"]["opencvAvailable"]:
        assert probed["environment"]["videoIO"]["readable"] is True

    assert probed["environment"]["output"]["writable"] is True
    assert str(tmp_path) not in json.dumps(probed)

    status, _headers, body = app.handle("GET", "/api/run-config/defaults")
    defaults = decode(body)
    assert status == 200
    assert defaults["format"] == "motionjson.local_ui_run_config_defaults.v0.1"
    assert "mock" in defaults["maskProviders"]
    assert {
        "manual_prompt",
        "auto_object_proposals",
        "sam_auto_masks",
        "text_detector",
        "class_detector",
        "motion_foreground",
        "external_masks",
    } <= set(defaults["discoveryProviders"])
    schemas = {schema["mode"]: schema for schema in defaults["discoveryProviderSchemas"]}
    assert set(defaults["discoveryProviders"]) == set(schemas)
    for schema in schemas.values():
        assert schema["description"]
        assert schema["whenToUse"]
        assert "configSchema" in schema
        assert "noModelSafe" in schema
        assert "mockAvailable" in schema
    assert defaults["defaults"]["maskProvider"] == "mock"

    status, _headers, body = app.handle("GET", "/api/exports/formats")
    exports = decode(body)
    assert status == 200
    assert {entry["id"] for entry in exports["exports"]} >= {"motionjson", "mp4", "website-zip", "remotion-plan"}
    assert {entry["id"] for entry in exports["presets"]} >= {"compact", "debug", "vector-heavy", "raster-fallback"}


def test_local_ui_deployment_readiness_and_hosted_mode_fail_closed(tmp_path):
    app = LocalUIApp(
        db_path=tmp_path / "backend.sqlite",
        storage_root=tmp_path / "storage",
        deployment_mode="hosted_multi_tenant",
    )

    status, _headers, body = app.handle("GET", "/api/health")
    health = decode(body)
    assert status == 200
    assert health["localFirst"] is False
    assert health["deployment"]["mode"] == "hosted_multi_tenant"
    assert health["deployment"]["hostedReady"] is False

    status, _headers, body = app.handle("GET", "/api/deployment-readiness")
    readiness = decode(body)
    blocker_codes = {blocker["code"] for blocker in readiness["blockers"]}
    assert status == 200
    assert readiness["mode"] == "hosted_multi_tenant"
    assert readiness["hostedReady"] is False
    assert "hosted_auth_not_configured" in blocker_codes
    assert "object_storage_not_configured" in blocker_codes

    for method, path, payload in [
        ("GET", "/api/workspace", None),
        ("GET", "/api/capabilities", None),
        ("GET", "/api/provider-settings", None),
        ("POST", "/api/model-runs", {"request": {"goal": "Cut out one object"}}),
        ("GET", "/api/videos/not-real/content", None),
    ]:
        body_bytes = json.dumps(payload).encode("utf-8") if payload is not None else b""
        status, _headers, raw = app.handle(method, path, body=body_bytes)
        assert status == 401
        assert "configured auth provider" in decode(raw)["error"]


def test_local_ui_direct_video_upload_creates_project_and_video(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    headers, body = multipart_body(
        {"projectName": "Uploaded Clip Project"},
        {"video": ("uploaded demo.mp4", "video/mp4", demo_video().read_bytes())},
    )

    status, _headers, response_body = app.handle("POST", "/api/videos/upload", headers=headers, body=body)
    payload = decode(response_body)

    assert status == 200
    assert payload["project"]["name"] == "Uploaded Clip Project"
    assert payload["video"]["project_id"] == payload["project"]["id"]
    assert payload["video"]["metadata"]["filename"] == "uploaded_demo.mp4"
    assert payload["video"]["contentUrl"].startswith("/api/videos/")
    assert payload["video"]["metadata"]["rights_context"]["source_uri"] == "upload://uploaded_demo.mp4"
    assert str(tmp_path) not in json.dumps(payload)

    status, _headers, videos_body = app.handle("GET", f"/api/videos?projectId={payload['project']['id']}")
    videos = decode(videos_body)["videos"]
    assert status == 200
    assert [video["id"] for video in videos] == [payload["video"]["id"]]


def test_local_ui_direct_video_upload_requires_real_multipart_file(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    headers, body = multipart_body({"projectName": "Missing File"}, {})

    status, _headers, response_body = app.handle("POST", "/api/videos/upload", headers=headers, body=body)

    assert status == 400
    assert "video file is required" in decode(response_body)["error"]


def test_capability_environment_profile_recommends_sam3_for_cuda_gpu():
    profile = local_environment_profile(
        {
            "torchInstalled": True,
            "torchVersion": "2.test",
            "available": True,
            "device": "cuda",
            "reasons": [],
            "devices": [{"name": "cuda", "available": True}],
        }
    )
    recommendation = gpu_model_recommendation(
        [
            {
                "name": "sam3-auto-masks",
                "status": "missing_dependency",
                "runnable": False,
                "reasons": ["SAM3 Tracker classes are missing."],
            },
            {
                "name": "motion_foreground",
                "status": "ready",
                "runnable": True,
                "reasons": [],
            },
        ],
        profile,
    )

    assert profile["accelerator"] == "cuda"
    assert "CUDA GPU" in profile["label"]
    assert recommendation["recommendedProviderId"] == "sam3_tracker_scene_sweep"
    assert recommendation["model"] == "facebook/sam3"
    assert "Cache facebook/sam3" in " ".join(recommendation["nextActions"])


def test_capability_environment_profile_guides_cpu_and_mps_fallbacks():
    cpu_profile = local_environment_profile(
        {
            "torchInstalled": True,
            "torchVersion": "2.test",
            "available": False,
            "device": "cpu",
            "reasons": ["torch.cuda.is_available() returned false."],
            "devices": [{"name": "cpu", "available": True}, {"name": "cuda", "available": False}],
        }
    )
    cpu_recommendation = gpu_model_recommendation(
        [
            {
                "name": "motion_foreground",
                "status": "ready",
                "runnable": True,
                "reasons": [],
            }
        ],
        cpu_profile,
    )

    assert cpu_profile["accelerator"] == "cpu"
    assert cpu_recommendation["recommendedProviderId"] == "no_model_cpu_workflow"
    assert cpu_recommendation["runnable"] is True
    assert "No-model CPU" in cpu_recommendation["label"]

    mps_profile = local_environment_profile(
        {
            "torchInstalled": True,
            "torchVersion": "2.test",
            "available": False,
            "device": "cpu",
            "reasons": ["torch.cuda.is_available() returned false."],
            "devices": [{"name": "mps", "available": True}],
        }
    )
    mps_recommendation = gpu_model_recommendation(
        [
            {
                "name": "sam2-hf-auto-masks",
                "status": "missing_dependency",
                "runnable": False,
                "reasons": ["SAM2 HF runtime is missing."],
            }
        ],
        mps_profile,
    )

    assert mps_profile["accelerator"] == "mps"
    assert mps_recommendation["recommendedProviderId"] == "sam2-hf-auto-masks"
    assert mps_recommendation["status"] == "missing_dependency"
    assert mps_recommendation["missing"] == ["SAM2 HF runtime is missing."]


def test_local_ui_capabilities_redacts_windows_probe_paths(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)

    for route, leaked in [
        ("/api/capabilities?video=C%3A%5CUsers%5CAlice%5Csecret.mp4&outputDir=%5C%5Cserver%5Cshare%5Cmotionjson", ["C:\\Users\\Alice", "\\\\server\\share"]),
        ("/api/capabilities?video=C%3A%2FUsers%2FAlice%2Fsecret.mp4&outputDir=C%3A%2FUsers%2FAlice%2Fout", ["C:/Users/Alice"]),
    ]:
        status, _headers, body = app.handle("GET", route)
        payload = decode(body)
        encoded = json.dumps(payload)

        assert status == 200
        assert "[LOCAL_PATH_REDACTED]" in encoded
        for value in leaked:
            assert value not in encoded


def test_local_ui_asset_library_routes_save_collections_and_creator_packs(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    status, _headers, body = app.handle("POST", "/api/projects", body=json.dumps({"name": "Library UI Project"}).encode("utf-8"))
    assert status == 200
    project = decode(body)["project"]
    approved_path = tmp_path / "approved-layer.mp4"
    approved_path.write_bytes(b"approved layer bytes")
    conn = app.connection()
    try:
        user = app._local_user(conn)
        asset = register_upload(
            conn,
            storage=app.storage(),
            user_id=user["id"],
            project_id=project["id"],
            path=approved_path,
            kind="source_video",
            metadata={"rights_context": approved_creator_pack_rights()},
        )
    finally:
        conn.close()

    status, _headers, body = app.handle(
        "POST",
        f"/api/projects/{project['id']}/library-assets",
        body=json.dumps({"assetId": asset["id"], "type": "motion_sticker", "title": "Approved Layer", "tags": ["Hero"]}).encode("utf-8"),
    )
    assert status == 200
    library_asset = decode(body)["libraryAsset"]
    assert library_asset["type"] == "motion_sticker"
    assert library_asset["creatorApproved"] is True
    assert library_asset["commercialUseStatus"] == "approved"
    assert "storage_key" not in body.decode("utf-8")
    assert "approved layer bytes" not in body.decode("utf-8")

    status, _headers, body = app.handle("GET", f"/api/library/assets/{library_asset['id']}")
    assert status == 200
    assert decode(body)["libraryAsset"]["id"] == library_asset["id"]

    status, _headers, body = app.handle("GET", "/api/library/assets?creatorApproved=true&tag=hero")
    listed = decode(body)
    assert status == 200
    assert listed["assets"][0]["id"] == library_asset["id"]
    assert listed["aiUsage"] == "none"

    status, _headers, body = app.handle(
        "POST",
        "/api/library/collections",
        body=json.dumps({"projectId": project["id"], "title": "Approved Brand"}).encode("utf-8"),
    )
    assert status == 200
    collection = decode(body)["collection"]
    status, _headers, body = app.handle(
        "POST",
        f"/api/library/collections/{collection['id']}/assets",
        body=json.dumps({"libraryAssetId": library_asset["id"]}).encode("utf-8"),
    )
    assert status == 200
    assert decode(body)["collectionAsset"]["aiUsage"] == "none"

    status, _headers, body = app.handle("GET", f"/api/library/collections/{collection['id']}/assets")
    assert status == 200
    assert decode(body)["assets"][0]["id"] == library_asset["id"]

    status, _headers, body = app.handle(
        "POST",
        "/api/library/packs",
        body=json.dumps({"collectionId": collection["id"], "title": "Approved Pack"}).encode("utf-8"),
    )
    assert status == 200
    pack = decode(body)["pack"]
    assert pack["assetCount"] == 1
    status, _headers, body = app.handle("GET", f"/api/library/assets?packId={pack['id']}")
    assert status == 200
    assert decode(body)["assets"][0]["id"] == library_asset["id"]


def test_local_ui_asset_library_pack_rejects_unapproved_layers(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    status, _headers, body = app.handle("POST", "/api/projects", body=json.dumps({"name": "Unapproved Library"}).encode("utf-8"))
    project = decode(body)["project"]
    status, _headers, body = app.handle(
        "POST",
        "/api/videos",
        body=json.dumps({"projectId": project["id"], "path": str(demo_video())}).encode("utf-8"),
    )
    source = decode(body)["video"]
    status, _headers, body = app.handle(
        "POST",
        f"/api/projects/{project['id']}/library-assets",
        body=json.dumps({"assetId": source["id"], "type": "motion_sticker", "title": "Needs Review"}).encode("utf-8"),
    )
    library_asset = decode(body)["libraryAsset"]
    status, _headers, body = app.handle(
        "POST",
        "/api/library/collections",
        body=json.dumps({"projectId": project["id"], "title": "Review Collection"}).encode("utf-8"),
    )
    collection = decode(body)["collection"]
    status, _headers, body = app.handle(
        "POST",
        f"/api/library/collections/{collection['id']}/assets",
        body=json.dumps({"libraryAssetId": library_asset["id"]}).encode("utf-8"),
    )
    assert status == 200

    status, _headers, body = app.handle(
        "POST",
        "/api/library/packs",
        body=json.dumps({"collectionId": collection["id"], "title": "Blocked Pack"}).encode("utf-8"),
    )

    assert status == 400
    assert "creator-approved packs require approved creator and commercial-use asset rights" in decode(body)["error"]
    assert "storage_key" not in body.decode("utf-8")


def test_local_ui_capabilities_preserve_provider_failure_details(tmp_path, monkeypatch):
    def fake_capability_report(**_kwargs):
        return {
            "schema": "motionjson.provider_diagnostics.v0.1",
            "summary": {
                "providersReady": 1,
                "providersTotal": 3,
                "readyNoModelProviders": ["motion_foreground"],
                "canRunNoModelSmoke": False,
                "missingOptional": ["text_detector", "sam_auto_masks"],
                "firstRun": {
                    "ready": False,
                    "recommendedCommand": "python3 -m motionjson.cli ui --no-open",
                    "nonBlockingOptionalMissing": ["text_detector", "sam_auto_masks"],
                },
            },
            "environment": {},
            "providers": [
                {
                    "name": "motion_foreground",
                    "kind": "discovery_provider",
                    "available": True,
                    "status": "ready",
                    "reasons": [],
                    "mockAvailable": True,
                    "noModelSafe": True,
                    "metadata": {"uiDescription": "CPU moving-region proposals."},
                },
                {
                    "name": "text_detector",
                    "kind": "discovery_provider",
                    "available": False,
                    "status": "missing_dependency",
                    "reasons": ["Open-vocabulary detector package is not importable."],
                    "installHint": "Install/configure an open-vocabulary detector, or use discovery mock mode.",
                    "mockAvailable": True,
                    "noModelSafe": False,
                    "metadata": {"uiDescription": "Text prompts become detector candidates before segmentation/tracking."},
                },
                {
                    "name": "sam_auto_masks",
                    "kind": "discovery_provider",
                    "available": False,
                    "status": "not_configured",
                    "reasons": ["SAM automatic-mask discovery is scaffolded."],
                    "mockAvailable": True,
                    "noModelSafe": False,
                    "metadata": {"uiDescription": "Automatic visible-segment proposals."},
                },
            ],
        }

    monkeypatch.setattr(ui_server, "build_capability_report", fake_capability_report)
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)

    status, _headers, body = app.handle("GET", "/api/capabilities")
    capabilities = decode(body)

    assert status == 200
    providers = {provider["name"]: provider for provider in capabilities["providers"]}
    assert providers["text_detector"]["status"] == "missing_dependency"
    assert providers["text_detector"]["reasons"]
    assert providers["text_detector"]["mockAvailable"] is True
    assert providers["text_detector"]["noModelSafe"] is False
    assert providers["text_detector"]["metadata"]["uiDescription"]
    assert capabilities["summary"]["firstRun"]["recommendedCommand"] == "python3 -m motionjson.cli ui --no-open"


def test_local_ui_validation_warns_when_configured_provider_is_not_runnable(tmp_path, monkeypatch):
    def fake_capability_report(**_kwargs):
        return {
            "schema": "motionjson.provider_diagnostics.v0.1",
            "summary": {"providersReady": 1, "providersTotal": 1},
            "environment": {},
            "providers": [
                {
                    "name": "sam2-hosted",
                    "kind": "mask_provider",
                    "available": True,
                    "configured": True,
                    "runnable": False,
                    "status": "ready",
                    "reasons": ["Hosted segmentation requires explicit network opt-in."],
                    "installHint": "Enable hosted network use explicitly.",
                    "mockAvailable": True,
                    "noModelSafe": False,
                    "networkRequired": True,
                    "needsCredentials": True,
                    "estimatedCost": {"amount": None, "unit": "provider_request", "status": "unknown_provider_cost"},
                    "metadata": {},
                }
            ],
        }

    monkeypatch.setattr(ui_server, "build_capability_report", fake_capability_report)
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)

    status, _headers, body = app.handle(
        "POST",
        "/api/run-config/validate",
        body=json.dumps(
            {
                "schema": "motionjson.extraction_run_config.v0.1",
                "input": {"path": "local-ui://assets/asset_1"},
                "output": {"directory": str(tmp_path / "out")},
                "sampling": {"sample_fps": 12, "max_frames": 2},
                "provider": {"name": "sam2-hosted"},
                "prompts": [{"kind": "point", "frame_index": 0, "object_id": "object_0", "label": "Object", "data": {"x": 1, "y": 1}}],
            }
        ).encode("utf-8"),
    )
    payload = decode(body)

    assert status == 200
    warning = next(item for item in payload["warnings"] if item["code"] == "runtime_proof_settings_not_ready")
    assert warning["status"] == "settings_not_ready"
    assert warning["provider"] == "sam2-hosted"
    assert warning["runtimeProof"]["format"] == "motionjson.runtime_proof.v0.1"
    assert warning["runtimeProof"]["allowsRun"] is False


def test_local_ui_validation_uses_sam3_auto_masks_for_scene_sweep_warnings(tmp_path, monkeypatch):
    def validate_with_report(report: dict) -> dict:
        monkeypatch.setattr(ui_server, "build_capability_report", lambda **_kwargs: report)
        app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
        status, _headers, body = app.handle(
            "POST",
            "/api/run-config/validate",
            body=json.dumps(
                {
                    "schema": "motionjson.extraction_run_config.v0.1",
                    "input": {"path": "local-ui://assets/asset_1"},
                    "output": {"directory": str(tmp_path / "out")},
                    "sampling": {"sample_fps": 12, "max_frames": 2},
                    "provider": {"name": "sam3-local"},
                    "discovery": {
                        "mode": "sam3_auto_masks",
                        "config": {
                            "sceneSweep": True,
                            "providerPreference": "sam3-local",
                            "sam3TrackerModel": "facebook/sam3",
                        },
                    },
                    "prompts": [],
                }
            ).encode("utf-8"),
        )
        assert status == 200
        return decode(body)

    official_adapter_unavailable = {
        "schema": "motionjson.provider_diagnostics.v0.1",
        "summary": {"providersReady": 1, "providersTotal": 2},
        "environment": {},
        "providers": [
            {
                "name": "sam3-local",
                "kind": "discovery_provider",
                "available": False,
                "runnable": False,
                "status": "missing_dependency",
                "reasons": ["Python module 'sam3' is not importable. SAM3 local adapter requires SAM3_LOCAL_MODEL."],
                "installHint": "Install official SAM3 only for advanced concept/exemplar workflows.",
            },
            {
                "name": "sam3-auto-masks",
                "kind": "discovery_provider",
                "available": True,
                "runnable": True,
                "status": "ready",
                "reasons": [],
                "installHint": "Install the sam3-transformers extra.",
            },
        ],
    }

    payload = validate_with_report(official_adapter_unavailable)
    assert payload["valid"] is True
    assert "SAM3_LOCAL_MODEL" not in json.dumps(payload["warnings"])
    assert "sam3-local" not in {warning.get("provider") for warning in payload["warnings"]}

    scene_sweep_unavailable = copy.deepcopy(official_adapter_unavailable)
    scene_sweep_unavailable["providers"][1].update(
        {
            "available": False,
            "runnable": False,
            "status": "missing_dependency",
            "reasons": ["Transformers does not expose Sam3TrackerModel/Sam3TrackerProcessor."],
        }
    )
    payload = validate_with_report(scene_sweep_unavailable)
    warnings = [warning for warning in payload["warnings"] if warning["code"] == "sam3_scene_sweep_missing_tracker_classes"]

    assert [warning["provider"] for warning in warnings] == ["sam3_tracker_scene_sweep"]
    assert warnings[0]["capabilityProvider"] == "sam3-auto-masks"
    assert "SAM3_LOCAL_MODEL" not in json.dumps(warnings)
    assert "Transformers does not expose" in json.dumps(warnings)


def test_local_ui_validation_blocks_unconfigured_local_sam3_concept(tmp_path, monkeypatch):
    monkeypatch.setattr(
        ui_server,
        "build_capability_report",
        lambda **_kwargs: {
            "schema": "motionjson.provider_diagnostics.v0.1",
            "summary": {"providersReady": 1, "providersTotal": 3},
            "environment": {},
            "providers": [
                {
                    "name": "sam3-local",
                    "kind": "discovery_provider",
                    "available": False,
                    "runnable": False,
                    "status": "missing_dependency",
                    "reasons": ["Python module 'sam3' is not importable."],
                    "installHint": "Install official SAM3 only for advanced concept/exemplar workflows.",
                },
                {
                    "name": "sam3-concept",
                    "kind": "discovery_provider",
                    "available": False,
                    "runnable": False,
                    "status": "missing_dependency",
                    "reasons": ["SAM3 local concept adapter requires the official SAM3 package and a local sam3.pt checkpoint."],
                    "installHint": "Use hosted SAM3 concept or configure the advanced local adapter.",
                },
                {
                    "name": "sam3-auto-masks",
                    "kind": "discovery_provider",
                    "available": True,
                    "runnable": True,
                    "status": "ready",
                    "reasons": [],
                    "installHint": "Install the sam3-transformers extra.",
                },
            ],
        },
    )
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)

    status, _headers, body = app.handle(
        "POST",
        "/api/run-config/validate",
        body=json.dumps(
            {
                "schema": "motionjson.extraction_run_config.v0.1",
                "input": {"path": "local-ui://assets/asset_1"},
                "output": {"directory": str(tmp_path / "out")},
                "sampling": {"sample_fps": 12, "max_frames": 2},
                "provider": {"name": "sam3-local"},
                "discovery": {
                    "mode": "sam3_concept",
                    "config": {
                        "concept": "red ball",
                        "text": "red ball",
                        "providerPreference": "sam3-local",
                        "hosted": False,
                    },
                },
                "prompts": [],
            }
        ).encode("utf-8"),
    )
    payload = decode(body)

    assert status == 200
    assert payload["valid"] is False
    error = next(item for item in payload["errors"] if item["code"] == "sam3_advanced_local_missing_checkpoint")
    assert error["legacyCode"] == "sam3_local_concept_unavailable"
    assert error["provider"] == "advanced_local_sam3_concept_exemplar"
    assert error["discoveryProvider"] == "sam3-concept"
    assert "Scene Sweep can propose visible objects" in error["message"]
    assert "hosted SAM3 concept" in error["action"]
    warnings = [warning for warning in payload["warnings"] if warning["code"] == "provider_unavailable"]
    assert {warning["provider"] for warning in warnings} >= {"sam3-local", "sam3-concept"}


def test_local_ui_serves_static_shell(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage")

    status, headers, body = app.handle("GET", "/")

    assert status == 200
    assert headers["content-type"].startswith("text/html")
    assert headers["cache-control"] == "no-store"
    assert b"skip-link" in body
    assert b"MotionJSON" in body
    assert b"/ui/app.js" in body

    status, headers, body = app.handle("GET", "/ui/modules/workflow.js")

    assert status == 200
    assert headers["content-type"].startswith("text/javascript")
    assert b"export const WORKFLOW_STEPS" in body


def test_local_ui_api_creates_project_and_registers_local_video(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage")

    status, _headers, body = app.handle("POST", "/api/projects", body=json.dumps({"name": "UI Project"}).encode("utf-8"))
    assert status == 200
    project = decode(body)["project"]
    assert project["name"] == "UI Project"

    status, _headers, body = app.handle("GET", "/api/projects")
    assert decode(body)["projects"][0]["id"] == project["id"]

    status, _headers, body = app.handle(
        "POST",
        "/api/videos",
        body=json.dumps({"projectId": project["id"], "path": str(demo_video())}).encode("utf-8"),
    )
    video = decode(body)["video"]
    assert status == 200
    assert video["kind"] == "source_video"
    assert video["contentUrl"] == f"/api/videos/{video['id']}/content"
    assert video["browserPreview"]["status"] in {"ready", "failed"}
    assert video["browserPreview"]["contentUrl"].startswith("/api/")
    assert "storage_key" not in video
    assert "uri" not in video
    assert video["metadata"]["filename"] == "demo_red_ball.mp4"
    assert str(demo_video()) not in body.decode("utf-8")
    assert "file://" not in body.decode("utf-8")

    status, _headers, body = app.handle("GET", f"/api/videos?projectId={project['id']}")
    videos = decode(body)["videos"]
    assert status == 200
    assert videos[0]["id"] == video["id"]
    assert videos[0]["contentUrl"] == video["contentUrl"]
    assert videos[0]["browserPreview"]["status"] in {"ready", "failed"}
    assert videos[0]["metadata"]["filename"] == "demo_red_ball.mp4"
    assert "uri" not in videos[0]
    assert str(demo_video()) not in body.decode("utf-8")

    status, _headers, body = app.handle("GET", f"/api/jobs?projectId={project['id']}")
    assert status == 200
    assert decode(body)["jobs"] == []

    status, _headers, body = app.handle("GET", f"/api/progress?projectId={project['id']}")
    assert status == 200
    assert decode(body)["progress"] == []


def test_local_ui_workspace_preferences_and_recent_work_are_public(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage")

    status, _headers, body = app.handle("POST", "/api/projects", body=json.dumps({"name": "Workspace Project"}).encode("utf-8"))
    assert status == 200
    project = decode(body)["project"]
    status, _headers, body = app.handle(
        "POST",
        "/api/videos",
        body=json.dumps({"projectId": project["id"], "path": str(demo_video())}).encode("utf-8"),
    )
    assert status == 200

    status, _headers, body = app.handle("GET", "/api/workspace")
    workspace = decode(body)
    assert status == 200
    assert workspace["format"] == "motionjson.local_ui_workspace.v0.1"
    assert workspace["projects"][0]["id"] == project["id"]
    assert workspace["recentVideos"][0]["filename"] == "demo_red_ball.mp4"
    assert workspace["preferences"]["preferences"]["defaultGoal"] == "trace_one_object"
    assert workspace["preferences"]["preferences"]["defaultExportPreset"] == "compact"
    assert workspace["providerSettingsSummary"]["mockNoModelDefault"] is True
    assert {preset["id"] for preset in workspace["exportPresets"]} >= {"compact", "debug"}
    assert workspace["deployment"]["mode"] == "local_single_user"
    assert workspace["deployment"]["hostedReady"] is False
    assert workspace["deployment"]["components"]["modelRuns"]["kind"] == "persistent_sqlite"
    assert str(demo_video()) not in body.decode("utf-8")
    assert "storage_key" not in body.decode("utf-8")

    status, _headers, body = app.handle(
        "POST",
        "/api/preferences",
        body=json.dumps(
            {
                "preferences": {
                    "defaultGoal": "motion_foreground",
                    "defaultMaskProvider": "motion",
                    "defaultExportPreset": "debug",
                    "lastProjectId": project["id"],
                }
            }
        ).encode("utf-8"),
    )
    preferences = decode(body)
    assert status == 200
    assert preferences["format"] == "motionjson.local_ui_preferences.v0.1"
    assert preferences["preferences"]["defaultGoal"] == "motion_foreground"
    assert preferences["preferences"]["defaultMaskProvider"] == "motion"
    assert preferences["preferences"]["defaultExportPreset"] == "debug"
    assert preferences["preferences"]["lastProjectId"] == project["id"]

    status, _headers, body = app.handle("GET", "/api/preferences")
    assert status == 200
    assert decode(body)["preferences"]["defaultGoal"] == "motion_foreground"


def test_local_ui_commercial_readiness_surface_is_local_and_audit_friendly(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage")

    status, _headers, body = app.handle("POST", "/api/projects", body=json.dumps({"name": "Readiness Project"}).encode("utf-8"))
    assert status == 200
    project = decode(body)["project"]
    status, _headers, body = app.handle(
        "POST",
        "/api/videos",
        body=json.dumps({"projectId": project["id"], "path": str(demo_video())}).encode("utf-8"),
    )
    assert status == 200

    status, _headers, body = app.handle("GET", "/api/commercial-readiness")
    readiness = decode(body)
    text = body.decode("utf-8")
    assert status == 200
    assert readiness["format"] == "motionjson.local_ui_commercial_readiness.v0.1"
    assert readiness["accountBoundary"]["mode"] == "local_single_user"
    assert readiness["accountBoundary"]["deploymentMode"] == "local_single_user"
    assert readiness["accountBoundary"]["hostedReady"] is False
    assert readiness["accountBoundary"]["teamMode"] == "placeholder_not_enabled"
    assert readiness["accountBoundary"]["billing"] == "not_implemented"
    assert readiness["deployment"]["components"]["auth"]["kind"] == "local_single_user_adapter"
    assert readiness["usageCost"]["costDashboard"]["schema"] == "motionjson.backend_cost_dashboard.v0.1"
    assert isinstance(readiness["providerRunHistory"], list)
    assert isinstance(readiness["exportHistory"], list)
    assert any("Hosted providers require explicit opt-in" in notice for notice in readiness["privacyNotices"])
    assert any("Commercial-use status" in reminder for reminder in readiness["rightsReminders"])
    assert str(demo_video()) not in text
    assert "storage_key" not in text


def test_local_ui_video_content_endpoint_serves_bytes_without_storage_paths(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage")
    status, _headers, body = app.handle(
        "POST",
        "/api/projects",
        body=json.dumps({"name": "UI Project"}).encode("utf-8"),
    )
    project = decode(body)["project"]
    status, _headers, body = app.handle(
        "POST",
        "/api/videos",
        body=json.dumps({"projectId": project["id"], "path": str(demo_video())}).encode("utf-8"),
    )
    video = decode(body)["video"]
    original = demo_video().read_bytes()

    assert status == 200
    assert "file://" not in video["contentUrl"]
    assert "projects/" not in video["contentUrl"]
    assert video["browserPreview"]["contentUrl"].startswith("/api/")

    status, headers, body = app.handle("GET", video["contentUrl"])
    assert status == 200
    assert headers["content-type"] == "video/mp4"
    assert headers["accept-ranges"] == "bytes"
    assert "file://" not in json.dumps(headers)
    assert "projects/" not in json.dumps(headers)
    assert body == original

    status, headers, body = app.handle("HEAD", video["contentUrl"])
    assert status == 200
    assert headers["content-length"] == str(len(original))
    assert body == b""

    status, headers, body = app.handle("GET", video["contentUrl"], headers={"Range": "bytes=0-7"})
    assert status == 206
    assert headers["content-range"] == f"bytes 0-7/{len(original)}"
    assert body == original[:8]

    status, headers, body = app.handle("HEAD", video["contentUrl"], headers={"Range": "bytes=0-7"})
    assert status == 206
    assert headers["content-range"] == f"bytes 0-7/{len(original)}"
    assert headers["content-length"] == "8"
    assert body == b""

    status, headers, body = app.handle(
        "GET",
        video["contentUrl"],
        headers={"Range": f"bytes={len(original)}-"},
    )
    assert status == 416
    assert headers["content-range"] == f"bytes */{len(original)}"
    assert body == b""

    poster_url = video["browserPreview"].get("posterUrl") or ""
    if poster_url:
        status, headers, poster_body = app.handle("GET", poster_url)
        assert status == 200
        assert headers["content-type"].startswith("image/")
        assert poster_body


def test_local_ui_preview_file_route_serves_review_tools_and_blocks_unsafe_paths(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    _project, _video, job = create_completed_mock_job(app, "Preview Tool Route Project")

    status, _headers, body = app.handle("GET", f"/api/jobs/{job['id']}/review-tools")
    tools_payload = decode(body)
    assert status == 200
    assert tools_payload["jobId"] == job["id"]
    assert tools_payload["readiness"]["readyForReview"] is True
    canvas = next(tool for tool in tools_payload["tools"] if tool["toolId"] == "canvas_player")
    assert canvas["status"] == "ready"
    assert canvas["missingArtifacts"] == []
    assert f"/api/jobs/{job['id']}/preview-files/scene_graph.json" in canvas["url"]
    assert f"/api/jobs/{job['id']}/preview-files/web_asset_manifest.json" in canvas["url"]
    assert f"jobId={job['id']}" in canvas["url"]
    assert "/out/demo" not in canvas["url"]

    status, headers, body = app.handle("GET", f"/api/jobs/{job['id']}/preview-files/preview/canvas_player.html")
    assert status == 200
    assert headers["content-type"].startswith("text/html")
    assert b"canvas" in body.lower()

    status, headers, body = app.handle("GET", f"/api/jobs/{job['id']}/preview-files/scene_graph.json")
    scene = decode(body)
    assert status == 200
    assert headers["content-type"].startswith("application/json")
    assert scene["schema"] == "motionjson.scene_graph.v0.1"
    assert "projects/" not in body.decode("utf-8")
    assert str(tmp_path) not in body.decode("utf-8")

    object_id = scene["objects"][0]["id"]
    status, headers, body = app.handle("HEAD", f"/api/jobs/{job['id']}/preview-files/objects/{object_id}/spritesheet.webp")
    assert status == 200
    assert headers["content-type"] == "image/webp"
    assert body == b""

    blocked_paths = [
        "../scene_graph.json",
        "%2FUsers%2Fedwin%2Fsecret.json",
        "provider_diagnostics.json",
        "run_config.json",
        "logs/job.log",
        "masks/object_0/mask_000000.png",
    ]
    for rel_path in blocked_paths:
        status, _headers, body = app.handle("GET", f"/api/jobs/{job['id']}/preview-files/{rel_path}")
        assert status == 404, rel_path
        assert "[LOCAL_PATH_REDACTED]" in body.decode("utf-8") or "not found" in body.decode("utf-8")


def test_local_ui_preview_file_route_serves_imported_result_directories(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    project, _video, job = create_completed_mock_job(app, "Imported Preview Tool Project")
    import_dir = tmp_path / "importable_result"
    conn = app.connection()
    try:
        assets = list_assets_for_job(conn, project_id=job["project_id"], source_job_id=job["id"])
    finally:
        conn.close()
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
        f"/api/projects/{project['id']}/imports/motionjson",
        body=json.dumps({"path": str(import_dir)}).encode("utf-8"),
    )
    imported = decode(body)["import"]
    assert status == 200
    assert imported["validation"]["ok"] is True

    imported_job_id = imported["job"]["id"]
    status, headers, body = app.handle("GET", f"/api/jobs/{imported_job_id}/preview-files/preview/timeline_editor.html")
    assert status == 200
    assert headers["content-type"].startswith("text/html")
    assert b"timeline" in body.lower()

    status, headers, body = app.handle("GET", f"/api/jobs/{imported_job_id}/preview-files/web_asset_manifest.json")
    assert status == 200
    assert headers["content-type"].startswith("application/json")
    assert "projects/" not in body.decode("utf-8")


def test_local_ui_run_config_validation_uses_existing_config_code_and_warns(tmp_path, monkeypatch):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage")
    monkeypatch.setattr(
        ui_server,
        "build_capability_report",
        lambda: {
            "providers": [
                {
                    "name": "sam2-local",
                    "kind": "mask_provider",
                    "available": False,
                    "status": "missing_dependency",
                    "reasons": ["sam2 package is not importable"],
                    "installHint": "Install SAM2 separately.",
                },
                {"name": "manual_prompt", "kind": "discovery_provider", "available": True, "status": "ready"},
            ]
        },
    )
    run_config = {
        "schema": "motionjson.extraction_run_config.v0.1",
        "input": {"path": "motionjson://assets/source-video"},
        "output": {"directory": "out/ui-preview"},
        "provider": {"name": "sam2-local"},
        "discovery": {"mode": "manual_prompt"},
        "prompts": [
            {
                "kind": "positive_point",
                "frame_index": 3,
                "object_id": "object_0",
                "label": "Ball",
                "data": {"x": 12, "y": 8},
            }
        ],
    }

    status, _headers, body = app.handle(
        "POST",
        "/api/run-config/validate",
        body=json.dumps({"runConfig": run_config}).encode("utf-8"),
    )
    payload = decode(body)

    assert status == 200
    assert payload["format"] == "motionjson.local_ui_run_config_validation.v0.1"
    assert payload["valid"] is True
    assert payload["errors"] == []
    assert payload["runConfig"]["prompts"][0]["data"] == {"x": 12, "y": 8}
    assert {warning["code"] for warning in payload["warnings"]} >= {
        "provider_unavailable",
    }
    by_code = {warning["code"]: warning for warning in payload["warnings"]}
    assert by_code["provider_unavailable"]["severity"] == "error"
    assert by_code["provider_unavailable"]["action"] == "Install SAM2 separately."

    invalid = {**run_config, "prompts": []}
    status, _headers, body = app.handle(
        "POST",
        "/api/run-config/validate",
        body=json.dumps(invalid).encode("utf-8"),
    )
    payload = decode(body)

    assert status == 200
    assert payload["valid"] is False
    assert "requires a point or box prompt" in payload["errors"][0]["message"]


def test_local_ui_run_config_validation_and_enqueue_gate_runtime_proof(tmp_path, monkeypatch):
    monkeypatch.setattr(
        ui_server,
        "build_capability_report",
        lambda **_kwargs: {
            "schema": "motionjson.provider_diagnostics.v0.1",
            "summary": {"providersReady": 0, "providersTotal": 1},
            "environment": {},
            "providers": [
                {
                    "name": "sam3-auto-masks",
                    "kind": "discovery_provider",
                    "available": True,
                    "runnable": False,
                    "status": "runtime_proof_required",
                    "reasons": ["SAM3 Scene Sweep needs runtime proof before extraction."],
                }
            ],
        },
    )
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    run_config = {
        "schema": "motionjson.extraction_run_config.v0.1",
        "input": {"path": "local-ui://assets/source-video"},
        "output": {"directory": "out/runtime-proof"},
        "sampling": {"sample_fps": 12, "max_frames": 2},
        "provider": {"name": "sam3-local"},
        "discovery": {
            "mode": "sam3_auto_masks",
            "config": {"sceneSweep": True, "providerPreference": "sam3-local"},
        },
        "prompts": [],
    }

    status, _headers, body = app.handle(
        "POST",
        "/api/run-config/validate",
        body=json.dumps({"runConfig": run_config}).encode("utf-8"),
    )
    payload = decode(body)
    proof_warning = next(item for item in payload["warnings"] if item["code"] == "runtime_proof_missing")

    assert status == 200
    assert payload["valid"] is True
    assert proof_warning["severity"] == "error"
    assert proof_warning["provider"] == "sam3-auto-masks"
    assert proof_warning["runtimeProof"]["format"] == "motionjson.runtime_proof.v0.1"
    assert proof_warning["runtimeProof"]["allowsRun"] is False

    status, _headers, body = app.handle("POST", "/api/projects", body=json.dumps({"name": "Proof gate"}).encode("utf-8"))
    project = decode(body)["project"]
    status, _headers, body = app.handle(
        "POST",
        "/api/jobs",
        body=json.dumps({"projectId": project["id"], "runConfig": run_config, "run": True}).encode("utf-8"),
    )
    failed = decode(body)

    assert status == 400
    assert "Runtime proof gate blocked extraction" in failed["error"]
    assert "storage_key" not in body.decode("utf-8")


def test_local_ui_blocks_hosted_sam2_without_per_run_ack_after_provider_opt_in(tmp_path, monkeypatch):
    monkeypatch.setattr(
        ui_server,
        "build_capability_report",
        lambda **_kwargs: {
            "schema": "motionjson.provider_diagnostics.v0.1",
            "summary": {"providersReady": 1, "providersTotal": 1},
            "environment": {},
            "providers": [{"name": "sam2-hosted", "kind": "mask_provider", "available": True, "runnable": True, "status": "ready"}],
        },
    )
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    secret = "replicate-hosted-secret-abcdef123456"
    status, _headers, body = app.handle(
        "POST",
        "/api/provider-settings",
        body=json.dumps(
            {
                "providerId": "sam2-hosted",
                "hostedProfileId": "replicate-sam2-video",
                "apiKey": secret,
                "allowHosted": True,
            }
        ).encode("utf-8"),
    )
    assert status == 200

    run_config = {
        "schema": "motionjson.extraction_run_config.v0.1",
        "input": {"path": "local-ui://assets/source-video"},
        "output": {"directory": "out/hosted-sam2"},
        "sampling": {"sample_fps": 12, "max_frames": 2},
        "provider": {
            "name": "sam2-hosted",
            "sam2": {"hosted_allow_network": False, "hosted_config": {"profile": "replicate-sam2-video"}},
        },
        "discovery": {"mode": "manual_prompt", "config": {}},
        "prompts": [{"kind": "point", "frame_index": 0, "object_id": "object_0", "label": "Object", "data": {"x": 1, "y": 1}}],
    }

    status, _headers, body = app.handle(
        "POST",
        "/api/run-config/validate",
        body=json.dumps({"runConfig": run_config}).encode("utf-8"),
    )
    payload = decode(body)
    warning = next(item for item in payload["warnings"] if item["code"] == "hosted_network_ack_required")
    assert status == 200
    assert warning["provider"] == "sam2-hosted"
    assert warning["field"] == "provider.sam2.hosted_allow_network"
    assert secret not in body.decode("utf-8")

    status, _headers, body = app.handle("POST", "/api/projects", body=json.dumps({"name": "Hosted SAM2 gate"}).encode("utf-8"))
    project = decode(body)["project"]
    status, _headers, body = app.handle(
        "POST",
        "/api/jobs",
        body=json.dumps({"projectId": project["id"], "runConfig": run_config, "run": True}).encode("utf-8"),
    )
    failed = decode(body)
    assert status == 400
    assert "hosted network" in failed["error"]
    assert secret not in body.decode("utf-8")

    allowed = copy.deepcopy(run_config)
    allowed["provider"]["sam2"]["hosted_allow_network"] = True
    status, _headers, body = app.handle(
        "POST",
        "/api/run-config/validate",
        body=json.dumps({"runConfig": allowed}).encode("utf-8"),
    )
    payload = decode(body)
    assert status == 200
    assert "hosted_network_ack_required" not in {warning["code"] for warning in payload["warnings"]}


def test_local_ui_blocks_hosted_sam3_without_per_run_ack_after_provider_opt_in(tmp_path, monkeypatch):
    monkeypatch.setattr(
        ui_server,
        "build_capability_report",
        lambda **_kwargs: {
            "schema": "motionjson.provider_diagnostics.v0.1",
            "summary": {"providersReady": 1, "providersTotal": 1},
            "environment": {},
            "providers": [
                {"name": "sam3-hosted", "kind": "discovery_provider", "available": True, "runnable": True, "status": "ready"},
                {"name": "sam3-concept", "kind": "discovery_provider", "available": True, "runnable": True, "status": "ready"},
            ],
        },
    )
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

    run_config = {
        "schema": "motionjson.extraction_run_config.v0.1",
        "input": {"path": "local-ui://assets/source-video"},
        "output": {"directory": "out/hosted-sam3"},
        "sampling": {"sample_fps": 12, "max_frames": 2},
        "provider": {"name": "sam3-hosted", "sam3": {"hosted_allow_network": False}},
        "discovery": {
            "mode": "sam3_concept",
            "config": {
                "providerPreference": "sam3-hosted",
                "hosted": True,
                "concept": "red ball",
                "allowNetwork": False,
                "acknowledgeCostPrivacy": False,
            },
        },
        "prompts": [],
    }

    status, _headers, body = app.handle(
        "POST",
        "/api/run-config/validate",
        body=json.dumps({"runConfig": run_config}).encode("utf-8"),
    )
    payload = decode(body)
    warning_codes = [item["code"] for item in payload["warnings"]]
    assert status == 200
    assert warning_codes.count("sam3_hosted_requires_opt_in") == 2
    assert secret not in body.decode("utf-8")

    status, _headers, body = app.handle("POST", "/api/projects", body=json.dumps({"name": "Hosted SAM3 gate"}).encode("utf-8"))
    project = decode(body)["project"]
    status, _headers, body = app.handle(
        "POST",
        "/api/jobs",
        body=json.dumps({"projectId": project["id"], "runConfig": run_config, "run": True}).encode("utf-8"),
    )
    failed = decode(body)
    assert status == 400
    assert "sam3-hosted requires" in failed["error"]
    assert secret not in body.decode("utf-8")

    allowed = copy.deepcopy(run_config)
    allowed["discovery"]["config"]["allowNetwork"] = True
    allowed["discovery"]["config"]["acknowledgeCostPrivacy"] = True
    status, _headers, body = app.handle(
        "POST",
        "/api/run-config/validate",
        body=json.dumps({"runConfig": allowed}).encode("utf-8"),
    )
    payload = decode(body)
    assert status == 200
    assert "sam3_hosted_requires_opt_in" not in {warning["code"] for warning in payload["warnings"]}


def test_local_ui_validation_reports_sam3_hosted_missing_credentials(tmp_path, monkeypatch):
    monkeypatch.setattr(
        ui_server,
        "build_capability_report",
        lambda **_kwargs: {
            "schema": "motionjson.provider_diagnostics.v0.1",
            "summary": {"providersReady": 0, "providersTotal": 2},
            "environment": {},
            "providers": [
                {
                    "name": "sam3-hosted",
                    "kind": "discovery_provider",
                    "available": False,
                    "configured": False,
                    "runnable": False,
                    "status": "not_configured",
                    "networkRequired": True,
                    "needsCredentials": True,
                    "reasons": ["SAM3_HOSTED_API_KEY is not set."],
                    "installHint": "Save hosted SAM3 credentials and opt into network use.",
                },
                {"name": "sam3-concept", "kind": "discovery_provider", "available": True, "runnable": True, "status": "ready"},
            ],
        },
    )
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    run_config = {
        "schema": "motionjson.extraction_run_config.v0.1",
        "input": {"path": "local-ui://assets/source-video"},
        "output": {"directory": "out/hosted-sam3"},
        "sampling": {"sample_fps": 12, "max_frames": 2},
        "provider": {"name": "sam3-hosted", "sam3": {"hosted_allow_network": True}},
        "discovery": {
            "mode": "sam3_concept",
            "config": {
                "providerPreference": "sam3-hosted",
                "hosted": True,
                "concept": "red ball",
                "allowNetwork": True,
                "acknowledgeCostPrivacy": True,
            },
        },
        "prompts": [],
    }

    status, _headers, body = app.handle(
        "POST",
        "/api/run-config/validate",
        body=json.dumps({"runConfig": run_config}).encode("utf-8"),
    )
    payload = decode(body)

    assert status == 200
    warning = next(item for item in payload["warnings"] if item["code"] == "sam3_hosted_missing_credentials")
    assert warning["provider"] == "sam3-hosted"
    assert "SAM3_HOSTED_API_KEY" in json.dumps(warning)


def test_local_ui_api_queues_mock_job_and_scrubs_storage_keys(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)

    status, _headers, body = app.handle("POST", "/api/projects", body=json.dumps({"name": "UI Project"}).encode("utf-8"))
    project = decode(body)["project"]
    status, _headers, body = app.handle(
        "POST",
        "/api/videos",
        body=json.dumps({"projectId": project["id"], "path": str(demo_video())}).encode("utf-8"),
    )
    video = decode(body)["video"]

    status, _headers, body = app.handle(
        "POST",
        "/api/jobs",
        body=json.dumps({"projectId": project["id"], "videoId": video["id"], "maxFrames": 1}).encode("utf-8"),
    )
    assert status == 200
    job = decode(body)["job"]
    assert job["type"] == "extract"
    assert job["payload"]["mask_provider"] == "mock"

    credential_sample = "redaction-sample-1234567890"
    authorization_label = "author" + "ization"
    signed_query_name = "query_redaction_sample"
    conn = app.connection()
    try:
        record_job_event(
            conn,
            job_id=job["id"],
            event_type="debug",
            message="storage_key=projects/private/source.mp4",
            metadata={"storageKey": "projects/private/event.mp4", "safe": True},
        )
        record_job_event(
            conn,
            job_id=job["id"],
            event_type="debug",
            message=f"failed at /Users/example/private/video.mp4 with secret={credential_sample}",
            metadata={
                "sourcePath": "/Users/example/private/video.mp4",
                "fileUri": "file:///Users/example/private/video.mp4",
                "remoteUrl": f"https://example.test/private.bin?{signed_query_name}=secret",
                "apiKey": credential_sample,
                authorization_label: credential_sample,
            },
        )
        register_generated_asset(
            conn,
            storage=app.storage(),
            project_id=project["id"],
            source_job_id=job["id"],
            kind="job_logs",
            data=b"local debug log",
            rel_path="logs/debug.txt",
            content_type="text/plain",
            metadata={"storage_key": "projects/private/artifact.txt", "note": "safe"},
        )
    finally:
        conn.close()

    status, _headers, body = app.handle("GET", f"/api/jobs/{job['id']}/events")
    events_payload = decode(body)
    assert status == 200
    assert any(event["event_type"] == "queued" for event in events_payload["events"])
    assert events_payload["job"]["id"] == job["id"]
    events_text = body.decode("utf-8")
    assert "storage_key" not in events_text
    assert "projects/private" not in events_text
    assert "/Users/example" not in events_text
    assert "file:///Users/example" not in events_text
    assert credential_sample not in events_text
    assert f"{signed_query_name}=secret" not in events_text
    assert "[LOCAL_PATH_REDACTED]" in events_text
    assert "[LOCAL_FILE_URI_REDACTED]" in events_text
    assert "[REDACTED]" in events_text

    status, _headers, body = app.handle("GET", f"/api/jobs/{job['id']}")
    job_payload = decode(body)["job"]
    assert status == 200
    assert any(event["event_type"] == "debug" for event in job_payload["events"])
    assert job_payload["lastEventAt"]
    job_text = body.decode("utf-8")
    assert "storage_key" not in job_text
    assert "projects/private" not in job_text
    assert "/Users/example" not in job_text
    assert "file:///Users/example" not in job_text
    assert credential_sample not in job_text
    assert f"{signed_query_name}=secret" not in job_text
    assert "[LOCAL_PATH_REDACTED]" in job_text
    assert "[LOCAL_FILE_URI_REDACTED]" in job_text
    assert "[REDACTED]" in job_text

    status, _headers, body = app.handle("GET", f"/api/progress?projectId={project['id']}")
    assert status == 200
    assert "storage_key" not in body.decode("utf-8")
    assert "projects/private" not in body.decode("utf-8")

    status, _headers, body = app.handle("GET", f"/api/jobs/{job['id']}/artifacts")
    artifacts = decode(body)["artifacts"]
    assert status == 200
    assert artifacts[0]["kind"] == "job_logs"
    assert artifacts[0]["metadata"] == {"note": "safe", "rel_path": "logs/debug.txt"}
    assert "uri" not in artifacts[0]
    assert "storage_key" not in body.decode("utf-8")
    assert "file://" not in body.decode("utf-8")
    assert "projects/private" not in body.decode("utf-8")

    status, _headers, body = app.handle("GET", f"/api/artifacts?jobId={job['id']}")
    assert status == 200
    assert decode(body)["artifacts"][0]["id"] == artifacts[0]["id"]
    assert "storage_key" not in body.decode("utf-8")
    assert "file://" not in body.decode("utf-8")


def test_local_ui_review_returns_api_first_candidates_and_redacts_private_fields(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)

    status, _headers, body = app.handle("POST", "/api/projects", body=json.dumps({"name": "Candidate Project"}).encode("utf-8"))
    project = decode(body)["project"]
    status, _headers, body = app.handle(
        "POST",
        "/api/videos",
        body=json.dumps({"projectId": project["id"], "path": str(demo_video())}).encode("utf-8"),
    )
    video = decode(body)["video"]
    status, _headers, body = app.handle(
        "POST",
        "/api/jobs",
        body=json.dumps({"projectId": project["id"], "videoId": video["id"], "maskProvider": "mock", "maxFrames": 1}).encode("utf-8"),
    )
    job = decode(body)["job"]
    candidates_payload = {
        "format": "motionjson.candidates.v0.1",
        "provider": "mock",
        "config": {"qualityPreset": "clean", "requireReview": True, "writeRejectedCandidates": True},
        "video": {"width": 200, "height": 100, "sampledFrameCount": 10},
        "candidates": [
            {
                "id": "cand_001",
                "label": "unlabeled object",
                "source": "auto_object_proposals",
                "frameIndex": 0,
                "box": {"x": 120, "y": 80, "w": 40, "h": 20},
                "score": 0.83,
                "metadata": {
                    "providerName": "mock",
                    "motionScore": 0.64,
                    "stabilityScore": 0.88,
                    "maskFiles": 7,
                    "maskDir": "discovery/mock/cand_001",
                    "storageKey": "projects/private/candidate-mask.png",
                },
            },
            {
                "id": "cand_002",
                "label": "background fragment",
                "source": "auto_object_proposals",
                "frameIndex": 0,
                "box": {"x": 0, "y": 0, "w": 200, "h": 90},
                "score": 0.4,
                "metadata": {
                    "rejectionReason": "background_like",
                    "warnings": [f"file://{tmp_path}/private.png", "api_key=sk-1234567890"],
                },
            },
        ],
    }
    conn = app.connection()
    try:
        register_generated_asset(
            conn,
            storage=app.storage(),
            project_id=project["id"],
            source_job_id=job["id"],
            kind="candidate_summary",
            data=json.dumps(candidates_payload).encode("utf-8"),
            rel_path="candidates.json",
            content_type="application/json",
            metadata={"storage_key": "projects/private/candidates.json"},
        )
    finally:
        conn.close()

    status, _headers, body = app.handle("GET", f"/api/jobs/{job['id']}/review")
    review = decode(body)["review"]

    assert status == 200
    assert review["candidates"][0]["candidateId"] == "cand_001"
    assert review["candidates"][0]["providerName"] == "mock"
    assert review["candidates"][0]["areaRatio"] == 0.04
    assert review["candidates"][0]["frameCoverageEstimate"] == 0.7
    assert review["candidates"][1]["rejectionReason"] == "background_like"
    assert review["candidateSummary"]["candidateCount"] == 2
    assert review["candidateSummary"]["acceptedCandidateCount"] == 1
    assert review["candidateSummary"]["rejectedCandidateCount"] == 1
    assert review["candidateSummary"]["defaultSelectedCount"] == 1
    assert review["candidateSummary"]["rejectionReasons"] == {"background_like": 1}
    assert review["candidateSummary"]["provider"] == "mock"
    assert review["candidateSummary"]["providerName"] == "mock"
    assert len(review["candidateSummary"]["candidates"]) == 2
    assert review["timeline"]["format"] == "motionjson.review_timeline.v0.1"
    assert review["timeline"]["frameCount"] == 10
    assert review["timeline"]["markerCountsByKind"] == {"candidate": 2}
    assert [item["frameIndex"] for item in review["timeline"]["suggestedKeyframes"]] == [0]
    public_body = body.decode("utf-8")
    assert "storage_key" not in public_body
    assert "storageKey" not in public_body
    assert "projects/private" not in public_body
    assert "file://" not in public_body
    assert "1234567890" not in public_body


def test_local_ui_review_exposes_partial_review_payload_and_redacts_diagnostics(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)

    status, _headers, body = app.handle("POST", "/api/projects", body=json.dumps({"name": "Partial Review Project"}).encode("utf-8"))
    project = decode(body)["project"]
    status, _headers, body = app.handle(
        "POST",
        "/api/videos",
        body=json.dumps({"projectId": project["id"], "path": str(demo_video())}).encode("utf-8"),
    )
    video = decode(body)["video"]
    status, _headers, body = app.handle(
        "POST",
        "/api/jobs",
        body=json.dumps({"projectId": project["id"], "videoId": video["id"], "maskProvider": "mock", "maxFrames": 1}).encode("utf-8"),
    )
    job = decode(body)["job"]
    partial_payload = {
        "format": "motionjson.partial_review_payload.v0.1",
        "status": "ready",
        "partialSuccess": True,
        "jobId": job["id"],
        "reviewableObjectCount": 2,
        "reviewableObjectIds": ["sam3_grid_001", "sam3_grid_002"],
        "failedObjectId": "sam3_grid_027",
        "diagnostic": {
            "reasonCode": "worker_heartbeat_stale",
            "objectId": "sam3_grid_027",
            "frame": 11,
            "totalFrames": 36,
            "message": f"failed while reading file://{tmp_path}/private/source.mp4 with token=sk-1234567890",
        },
        "runtimeProof": {"acceleratorKind": "cuda", "runtimeProofStatus": "verified"},
    }
    conn = app.connection()
    try:
        register_generated_asset(
            conn,
            storage=app.storage(),
            project_id=project["id"],
            source_job_id=job["id"],
            kind="partial_review",
            data=json.dumps(partial_payload).encode("utf-8"),
            rel_path="partial_review.json",
            content_type="application/json",
            metadata={"storage_key": "projects/private/partial_review.json"},
        )
    finally:
        conn.close()

    status, _headers, body = app.handle("GET", f"/api/jobs/{job['id']}/review")
    review = decode(body)["review"]
    public_body = body.decode("utf-8")

    assert status == 200
    assert review["artifactCountsByKind"]["partial_review"] == 1
    assert review["partialSuccess"] is True
    assert review["reviewableObjectCount"] == 2
    assert review["partialReview"]["failedObjectId"] == "sam3_grid_027"
    assert review["partialReview"]["diagnostic"]["reasonCode"] == "worker_heartbeat_stale"
    assert review["partialReview"]["diagnostic"]["frame"] == 11
    assert review["partialReview"]["runtimeProof"]["acceleratorKind"] == "cuda"
    assert "file://" not in public_body
    assert str(tmp_path) not in public_body
    assert "1234567890" not in public_body
    assert "storage_key" not in public_body
    assert "projects/private" not in public_body


def test_local_ui_review_redacts_unavailable_candidate_artifact_diagnostics(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)

    status, _headers, body = app.handle("POST", "/api/projects", body=json.dumps({"name": "Missing Candidate Artifact"}).encode("utf-8"))
    project = decode(body)["project"]
    status, _headers, body = app.handle(
        "POST",
        "/api/videos",
        body=json.dumps({"projectId": project["id"], "path": str(demo_video())}).encode("utf-8"),
    )
    video = decode(body)["video"]
    status, _headers, body = app.handle(
        "POST",
        "/api/jobs",
        body=json.dumps({"projectId": project["id"], "videoId": video["id"], "maskProvider": "mock", "maxFrames": 1}).encode("utf-8"),
    )
    job = decode(body)["job"]
    conn = app.connection()
    try:
        asset = register_generated_asset(
            conn,
            storage=app.storage(),
            project_id=project["id"],
            source_job_id=job["id"],
            kind="candidate_summary",
            data=json.dumps({"format": "motionjson.candidates.v0.1", "candidates": []}).encode("utf-8"),
            rel_path="candidates.json",
            content_type="application/json",
        )
    finally:
        conn.close()
    (app.storage().root / asset["storage_key"]).unlink()

    status, _headers, body = app.handle("GET", f"/api/jobs/{job['id']}/review")
    review = decode(body)["review"]
    public_body = body.decode("utf-8")

    assert status == 200
    assert review["diagnostics"][0]["code"] == "artifact_review_unavailable"
    assert "storage_key" not in public_body
    assert "storageKey" not in public_body
    assert "projects/" not in public_body
    assert asset["storage_key"] not in public_body


def test_local_ui_auto_object_proposals_mock_review_uses_artifact_backed_candidates(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)

    status, _headers, body = app.handle("POST", "/api/projects", body=json.dumps({"name": "Auto Object Proposals"}).encode("utf-8"))
    project = decode(body)["project"]
    status, _headers, body = app.handle(
        "POST",
        "/api/videos",
        body=json.dumps({"projectId": project["id"], "path": str(demo_video())}).encode("utf-8"),
    )
    video = decode(body)["video"]
    run_config = {
        "schema": "motionjson.extraction_run_config.v0.1",
        "input": {"path": f"local-ui://assets/{video['id']}"},
        "output": {"directory": str(tmp_path / "private-output")},
        "objects": [{"object_id": "object_0", "label": "Discovered objects"}],
        "sampling": {"sample_fps": 12.0, "max_frames": 2},
        "provider": {"name": "mock"},
        "discovery": {
            "mode": "auto_object_proposals",
            "config": {
                "mock": True,
                "qualityPreset": "clean",
                "maxCandidatesPerKeyframe": 4,
                "maxObjects": 2,
                "writeRejectedCandidates": True,
            },
        },
        "prompts": [],
    }

    status, _headers, body = app.handle(
        "POST",
        "/api/jobs",
        body=json.dumps({"projectId": project["id"], "runConfig": run_config, "run": True}).encode("utf-8"),
    )
    job = wait_for_job(app, decode(body)["job"]["id"])
    artifact_payload = decode(app.handle("GET", f"/api/jobs/{job['id']}/artifacts")[2])
    review = artifact_payload["review"]
    artifact_ids = {artifact["id"] for artifact in artifact_payload["artifacts"]}

    assert status == 200
    assert job["status"] == "succeeded"
    assert review["candidateSummary"]["provider"] == "auto_object_proposals"
    assert review["candidateSummary"]["providerName"] == "mock"
    assert review["candidateSummary"]["qualityPreset"] == "clean"
    assert review["candidateSummary"]["candidateCount"] == 4
    assert review["candidateSummary"]["acceptedCandidateCount"] == 2
    assert review["candidateSummary"]["rejectedCandidateCount"] == 2
    assert len(review["tracks"]) == 2
    assert review["timeline"]["markerCountsByKind"]["candidate"] == 4
    assert review["timeline"]["markerCountsByKind"]["track_start"] == 2
    assert review["timeline"]["suggestedKeyframes"][0]["source"] == "review.timeline"
    assert review["candidates"][0]["thumbnailArtifactId"] in artifact_ids
    assert review["candidates"][0]["maskPreviewArtifactId"] in artifact_ids
    assert review["candidates"][2]["reviewStatus"] == "rejected"
    assert review["candidates"][2]["rejectionReason"] in {"too_small", "duplicate_mask"}
    assert "storage_key" not in json.dumps(artifact_payload)


def test_local_ui_track_selected_validates_candidates_and_gates_export(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)

    status, _headers, body = app.handle("POST", "/api/projects", body=json.dumps({"name": "Track Selected"}).encode("utf-8"))
    project = decode(body)["project"]
    status, _headers, body = app.handle(
        "POST",
        "/api/videos",
        body=json.dumps({"projectId": project["id"], "path": str(demo_video())}).encode("utf-8"),
    )
    video = decode(body)["video"]
    run_config = {
        "schema": "motionjson.extraction_run_config.v0.1",
        "input": {"path": f"local-ui://assets/{video['id']}"},
        "output": {"directory": str(tmp_path / "private-output")},
        "objects": [{"object_id": "object_0", "label": "Discovered objects"}],
        "sampling": {"sample_fps": 12.0, "max_frames": 2},
        "provider": {"name": "mock"},
        "discovery": {
            "mode": "auto_object_proposals",
            "config": {
                "mock": True,
                "qualityPreset": "clean",
                "maxCandidatesPerKeyframe": 4,
                "maxObjects": 2,
                "writeRejectedCandidates": True,
            },
        },
        "prompts": [],
        "filters": {"min_area": 1, "simplify_ratio": 0.006},
        "export": {"output_mode": "authoring", "feather": 0, "layer_padding": 4, "sprite_format": "webp", "production_avif": False},
    }
    status, _headers, body = app.handle(
        "POST",
        "/api/jobs",
        body=json.dumps({"projectId": project["id"], "runConfig": run_config, "run": True}).encode("utf-8"),
    )
    job = wait_for_job(app, decode(body)["job"]["id"])
    review = decode(app.handle("GET", f"/api/jobs/{job['id']}/review")[2])["review"]
    selected_id = review["candidates"][0]["candidateId"]
    rejected_id = review["candidates"][2]["candidateId"]

    status, _headers, body = app.handle(
        "POST",
        f"/api/jobs/{job['id']}/track-selected",
        body=json.dumps({"candidateIds": [selected_id], "trackMode": "selected_only", "exportReviewRequired": True}).encode("utf-8"),
    )
    payload = decode(body)
    updated = payload["review"]

    assert status == 200
    assert payload["trackSelected"]["trackedObjectIds"] == [selected_id]
    assert len(updated["tracks"]) == 1
    assert updated["tracks"][0]["objectId"] == selected_id
    assert updated["tracks"][0]["exportStatus"] == "review_pending"
    assert updated["candidateSummary"]["candidateCount"] == 4
    assert updated["candidateSummary"]["acceptedCandidateCount"] == 1
    assert any(artifact["kind"] == "track_summary" for artifact in payload["artifacts"])
    assert any(artifact["kind"] == "scene_graph" for artifact in payload["artifacts"])
    assert "storage_key" not in body.decode("utf-8")

    status, _headers, body = app.handle(
        "POST",
        f"/api/jobs/{job['id']}/track-selected",
        body=json.dumps({"candidateIds": ["missing_candidate"], "trackMode": "selected_only"}).encode("utf-8"),
    )
    assert status == 400
    assert "do not belong" in decode(body)["error"]

    status, _headers, body = app.handle(
        "POST",
        f"/api/jobs/{job['id']}/track-selected",
        body=json.dumps({"candidateIds": [rejected_id], "trackMode": "selected_only"}).encode("utf-8"),
    )
    assert status == 400
    assert "cannot be tracked" in decode(body)["error"]

    status, _headers, body = app.handle(
        "POST",
        f"/api/jobs/{job['id']}/validate",
        body=json.dumps({"preset": "compact"}).encode("utf-8"),
    )
    assert status == 400
    assert "No exportable object tracks" in decode(body)["error"]

    status, _headers, body = app.handle(
        "POST",
        f"/api/jobs/{job['id']}/track-edits",
        body=json.dumps({"action": {"type": "set_export_inclusion", "trackId": selected_id, "included": True}}).encode("utf-8"),
    )
    accepted = decode(body)
    assert status == 200
    assert accepted["review"]["tracks"][0]["objectId"] == selected_id
    assert accepted["review"]["tracks"][0]["exportIncluded"] is True
    assert accepted["review"]["tracks"][0]["exportStatus"] == "accepted"

    status, _headers, body = app.handle(
        "POST",
        f"/api/jobs/{job['id']}/validate",
        body=json.dumps({"preset": "compact", "includePreview": False}).encode("utf-8"),
    )
    validation = decode(body)
    assert status == 200
    assert validation["includedObjectIds"] == [selected_id]
    assert validation["validation"]["ok"] is True

    status, _headers, body = app.handle(
        "POST",
        f"/api/jobs/{job['id']}/exports/motionjson",
        body=json.dumps({"preset": "compact", "includePreview": False}).encode("utf-8"),
    )
    exported = decode(body)
    assert status == 200
    assert exported["export"]["includedObjectIds"] == [selected_id]
    assert any(asset["kind"] == "validated_motionjson_scene" for asset in exported["artifacts"])


def test_local_ui_exports_accepted_track_summary_with_masks_when_scene_review_gate_is_stale(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)

    status, _headers, body = app.handle("POST", "/api/projects", body=json.dumps({"name": "Accepted Track Export"}).encode("utf-8"))
    project = decode(body)["project"]
    status, _headers, body = app.handle(
        "POST",
        "/api/videos",
        body=json.dumps({"projectId": project["id"], "path": str(demo_video())}).encode("utf-8"),
    )
    video = decode(body)["video"]
    run_config = {
        "schema": "motionjson.extraction_run_config.v0.1",
        "input": {"path": f"local-ui://assets/{video['id']}"},
        "output": {"directory": str(tmp_path / "private-output")},
        "objects": [{"object_id": "object_0", "label": "Discovered objects"}],
        "sampling": {"sample_fps": 12.0, "max_frames": 2},
        "provider": {"name": "mock"},
        "discovery": {
            "mode": "auto_object_proposals",
            "config": {
                "mock": True,
                "qualityPreset": "clean",
                "maxCandidatesPerKeyframe": 4,
                "maxObjects": 2,
                "writeRejectedCandidates": True,
            },
        },
        "prompts": [],
        "filters": {"min_area": 1, "simplify_ratio": 0.006},
        "export": {"output_mode": "authoring", "feather": 0, "layer_padding": 4, "sprite_format": "webp", "production_avif": False},
    }
    status, _headers, body = app.handle(
        "POST",
        "/api/jobs",
        body=json.dumps({"projectId": project["id"], "runConfig": run_config, "run": True}).encode("utf-8"),
    )
    job = wait_for_job(app, decode(body)["job"]["id"])
    review = decode(app.handle("GET", f"/api/jobs/{job['id']}/review")[2])["review"]
    selected_id = review["candidates"][0]["candidateId"]

    status, _headers, body = app.handle(
        "POST",
        f"/api/jobs/{job['id']}/track-selected",
        body=json.dumps({"candidateIds": [selected_id], "trackMode": "selected_only", "exportReviewRequired": True}).encode("utf-8"),
    )
    assert status == 200

    conn = app.connection()
    try:
        assets = list_assets_for_job(conn, project_id=job["project_id"], source_job_id=job["id"])
    finally:
        conn.close()
    track_asset = next(asset for asset in assets if asset["kind"] == "track_summary")
    scene_asset = next(asset for asset in assets if asset["kind"] == "scene_graph")
    storage = app.storage()
    track_summary = json.loads(storage.load_bytes(track_asset["storage_key"]).decode("utf-8"))
    track_summary["tracks"][0]["exportStatus"] = "accepted"
    track_summary["tracks"][0]["exportIncluded"] = True
    storage.save_bytes(
        track_asset["storage_key"],
        (json.dumps(track_summary, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        content_type=track_asset.get("content_type"),
    )
    stale_scene = json.loads(storage.load_bytes(scene_asset["storage_key"]).decode("utf-8"))
    assert stale_scene["objects"][0]["quality"]["reviewRequired"] is True
    assert stale_scene["objects"][0]["discovery"]["exportStatus"] == "review_pending"

    status, _headers, body = app.handle(
        "POST",
        f"/api/jobs/{job['id']}/validate",
        body=json.dumps({"preset": "debug", "includeMasks": True, "includePreview": False}).encode("utf-8"),
    )
    validation = decode(body)
    assert status == 200
    assert validation["includedObjectIds"] == [selected_id]
    assert validation["validation"]["ok"] is True

    status, _headers, body = app.handle(
        "POST",
        f"/api/jobs/{job['id']}/exports",
        body=json.dumps({"preset": "debug", "includeMasks": True, "includePreview": False}).encode("utf-8"),
    )
    exported = decode(body)
    assert status == 200
    assert exported["export"]["includedObjectIds"] == [selected_id]
    assert exported["export"]["validation"]["ok"] is True
    assert any(asset["kind"] == "export_mask" for asset in exported["artifacts"])


def test_local_ui_export_validation_messages_explain_unreviewed_auto_discovery(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    _project, _video, job = create_completed_mock_job(app, "Unreviewed Discovery Export")
    scene_asset = scene_asset_for_job(app, job)
    storage = app.storage()
    scene = json.loads(storage.load_bytes(scene_asset["storage_key"]).decode("utf-8"))
    pending = copy.deepcopy(scene["objects"][0])
    pending["id"] = "auto_pending"
    pending["label"] = "Auto pending"
    pending["discovery"] = {
        "source": "auto_object_proposals",
        "qualityPreset": "clean",
        "reviewStatus": "pending",
        "reviewRequired": True,
        "exportStatus": "review_pending",
    }
    scene["objects"].append(pending)
    storage.save_bytes(scene_asset["storage_key"], json.dumps(scene).encode("utf-8"), content_type="application/json")

    status, _headers, body = app.handle(
        "POST",
        f"/api/jobs/{job['id']}/validate",
        body=json.dumps({"preset": "compact", "includePreview": False}).encode("utf-8"),
    )
    validation = decode(body)

    assert status == 200
    assert validation["includedObjectIds"] == ["object_0"]
    assert validation["excludedObjectIds"] == ["auto_pending"]
    assert validation["objectLayerPack"]["selectedObjectIds"] == ["object_0"]
    assert validation["objectLayerPack"]["excludedObjectIds"] == ["auto_pending"]
    assert any(
        message["code"] == "auto_discovered_object_review_required" and message["objectId"] == "auto_pending"
        for message in validation["exportValidationMessages"]
    )
    assert str(tmp_path) not in body.decode("utf-8")
    assert "projects/" not in body.decode("utf-8")


def test_local_ui_cancel_pending_job_records_public_status_and_event(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)

    status, _headers, body = app.handle("POST", "/api/projects", body=json.dumps({"name": "Cancel Project"}).encode("utf-8"))
    project = decode(body)["project"]
    status, _headers, body = app.handle(
        "POST",
        "/api/videos",
        body=json.dumps({"projectId": project["id"], "path": str(demo_video())}).encode("utf-8"),
    )
    video = decode(body)["video"]
    status, _headers, body = app.handle(
        "POST",
        "/api/jobs",
        body=json.dumps({"projectId": project["id"], "videoId": video["id"], "maskProvider": "mock", "maxFrames": 2}).encode("utf-8"),
    )
    job = decode(body)["job"]
    assert status == 200
    assert job["status"] == "pending"

    status, headers, body = app.handle(
        "POST",
        f"/api/jobs/{job['id']}/cancel",
        body=json.dumps({"reason": "user_canceled"}).encode("utf-8"),
    )
    canceled = decode(body)["job"]

    assert status == 200
    assert headers["cache-control"] == "no-store"
    assert canceled["status"] == "canceled"
    assert canceled["error"] == "user_canceled"
    assert any(event["event_type"] == "canceled" for event in canceled["events"])
    assert "storage_key" not in body.decode("utf-8")
    assert "projects/" not in body.decode("utf-8")


def test_local_ui_api_runs_mock_job_from_run_config_and_exposes_review_metadata(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)

    status, _headers, body = app.handle("POST", "/api/projects", body=json.dumps({"name": "UI Project"}).encode("utf-8"))
    project = decode(body)["project"]
    status, _headers, body = app.handle(
        "POST",
        "/api/videos",
        body=json.dumps({"projectId": project["id"], "path": str(demo_video())}).encode("utf-8"),
    )
    video = decode(body)["video"]
    run_config = {
        "schema": "motionjson.extraction_run_config.v0.1",
        "input": {"path": f"local-ui://assets/{video['id']}"},
        "output": {"directory": str(tmp_path / "private-output")},
        "objects": [{"object_id": "object_0", "label": "Ball"}],
        "sampling": {"sample_fps": 12.0, "max_frames": 2},
        "provider": {"name": "mock"},
        "discovery": {"mode": "manual_prompt"},
        "prompts": [],
        "rights": {
            "source_type": "user_upload",
            "source_uri": str(demo_video()),
            "source_asset_id": video["id"],
        },
    }

    status, _headers, body = app.handle(
        "POST",
        "/api/jobs",
        body=json.dumps({"projectId": project["id"], "runConfig": run_config, "run": True}).encode("utf-8"),
    )
    assert status == 200
    payload = decode(body)
    assert payload["worker"]["status"] == "started"
    job = wait_for_job(app, payload["job"]["id"])
    assert job["status"] == "succeeded"
    assert job["progress"] == 100
    assert job["payload"]["mask_provider"] == "mock"

    status, _headers, body = app.handle("GET", f"/api/progress?projectId={project['id']}")
    progress = decode(body)["progress"][0]
    assert status == 200
    assert progress["events"]
    assert progress["percent"] == 100
    assert str(tmp_path) not in body.decode("utf-8")
    assert "storage_key" not in body.decode("utf-8")
    assert "projects/" not in body.decode("utf-8")

    status, _headers, body = app.handle("GET", f"/api/jobs/{job['id']}/artifacts")
    artifact_payload = decode(body)
    assert status == 200
    kinds = {artifact["kind"] for artifact in artifact_payload["artifacts"]}
    assert {"scene_graph", "track_summary", "fallback_diagnostics", "job_logs"}.issubset(kinds)
    assert any(artifact.get("contentUrl", "").startswith("/api/artifacts/") for artifact in artifact_payload["artifacts"])
    assert "contentUrl" not in next(artifact for artifact in artifact_payload["artifacts"] if artifact["kind"] == "job_logs")
    visual_artifact = next(artifact for artifact in artifact_payload["artifacts"] if artifact.get("contentUrl"))
    status, headers, visual_body = app.handle("GET", visual_artifact["contentUrl"])
    assert status == 200
    assert headers["content-type"].startswith(("image/", "video/"))
    assert visual_body
    review = artifact_payload["review"]
    assert review["format"] == "motionjson.local_ui_review.v0.1"
    assert review["artifactCountsByKind"]["track_summary"] == 1
    assert review["tracks"][0]["objectId"] == "object_0"
    assert review["tracks"][0]["visibleFrameCount"] == 2
    assert review["objects"][0]["objectId"] == "object_0"
    assert review["objects"][0]["rightsSummary"]["license"] == "user_uploaded_unverified"
    assert review["rightsSummary"]["format"] == "motionjson.export_rights_summary.v0.1"
    assert review["rightsSummary"]["summary"]["commercialUseApproved"] is False
    assert {warning["code"] for warning in review["rightsSummary"]["warnings"]} >= {
        "commercial_use_review_required",
        "creator_approval_unverified",
        "license_unverified",
    }
    assert review["fallbackDiagnostics"] == []
    assert str(tmp_path) not in body.decode("utf-8")
    assert "storage_key" not in body.decode("utf-8")
    assert "projects/" not in body.decode("utf-8")

    status, _headers, body = app.handle("GET", f"/api/jobs/{job['id']}/review")
    assert status == 200
    assert decode(body)["review"]["tracks"][0]["objectId"] == "object_0"


def test_local_ui_exports_valid_motionjson_from_corrected_review_state_and_imports_previous_result(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)

    status, _headers, body = app.handle("POST", "/api/projects", body=json.dumps({"name": "Export Project"}).encode("utf-8"))
    project = decode(body)["project"]
    status, _headers, body = app.handle(
        "POST",
        "/api/videos",
        body=json.dumps({"projectId": project["id"], "path": str(demo_video())}).encode("utf-8"),
    )
    video = decode(body)["video"]
    status, _headers, body = app.handle(
        "POST",
        "/api/jobs",
        body=json.dumps({"projectId": project["id"], "videoId": video["id"], "maskProvider": "mock", "maxFrames": 2, "run": True}).encode("utf-8"),
    )
    job = wait_for_job(app, decode(body)["job"]["id"])

    status, _headers, body = app.handle("GET", f"/api/jobs/{job['id']}/review")
    review_payload = decode(body)["review"]
    assert status == 200
    assert review_payload["tracks"][0]["objectId"] == "object_0"
    assert review_payload["tracks"][0]["visibleFrameCount"] == 2
    assert review_payload["objects"][0]["objectId"] == "object_0"
    assert review_payload["fallbackDiagnostics"] == []
    assert str(tmp_path) not in body.decode("utf-8")
    assert "storage_key" not in body.decode("utf-8")
    assert "projects/" not in body.decode("utf-8")

    status, _headers, body = app.handle(
        "POST",
        f"/api/jobs/{job['id']}/track-edits",
        body=json.dumps({"operation": "relabel", "objectId": "object_0", "label": "Export Ball"}).encode("utf-8"),
    )
    assert status == 200

    status, _headers, body = app.handle(
        "POST",
        f"/api/jobs/{job['id']}/validate",
        body=json.dumps({"preset": "debug"}).encode("utf-8"),
    )
    validation_payload = decode(body)
    assert status == 200
    assert validation_payload["validation"]["ok"] is True
    assert validation_payload["includedObjectIds"] == ["object_0"]
    assert validation_payload["qualityRouting"]["preview"]["mp4Preview"]["status"] in {"plan_ready", "unavailable"}
    assert str(tmp_path) not in body.decode("utf-8")
    assert "projects/" not in body.decode("utf-8")

    status, _headers, body = app.handle(
        "POST",
        f"/api/jobs/{job['id']}/validate",
        body=json.dumps(
            {
                "preset": "compact",
                "includeMasks": True,
                "includeContours": True,
                "includePreview": False,
            }
        ).encode("utf-8"),
    )
    validation_payload = decode(body)
    assert status == 200
    assert validation_payload["config"]["preset"] == "compact"
    assert validation_payload["config"]["includeMasks"] is True
    assert validation_payload["config"]["includeContours"] is True
    assert validation_payload["config"]["includePreview"] is False
    assert validation_payload["qualityRouting"]["format"] == "motionjson.export_quality_routing.v0.1"
    assert validation_payload["qualityRouting"]["includePreview"] is False
    assert validation_payload["qualityRouting"]["aiUsage"] == "none"
    assert validation_payload["qualityRouting"]["objects"][0]["objectId"] == "object_0"
    assert validation_payload["qualityRouting"]["objects"][0]["selectedOutput"] in {
        "raster_alpha_sequence",
        "hybrid_vector_silhouette_plus_raster",
    }
    assert validation_payload["qualityRouting"]["objects"][0]["selectedDelivery"]["route"] in {
        "raster_alpha_sequence",
        "sprite_atlas",
        "sprite_atlas_webp",
        "sprite_atlas_avif",
        "transparent_webm",
    }
    assert validation_payload["qualityRouting"]["preview"]["mp4Preview"]["status"] == "skipped"
    assert validation_payload["rightsSummary"]["format"] == "motionjson.export_rights_summary.v0.1"
    assert validation_payload["rightsSummary"]["summary"]["commercialUseApproved"] is False
    assert {warning["code"] for warning in validation_payload["exportWarnings"]} >= {
        "commercial_use_review_required",
        "creator_approval_unverified",
        "license_unverified",
    }

    status, _headers, body = app.handle(
        "POST",
        f"/api/jobs/{job['id']}/exports",
        body=json.dumps({"preset": "debug", "includeMasks": True, "includeContours": True, "includePreview": True}).encode("utf-8"),
    )
    export_payload = decode(body)
    assert status == 200
    exported = export_payload["export"]
    assert exported["validation"]["ok"] is True
    assert exported["provenance"]["sourceJobId"] == job["id"]
    assert exported["provenance"]["correctionEventCount"] == 1
    assert exported["config"]["preset"] == "debug"
    assert exported["qualityRouting"]["format"] == "motionjson.export_quality_routing.v0.1"
    assert exported["qualityRouting"]["aiUsage"] == "none"
    assert exported["qualityRouting"]["objects"][0]["objectId"] == "object_0"
    assert exported["qualityRouting"]["objects"][0]["rasterAlpha"]["status"] == "ready"
    assert exported["qualityRouting"]["objects"][0]["vectorSilhouette"]["status"] in {"ready", "skipped"}
    assert exported["qualityRouting"]["preview"]["mp4Preview"]["status"] in {"ready", "unavailable", "error", "skipped"}
    assert exported["rightsSummary"]["summary"]["commercialUseApproved"] is False
    assert {warning["code"] for warning in exported["exportWarnings"]} >= {
        "commercial_use_review_required",
        "creator_approval_unverified",
        "license_unverified",
    }
    kinds = {asset["kind"] for asset in exported["assets"]}
    assert {
        "validated_motionjson_scene",
        "final_export_manifest",
        "export_validation_report",
        "export_quality_routing",
        "object_layer_pack",
        "remotion_plan",
        "preview_overlay",
        "contours_boxes",
        "website_package",
        "motionjson_export_zip",
    }.issubset(kinds)
    if exported["qualityRouting"]["preview"]["mp4Preview"]["status"] == "ready":
        assert "mp4_preview" in kinds

    layer_pack_asset = next(asset for asset in exported["assets"] if asset["kind"] == "object_layer_pack")
    status, _headers, pack_body = app.handle("GET", layer_pack_asset["contentUrl"])
    object_layer_pack = decode(pack_body)
    assert status == 200
    assert object_layer_pack["format"] == "motionjson.object_layer_pack.v0.1"
    assert object_layer_pack["selectedObjectIds"] == ["object_0"]
    assert object_layer_pack["objectCount"] == 1
    assert "plainJs" in object_layer_pack["snippets"]

    website_asset = next(asset for asset in exported["assets"] if asset["kind"] == "website_package")
    status, headers, website_body = app.handle("GET", website_asset["contentUrl"])
    assert status == 200
    assert headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(website_body)) as archive:
        website_names = archive.namelist()
        website_manifest = json.loads(archive.read("package_manifest.json").decode("utf-8"))
        website_pack = json.loads(archive.read("object_layer_pack.json").decode("utf-8"))
    assert "scene_graph.json" in website_names
    assert website_manifest["selectedObjectIds"] == ["object_0"]
    assert website_pack["selectedObjectIds"] == ["object_0"]

    zip_asset = next(asset for asset in exported["assets"] if asset["kind"] == "motionjson_export_zip")
    status, headers, zip_body = app.handle("GET", zip_asset["contentUrl"])
    assert status == 200
    assert headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(zip_body)) as archive:
        names = archive.namelist()
    assert {
        "scene_graph.json",
        "final_export_manifest.json",
        "validation_report.json",
        "quality_routing.json",
        "object_layer_pack.json",
        "remotion_export_plan.json",
        "website_package.zip",
    }.issubset(set(names))
    if exported["qualityRouting"]["preview"]["mp4Preview"]["status"] == "ready":
        assert "preview/preview.mp4" in names
    assert all(not Path(name).is_absolute() and ".." not in Path(name).parts for name in names)

    scene_asset = next(asset for asset in exported["assets"] if asset["kind"] == "validated_motionjson_scene")
    assert scene_asset["contentUrl"].startswith("/api/artifacts/")
    status, headers, scene_body = app.handle("GET", scene_asset["contentUrl"])
    assert status == 200
    assert headers["content-type"].startswith("application/json")
    scene = decode(scene_body)
    assert validate_document(scene) == []
    assert scene["objects"][0]["label"] == "Export Ball"
    assert "exportStatus" not in scene["objects"][0]
    assert str(tmp_path) not in scene_body.decode("utf-8")
    assert "projects/" not in scene_body.decode("utf-8")

    manifest_asset = next(asset for asset in exported["assets"] if asset["kind"] == "final_export_manifest")
    status, _headers, manifest_body = app.handle("GET", manifest_asset["contentUrl"])
    manifest = decode(manifest_body)
    assert status == 200
    assert validate_document(manifest) == []
    assert manifest["source"]["directory"] == "."
    assert manifest["validation"]["ok"] is True
    assert manifest["provenance"]["aiUsage"] == "none"
    assert manifest["qualityRouting"]["format"] == "motionjson.export_quality_routing.v0.1"
    assert manifest["objectLayerPack"]["format"] == "motionjson.object_layer_pack.v0.1"
    assert manifest["objectLayerPack"]["selectedObjectIds"] == ["object_0"]
    assert manifest["qualityRouting"]["objects"][0]["selectedOutput"] in {
        "raster_alpha_sequence",
        "hybrid_vector_silhouette_plus_raster",
    }
    assert manifest["qualityRouting"]["preview"]["mp4Preview"]["status"] in {"ready", "unavailable", "error", "skipped"}
    assert {warning["code"] for warning in manifest["exportWarnings"]} >= {
        "commercial_use_review_required",
        "creator_approval_unverified",
        "license_unverified",
    }

    routing_asset = next(asset for asset in exported["assets"] if asset["kind"] == "export_quality_routing")
    assert routing_asset["metadata"]["qualityRouting"]["format"] == "motionjson.export_quality_routing.v0.1"
    assert routing_asset["metadata"]["rightsSummary"]["format"] == "motionjson.export_rights_summary.v0.1"
    status, _headers, routing_body = app.handle("GET", routing_asset["contentUrl"])
    routing = decode(routing_body)
    assert status == 200
    assert routing["format"] == "motionjson.export_quality_routing.v0.1"
    assert routing["objects"][0]["label"] == "Export Ball"
    assert str(tmp_path) not in routing_body.decode("utf-8")
    assert "projects/" not in routing_body.decode("utf-8")

    conn = app.connection()
    try:
        zip_lineage = list_asset_lineage(conn, asset_id=zip_asset["id"])
        zip_rights = list_asset_rights(conn, asset_id=zip_asset["id"])
    finally:
        conn.close()
    assert any(row["operation"] == "validated_motionjson_export" and row["source_asset_id"] == video["id"] for row in zip_lineage)
    assert any(json.loads(row["rights_json"])["license"] == "user_uploaded_unverified" for row in zip_rights)

    imported_scene = tmp_path / "imported_scene_graph.json"
    imported_scene.write_bytes(scene_body)
    status, _headers, body = app.handle(
        "POST",
        f"/api/projects/{project['id']}/imports/motionjson",
        body=json.dumps({"path": str(imported_scene)}).encode("utf-8"),
    )
    imported = decode(body)["import"]
    assert status == 200
    assert imported["validation"]["ok"] is True
    assert imported["job"]["type"] == "motionjson_import"
    assert imported["job"]["status"] == "succeeded"
    assert "projects/" not in body.decode("utf-8")
    assert str(tmp_path) not in body.decode("utf-8")

    status, _headers, body = app.handle("GET", f"/api/jobs/{imported['job']['id']}/review")
    assert status == 200
    imported_review = decode(body)["review"]
    assert imported_review["objects"][0]["objectId"] == "object_0"
    assert imported_review["objects"][0]["label"] == "Export Ball"


def test_local_ui_review_and_export_accept_legacy_boolean_rights(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    _project, _video, job = create_completed_mock_job(app, "Legacy Rights Export")
    scene_asset = scene_asset_for_job(app, job)
    storage = app.storage()
    scene = json.loads(storage.load_bytes(scene_asset["storage_key"]).decode("utf-8"))
    scene["objects"][0]["rights"] = {
        "sourceAttribution": True,
        "license": "user_uploaded_placeholder",
        "notes": "Rights and likeness review required before remixing third-party footage.",
    }
    storage.save_bytes(scene_asset["storage_key"], json.dumps(scene).encode("utf-8"), content_type="application/json")

    status, _headers, body = app.handle("GET", f"/api/jobs/{job['id']}/review")
    review = decode(body)["review"]
    assert status == 200
    assert review["objects"][0]["rightsSummary"]["sourceAttribution"]["required"] is True
    assert review["rightsSummary"]["summary"]["attributionRequired"] == ["object_0"]
    assert "attribution_required" in {warning["code"] for warning in review["rightsSummary"]["warnings"]}

    status, _headers, body = app.handle(
        "POST",
        f"/api/jobs/{job['id']}/exports",
        body=json.dumps({"preset": "compact", "includeMasks": False, "includeContours": False, "includePreview": False}).encode("utf-8"),
    )
    exported = decode(body)["export"]
    assert status == 200
    assert exported["validation"]["ok"] is True
    assert exported["rightsSummary"]["summary"]["attributionRequired"] == ["object_0"]
    assert "attribution_required" in {warning["code"] for warning in exported["exportWarnings"]}


def test_local_ui_motionjson_import_missing_path_returns_redacted_bad_request(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)

    status, _headers, body = app.handle("POST", "/api/projects", body=json.dumps({"name": "Import Project"}).encode("utf-8"))
    project = decode(body)["project"]
    missing_path = tmp_path / "o'brien missing folder" / "secret scene.json"

    status, _headers, body = app.handle(
        "POST",
        f"/api/projects/{project['id']}/imports/motionjson",
        body=json.dumps({"path": str(missing_path)}).encode("utf-8"),
    )

    assert status == 400
    assert "does not exist" in decode(body)["error"]
    assert "[LOCAL_PATH_REDACTED]" in body.decode("utf-8")
    assert str(tmp_path) not in body.decode("utf-8")
    assert "secret scene" not in body.decode("utf-8")
    assert "brien" not in body.decode("utf-8")


def test_local_ui_motionjson_import_rejects_directory_symlinks_before_registration(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)

    status, _headers, body = app.handle("POST", "/api/projects", body=json.dumps({"name": "Import Symlink Project"}).encode("utf-8"))
    project = decode(body)["project"]
    import_dir = tmp_path / "motionjson-result"
    import_dir.mkdir()
    secret = tmp_path / "secret.json"
    secret.write_text('{"secret": "SUPER_SECRET"}\n', encoding="utf-8")
    (import_dir / "linked_secret.json").symlink_to(secret)

    status, _headers, body = app.handle(
        "POST",
        f"/api/projects/{project['id']}/imports/motionjson",
        body=json.dumps({"path": str(import_dir)}).encode("utf-8"),
    )

    assert status == 400
    assert "symlinks" in decode(body)["error"]
    assert "SUPER_SECRET" not in body.decode("utf-8")
    status, _headers, body = app.handle("GET", f"/api/jobs?projectId={project['id']}")
    assert status == 200
    assert decode(body)["jobs"] == []


def test_local_ui_imported_svg_is_not_served_as_public_same_origin_content(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)

    status, _headers, body = app.handle("POST", "/api/projects", body=json.dumps({"name": "Import SVG Project"}).encode("utf-8"))
    project = decode(body)["project"]
    svg_path = tmp_path / "preview.svg"
    svg_path.write_text('<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>\n', encoding="utf-8")

    status, _headers, body = app.handle(
        "POST",
        f"/api/projects/{project['id']}/imports/motionjson",
        body=json.dumps({"path": str(svg_path)}).encode("utf-8"),
    )
    imported = decode(body)["import"]
    assert status == 200
    assert imported["validation"]["ok"] is False
    assert imported["assets"][0]["kind"] == "imported_preview"
    assert imported["assets"][0]["content_type"] == "image/svg+xml"
    assert "contentUrl" not in imported["assets"][0]

    status, _headers, body = app.handle("GET", f"/api/artifacts/{imported['assets'][0]['id']}/content")
    assert status == 404
    assert "<script>" not in body.decode("utf-8")


def test_local_ui_export_preview_svg_escapes_corrected_labels(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    _project, _video, job = create_completed_mock_job(app, "Escaped Preview Project")
    malicious_label = "Ball </text><script>alert(1)</script>"

    status, _headers, body = app.handle(
        "POST",
        f"/api/jobs/{job['id']}/track-edits",
        body=json.dumps({"operation": "relabel", "objectId": "object_0", "label": malicious_label}).encode("utf-8"),
    )
    assert status == 200
    status, _headers, body = app.handle(
        "POST",
        f"/api/jobs/{job['id']}/exports",
        body=json.dumps({"preset": "compact", "includePreview": True}).encode("utf-8"),
    )
    assert status == 200
    exported = decode(body)["export"]
    preview_asset = next(asset for asset in exported["assets"] if asset["kind"] == "preview_overlay")
    status, headers, svg_body = app.handle("GET", preview_asset["contentUrl"])

    assert status == 200
    assert headers["content-type"].startswith("image/svg+xml")
    svg = svg_body.decode("utf-8")
    assert "<script" not in svg
    assert "&lt;/text&gt;&lt;script&gt;alert(1)&lt;/script&gt;" in svg


def test_local_ui_export_raw_json_redacts_windows_paths(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    _project, _video, job = create_completed_mock_job(app, "Windows Path Export Project")
    asset = scene_asset_for_job(app, job)
    storage = app.storage()
    scene = json.loads(storage.load_bytes(asset["storage_key"]).decode("utf-8"))
    obj = scene["objects"][0]
    obj["asset"] = r"C:\Users\Alice\secret\cutout.png"
    obj["assets"]["cutoutPattern"] = r"C:\Users\Alice\secret\cutouts\frame_%06d.png"
    obj["assets"]["production"] = {
        "assets": {
            "webpSpriteAtlas": {"status": "ready", "path": r"\\server\share\atlas.webp", "bytes": 100},
            "transparentWebm": {"status": "ready", "path": r"C:\Users\Alice\secret\object.webm", "bytes": 40},
        }
    }
    storage.save_bytes(asset["storage_key"], json.dumps(scene).encode("utf-8"), content_type="application/json")

    status, _headers, body = app.handle(
        "POST",
        f"/api/jobs/{job['id']}/exports",
        body=json.dumps({"preset": "debug", "includeContours": True, "includePreview": False}).encode("utf-8"),
    )
    assert status == 200
    exported = decode(body)["export"]

    for kind in {"validated_motionjson_scene", "final_export_manifest", "export_quality_routing"}:
        artifact = next(asset for asset in exported["assets"] if asset["kind"] == kind)
        status, _headers, artifact_body = app.handle("GET", artifact["contentUrl"])
        text = artifact_body.decode("utf-8")
        assert status == 200
        assert "[LOCAL_PATH_REDACTED]" in text
        assert "C:" not in text
        assert "Alice" not in text
        assert "server" not in text
        assert "projects/" not in text


def test_local_ui_export_excludes_pending_add_object_until_assets_are_materialized(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    _project, _video, job = create_completed_mock_job(app, "Pending Add Object Project")

    status, _headers, body = app.handle(
        "POST",
        f"/api/jobs/{job['id']}/track-edits",
        body=json.dumps(
            {
                "operation": "add-object",
                "objectId": "object_1",
                "label": "Missing ball",
                "prompt": {"type": "box", "frame": 1, "x": 8, "y": 9, "w": 20, "h": 18},
            }
        ).encode("utf-8"),
    )
    assert status == 200

    status, _headers, body = app.handle(
        "POST",
        f"/api/jobs/{job['id']}/validate",
        body=json.dumps({"preset": "compact"}).encode("utf-8"),
    )
    validation = decode(body)
    assert status == 200
    assert validation["includedObjectIds"] == ["object_0"]
    assert validation["excludedObjectIds"] == ["object_1"]
    assert validation["diagnostics"][0]["code"] == "correction_track_not_materialized"

    status, _headers, body = app.handle(
        "POST",
        f"/api/jobs/{job['id']}/exports",
        body=json.dumps({"preset": "compact"}).encode("utf-8"),
    )
    exported = decode(body)["export"]
    assert status == 200
    assert exported["includedObjectIds"] == ["object_0"]
    assert exported["excludedObjectIds"] == ["object_1"]
    scene_asset = next(asset for asset in exported["assets"] if asset["kind"] == "validated_motionjson_scene")
    status, _headers, scene_body = app.handle("GET", scene_asset["contentUrl"])
    scene = decode(scene_body)
    assert status == 200
    assert [item["id"] for item in scene["objects"]] == ["object_0"]


def test_local_ui_export_validation_failure_does_not_register_public_export_assets(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    _project, _video, job = create_completed_mock_job(app, "Invalid Export Project")
    scene_asset = scene_asset_for_job(app, job)
    scene = json.loads(app.storage().load_bytes(scene_asset["storage_key"]).decode("utf-8"))
    scene["source"]["width"] = 0
    app.storage().save_bytes(
        scene_asset["storage_key"],
        (json.dumps(scene, sort_keys=True) + "\n").encode("utf-8"),
        content_type="application/json",
    )

    status, _headers, body = app.handle(
        "POST",
        f"/api/jobs/{job['id']}/validate",
        body=json.dumps({"preset": "compact"}).encode("utf-8"),
    )
    validation = decode(body)
    assert status == 200
    assert validation["validation"]["ok"] is False
    assert validation["validation"]["issueCount"] > 0

    status, _headers, body = app.handle(
        "POST",
        f"/api/jobs/{job['id']}/exports",
        body=json.dumps({"preset": "compact"}).encode("utf-8"),
    )
    assert status == 400
    assert "validation failed" in decode(body)["error"]

    conn = app.connection()
    try:
        assets = list_assets_for_job(conn, project_id=job["project_id"], source_job_id=job["id"])
    finally:
        conn.close()
    export_kinds = {asset["kind"] for asset in assets}
    assert "validated_motionjson_scene" not in export_kinds
    assert "motionjson_export_zip" not in export_kinds


def test_local_ui_api_run_endpoint_executes_current_simple_payload(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)

    status, _headers, body = app.handle("POST", "/api/projects", body=json.dumps({"name": "UI Project"}).encode("utf-8"))
    project = decode(body)["project"]
    status, _headers, body = app.handle(
        "POST",
        "/api/videos",
        body=json.dumps({"projectId": project["id"], "path": str(demo_video())}).encode("utf-8"),
    )
    video = decode(body)["video"]
    status, _headers, body = app.handle(
        "POST",
        "/api/jobs",
        body=json.dumps({"projectId": project["id"], "videoId": video["id"], "maskProvider": "mock", "maxFrames": 1}).encode("utf-8"),
    )
    job = decode(body)["job"]
    assert status == 200
    assert job["status"] == "pending"
    assert job["percent"] == 0

    status, _headers, body = app.handle("POST", f"/api/jobs/{job['id']}/run")
    assert status == 200
    assert decode(body)["worker"]["status"] == "started"
    finished = wait_for_job(app, job["id"])
    assert finished["status"] == "succeeded"


def test_local_ui_artifact_review_surfaces_fallback_without_private_storage(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)

    status, _headers, body = app.handle("POST", "/api/projects", body=json.dumps({"name": "UI Project"}).encode("utf-8"))
    project = decode(body)["project"]
    status, _headers, body = app.handle(
        "POST",
        "/api/videos",
        body=json.dumps({"projectId": project["id"], "path": str(demo_video())}).encode("utf-8"),
    )
    video = decode(body)["video"]
    status, _headers, body = app.handle(
        "POST",
        "/api/jobs",
        body=json.dumps({"projectId": project["id"], "videoId": video["id"], "maxFrames": 1}).encode("utf-8"),
    )
    job = decode(body)["job"]
    fallback_payload = {
        "format": "motionjson.raster_fallback_diagnostics.v0.1",
        "diagnostics": [
            {
                "reasonCode": "masks_too_large_whole_frame",
                "message": "storage_key=projects/private/source.mp4",
                "metadata": {"sourcePath": str(tmp_path / "private-source.mp4")},
                "suggestedFixes": ["Use a tighter point or box prompt."],
            },
            {
                "reasonCode": "plain_private_artifact_text",
                "message": "failed to read projects/private/source.mp4",
                "suggestedFixes": ["Do not expose projects/private/source.mp4 in public review payloads."],
            }
        ],
        "summary": {"fallbackReasonCounts": {"masks_too_large_whole_frame": 1}},
    }
    conn = app.connection()
    try:
        register_generated_asset(
            conn,
            storage=app.storage(),
            project_id=project["id"],
            source_job_id=job["id"],
            kind="fallback_diagnostics",
            data=json.dumps(fallback_payload).encode("utf-8"),
            rel_path="fallback_diagnostics.json",
            content_type="application/json",
            metadata={"storage_key": "projects/private/fallback.json", "note": "safe"},
        )
    finally:
        conn.close()

    status, _headers, body = app.handle("GET", f"/api/jobs/{job['id']}/artifacts")
    payload = decode(body)

    assert status == 200
    assert payload["review"]["rasterFallback"] is True
    assert payload["review"]["rasterFallbackReason"] == "masks_too_large_whole_frame"
    assert payload["review"]["vectorUnavailableReason"] == "masks_too_large_whole_frame"
    assert payload["review"]["fallbackDiagnostics"][0]["message"] == "[REDACTED]"
    assert payload["review"]["fallbackDiagnostics"][1]["message"] == "failed to read [STORAGE_KEY_REDACTED]"
    assert "storage_key" not in body.decode("utf-8")
    assert "projects/private" not in body.decode("utf-8")
    assert str(tmp_path) not in body.decode("utf-8")


def test_local_ui_api_returns_not_found_for_missing_api_route(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage")

    status, _headers, body = app.handle("GET", "/api/missing")

    assert status == 404
    assert decode(body)["error"] == "route not found"


def test_local_ui_local_user_handles_concurrent_create_race(tmp_path, monkeypatch):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage")
    conn = app.connection()
    original_register_user = ui_server.register_user
    calls = []

    def racing_register_user(conn, *, email, password):
        calls.append(email)
        original_register_user(conn, email=email, password=password)
        raise sqlite3.IntegrityError("UNIQUE constraint failed: users.email")

    monkeypatch.setattr(ui_server, "register_user", racing_register_user)
    try:
        user = app._local_user(conn)
    finally:
        conn.close()

    assert calls == [LOCAL_UI_EMAIL]
    assert user["email"] == LOCAL_UI_EMAIL


def test_local_ui_video_upload_rejects_missing_path(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage")
    status, _headers, body = app.handle("POST", "/api/projects", body=json.dumps({"name": "UI Project"}).encode("utf-8"))
    project_id = decode(body)["project"]["id"]

    status, _headers, body = app.handle(
        "POST",
        "/api/videos",
        body=json.dumps({"projectId": project_id, "path": str(tmp_path / "missing.mp4")}).encode("utf-8"),
    )

    assert status == 400
    assert "existing local file" in decode(body)["error"]
