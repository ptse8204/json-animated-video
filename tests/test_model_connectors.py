from __future__ import annotations

import sqlite3
import time

import pytest

from motionjson.backend.auth import register_user
from motionjson.backend.db import initialize_database
from motionjson.config import ExtractionRunConfig
from motionjson.model_connectors import (
    EvoLinkPlanningConnector,
    FakeModelConnector,
    ModelConnectorError,
    ModelConnectorRegistry,
    ModelPlanRequest,
    OpenAIPlanningConnector,
    OpenRouterSettingsModelConnector,
    SQLiteModelRunStore,
    VolatileModelRunStore,
)


def test_fake_model_connector_builds_valid_text_plan_without_network():
    connector = FakeModelConnector()
    request = ModelPlanRequest.from_dict(
        {
            "goal": "Find by description",
            "prompt": "red ball . hand . cup",
            "videoId": "asset_123",
            "projectId": "project_123",
        }
    )

    estimate = connector.estimate(request)
    result = connector.plan(request)

    assert connector.readiness()["networkAttempted"] is False
    assert estimate.hosted_calls_required is False
    assert result.validation["valid"] is True
    assert result.privacy["framesLeaveDevice"] is False
    assert result.provider_plan["reasoningProvider"] == "fake-local-planner"
    assert result.run_config["discovery"]["mode"] == "text_detector"
    assert result.run_config["provider"]["name"] == "mock"
    assert result.requires_user_confirmation is True
    ExtractionRunConfig.from_dict(result.run_config)


def test_fake_model_connector_builds_valid_trace_all_plan_without_network():
    connector = FakeModelConnector()
    request = ModelPlanRequest.from_dict(
        {
            "goal": "Trace all objects",
            "prompt": "find every likely foreground object",
            "videoId": "asset_123",
            "projectId": "project_123",
            "maxObjects": 6,
        }
    )

    result = connector.plan(request)

    assert result.goal == "discover_objects"
    assert result.provider_plan["discoveryProvider"] == "auto_object_proposals"
    assert result.provider_plan["trackingMode"] == "selected_only"
    assert result.run_config["discovery"]["mode"] == "auto_object_proposals"
    assert result.run_config["discovery"]["config"]["maxObjects"] == 6
    assert result.run_config["discovery"]["config"]["requireReview"] is True
    assert result.run_config["provider"]["name"] == "mock"
    ExtractionRunConfig.from_dict(result.run_config)


def test_openrouter_settings_connector_is_no_network_and_not_runnable():
    connector = OpenRouterSettingsModelConnector()
    request = ModelPlanRequest.from_dict({"goal": "Find by description", "prompt": "red ball"})

    readiness = connector.readiness()
    estimate = connector.estimate(request)

    assert connector.provider.settings_provider_id == "openrouter"
    assert connector.provider.implemented is False
    assert readiness["networkAttempted"] is False
    assert readiness["runnable"] is False
    assert estimate.hosted_calls_required is True
    assert estimate.frames_leave_device is False
    with pytest.raises(ModelConnectorError, match="settings-only"):
        connector.plan(request)


def test_openai_planning_connector_builds_valid_plan_with_mocked_transport():
    captured = {}

    def transport(url, payload, headers, timeout):
        captured["url"] = url
        captured["payload"] = payload
        captured["headers"] = headers
        captured["timeout"] = timeout
        return {
            "output_text": (
                '{"goal":"find_objects_from_text","objectLabels":["red ball"],'
                '"objectId":"red_ball","textPrompt":"red ball",'
                '"suggestedKeyframes":[0,3,3,99],'
                '"providerPlan":{"discoveryProvider":"text_detector","maskProvider":"mock",'
                '"trackingMode":"selected_only","rationale":"Use text candidates first."},'
                '"troubleshooting":["If candidates are broad, lower max area."]}'
            )
        }

    connector = OpenAIPlanningConnector(
        api_key="sk-openai-test-secret-123456",
        model="gpt-test-planner",
        transport=transport,
        timeout=9,
        allow_network=True,
    )
    request = ModelPlanRequest.from_dict(
        {
            "goal": "Find by description",
            "prompt": "red ball api_key=sk-or-v1-do-not-send-123456",
            "sourcePath": "/Users/alice/private/movie.mp4",
            "videoId": "asset_123",
            "projectId": "project_123",
            "maxFrames": 8,
        }
    )

    result = connector.plan(request)
    encoded_payload = str(captured["payload"])

    assert captured["url"] == "https://api.openai.com/v1/responses"
    assert captured["headers"]["Authorization"] == "Bearer sk-openai-test-secret-123456"
    assert captured["payload"]["model"] == "gpt-test-planner"
    assert captured["payload"]["text"]["format"]["type"] == "json_schema"
    assert captured["payload"]["store"] is False
    assert "sk-or-v1-do-not-send" not in encoded_payload
    assert "/Users/alice" not in encoded_payload
    assert result.validation["valid"] is True
    assert result.privacy["framesLeaveDevice"] is False
    assert result.privacy["hostedCallsRequired"] is True
    assert result.provider_plan["reasoningProvider"] == "openai-planner"
    assert result.run_config["discovery"]["mode"] == "text_detector"
    assert result.run_config["discovery"]["config"]["keyframes"] == [0, 3]
    assert result.run_config["provider"]["name"] == "mock"
    assert result.requires_user_confirmation is True
    ExtractionRunConfig.from_dict(result.run_config)


def test_openai_planning_connector_requires_network_opt_in_before_transport():
    called = False

    def transport(url, payload, headers, timeout):
        nonlocal called
        called = True
        return {}

    connector = OpenAIPlanningConnector(api_key="sk-openai-test-secret-123456", transport=transport)

    with pytest.raises(ModelConnectorError, match="does not make hosted calls by default"):
        connector.plan(ModelPlanRequest.from_dict({"goal": "Cut out one object"}))

    assert called is False


def test_evolink_planning_connector_uses_openai_compatible_chat_completions_with_mocked_transport():
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
                            '"suggestedKeyframes":[0,2],'
                            '"providerPlan":{"discoveryProvider":"text_detector","maskProvider":"mock",'
                            '"trackingMode":"selected_only","rationale":"Use text candidates first."},'
                            '"troubleshooting":["Review candidates before export."]}'
                        )
                    }
                }
            ]
        }

    connector = EvoLinkPlanningConnector(
        api_key="evl-test-secret-123456",
        model="gpt-5.2",
        transport=transport,
        timeout=11,
        allow_network=True,
    )
    request = ModelPlanRequest.from_dict(
        {
            "goal": "Find by description",
            "prompt": "red ball api_key=sk-or-v1-do-not-send-123456",
            "sourcePath": "/Users/alice/private/movie.mp4",
            "videoId": "asset_123",
            "projectId": "project_123",
            "maxFrames": 8,
        }
    )

    result = connector.plan(request)
    encoded_payload = str(captured["payload"])

    assert captured["url"] == "https://direct.evolink.ai/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer evl-test-secret-123456"
    assert captured["payload"]["model"] == "gpt-5.2"
    assert captured["payload"]["response_format"] == {"type": "json_object"}
    assert "sk-or-v1-do-not-send" not in encoded_payload
    assert "/Users/alice" not in encoded_payload
    assert result.validation["valid"] is True
    assert result.provider_plan["reasoningProvider"] == "evolink-planner"
    assert result.privacy["framesLeaveDevice"] is False
    assert result.run_config["discovery"]["mode"] == "text_detector"
    assert result.run_config["provider"]["name"] == "mock"
    ExtractionRunConfig.from_dict(result.run_config)


def test_evolink_planning_connector_requires_network_opt_in_before_transport():
    called = False

    def transport(url, payload, headers, timeout):
        nonlocal called
        called = True
        return {}

    connector = EvoLinkPlanningConnector(api_key="evl-test-secret-123456", transport=transport)

    with pytest.raises(ModelConnectorError, match="does not make hosted calls by default"):
        connector.plan(ModelPlanRequest.from_dict({"goal": "Cut out one object"}))

    assert called is False


def test_model_connector_registry_exposes_fake_default_and_settings_provider():
    registry = ModelConnectorRegistry()

    assert registry.default_provider_id() == "fake-local-planner"
    provider_ids = [connector.provider.id for connector in registry.list()]
    assert provider_ids == ["fake-local-planner", "evolink-planner", "openai-planner", "openrouter-planner"]


def test_volatile_model_run_store_tracks_events_and_cancellation():
    store = VolatileModelRunStore(max_runs=2)
    request = ModelPlanRequest.from_dict({"goal": "Cut out one object"})
    first = store.create(provider_id="fake-local-planner", request=request)

    assert first.status == "pending"
    assert store.events(first.id)[0].event_type == "queued"

    canceled = store.cancel(first.id, reason="test_cancel")
    assert canceled.status == "canceled"
    assert canceled.events[-1].event_type == "canceled"

    store.create(provider_id="fake-local-planner", request=request)
    third = store.create(provider_id="fake-local-planner", request=request)
    assert store.get(third.id).id == third.id


def test_sqlite_model_run_store_persists_events_and_scopes_by_owner(tmp_path):
    db_path = tmp_path / "model-runs.sqlite"
    conn = initialize_database(sqlite3.connect(db_path))
    try:
        owner = register_user(conn, email="owner@example.test", password="secret")
        other = register_user(conn, email="other@example.test", password="secret")
    finally:
        conn.close()

    def connect():
        return initialize_database(sqlite3.connect(db_path))

    owner_store = SQLiteModelRunStore(
        connection_factory=connect,
        owner_user_id_factory=lambda conn: owner["id"],
        max_runs=4,
    )
    other_store = SQLiteModelRunStore(
        connection_factory=connect,
        owner_user_id_factory=lambda conn: other["id"],
        max_runs=4,
    )
    request = ModelPlanRequest.from_dict(
        {
            "goal": "Find by description",
            "prompt": "red ball",
        }
    )

    run = owner_store.create(provider_id="fake-local-planner", request=request)
    owner_store.mark_running(run.id)
    planned = FakeModelConnector().plan(request)
    owner_store.mark_succeeded(run.id, planned)

    reloaded_store = SQLiteModelRunStore(
        connection_factory=connect,
        owner_user_id_factory=lambda conn: owner["id"],
        max_runs=4,
    )
    reloaded = reloaded_store.get(run.id)
    events = reloaded_store.events(run.id)

    assert reloaded.status == "succeeded"
    assert reloaded.request.prompt == "red ball"
    assert reloaded.result is not None
    assert reloaded.result.validation["valid"] is True
    assert [event.event_type for event in events] == ["queued", "running", "planned"]
    with pytest.raises(ModelConnectorError, match="model run not found"):
        other_store.get(run.id)


def test_sqlite_model_run_store_trims_per_owner_and_removes_events(tmp_path):
    db_path = tmp_path / "model-runs-trim.sqlite"
    conn = initialize_database(sqlite3.connect(db_path))
    try:
        owner = register_user(conn, email="trim-owner@example.test", password="secret")
        other = register_user(conn, email="trim-other@example.test", password="secret")
    finally:
        conn.close()

    def connect():
        return initialize_database(sqlite3.connect(db_path))

    owner_store = SQLiteModelRunStore(
        connection_factory=connect,
        owner_user_id_factory=lambda conn: owner["id"],
        max_runs=2,
    )
    other_store = SQLiteModelRunStore(
        connection_factory=connect,
        owner_user_id_factory=lambda conn: other["id"],
        max_runs=2,
    )
    request = ModelPlanRequest.from_dict({"goal": "Cut out one object"})

    first = owner_store.create(provider_id="fake-local-planner", request=request)
    owner_store.mark_running(first.id)
    time.sleep(0.001)
    other_run = other_store.create(provider_id="fake-local-planner", request=request)
    time.sleep(0.001)
    second = owner_store.create(provider_id="fake-local-planner", request=request)
    time.sleep(0.001)
    third = owner_store.create(provider_id="fake-local-planner", request=request)

    with pytest.raises(ModelConnectorError, match="model run not found"):
        owner_store.get(first.id)
    assert owner_store.get(second.id).id == second.id
    assert owner_store.get(third.id).id == third.id
    assert other_store.get(other_run.id).id == other_run.id

    conn = connect()
    try:
        event_count = conn.execute(
            "SELECT COUNT(*) FROM model_run_events WHERE model_run_id = ?",
            (first.id,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert event_count == 0
