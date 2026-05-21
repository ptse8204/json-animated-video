from __future__ import annotations

import pytest

from motionjson.config import ExtractionRunConfig
from motionjson.model_connectors import (
    FakeModelConnector,
    ModelConnectorError,
    ModelConnectorRegistry,
    ModelPlanRequest,
    OpenAIPlanningConnector,
    OpenRouterSettingsModelConnector,
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


def test_model_connector_registry_exposes_fake_default_and_settings_provider():
    registry = ModelConnectorRegistry()

    assert registry.default_provider_id() == "fake-local-planner"
    provider_ids = [connector.provider.id for connector in registry.list()]
    assert provider_ids == ["fake-local-planner", "openai-planner", "openrouter-planner"]


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
