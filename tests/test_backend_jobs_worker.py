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
from motionjson.backend.stale_jobs import (
    asset_preparation_frame_timeout_seconds,
    reconcile_stale_asset_preparation_job,
    worker_heartbeat_stale_seconds,
)
from motionjson.backend.usage import summarize_usage
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
