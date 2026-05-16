from __future__ import annotations

import json
import sqlite3
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
    assert "storage_key" not in video
    assert "uri" not in video
    assert video["metadata"]["filename"] == "demo_red_ball.mp4"

    status, _headers, body = app.handle("GET", f"/api/videos?projectId={project['id']}")
    videos = decode(body)["videos"]
    assert status == 200
    assert videos[0]["id"] == video["id"]
    assert videos[0]["metadata"]["filename"] == "demo_red_ball.mp4"
    assert "uri" not in videos[0]

    status, _headers, body = app.handle("GET", f"/api/jobs?projectId={project['id']}")
    assert status == 200
    assert decode(body)["jobs"] == []

    status, _headers, body = app.handle("GET", f"/api/progress?projectId={project['id']}")
    assert status == 200
    assert decode(body)["progress"] == []


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
