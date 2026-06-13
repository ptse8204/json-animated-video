from __future__ import annotations

import json
import time
from pathlib import Path

from motionjson.model_connectors import (
    EvoLinkPlanningConnector,
    FakeModelConnector,
    ModelConnectorRegistry,
    ModelPlanResult,
    ModelPlanRequest,
    OpenAIPlanningConnector,
    OpenRouterSettingsModelConnector,
)
from motionjson.ui.server import LocalUIApp


def decode(body: bytes) -> dict:
    return json.loads(body.decode("utf-8"))


def demo_video() -> Path:
    return Path(__file__).resolve().parents[1] / "examples" / "demo_red_ball.mp4"


def api(app: LocalUIApp, method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
    body = json.dumps(payload or {}).encode("utf-8") if payload is not None else b""
    status, _headers, raw = app.handle(method, path, body=body)
    return status, decode(raw)


def model_provider_by_id(payload: dict, provider_id: str) -> dict:
    return next(provider for provider in payload["providers"] if provider["id"] == provider_id)


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


def test_local_ui_model_provider_routes_are_no_network_and_redacted(tmp_path, monkeypatch):
    monkeypatch.delenv("EVOLINK_API_KEY", raising=False)
    monkeypatch.delenv("EVOLINK_DEFAULT_MODEL", raising=False)
    monkeypatch.delenv("EVOLINK_BASE_URL", raising=False)
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)

    status, health = api(app, "GET", "/api/health")
    assert status == 200
    assert "/api/model-providers" in health["routes"]
    assert "/api/model-runs/{runId}/cancel" in health["routes"]
    assert "/api/model-runs/{runId}/confirm-job" in health["routes"]
    assert "/api/jobs/{jobId}/model-plan" in health["routes"]

    status, providers = api(app, "GET", "/api/model-providers")
    assert status == 200
    provider = providers["providers"][0]
    assert provider["id"] == "fake-local-planner"
    assert provider["readiness"]["networkAttempted"] is False
    assert provider["hostedCallsRequired"] is False
    openrouter = model_provider_by_id(providers, "openrouter-planner")
    assert openrouter["settingsProviderId"] == "openrouter"
    assert openrouter["readiness"]["status"] == "missing_key"
    assert openrouter["readiness"]["runnable"] is False
    assert openrouter["readiness"]["networkAttempted"] is False
    assert openrouter["readiness"]["hostedCallsRequired"] is True
    openai = model_provider_by_id(providers, "openai-planner")
    assert openai["settingsProviderId"] == "openai"
    assert openai["readiness"]["status"] == "missing_key"
    assert openai["readiness"]["runnable"] is False
    assert openai["readiness"]["networkAttempted"] is False
    evolink = model_provider_by_id(providers, "evolink-planner")
    assert evolink["settingsProviderId"] == "evolink"
    assert evolink["readiness"]["status"] == "missing_key"
    assert evolink["readiness"]["runnable"] is False
    assert evolink["readiness"]["networkAttempted"] is False

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


def test_openrouter_model_provider_uses_provider_settings_without_network(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    secret = "sk-or-v1-model-settings-secret-123456"

    status, saved = api(
        app,
        "POST",
        "/api/provider-settings",
        {"providerId": "openrouter", "apiKey": secret, "selectedModel": "__custom__", "customModelId": "example/planner"},
    )
    assert status == 200
    assert secret not in json.dumps(saved)

    status, body = api(app, "GET", "/api/model-providers/openrouter-planner")
    assert status == 200
    assert secret not in json.dumps(body)
    readiness = body["readiness"]
    assert readiness["settingsProviderId"] == "openrouter"
    assert readiness["status"] == "hosted_opt_in_required"
    assert readiness["configured"] is True
    assert readiness["runnable"] is False
    assert readiness["hostedCallsAllowed"] is False
    assert readiness["networkAttempted"] is False
    assert readiness["effectiveModel"] == "example/planner"

    status, tested = api(app, "POST", "/api/model-providers/openrouter-planner/test", {"apiKey": secret})
    assert status == 200
    assert tested["networkAttempted"] is False
    assert tested["configured"] is True
    assert tested["ready"] is False
    assert tested["settingsCheck"]["status"] == "configured"
    assert tested["status"] == "hosted_opt_in_required"
    assert secret not in json.dumps(tested)


def test_openrouter_model_provider_uses_environment_settings_precedence(tmp_path, monkeypatch):
    secret = "sk-or-v1-model-env-secret-123456"
    monkeypatch.setenv("OPENROUTER_API_KEY", secret)
    monkeypatch.setenv("OPENROUTER_DEFAULT_MODEL", "env/planner")
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)

    status, body = api(app, "GET", "/api/model-providers/openrouter-planner")

    assert status == 200
    readiness = body["readiness"]
    assert readiness["status"] == "hosted_opt_in_required"
    assert readiness["configured"] is True
    assert readiness["credentials"][0]["source"] == "environment"
    assert readiness["effectiveModel"] == "env/planner"
    assert readiness["networkAttempted"] is False
    assert secret not in json.dumps(body)


def test_openrouter_model_provider_opt_in_remains_settings_only_until_connector_exists(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    secret = "sk-or-v1-model-opt-in-secret-123456"

    status, _saved = api(
        app,
        "POST",
        "/api/provider-settings",
        {"providerId": "openrouter", "apiKey": secret, "allowHosted": True},
    )
    assert status == 200

    status, body = api(app, "GET", "/api/model-providers")
    assert status == 200
    openrouter = model_provider_by_id(body, "openrouter-planner")
    readiness = openrouter["readiness"]
    assert readiness["status"] == "configured_settings_only"
    assert readiness["configured"] is True
    assert readiness["hostedCallsAllowed"] is True
    assert readiness["plannedConnector"] is True
    assert readiness["runnable"] is False
    assert secret not in json.dumps(body)

    status, estimate = api(
        app,
        "POST",
        "/api/model-providers/openrouter-planner/estimate",
        {"request": {"goal": "Find by description", "prompt": "red ball", "maxObjects": 3}},
    )
    assert status == 200
    assert estimate["status"] == "unknown_provider_cost"
    assert estimate["hostedCallsRequired"] is True
    assert estimate["framesLeaveDevice"] is False
    assert estimate["networkAttempted"] is False
    assert estimate["blocked"] is True
    assert "not implemented" in estimate["blockedReason"]
    assert secret not in json.dumps(estimate)

    status, failed = api(
        app,
        "POST",
        "/api/model-runs",
        {"providerId": "openrouter-planner", "request": {"goal": "Find by description", "prompt": "red ball"}},
    )
    assert status == 400
    assert "not ready to run" in failed["error"]
    assert secret not in json.dumps(failed)


def test_openai_model_provider_requires_settings_opt_in_and_per_request_ack(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    secret = "sk-openai-model-secret-123456"

    status, saved = api(
        app,
        "POST",
        "/api/provider-settings",
        {"providerId": "openai", "apiKey": secret, "allowHosted": True},
    )
    assert status == 200
    assert secret not in json.dumps(saved)

    status, body = api(app, "GET", "/api/model-providers/openai-planner")
    assert status == 200
    readiness = body["readiness"]
    assert readiness["status"] == "ready"
    assert readiness["configured"] is True
    assert readiness["hostedCallsAllowed"] is True
    assert readiness["runnable"] is True
    assert readiness["effectiveModel"] == "gpt-5.4-mini"
    assert secret not in json.dumps(body)

    status, failed = api(
        app,
        "POST",
        "/api/model-runs",
        {"providerId": "openai-planner", "request": {"goal": "Find by description", "prompt": "red ball"}},
    )
    assert status == 400
    assert "allowNetwork=true" in failed["error"]
    assert secret not in json.dumps(failed)

    status, failed = api(
        app,
        "POST",
        "/api/model-runs",
        {
            "providerId": "openai-planner",
            "allowNetwork": True,
            "request": {"goal": "Find by description", "prompt": "red ball"},
        },
    )
    assert status == 400
    assert "acknowledgeCostPrivacy=true" in failed["error"]
    assert secret not in json.dumps(failed)


def test_evolink_model_provider_requires_settings_opt_in_and_per_request_ack(tmp_path, monkeypatch):
    monkeypatch.delenv("EVOLINK_API_KEY", raising=False)
    monkeypatch.delenv("EVOLINK_DEFAULT_MODEL", raising=False)
    monkeypatch.delenv("EVOLINK_BASE_URL", raising=False)
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    secret = "evl-model-secret-123456"

    status, saved = api(
        app,
        "POST",
        "/api/provider-settings",
        {
            "providerId": "evolink",
            "apiKey": secret,
            "allowHosted": True,
            "selectedModel": "__custom__",
            "customModelId": "gpt-5.1",
        },
    )
    assert status == 200
    assert secret not in json.dumps(saved)

    status, body = api(app, "GET", "/api/model-providers/evolink-planner")
    assert status == 200
    readiness = body["readiness"]
    assert readiness["status"] == "ready"
    assert readiness["configured"] is True
    assert readiness["hostedCallsAllowed"] is True
    assert readiness["runnable"] is True
    assert readiness["effectiveModel"] == "gpt-5.1"
    assert secret not in json.dumps(body)

    status, failed = api(
        app,
        "POST",
        "/api/model-runs",
        {"providerId": "evolink-planner", "request": {"goal": "Find by description", "prompt": "red ball"}},
    )
    assert status == 400
    assert "allowNetwork=true" in failed["error"]
    assert secret not in json.dumps(failed)

    status, failed = api(
        app,
        "POST",
        "/api/model-runs",
        {
            "providerId": "evolink-planner",
            "allowNetwork": True,
            "request": {"goal": "Find by description", "prompt": "red ball"},
        },
    )
    assert status == 400
    assert "acknowledgeCostPrivacy=true" in failed["error"]
    assert secret not in json.dumps(failed)


def test_openai_model_run_uses_server_secret_with_mocked_transport_and_redacts_response(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    secret = "sk-openai-runtime-secret-123456"
    captured = {}

    def transport(url, payload, headers, timeout):
        captured["url"] = url
        captured["payload"] = payload
        captured["headers"] = headers
        captured["timeout"] = timeout
        return {
            "output": [
                {
                    "content": [
                        {
                            "type": "output_text",
                            "text": (
                                '{"goal":"find_objects_from_text","objectLabels":["red ball"],'
                                '"objectId":"red_ball","textPrompt":"red ball",'
                                '"suggestedKeyframes":[0],'
                                '"providerPlan":{"discoveryProvider":"text_detector","maskProvider":"mock",'
                                '"trackingMode":"selected_only","rationale":"Use a text detector."},'
                                '"troubleshooting":["Review candidates before export."]}'
                            ),
                        }
                    ]
                }
            ],
            "usage": {"input_tokens": 10, "output_tokens": 20},
        }

    app.model_connectors = ModelConnectorRegistry(
        [
            FakeModelConnector(),
            EvoLinkPlanningConnector(),
            OpenAIPlanningConnector(transport=transport),
            OpenRouterSettingsModelConnector(),
        ]
    )
    status, _saved = api(
        app,
        "POST",
        "/api/provider-settings",
        {"providerId": "openai", "apiKey": secret, "allowHosted": True},
    )
    assert status == 200

    status, body = api(
        app,
        "POST",
        "/api/model-runs",
        {
            "providerId": "openai-planner",
            "allowNetwork": True,
            "acknowledgeCostPrivacy": True,
            "request": {
                "goal": "Find by description",
                "prompt": "red ball api_key=sk-or-v1-do-not-send-123456",
                "sourcePath": "/Users/alice/private/movie.mp4",
            },
        },
    )

    assert status == 200
    assert captured["url"] == "https://api.openai.com/v1/responses"
    assert captured["headers"]["Authorization"] == f"Bearer {secret}"
    encoded_payload = json.dumps(captured["payload"])
    assert "sk-or-v1-do-not-send" not in encoded_payload
    assert "/Users/alice" not in encoded_payload
    encoded_response = json.dumps(body)
    assert secret not in encoded_response
    assert "sk-or-v1-do-not-send" not in encoded_response
    assert body["modelRun"]["status"] == "succeeded"
    assert body["modelRun"]["result"]["providerId"] == "openai-planner"
    assert body["modelRun"]["result"]["validation"]["valid"] is True
    assert body["modelRun"]["result"]["runConfig"]["discovery"]["mode"] == "text_detector"


def test_evolink_model_run_uses_server_secret_with_mocked_chat_transport_and_redacts_response(tmp_path, monkeypatch):
    monkeypatch.delenv("EVOLINK_API_KEY", raising=False)
    monkeypatch.delenv("EVOLINK_DEFAULT_MODEL", raising=False)
    monkeypatch.delenv("EVOLINK_BASE_URL", raising=False)
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    secret = "evl-runtime-secret-123456"
    captured = {}

    def transport(url, payload, headers, timeout):
        captured["url"] = url
        captured["payload"] = payload
        captured["headers"] = headers
        captured["timeout"] = timeout
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"goal":"find_objects_from_text","objectLabels":["red ball"],'
                            '"objectId":"red_ball","textPrompt":"red ball",'
                            '"suggestedKeyframes":[0],'
                            '"providerPlan":{"discoveryProvider":"text_detector","maskProvider":"mock",'
                            '"trackingMode":"selected_only","rationale":"Use a text detector."},'
                            '"troubleshooting":["Review candidates before export."]}'
                        )
                    }
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }

    app.model_connectors = ModelConnectorRegistry(
        [
            FakeModelConnector(),
            EvoLinkPlanningConnector(transport=transport),
            OpenAIPlanningConnector(),
            OpenRouterSettingsModelConnector(),
        ]
    )
    status, _saved = api(
        app,
        "POST",
        "/api/provider-settings",
        {"providerId": "evolink", "apiKey": secret, "allowHosted": True},
    )
    assert status == 200

    status, body = api(
        app,
        "POST",
        "/api/model-runs",
        {
            "providerId": "evolink-planner",
            "allowNetwork": True,
            "acknowledgeCostPrivacy": True,
            "request": {
                "goal": "Find by description",
                "prompt": "red ball api_key=sk-or-v1-do-not-send-123456",
                "sourcePath": "/Users/alice/private/movie.mp4",
            },
        },
    )

    assert status == 200
    assert captured["url"] == "https://direct.evolink.ai/v1/chat/completions"
    assert captured["headers"]["Authorization"] == f"Bearer {secret}"
    encoded_payload = json.dumps(captured["payload"])
    assert "sk-or-v1-do-not-send" not in encoded_payload
    assert "/Users/alice" not in encoded_payload
    encoded_response = json.dumps(body)
    assert secret not in encoded_response
    assert "sk-or-v1-do-not-send" not in encoded_response
    assert body["modelRun"]["status"] == "succeeded"
    assert body["modelRun"]["result"]["providerId"] == "evolink-planner"
    assert body["modelRun"]["result"]["validation"]["valid"] is True
    assert body["modelRun"]["result"]["runConfig"]["discovery"]["mode"] == "text_detector"


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


def test_local_ui_model_runs_persist_across_app_instances_and_redact_paths(tmp_path):
    db_path = tmp_path / "backend.sqlite"
    storage_root = tmp_path / "storage"
    app = LocalUIApp(db_path=db_path, storage_root=storage_root, mock_mode=True)

    status, body = api(
        app,
        "POST",
        "/api/model-runs",
        {
            "providerId": "fake-local-planner",
            "request": {
                "goal": "Find by description",
                "prompt": "red ball",
                "sourcePath": str(tmp_path / "private-source.mp4"),
                "outputDirectory": str(tmp_path / "private-output"),
            },
        },
    )
    assert status == 200
    run_id = body["modelRun"]["id"]
    assert body["modelRun"]["status"] == "succeeded"
    assert str(tmp_path) not in json.dumps(body)

    reloaded_app = LocalUIApp(db_path=db_path, storage_root=storage_root, mock_mode=True)
    status, persisted = api(reloaded_app, "GET", f"/api/model-runs/{run_id}")

    assert status == 200
    assert persisted["modelRun"]["id"] == run_id
    assert persisted["modelRun"]["status"] == "succeeded"
    assert persisted["modelRun"]["result"]["validation"]["valid"] is True
    assert [event["eventType"] for event in persisted["modelRun"]["events"]] == ["queued", "running", "planned"]
    assert str(tmp_path) not in json.dumps(persisted)


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


def test_local_ui_confirms_model_plan_before_creating_extraction_job(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    secret = "sk-model-confirm-secret-123456"
    status, project_body = api(app, "POST", "/api/projects", {"name": "Confirmed Plan Project"})
    assert status == 200
    project = project_body["project"]
    status, video_body = api(app, "POST", "/api/videos", {"projectId": project["id"], "path": str(demo_video())})
    assert status == 200
    video = video_body["video"]

    status, run_body = api(
        app,
        "POST",
        "/api/model-runs",
        {
            "providerId": "fake-local-planner",
            "request": {"goal": "Cut out one object", "prompt": f"red ball api_key={secret}", "projectId": project["id"], "videoId": video["id"]},
        },
    )
    assert status == 200
    model_run = run_body["modelRun"]
    assert model_run["status"] == "succeeded"

    status, jobs_before = api(app, "GET", f"/api/jobs?projectId={project['id']}")
    assert status == 200
    assert jobs_before["jobs"] == []

    status, unconfirmed = api(
        app,
        "POST",
        f"/api/model-runs/{model_run['id']}/confirm-job",
        {"projectId": project["id"], "videoId": video["id"], "run": True},
    )
    assert status == 400
    assert "confirmation is required" in unconfirmed["error"]

    status, confirmed = api(
        app,
        "POST",
        f"/api/model-runs/{model_run['id']}/confirm-job",
        {"confirmed": True, "projectId": project["id"], "videoId": video["id"], "run": True},
    )
    assert status == 200
    assert confirmed["validation"]["valid"] is True
    assert confirmed["job"]["id"]
    event_types = [event["event_type"] for event in confirmed["job"]["events"]]
    assert "model_plan_attached" in event_types
    assert "worker_start_requested" in event_types
    assert event_types.index("model_plan_attached") < event_types.index("worker_start_requested")
    assert "apiKey" not in json.dumps(confirmed)
    assert secret not in json.dumps(confirmed)

    status, repeated = api(
        app,
        "POST",
        f"/api/model-runs/{model_run['id']}/confirm-job",
        {"confirmed": True, "projectId": project["id"], "videoId": video["id"], "run": True},
    )
    assert status == 200
    assert repeated["job"]["id"] == confirmed["job"]["id"]
    assert repeated["worker"]["status"] == "not_started"
    status, jobs_after_repeat = api(app, "GET", f"/api/jobs?projectId={project['id']}")
    assert status == 200
    assert len(jobs_after_repeat["jobs"]) == 1

    for _ in range(80):
        status, job_body = api(app, "GET", f"/api/jobs/{confirmed['job']['id']}")
        assert status == 200
        if job_body["job"]["status"] in {"succeeded", "failed", "canceled"}:
            break
        time.sleep(0.05)


def test_local_ui_confirm_model_plan_rejects_changed_video_selection(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    status, project_body = api(app, "POST", "/api/projects", {"name": "Mismatched Plan Project"})
    assert status == 200
    project = project_body["project"]
    status, video_body = api(app, "POST", "/api/videos", {"projectId": project["id"], "path": str(demo_video())})
    assert status == 200
    video = video_body["video"]
    status, second_video_body = api(app, "POST", "/api/videos", {"projectId": project["id"], "path": str(demo_video())})
    assert status == 200
    second_video = second_video_body["video"]

    status, run_body = api(
        app,
        "POST",
        "/api/model-runs",
        {
            "providerId": "fake-local-planner",
            "request": {"goal": "Cut out one object", "prompt": "red ball", "projectId": project["id"], "videoId": video["id"]},
        },
    )
    assert status == 200
    model_run = run_body["modelRun"]

    status, blocked = api(
        app,
        "POST",
        f"/api/model-runs/{model_run['id']}/confirm-job",
        {"confirmed": True, "projectId": project["id"], "videoId": second_video["id"], "run": True},
    )
    assert status == 400
    assert "selected video does not match" in blocked["error"]
    status, jobs = api(app, "GET", f"/api/jobs?projectId={project['id']}")
    assert status == 200
    assert jobs["jobs"] == []


def test_local_ui_confirm_model_plan_revalidates_and_blocks_nonlocal_provider(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    status, project_body = api(app, "POST", "/api/projects", {"name": "Blocked Plan Project"})
    assert status == 200
    project = project_body["project"]
    status, video_body = api(app, "POST", "/api/videos", {"projectId": project["id"], "path": str(demo_video())})
    assert status == 200
    video = video_body["video"]

    request = ModelPlanRequest.from_dict(
        {"goal": "Find by description", "prompt": "red ball", "projectId": project["id"], "videoId": video["id"]}
    )
    run = app.model_runs.create(provider_id="fake-local-planner", request=request)
    local_plan = FakeModelConnector().plan(request)
    bad_run_config = {
        **local_plan.run_config,
        "provider": {**local_plan.run_config["provider"], "name": "sam2-local"},
    }
    bad_plan = ModelPlanResult(
        provider_id=local_plan.provider_id,
        request=local_plan.request,
        goal=local_plan.goal,
        provider_plan={**local_plan.provider_plan, "maskProvider": "sam2-local"},
        privacy=local_plan.privacy,
        estimated_cost=local_plan.estimated_cost,
        run_config=bad_run_config,
        validation=local_plan.validation,
        requires_user_confirmation=True,
        messages=local_plan.messages,
    )
    app.model_runs.mark_running(run.id)
    app.model_runs.mark_succeeded(run.id, bad_plan)

    status, blocked = api(
        app,
        "POST",
        f"/api/model-runs/{run.id}/confirm-job",
        {"confirmed": True, "projectId": project["id"], "videoId": video["id"], "run": True},
    )
    assert status == 400
    assert "did not pass backend validation" in blocked["error"] or "cannot start extraction" in blocked["error"]
    status, jobs = api(app, "GET", f"/api/jobs?projectId={project['id']}")
    assert status == 200
    assert jobs["jobs"] == []
