from __future__ import annotations

import pytest

from motionjson.config import ExtractionRunConfig
from motionjson.model_connectors import (
    FakeModelConnector,
    ModelConnectorError,
    ModelConnectorRegistry,
    ModelPlanRequest,
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


def test_model_connector_registry_exposes_fake_default_and_settings_provider():
    registry = ModelConnectorRegistry()

    assert registry.default_provider_id() == "fake-local-planner"
    provider_ids = [connector.provider.id for connector in registry.list()]
    assert provider_ids == ["fake-local-planner", "openrouter-planner"]


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
