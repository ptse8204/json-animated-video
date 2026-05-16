from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from motionjson.backend.assets import register_generated_asset
from motionjson.backend.jobs import record_job_event
from motionjson.ui import server as ui_server
from motionjson.ui.server import LOCAL_UI_EMAIL
from motionjson.ui.server import LocalUIApp


def demo_video() -> Path:
    return Path(__file__).resolve().parents[1] / "examples" / "demo_red_ball.mp4"


def decode(body: bytes) -> dict:
    return json.loads(body.decode("utf-8"))


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


def test_local_ui_api_health_capabilities_and_defaults_are_public(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)

    status, _headers, body = app.handle("GET", "/api/health")
    health = decode(body)
    assert status == 200
    assert health["format"] == "motionjson.local_ui.v0.1"
    assert health["status"] == "ok"
    assert health["localFirst"] is True
    assert health["mockModeAvailable"] is True
    assert health["mockMode"] is True
    assert "/api/capabilities" in health["routes"]
    assert "/api/progress" in health["routes"]
    assert "/api/artifacts" in health["routes"]
    assert "/api/videos/{videoId}/content" in health["routes"]
    assert "/api/run-config/validate" in health["routes"]
    assert "/api/jobs/{jobId}/run" in health["routes"]
    assert "/api/jobs/{jobId}/review" in health["routes"]

    status, _headers, body = app.handle("GET", "/api/capabilities")
    capabilities = decode(body)
    assert status == 200
    assert capabilities["schema"] == "motionjson.provider_diagnostics.v0.1"
    assert any(provider["name"] == "mock" and provider["noModelSafe"] for provider in capabilities["providers"])

    status, _headers, body = app.handle("GET", "/api/run-config/defaults")
    defaults = decode(body)
    assert status == 200
    assert defaults["format"] == "motionjson.local_ui_run_config_defaults.v0.1"
    assert "mock" in defaults["maskProviders"]
    assert "manual_prompt" in defaults["discoveryProviders"]
    assert defaults["defaults"]["maskProvider"] == "mock"

    status, _headers, body = app.handle("GET", "/api/exports/formats")
    exports = decode(body)
    assert status == 200
    assert {entry["id"] for entry in exports["exports"]} >= {"mp4", "website-zip", "remotion-plan"}


def test_local_ui_serves_static_shell(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage")

    status, headers, body = app.handle("GET", "/")

    assert status == 200
    assert headers["content-type"].startswith("text/html")
    assert b"MotionJSON" in body
    assert b"/ui/app.js" in body


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
    assert videos[0]["metadata"]["filename"] == "demo_red_ball.mp4"
    assert "uri" not in videos[0]
    assert str(demo_video()) not in body.decode("utf-8")

    status, _headers, body = app.handle("GET", f"/api/jobs?projectId={project['id']}")
    assert status == 200
    assert decode(body)["jobs"] == []

    status, _headers, body = app.handle("GET", f"/api/progress?projectId={project['id']}")
    assert status == 200
    assert decode(body)["progress"] == []


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
        "local_job_policy",
    }

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

    conn = app.connection()
    try:
        record_job_event(
            conn,
            job_id=job["id"],
            event_type="debug",
            message="storage_key=projects/private/source.mp4",
            metadata={"storageKey": "projects/private/event.mp4", "safe": True},
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
    assert "storage_key" not in body.decode("utf-8")
    assert "projects/private" not in body.decode("utf-8")

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
    assert review["fallbackDiagnostics"] == []
    assert str(tmp_path) not in body.decode("utf-8")
    assert "storage_key" not in body.decode("utf-8")
    assert "projects/" not in body.decode("utf-8")

    status, _headers, body = app.handle("GET", f"/api/jobs/{job['id']}/review")
    assert status == 200
    assert decode(body)["review"]["tracks"][0]["objectId"] == "object_0"


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
