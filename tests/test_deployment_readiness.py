from __future__ import annotations

import pytest

from motionjson.backend.deployment import build_deployment_readiness, deployment_mode_from_env


def test_local_deployment_readiness_preserves_mock_first_run_defaults():
    readiness = build_deployment_readiness(
        environ={},
        explicit_mode="local_single_user",
        mock_mode=True,
        model_run_store="persistent_sqlite",
    )

    assert readiness["format"] == "motionjson.deployment_readiness.v0.1"
    assert readiness["mode"] == "local_single_user"
    assert readiness["profileSource"] == "explicit"
    assert readiness["localFirst"] is True
    assert readiness["hostedRequested"] is False
    assert readiness["hostedReady"] is False
    assert readiness["mockMode"] is True
    assert readiness["safeDefaults"]["mockNoModelFirstRun"] is True
    assert readiness["components"]["auth"]["kind"] == "local_single_user_adapter"
    assert readiness["components"]["modelRuns"]["kind"] == "persistent_sqlite"
    assert readiness["components"]["modelRuns"]["implemented"] is True
    assert [blocker["code"] for blocker in readiness["blockers"]] == ["hosted_collaboration_not_enabled"]


def test_hosted_deployment_readiness_fails_closed_without_hosted_components():
    readiness = build_deployment_readiness(
        environ={"MOTIONJSON_DEPLOYMENT_PROFILE": "hosted_multi_tenant"},
        mock_mode=False,
        model_run_store="persistent_sqlite",
    )

    blocker_codes = {blocker["code"] for blocker in readiness["blockers"]}
    assert readiness["mode"] == "hosted_multi_tenant"
    assert readiness["profileSource"] == "explicit"
    assert readiness["localFirst"] is False
    assert readiness["hostedRequested"] is True
    assert readiness["hostedReady"] is False
    assert readiness["safeDefaults"]["hostedModeFailsClosed"] is True
    assert readiness["components"]["auth"]["status"] == "not_configured"
    assert readiness["components"]["modelRuns"]["status"] == "implemented_local_only"
    assert {
        "hosted_auth_not_configured",
        "hosted_database_not_configured",
        "object_storage_not_configured",
        "external_queue_not_configured",
        "secrets_manager_not_configured",
        "external_workers_not_configured",
        "team_mode_not_implemented",
        "billing_not_implemented",
    } <= blocker_codes


def test_deployment_profile_detection_requires_explicit_hosted_profile():
    assert deployment_mode_from_env({}) == ("local_single_user", "default")
    assert deployment_mode_from_env({"CI": "true"}) == ("ci", "detected")
    assert deployment_mode_from_env({"MOTIONJSON_DATABASE_PROVIDER": "postgres"}) == ("local_single_user", "default")
    assert deployment_mode_from_env({"MOTIONJSON_DEPLOYMENT_PROFILE": "hosted_single_tenant"}) == (
        "hosted_single_tenant",
        "explicit",
    )
    with pytest.raises(ValueError, match="MOTIONJSON_DEPLOYMENT_PROFILE"):
        deployment_mode_from_env({"MOTIONJSON_DEPLOYMENT_PROFILE": "production"})
