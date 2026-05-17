from __future__ import annotations

import base64
import json
import sqlite3
from pathlib import Path

from motionjson.backend.api import MotionJSONAPI
from motionjson.backend.api_keys import create_api_key, list_api_keys, require_api_key, revoke_api_key
from motionjson.backend.assets import list_assets_for_job, register_generated_asset, register_upload
from motionjson.backend.auth import register_user
from motionjson.backend.db import initialize_database
from motionjson.backend.jobs import enqueue_asset_package_job, enqueue_extract_job, enqueue_render_job
from motionjson.backend.projects import create_project
from motionjson.backend.webhooks import create_webhook, list_webhook_deliveries, verify_webhook_signature
from motionjson.backend.worker import worker_once
from motionjson.providers.local_storage import LocalStorageProvider


def backend(tmp_path):
    conn = sqlite3.connect(tmp_path / "backend.sqlite")
    conn.row_factory = sqlite3.Row
    initialize_database(conn)
    storage = LocalStorageProvider(tmp_path / "storage")
    user = register_user(conn, email="api@example.com", password="pw")
    project = create_project(conn, user_id=user["id"], name="API Project")
    return conn, storage, user, project


def demo_video() -> Path:
    return Path(__file__).resolve().parents[1] / "examples" / "demo_red_ball.mp4"


def test_api_key_lifecycle_hashes_raw_key_and_revokes(tmp_path):
    conn, _storage, user, _project = backend(tmp_path)
    created = create_api_key(conn, user_id=user["id"], name="SDK")
    raw_key = created["apiKey"]
    stored = conn.execute("SELECT * FROM api_keys WHERE id = ?", (created["id"],)).fetchone()

    assert raw_key.startswith("mj_local_")
    assert stored["key_hash"] != raw_key
    assert raw_key not in dict(stored).values()
    assert list_api_keys(conn, user_id=user["id"])[0]["key_prefix"] == raw_key[:16]
    assert require_api_key(conn, raw_key)["user_id"] == user["id"]
    assert revoke_api_key(conn, user_id=user["id"], key_id=created["id"])
    assert list_api_keys(conn, user_id=user["id"]) == []


def test_dependency_light_rest_api_covers_projects_assets_jobs_and_webhooks(tmp_path):
    conn, _storage, user, _project = backend(tmp_path)
    key = create_api_key(conn, user_id=user["id"], name="API")["apiKey"]
    conn.close()
    api = MotionJSONAPI(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage")
    headers = {"authorization": f"Bearer {key}"}

    status, _headers, body = api.handle("POST", "/v1/projects", headers, json.dumps({"name": "REST Project"}).encode())
    assert status == 201
    project = json.loads(body)

    upload_payload = {
        "filename": "clip.mp4",
        "kind": "source_video",
        "contentType": "video/mp4",
        "dataBase64": base64.b64encode(demo_video().read_bytes()).decode("ascii"),
        "metadata": {"rights_context": {"source_uri": "local-demo"}},
    }
    status, _headers, body = api.handle("POST", f"/v1/projects/{project['id']}/assets", headers, json.dumps(upload_payload).encode())
    assert status == 201
    asset = json.loads(body)
    assert "storage_key" not in asset

    status, _headers, body = api.handle("GET", f"/v1/projects/{project['id']}/assets", headers, b"")
    assert json.loads(body)["assets"][0]["id"] == asset["id"]
    status, response_headers, data = api.handle("GET", f"/v1/assets/{asset['id']}/download", headers, b"")
    assert status == 200
    assert response_headers["content-type"] == "video/mp4"
    assert data[:4]

    status, _headers, body = api.handle(
        "POST",
        f"/v1/projects/{project['id']}/extractions",
        headers,
        json.dumps({"assetId": asset["id"], "maskProvider": "threshold", "maxFrames": 1}).encode(),
    )
    assert status == 202
    extract_job = json.loads(body)

    status, _headers, body = api.handle(
        "POST",
        f"/v1/projects/{project['id']}/asset-packages",
        headers,
        json.dumps({"sourceJobId": extract_job["id"]}).encode(),
    )
    assert status == 202
    assert json.loads(body)["type"] == "export"

    status, _headers, body = api.handle(
        "POST",
        f"/v1/projects/{project['id']}/renders",
        headers,
        json.dumps({"sourceJobId": extract_job["id"], "format": "remotion-plan"}).encode(),
    )
    assert status == 202
    assert json.loads(body)["type"] == "render"

    status, _headers, body = api.handle("POST", "/v1/webhooks", headers, json.dumps({"url": "https://example.test/hook"}).encode())
    assert status == 201
    assert json.loads(body)["signingSecret"].startswith("whsec_")
    status, _headers, body = api.handle("GET", "/v1/webhooks", headers, b"")
    assert len(json.loads(body)["webhooks"]) == 1

    status, _headers, body = api.handle("GET", f"/v1/jobs/{extract_job['id']}/events", headers, b"")
    assert status == 200
    assert json.loads(body)["events"][0]["event_type"] == "queued"


def test_rest_api_track_edits_persist_corrections_and_update_artifacts(tmp_path):
    conn, storage, user, project = backend(tmp_path)
    key = create_api_key(conn, user_id=user["id"], name="API")["apiKey"]
    upload = register_upload(conn, storage=storage, user_id=user["id"], project_id=project["id"], path=demo_video(), kind="source_video")
    job = enqueue_extract_job(conn, user_id=user["id"], project_id=project["id"], asset_id=upload["id"], mask_provider="mock", max_frames=2)
    tracks_payload = {
        "format": "motionjson.tracks.v0.1",
        "tracks": [
            {
                "objectId": "object_0",
                "label": "red ball",
                "source": "mock",
                "frameCount": 2,
                "visibleFrameCount": 2,
                "exportStatus": "accepted",
                "warnings": [],
                "frames": [
                    {"frame": 1, "visible": True, "bbox": [10, 10, 12, 12]},
                    {"frame": 2, "visible": True, "bbox": [11, 10, 12, 12]},
                ],
            }
        ],
    }
    register_generated_asset(
        conn,
        storage=storage,
        project_id=project["id"],
        source_job_id=job["id"],
        kind="track_summary",
        data=json.dumps(tracks_payload).encode("utf-8"),
        rel_path="tracks.json",
        content_type="application/json",
        metadata={"aiUsage": "none", "fixture": "rest-track-edits"},
    )
    conn.close()

    api = MotionJSONAPI(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage")
    headers = {"authorization": f"Bearer {key}"}
    status, _headers, body = api.handle(
        "POST",
        f"/v1/jobs/{job['id']}/track-edits",
        headers,
        json.dumps({"operation": "relabel", "objectId": "object_0", "label": "API ball"}).encode(),
    )

    assert status == 201
    edited = json.loads(body)
    assert edited["correction"]["operation"] == "relabel"
    assert edited["updatedAssets"][0]["kind"] == "track_summary"
    assert edited["reviewStateManifest"]["kind"] == "review_state_manifest"

    status, _headers, body = api.handle(
        "POST",
        f"/v1/jobs/{job['id']}/track-edits",
        headers,
        json.dumps({"action": {"type": "set_export_inclusion", "trackId": "object_0", "included": False}}).encode(),
    )

    assert status == 201
    export_edit = json.loads(body)
    assert export_edit["correction"]["operation"] == "set_export_inclusion"
    assert export_edit["result"]["exportIncluded"] is False
    assert export_edit["result"]["visibleFrameCount"] == 2

    status, _headers, body = api.handle("GET", f"/v1/jobs/{job['id']}/corrections", headers, b"")
    assert status == 200
    corrections = json.loads(body)["corrections"]
    assert corrections[0]["operation"] == "relabel"
    assert corrections[0]["result"]["label"] == "API ball"
    assert corrections[1]["operation"] == "set_export_inclusion"

    status, _headers, body = api.handle("GET", f"/v1/jobs/{job['id']}/artifacts", headers, b"")
    assert status == 200
    artifacts = json.loads(body)["artifacts"]
    assert any(artifact["kind"] == "review_state_manifest" for artifact in artifacts)


def test_worker_render_job_registers_remotion_plan_and_manifest_with_no_ai_usage(tmp_path):
    conn, storage, user, project = backend(tmp_path)
    upload = register_upload(conn, storage=storage, user_id=user["id"], project_id=project["id"], path=demo_video(), kind="source_video")
    extract = enqueue_extract_job(conn, user_id=user["id"], project_id=project["id"], asset_id=upload["id"], mask_provider="threshold", max_frames=1)
    assert worker_once(conn, storage=storage)["status"] == "succeeded"
    render = enqueue_render_job(conn, user_id=user["id"], project_id=project["id"], source_job_id=extract["id"], format="remotion-plan")

    result = worker_once(conn, storage=storage)
    assets = list_assets_for_job(conn, project_id=project["id"], source_job_id=render["id"])
    kinds = {asset["kind"] for asset in assets}
    result_json = json.loads(result["result_json"])

    assert result["status"] == "succeeded"
    assert {"remotion_plan", "final_export_manifest"}.issubset(kinds)
    assert result_json["aiUsage"] == "none"
    assert result_json["entry"]["status"] == "plan_ready"


def test_webhook_signing_and_delivery_records_use_injected_transport(tmp_path):
    conn, storage, user, project = backend(tmp_path)
    webhook = create_webhook(conn, user_id=user["id"], url="https://example.test/webhook", event_types=["job.succeeded"])

    class FakeTransport:
        def __init__(self):
            self.calls = []

        def post(self, url, *, headers, body):
            self.calls.append((url, headers, body))
            return {"status": "delivered", "status_code": 200, "response_body": "ok"}

    upload = register_upload(conn, storage=storage, user_id=user["id"], project_id=project["id"], path=demo_video(), kind="source_video")
    job = enqueue_extract_job(conn, user_id=user["id"], project_id=project["id"], asset_id=upload["id"], mask_provider="threshold", max_frames=1)
    transport = FakeTransport()

    assert worker_once(conn, storage=storage, webhook_transport=transport)["status"] == "succeeded"
    deliveries = list_webhook_deliveries(conn, user_id=user["id"], webhook_id=webhook["id"])

    assert len(transport.calls) == 1
    assert deliveries[0]["status"] == "delivered"
    assert deliveries[0]["event_type"] == "job.succeeded"
    assert verify_webhook_signature(webhook["signingSecret"], transport.calls[0][2], transport.calls[0][1]["motionjson-signature"])
    assert job["id"] in deliveries[0]["payload_json"]


def test_webhook_product_events_cover_assets_packages_and_renders(tmp_path):
    conn, storage, user, project = backend(tmp_path)
    create_webhook(conn, user_id=user["id"], url="https://example.test/webhook", event_types=["*"])

    class FakeTransport:
        def __init__(self):
            self.events = []

        def post(self, url, *, headers, body):
            del url, headers
            self.events.append(json.loads(body.decode("utf-8"))["type"])
            return {"status": "delivered", "status_code": 200, "response_body": "ok"}

    transport = FakeTransport()
    upload = register_upload(conn, storage=storage, user_id=user["id"], project_id=project["id"], path=demo_video(), kind="source_video")
    extract = enqueue_extract_job(conn, user_id=user["id"], project_id=project["id"], asset_id=upload["id"], mask_provider="threshold", max_frames=1)
    assert worker_once(conn, storage=storage, webhook_transport=transport)["status"] == "succeeded"
    package = enqueue_asset_package_job(conn, user_id=user["id"], project_id=project["id"], source_job_id=extract["id"])
    assert worker_once(conn, storage=storage, webhook_transport=transport)["status"] == "succeeded"
    render = enqueue_render_job(conn, user_id=user["id"], project_id=project["id"], source_job_id=extract["id"], format="remotion-plan")
    assert worker_once(conn, storage=storage, webhook_transport=transport)["status"] == "succeeded"

    assert "asset.created" in transport.events
    assert "asset_package.ready" in transport.events
    assert "render.ready" in transport.events
    deliveries = list_webhook_deliveries(conn, user_id=user["id"])
    event_types = {delivery["event_type"] for delivery in deliveries}
    assert {"job.succeeded", "asset.created", "asset_package.ready", "render.ready"}.issubset(event_types)
    assert package["id"] in "".join(delivery["payload_json"] for delivery in deliveries)
    assert render["id"] in "".join(delivery["payload_json"] for delivery in deliveries)
