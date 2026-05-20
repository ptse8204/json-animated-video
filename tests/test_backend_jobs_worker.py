from __future__ import annotations

import json
import sqlite3
import zipfile
from pathlib import Path

import pytest

from motionjson.backend.assets import list_assets_for_job, register_upload
from motionjson.backend.auth import register_user
from motionjson.backend.db import initialize_database
from motionjson.backend.jobs import enqueue_export_job, enqueue_extract_job, list_job_events
from motionjson.backend.projects import create_project
from motionjson.backend.queue import mark_failed
from motionjson.backend.usage import summarize_usage
from motionjson.backend.worker import _ui_discovery_provider, validate_extract_provider_policy, worker_once
from motionjson.backend.models import ProviderPolicyError
from motionjson.providers.discovery import MockObjectDiscoveryProvider, SAM2AutomaticProposalDiscoveryProvider, SamAutoMasksDiscoveryProvider
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
    kinds = {asset["kind"] for asset in assets}
    usage = summarize_usage(conn, project_id=project["id"])

    assert result["status"] == "succeeded"
    assert {"scene_graph", "object_manifest", "web_manifest"}.issubset(kinds)
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
    export = enqueue_export_job(conn, user_id=user["id"], project_id=project["id"], source_job_id=extract["id"], format="website-zip")

    result = worker_once(conn, storage=storage)
    package_assets = [asset for asset in list_assets_for_job(conn, project_id=project["id"], source_job_id=export["id"]) if asset["kind"] == "website_package"]
    package_path = tmp_path / "package.zip"
    package_path.write_bytes(storage.load_bytes(package_assets[0]["storage_key"]))

    with zipfile.ZipFile(package_path) as archive:
        manifest = json.loads(archive.read("package_manifest.json"))

    assert result["status"] == "succeeded"
    assert manifest["aiUsage"] == "none"
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
