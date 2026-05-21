from __future__ import annotations

import json
from pathlib import Path

from motionjson.ui.server import LocalUIApp


def decode(body: bytes) -> dict:
    return json.loads(body.decode("utf-8"))


def demo_video() -> Path:
    return Path(__file__).resolve().parents[1] / "examples" / "demo_red_ball.mp4"


def api(app: LocalUIApp, method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
    body = json.dumps(payload or {}).encode("utf-8") if payload is not None else b""
    status, _headers, raw = app.handle(method, path, body=body)
    return status, decode(raw)


def create_project_video_and_job(app: LocalUIApp) -> tuple[dict, dict, dict]:
    status, project_body = api(app, "POST", "/api/projects", {"name": "Model Plan Project"})
    assert status == 200
    project = project_body["project"]
    status, video_body = api(app, "POST", "/api/videos", {"projectId": project["id"], "path": str(demo_video())})
    assert status == 200
    video = video_body["video"]
    status, job_body = api(
        app,
        "POST",
        "/api/jobs",
        {"projectId": project["id"], "videoId": video["id"], "maskProvider": "mock", "maxFrames": 2},
    )
    assert status == 200
    return project, video, job_body["job"]


def test_local_ui_model_provider_routes_are_no_network_and_redacted(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)

    status, health = api(app, "GET", "/api/health")
    assert status == 200
    assert "/api/model-providers" in health["routes"]
    assert "/api/model-runs/{runId}/cancel" in health["routes"]
    assert "/api/jobs/{jobId}/model-plan" in health["routes"]

    status, providers = api(app, "GET", "/api/model-providers")
    assert status == 200
    provider = providers["providers"][0]
    assert provider["id"] == "fake-local-planner"
    assert provider["readiness"]["networkAttempted"] is False
    assert provider["hostedCallsRequired"] is False

    status, tested = api(app, "POST", "/api/model-providers/fake-local-planner/test", {"apiKey": "sk-test-secret-123456"})
    assert status == 200
    assert tested["networkAttempted"] is False
    assert "sk-test-secret" not in json.dumps(tested)

    status, estimate = api(
        app,
        "POST",
        "/api/model-providers/fake-local-planner/estimate",
        {"request": {"goal": "Find by description", "prompt": "red ball"}},
    )
    assert status == 200
    assert estimate["status"] == "zero_local"
    assert estimate["hostedCallsRequired"] is False


def test_local_ui_model_run_redacts_request_plan_and_events(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    secret = "sk-or-v1-model-run-secret-123456"

    status, body = api(
        app,
        "POST",
        "/api/model-runs",
        {
            "providerId": "fake-local-planner",
            "request": {
                "goal": "Find by description",
                "prompt": f"red ball api_key={secret}",
                "sourcePath": f"/Users/alice/private/movie.mp4?api_key={secret}",
            },
        },
    )

    assert status == 200
    text = json.dumps(body)
    assert secret not in text
    assert "/Users/alice" not in text
    run = body["modelRun"]
    assert run["status"] == "succeeded"
    assert run["result"]["validation"]["valid"] is True
    assert run["result"]["requiresUserConfirmation"] is True
    assert run["result"]["privacy"]["framesLeaveDevice"] is False

    status, events = api(app, "GET", f"/api/model-runs/{run['id']}/events")
    assert status == 200
    assert [event["eventType"] for event in events["events"]] == ["queued", "running", "planned"]


def test_local_ui_model_run_cancel_supports_deferred_runs(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)

    status, body = api(
        app,
        "POST",
        "/api/model-runs",
        {"providerId": "fake-local-planner", "defer": True, "request": {"goal": "Cut out one object"}},
    )
    assert status == 200
    run = body["modelRun"]
    assert run["status"] == "pending"

    status, canceled = api(app, "POST", f"/api/model-runs/{run['id']}/cancel", {"reason": "test_cancel"})
    assert status == 200
    assert canceled["modelRun"]["status"] == "canceled"
    assert canceled["modelRun"]["events"][-1]["eventType"] == "canceled"


def test_local_ui_attaches_model_plan_to_job_as_redacted_event(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    _project, video, job = create_project_video_and_job(app)

    status, run_body = api(
        app,
        "POST",
        "/api/model-runs",
        {
            "providerId": "fake-local-planner",
            "request": {"goal": "Find moving things", "videoId": video["id"], "projectId": job["project_id"]},
        },
    )
    assert status == 200
    model_run = run_body["modelRun"]
    assert model_run["status"] == "succeeded"

    status, attached = api(app, "POST", f"/api/jobs/{job['id']}/model-plan", {"modelRunId": model_run["id"]})
    assert status == 200
    assert attached["modelPlan"]["validation"]["valid"] is True
    assert attached["modelPlan"]["runConfig"]["discovery"]["mode"] == "motion_foreground"
    event_types = [event["event_type"] for event in attached["job"]["events"]]
    assert "model_plan_attached" in event_types
    assert "apiKey" not in json.dumps(attached)
