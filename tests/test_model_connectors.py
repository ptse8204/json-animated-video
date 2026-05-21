from __future__ import annotations

from motionjson.config import ExtractionRunConfig
from motionjson.model_connectors import FakeModelConnector, ModelPlanRequest, VolatileModelRunStore


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
