from __future__ import annotations

import json
import sqlite3
import zipfile
from pathlib import Path

import pytest

from motionjson.backend.assets import list_assets_for_job, register_generated_asset, register_upload
from motionjson.backend.auth import register_user
from motionjson.backend.db import initialize_database
from motionjson.backend.jobs import enqueue_export_job, enqueue_extract_job, list_job_events, record_job_event
from motionjson.backend.projects import create_project
from motionjson.backend.queue import mark_failed
from motionjson.backend.readiness import job_readiness
from motionjson.backend.stale_jobs import (
    asset_preparation_frame_timeout_seconds,
    reconcile_stale_asset_preparation_job,
    worker_heartbeat_stale_seconds,
)
from motionjson.backend.usage import summarize_usage
import motionjson.backend.worker as worker_module
from motionjson.backend.partial_review import synthesize_partial_review_payload
from motionjson.backend.worker import (
    _raise_if_requested_cuda_not_loaded,
    _server_runtime_value,
    _ui_discovery_provider,
    validate_extract_provider_policy,
    worker_once,
)
from motionjson.backend.models import ProviderPolicyError
from motionjson.providers.base import ProviderConfigError
from motionjson.providers.discovery import (
    MockObjectDiscoveryProvider,
    SAM2AutomaticProposalDiscoveryProvider,
    SAM3ConceptDiscoveryProvider,
    SamAutoMasksDiscoveryProvider,
)
from motionjson.providers.local_storage import LocalStorageProvider


def backend(tmp_path):
    conn = sqlite3.connect(tmp_path / "backend.sqlite")
    conn.row_factory = sqlite3.Row
    initialize_database(conn)
    storage = LocalStorageProvider(tmp_path / "storage")
    user = register_user(conn, email="worker@example.com", password="pw")
    project = create_project(conn, user_id=user["id"], name="Worker Project")
    return conn, storage, user, project


def demo_video() -> Path:
    return Path(__file__).resolve().parents[1] / "examples" / "demo_red_ball.mp4"


def asset_rel_path(asset: dict) -> str | None:
    metadata = json.loads(asset.get("metadata_json") or "{}")
    value = metadata.get("rel_path")
    return value if isinstance(value, str) else None


def test_worker_resolves_public_redacted_local_paths_from_server_runtime_settings():
    assert _server_runtime_value("[LOCAL_PATH_REDACTED]", "/content/sam2/checkpoint.pt") == "/content/sam2/checkpoint.pt"
    assert _server_runtime_value("", "configs/sam2.yaml") == "configs/sam2.yaml"
    assert _server_runtime_value("<redacted:sam2-local>", "cuda") == "cuda"
    assert _server_runtime_value("configs/sam2.yaml", "server-side.yaml") == "configs/sam2.yaml"


def test_worker_routes_non_mock_auto_discovery_to_sam2_adapter():
    provider, message, requires_mock = _ui_discovery_provider(
        "auto_object_proposals",
        {"providerPreference": "sam2-local"},
    )
    mock_provider, _mock_message, mock_requires = _ui_discovery_provider(
        "auto_object_proposals",
        {"mock": True},
    )
    sam_auto_provider, _sam_message, sam_requires = _ui_discovery_provider("sam_auto_masks", {})

    assert isinstance(provider, SAM2AutomaticProposalDiscoveryProvider)
    assert "SAM2 automatic" in message
    assert requires_mock is False
    assert isinstance(mock_provider, MockObjectDiscoveryProvider)
    assert mock_requires is True
    assert isinstance(sam_auto_provider, SamAutoMasksDiscoveryProvider)
    assert sam_requires is False


def test_worker_routes_non_mock_sam3_discovery_to_local_adapter():
    provider, message, requires_mock = _ui_discovery_provider("sam3_concept", {"concept": "red ball"})
    mock_provider, _mock_message, mock_requires = _ui_discovery_provider("sam3_concept", {"mock": True, "concept": "red ball"})

    assert isinstance(provider, SAM3ConceptDiscoveryProvider)
    assert "SAM3 concept runtime" in message
    assert requires_mock is False
    assert isinstance(mock_provider, SAM3ConceptDiscoveryProvider)
    assert mock_requires is True


def test_sam3_cuda_requested_requires_cuda_runtime_proof():
    with pytest.raises(ProviderConfigError, match="gpu_device_mismatch"):
        _raise_if_requested_cuda_not_loaded(
            "sam3-local",
            {"loadedOnCuda": False, "deviceActual": "cpu", "runtimeProofStatus": "verified"},
            device_requested="cuda:0",
        )

    _raise_if_requested_cuda_not_loaded(
        "sam3-local",
        {"loadedOnCuda": True, "deviceActual": "cuda:0", "runtimeProofStatus": "verified"},
        device_requested="cuda:0",
    )
    _raise_if_requested_cuda_not_loaded("sam3-local", {"loadedOnMps": True, "deviceActual": "mps"}, device_requested="mps")


def test_extract_worker_runs_threshold_and_registers_manifest_assets(tmp_path):
    conn, storage, user, project = backend(tmp_path)
    upload = register_upload(conn, storage=storage, user_id=user["id"], project_id=project["id"], path=demo_video(), kind="source_video")
    job = enqueue_extract_job(
        conn,
        user_id=user["id"],
        project_id=project["id"],
        asset_id=upload["id"],
        mask_provider="threshold",
        max_frames=3,
    )

    result = worker_once(conn, storage=storage)
    assets = list_assets_for_job(conn, project_id=project["id"], source_job_id=job["id"])
    events = list_job_events(conn, job_id=job["id"])
    result_payload = json.loads(result["result_json"])
    kinds = {asset["kind"] for asset in assets}
    usage = summarize_usage(conn, project_id=project["id"])

    assert result["status"] == "succeeded"
    assert {"scene_graph", "object_manifest", "web_manifest"}.issubset(kinds)
    assert result_payload["readiness"]["workerComplete"] is True
    assert result_payload["readiness"]["artifactsRegistered"] is True
    assert result_payload["readiness"]["reviewPayloadReady"] is True
    assert result_payload["readiness"]["previewToolsReady"] is True
    assert result_payload["readiness"]["readyForReview"] is True
    assert {
        "worker_complete",
        "artifacts_registered",
        "review_payload_ready",
        "preview_tools_ready",
        "ready_for_review",
    }.issubset({event["event_type"] for event in events})
    assert usage["totals"]["frames_processed"]["frame"] == 3.0
    assert usage["totals"]["objects_extracted"]["object"] == 1.0
    assert usage["totals"]["latency_ms"]["ms"] >= 0
    assert usage["costDashboard"]["schema"] == "motionjson.backend_cost_dashboard.v0.1"


def test_extract_worker_runs_mock_provider_without_network(tmp_path):
    conn, storage, user, project = backend(tmp_path)
    upload = register_upload(conn, storage=storage, user_id=user["id"], project_id=project["id"], path=demo_video(), kind="source_video")
    job = enqueue_extract_job(
        conn,
        user_id=user["id"],
        project_id=project["id"],
        asset_id=upload["id"],
        mask_provider="mock",
        max_frames=2,
    )

    result = worker_once(conn, storage=storage)
    assets = list_assets_for_job(conn, project_id=project["id"], source_job_id=job["id"])

    assert result["status"] == "succeeded"
    assert any(asset["kind"] == "scene_graph" for asset in assets)


def test_extract_worker_synthesizes_partial_review_payload_after_object_failure(tmp_path, monkeypatch):
    conn, storage, user, project = backend(tmp_path)
    upload = register_upload(conn, storage=storage, user_id=user["id"], project_id=project["id"], path=demo_video(), kind="source_video")
    job = enqueue_extract_job(
        conn,
        user_id=user["id"],
        project_id=project["id"],
        asset_id=upload["id"],
        mask_provider="mock",
        max_frames=2,
    )

    def fake_run_pipeline(*, out_dir, **_kwargs):
        out = Path(out_dir)
        object_dir = out / "objects" / "object_done"
        (object_dir / "cutouts").mkdir(parents=True, exist_ok=True)
        (out / "masks" / "object_done").mkdir(parents=True, exist_ok=True)
        (object_dir / "cutouts" / "cutout_000001.png").write_bytes(b"png")
        (out / "masks" / "object_done" / "mask_000001.png").write_bytes(b"png")
        manifest = {
            "schema": "motionjson.object_manifest.v0.1",
            "objectId": "object_done",
            "label": "Completed object",
            "renderMode": "raster_alpha_sequence",
            "motion": [
                {
                    "frame": 1,
                    "sampleIndex": 0,
                    "sourceFrameIndex": 0,
                    "outIndex": 0,
                    "t": 0.0,
                    "sampleFps": 6,
                    "visible": True,
                    "x": 4,
                    "y": 5,
                    "w": 20,
                    "h": 21,
                    "bbox": [4, 5, 20, 21],
                    "sourceBbox": [4, 5, 20, 21],
                    "maskShape": [64, 96],
                    "maskArea": 420,
                    "asset": "objects/object_done/cutouts/cutout_000001.png",
                    "mask": "masks/object_done/mask_000001.png",
                    "anchor": [0.5, 0.5],
                    "opacity": 1.0,
                    "scale": 1.0,
                    "rotation": 0.0,
                    "contourPoints": [[4, 5], [24, 5], [22, 26], [4, 25]],
                    "outlineStatus": "real_outline",
                    "outlineSource": "mask_contour",
                }
            ],
            "frames": [],
            "frameMap": [{"sampleIndex": 0, "sourceFrameIndex": 0, "t": 0.0, "frame": 1, "outIndex": 0, "sampleFps": 6}],
            "quality": {"qualityStatus": "needs_review"},
            "recommendedOutput": "raster_alpha_sequence",
            "discovery": {"candidateProvider": "mock", "exportStatus": "review_pending"},
            "rights": {"commercialUseStatus": "review_required"},
        }
        (object_dir / "object_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        failed_dir = out / "objects" / "object_failed"
        failed_dir.mkdir(parents=True, exist_ok=True)
        (failed_dir / "failure.json").write_text(
            json.dumps(
                {
                    "format": "motionjson.object_failure.v0.1",
                    "objectId": "object_failed",
                    "reasonCode": "object_extraction_failed",
                    "message": "object_failed exploded",
                }
            ),
            encoding="utf-8",
        )
        raise RuntimeError("object_failed exploded")

    monkeypatch.setattr(worker_module, "run_pipeline", fake_run_pipeline)

    result = worker_once(conn, storage=storage, max_attempts=1)
    assets = list_assets_for_job(conn, project_id=project["id"], source_job_id=job["id"])
    rel_paths = {asset_rel_path(asset) for asset in assets}
    kinds = {asset["kind"] for asset in assets}
    events = list_job_events(conn, job_id=job["id"])
    partial_asset = next(asset for asset in assets if asset["kind"] == "partial_review")
    partial_payload = json.loads(storage.load_bytes(partial_asset["storage_key"]).decode("utf-8"))
    scene_asset = next(asset for asset in assets if asset["kind"] == "scene_graph")
    scene = json.loads(storage.load_bytes(scene_asset["storage_key"]).decode("utf-8"))
    readiness = job_readiness(
        rel_paths=[path for path in rel_paths if path],
        worker_complete=True,
        artifacts_registered=True,
        job_active=False,
        review_summary={"trackCount": 1, "pendingTrackCount": 1, "exportableTrackCount": 0},
    )

    assert result["status"] == "failed"
    assert {"scene_graph", "web_manifest", "track_summary", "fallback_diagnostics", "partial_review"}.issubset(kinds)
    assert {
        "scene_graph.json",
        "web_asset_manifest.json",
        "tracks.json",
        "fallback_diagnostics.json",
        "partial_review.json",
        "preview/canvas_player.html",
        "preview/object_selection_workflow.html",
        "preview/object_selection_workflow.js",
        "preview/timeline_editor.html",
        "preview/timeline_editor.js",
    }.issubset(rel_paths)
    assert scene["partialSuccess"] is True
    assert scene["objects"][0]["id"] == "object_done"
    assert scene["partialReview"]["failedObjectId"] == "object_failed"
    assert partial_payload["reviewableObjectIds"] == ["object_done"]
    assert readiness["reviewPayloadReady"] is True
    assert readiness["previewToolsReady"] is True
    assert readiness["readyForReview"] is True
    assert any(event["event_type"] == "partial_review_payload_ready" for event in events)
    assert any(event["event_type"] == "partial_preview_tools_ready" for event in events)


def test_partial_review_synthesis_does_not_overwrite_complete_root_payload(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    scene_path = out / "scene_graph.json"
    manifest_path = out / "web_asset_manifest.json"
    tracks_path = out / "tracks.json"
    scene_path.write_text(json.dumps({"schema": "motionjson.scene_graph.v0.1", "objects": [{"id": "complete"}]}), encoding="utf-8")
    manifest_path.write_text(json.dumps({"schema": "motionjson.web_asset_manifest.v0.1"}), encoding="utf-8")
    tracks_path.write_text(json.dumps({"tracks": [{"objectId": "complete"}]}), encoding="utf-8")
    object_dir = out / "objects" / "partial"
    object_dir.mkdir(parents=True)
    (object_dir / "object_manifest.json").write_text(
        json.dumps({"objectId": "partial", "motion": [{"frame": 0, "visible": True}]}),
        encoding="utf-8",
    )

    result = synthesize_partial_review_payload(
        out,
        job_id="job_complete",
        diagnostic={"reasonCode": "late_failure", "message": "late failure"},
    )

    assert result["status"] == "skipped"
    assert result["reasonCode"] == "root_review_payload_exists"
    assert json.loads(scene_path.read_text(encoding="utf-8"))["objects"][0]["id"] == "complete"
    assert not (out / "partial_review.json").exists()


def test_export_worker_packages_existing_extraction_with_no_ai_usage(tmp_path):
    conn, storage, user, project = backend(tmp_path)
    upload = register_upload(conn, storage=storage, user_id=user["id"], project_id=project["id"], path=demo_video(), kind="source_video")
    extract = enqueue_extract_job(conn, user_id=user["id"], project_id=project["id"], asset_id=upload["id"], mask_provider="threshold", max_frames=2)
    assert worker_once(conn, storage=storage)["status"] == "succeeded"
    export = enqueue_export_job(
        conn,
        user_id=user["id"],
        project_id=project["id"],
        source_job_id=extract["id"],
        format="website-zip",
        object_ids=["object_0"],
    )

    result = worker_once(conn, storage=storage)
    package_assets = [asset for asset in list_assets_for_job(conn, project_id=project["id"], source_job_id=export["id"]) if asset["kind"] == "website_package"]
    package_path = tmp_path / "package.zip"
    package_path.write_bytes(storage.load_bytes(package_assets[0]["storage_key"]))

    with zipfile.ZipFile(package_path) as archive:
        manifest = json.loads(archive.read("package_manifest.json"))

    assert result["status"] == "succeeded"
    assert json.loads(result["result_json"])["selectedObjectIds"] == ["object_0"]
    assert manifest["aiUsage"] == "none"
    assert manifest["selectedObjectIds"] == ["object_0"]
    assert manifest["objectLayerPack"] == "object_layer_pack.json"
    assert summarize_usage(conn, project_id=project["id"])["totals"]["exports_produced"]["export"] == 1.0


def test_queue_failure_records_events_and_usage_failure(tmp_path):
    conn, storage, user, project = backend(tmp_path)
    upload = register_upload(conn, storage=storage, user_id=user["id"], project_id=project["id"], path=demo_video(), kind="source_video")
    job = enqueue_extract_job(conn, user_id=user["id"], project_id=project["id"], asset_id=upload["id"], mask_provider="external", max_frames=1)

    result = worker_once(conn, storage=storage, max_attempts=1)
    events = list_job_events(conn, job_id=job["id"])
    usage = summarize_usage(conn, project_id=project["id"])

    assert result["status"] == "failed"
    assert any(event["event_type"] == "failed" for event in events)
    assert usage["totals"]["job_failures"]["failure"] == 1.0


def test_queue_retry_then_failure_path(tmp_path):
    conn, storage, user, project = backend(tmp_path)
    upload = register_upload(conn, storage=storage, user_id=user["id"], project_id=project["id"], path=demo_video(), kind="source_video")
    job = enqueue_extract_job(conn, user_id=user["id"], project_id=project["id"], asset_id=upload["id"], mask_provider="threshold", max_frames=1)
    conn.execute("UPDATE jobs SET status = 'running' WHERE id = ?", (job["id"],))
    first = mark_failed(conn, job_id=job["id"], error="temporary", retry_delay_seconds=0, max_attempts=2)
    second = mark_failed(conn, job_id=job["id"], error="permanent", retry_delay_seconds=0, max_attempts=2)

    assert first["status"] == "pending"
    assert second["status"] == "failed"


def test_asset_preparation_watchdog_timeout_env_overrides(monkeypatch):
    monkeypatch.setenv("MOTIONJSON_ASSET_PREP_FRAME_TIMEOUT_SECONDS", "360")
    monkeypatch.setenv("MOTIONJSON_WORKER_HEARTBEAT_STALE_SECONDS", "420")
    assert asset_preparation_frame_timeout_seconds() == 360.0
    assert worker_heartbeat_stale_seconds() == 420.0

    monkeypatch.setenv("MOTIONJSON_ASSET_PREP_FRAME_TIMEOUT_SECONDS", "5")
    monkeypatch.setenv("MOTIONJSON_WORKER_HEARTBEAT_STALE_SECONDS", "bad")
    assert asset_preparation_frame_timeout_seconds() == 30.0
    assert worker_heartbeat_stale_seconds() == 240.0


def test_reconcile_stale_asset_preparation_fails_running_job(tmp_path):
    conn, storage, user, project = backend(tmp_path)
    upload = register_upload(conn, storage=storage, user_id=user["id"], project_id=project["id"], path=demo_video(), kind="source_video")
    job = enqueue_extract_job(conn, user_id=user["id"], project_id=project["id"], asset_id=upload["id"], mask_provider="sam3-local", max_frames=48)
    stale_at = "2026-06-03T04:33:51+00:00"
    conn.execute("UPDATE jobs SET status = 'running', updated_at = ? WHERE id = ?", (stale_at, job["id"]))
    conn.execute("UPDATE queue_items SET status = 'running' WHERE job_id = ?", (job["id"],))
    conn.execute("UPDATE job_events SET created_at = ? WHERE job_id = ?", ("2026-06-03T04:26:56+00:00", job["id"]))
    conn.commit()
    event = record_job_event(
        conn,
        job_id=job["id"],
        event_type="progress",
        message="prepared raster asset frame 1/48 for sam3_grid_024",
        metadata={
            "stage": "asset_preparation",
            "status": "running",
            "progress": {"overallRatio": 0.73, "current": 1, "total": 48},
            "metadata": {"objectId": "sam3_grid_024"},
        },
    )
    conn.execute("UPDATE job_events SET created_at = ? WHERE id = ?", (stale_at, event["id"]))
    conn.commit()

    reconciled = reconcile_stale_asset_preparation_job(
        conn,
        job_id=job["id"],
        now="2026-06-03T04:45:37+00:00",
        threshold_seconds=240,
    )
    events = list_job_events(conn, job_id=job["id"])
    stalled_event = next(event for event in events if event["event_type"] == "worker_heartbeat_stale")
    stalled_metadata = json.loads(stalled_event["metadata_json"])
    queue_row = conn.execute("SELECT status FROM queue_items WHERE job_id = ?", (job["id"],)).fetchone()

    assert reconciled["status"] == "failed"
    assert reconciled["attempts"] == 1
    assert "after frame 1/48 for sam3_grid_024" in reconciled["error"]
    assert queue_row["status"] == "failed"
    assert stalled_metadata["reasonCode"] == "worker_heartbeat_stale"
    assert stalled_metadata["compatibilityReasonCode"] == "asset_preparation_stalled"
    assert stalled_metadata["phase"] == "asset_preparation"
    assert stalled_metadata["objectId"] == "sam3_grid_024"
    assert stalled_metadata["preparedFrames"] == 1
    assert stalled_metadata["totalFrames"] == 48
    assert stalled_metadata["artifactsAvailable"] is False
    assert any(event["event_type"] == "failed" for event in events)


def test_reconcile_worker_heartbeat_stale_with_partial_objects_succeeds_for_review(tmp_path):
    conn, storage, user, project = backend(tmp_path)
    upload = register_upload(conn, storage=storage, user_id=user["id"], project_id=project["id"], path=demo_video(), kind="source_video")
    job = enqueue_extract_job(conn, user_id=user["id"], project_id=project["id"], asset_id=upload["id"], mask_provider="sam3-local", max_frames=48)
    stale_at = "2026-06-04T01:07:13.494128+00:00"
    conn.execute("UPDATE jobs SET status = 'running', updated_at = ? WHERE id = ?", (stale_at, job["id"]))
    conn.execute("UPDATE queue_items SET status = 'running' WHERE job_id = ?", (job["id"],))
    conn.execute("UPDATE job_events SET created_at = ? WHERE job_id = ?", ("2026-06-04T01:01:00+00:00", job["id"]))
    conn.commit()
    register_generated_asset(
        conn,
        storage=storage,
        project_id=project["id"],
        kind="object_manifest",
        source_job_id=job["id"],
        data=json.dumps({"objectId": "sam3_grid_021", "label": "partial", "motion": []}).encode("utf-8"),
        rel_path="objects/sam3_grid_021/object_manifest.json",
        content_type="application/json",
    )
    register_generated_asset(
        conn,
        storage=storage,
        project_id=project["id"],
        kind="object_manifest",
        source_job_id=job["id"],
        data=json.dumps({"objectId": "sam3_grid_022", "label": "partial", "motion": []}).encode("utf-8"),
        rel_path="objects/sam3_grid_022/object_manifest.json",
        content_type="application/json",
    )
    event = record_job_event(
        conn,
        job_id=job["id"],
        event_type="asset_preparation_frame_finished",
        message="finished raster asset frame 41/48 for sam3_grid_023",
        metadata={
            "stage": "asset_preparation",
            "status": "running",
            "progress": {"overallRatio": 0.73, "current": 41, "total": 48},
            "metadata": {
                "objectId": "sam3_grid_023",
                "frame": 40,
                "position": 41,
                "totalFrames": 48,
                "sourceFrameIndex": 40,
            },
        },
    )
    conn.execute("UPDATE job_events SET created_at = ? WHERE id = ?", (stale_at, event["id"]))
    conn.commit()

    reconciled = reconcile_stale_asset_preparation_job(
        conn,
        job_id=job["id"],
        now="2026-06-04T01:11:33.300141+00:00",
        threshold_seconds=240,
    )
    events = list_job_events(conn, job_id=job["id"])
    stale_event = next(event for event in events if event["event_type"] == "worker_heartbeat_stale")
    object_failed_event = next(event for event in events if event["event_type"] == "asset_preparation_object_failed")
    partial_event = next(event for event in events if event["event_type"] == "asset_preparation_partial_success")
    stale_metadata = json.loads(stale_event["metadata_json"])
    object_failed_metadata = json.loads(object_failed_event["metadata_json"])
    partial_metadata = json.loads(partial_event["metadata_json"])
    result = json.loads(reconciled["result_json"])
    queue_row = conn.execute("SELECT status FROM queue_items WHERE job_id = ?", (job["id"],)).fetchone()

    assert reconciled["status"] == "succeeded"
    assert reconciled["error"] is None
    assert queue_row["status"] == "succeeded"
    assert result["partialSuccess"] is True
    assert result["reasonCode"] == "worker_heartbeat_stale"
    assert result["progress"]["overallRatio"] == 1.0
    assert result["reviewableObjectCount"] == 2
    assert result["reviewableObjectIds"] == ["sam3_grid_021", "sam3_grid_022"]
    assert result["failedObjects"][0]["objectId"] == "sam3_grid_023"
    assert result["failedObjects"][0]["preparedFrames"] == 41
    assert "Kept 2 completed objects" in result["message"]
    assert stale_metadata["artifactsAvailable"] is True
    assert stale_metadata["partialSuccess"] is True
    assert stale_metadata["reviewableObjectCount"] == 2
    assert stale_metadata["objectId"] == "sam3_grid_023"
    assert stale_metadata["preparedFrames"] == 41
    assert object_failed_metadata["eventSource"] == "watchdog"
    assert object_failed_metadata["failureScope"] == "object"
    assert object_failed_metadata["objectId"] == "sam3_grid_023"
    assert partial_metadata["assetPreparationDiagnostic"]["reasonCode"] == "worker_heartbeat_stale"
    assert any(event["event_type"] == "succeeded" for event in events)
    assert not any(event["event_type"] == "failed" for event in events)


def test_reconcile_asset_preparation_frame_start_timeout_fails_running_job(tmp_path):
    conn, storage, user, project = backend(tmp_path)
    upload = register_upload(conn, storage=storage, user_id=user["id"], project_id=project["id"], path=demo_video(), kind="source_video")
    job = enqueue_extract_job(conn, user_id=user["id"], project_id=project["id"], asset_id=upload["id"], mask_provider="sam3-local", max_frames=48)
    stale_at = "2026-06-03T04:33:51+00:00"
    conn.execute("UPDATE jobs SET status = 'running', updated_at = ? WHERE id = ?", (stale_at, job["id"]))
    conn.execute("UPDATE queue_items SET status = 'running' WHERE job_id = ?", (job["id"],))
    conn.execute("UPDATE job_events SET created_at = ? WHERE job_id = ?", ("2026-06-03T04:26:56+00:00", job["id"]))
    conn.commit()
    event = record_job_event(
        conn,
        job_id=job["id"],
        event_type="asset_preparation_frame_started",
        message="started raster asset frame 13/48 for sam3_grid_024",
        metadata={
            "stage": "asset_preparation",
            "status": "running",
            "progress": {"overallRatio": 0.73, "current": 13, "total": 48},
            "metadata": {
                "objectId": "sam3_grid_024",
                "frame": 12,
                "position": 13,
                "totalFrames": 48,
                "sourceFrameIndex": 12,
            },
        },
    )
    conn.execute("UPDATE job_events SET created_at = ? WHERE id = ?", (stale_at, event["id"]))
    conn.commit()

    reconciled = reconcile_stale_asset_preparation_job(
        conn,
        job_id=job["id"],
        now="2026-06-03T04:45:37+00:00",
        threshold_seconds=240,
    )
    events = list_job_events(conn, job_id=job["id"])
    timeout_event = next(event for event in events if event["event_type"] == "asset_preparation_frame_timeout")
    timeout_metadata = json.loads(timeout_event["metadata_json"])
    queue_row = conn.execute("SELECT status FROM queue_items WHERE job_id = ?", (job["id"],)).fetchone()

    assert reconciled["status"] == "failed"
    assert "timed out on frame 13/48 for sam3_grid_024" in reconciled["error"]
    assert queue_row["status"] == "failed"
    assert timeout_metadata["reasonCode"] == "asset_preparation_frame_timeout"
    assert timeout_metadata["compatibilityReasonCode"] == "asset_preparation_stalled"
    assert timeout_metadata["phase"] == "asset_preparation"
    assert timeout_metadata["objectId"] == "sam3_grid_024"
    assert timeout_metadata["frame"] == 12
    assert timeout_metadata["position"] == 13
    assert timeout_metadata["preparedFrames"] == 13
    assert timeout_metadata["totalFrames"] == 48
    assert any(event["event_type"] == "failed" for event in events)


def test_reconcile_asset_preparation_keeps_fresh_running_job(tmp_path):
    conn, storage, user, project = backend(tmp_path)
    upload = register_upload(conn, storage=storage, user_id=user["id"], project_id=project["id"], path=demo_video(), kind="source_video")
    job = enqueue_extract_job(conn, user_id=user["id"], project_id=project["id"], asset_id=upload["id"], mask_provider="sam3-local", max_frames=48)
    fresh_at = "2026-06-03T04:44:30+00:00"
    conn.execute("UPDATE jobs SET status = 'running', updated_at = ? WHERE id = ?", (fresh_at, job["id"]))
    conn.execute("UPDATE job_events SET created_at = ? WHERE job_id = ?", ("2026-06-03T04:43:00+00:00", job["id"]))
    conn.commit()
    event = record_job_event(
        conn,
        job_id=job["id"],
        event_type="progress",
        message="prepared raster asset frame 1/48 for sam3_grid_024",
        metadata={"stage": "asset_preparation", "progress": {"overallRatio": 0.73, "current": 1, "total": 48}, "metadata": {"objectId": "sam3_grid_024"}},
    )
    conn.execute("UPDATE job_events SET created_at = ? WHERE id = ?", (fresh_at, event["id"]))
    conn.commit()

    reconciled = reconcile_stale_asset_preparation_job(
        conn,
        job_id=job["id"],
        now="2026-06-03T04:45:37+00:00",
        threshold_seconds=240,
    )

    assert reconciled["status"] == "running"
    assert not any(event["event_type"] in {"asset_preparation_stalled", "asset_preparation_frame_timeout", "worker_heartbeat_stale"} for event in list_job_events(conn, job_id=job["id"]))


def test_asset_preparation_heartbeat_prevents_false_worker_stale(tmp_path):
    from motionjson.backend.stale_jobs import asset_preparation_stall_diagnostic

    conn, storage, user, project = backend(tmp_path)
    upload = register_upload(conn, storage=storage, user_id=user["id"], project_id=project["id"], path=demo_video(), kind="source_video")
    job = enqueue_extract_job(conn, user_id=user["id"], project_id=project["id"], asset_id=upload["id"], mask_provider="sam3-local", max_frames=48)
    conn.execute("UPDATE jobs SET status = 'running', updated_at = ? WHERE id = ?", ("2026-06-05T07:31:00+00:00", job["id"]))
    conn.commit()
    finished = record_job_event(
        conn,
        job_id=job["id"],
        event_type="asset_preparation_frame_finished",
        message="finished raster asset frame 11/36 for sam3_grid_027",
        metadata={
            "stage": "asset_preparation",
            "status": "running",
            "progress": {"overallRatio": 0.73, "current": 11, "total": 36},
            "metadata": {"objectId": "sam3_grid_027", "position": 11, "totalFrames": 36},
        },
    )
    heartbeat = record_job_event(
        conn,
        job_id=job["id"],
        event_type="worker_heartbeat",
        message="worker heartbeat during asset_preparation",
        metadata={
            "stage": "asset_preparation",
            "status": "running",
            "metadata": {
                "objectId": "sam3_grid_027",
                "position": 11,
                "totalFrames": 36,
                "activeStage": "asset_preparation",
            },
        },
    )
    conn.execute("UPDATE job_events SET created_at = ? WHERE id = ?", ("2026-06-05T07:31:25+00:00", finished["id"]))
    conn.execute("UPDATE job_events SET created_at = ? WHERE id = ?", ("2026-06-05T07:35:00+00:00", heartbeat["id"]))
    conn.commit()

    diagnostic = asset_preparation_stall_diagnostic(
        {"status": "running"},
        [dict(event) for event in list_job_events(conn, job_id=job["id"])],
        now="2026-06-05T07:35:32+00:00",
        threshold_seconds=240,
    )

    assert diagnostic is None


def test_fresh_heartbeat_does_not_hide_inflight_frame_timeout(tmp_path):
    from motionjson.backend.stale_jobs import asset_preparation_stall_diagnostic

    conn, storage, user, project = backend(tmp_path)
    upload = register_upload(conn, storage=storage, user_id=user["id"], project_id=project["id"], path=demo_video(), kind="source_video")
    job = enqueue_extract_job(conn, user_id=user["id"], project_id=project["id"], asset_id=upload["id"], mask_provider="sam3-local", max_frames=48)
    conn.execute("UPDATE jobs SET status = 'running', updated_at = ? WHERE id = ?", ("2026-06-05T07:31:00+00:00", job["id"]))
    conn.commit()
    started = record_job_event(
        conn,
        job_id=job["id"],
        event_type="asset_preparation_frame_started",
        message="started raster asset frame 12/36 for sam3_grid_027",
        metadata={
            "stage": "asset_preparation",
            "status": "running",
            "progress": {"overallRatio": 0.73, "current": 12, "total": 36},
            "metadata": {"objectId": "sam3_grid_027", "frame": 11, "position": 12, "totalFrames": 36},
        },
    )
    heartbeat = record_job_event(
        conn,
        job_id=job["id"],
        event_type="worker_heartbeat",
        message="worker heartbeat during asset_preparation",
        metadata={"stage": "asset_preparation", "status": "running", "metadata": {"objectId": "sam3_grid_027"}},
    )
    conn.execute("UPDATE job_events SET created_at = ? WHERE id = ?", ("2026-06-05T07:31:25+00:00", started["id"]))
    conn.execute("UPDATE job_events SET created_at = ? WHERE id = ?", ("2026-06-05T07:35:00+00:00", heartbeat["id"]))
    conn.commit()

    diagnostic = asset_preparation_stall_diagnostic(
        {"status": "running"},
        [dict(event) for event in list_job_events(conn, job_id=job["id"])],
        now="2026-06-05T07:35:32+00:00",
        threshold_seconds=240,
    )

    assert diagnostic is not None
    assert diagnostic["reasonCode"] == "asset_preparation_frame_timeout"
    assert diagnostic["objectId"] == "sam3_grid_027"
    assert diagnostic["position"] == 12


def test_provider_policy_rejects_openrouter_as_segmentation(tmp_path):
    with pytest.raises(ProviderPolicyError):
        validate_extract_provider_policy("openrouter")
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    initialize_database(conn)
    user = register_user(conn, email="policy@example.com", password="pw")
    project = create_project(conn, user_id=user["id"], name="Policy")
    storage = LocalStorageProvider(tmp_path / "policy_storage")
    upload = register_upload(conn, storage=storage, user_id=user["id"], project_id=project["id"], path=demo_video(), kind="source_video")
    with pytest.raises(ProviderPolicyError):
        enqueue_extract_job(conn, user_id=user["id"], project_id=project["id"], asset_id=upload["id"], mask_provider="openrouter")
    assert validate_extract_provider_policy("threshold") == "threshold"


def test_provider_policy_accepts_sam2_and_sam3_ui_engine_names():
    assert validate_extract_provider_policy("sam2-local") == "sam2-local"
    assert validate_extract_provider_policy("sam2-hosted") == "sam2-hosted"
    assert validate_extract_provider_policy("sam3-local") == "sam3-local"
    assert validate_extract_provider_policy("sam3-hosted") == "sam3-hosted"
