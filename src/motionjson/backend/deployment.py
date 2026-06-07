from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping


DEPLOYMENT_READINESS_FORMAT = "motionjson.deployment_readiness.v0.1"
DEPLOYMENT_MODES = {
    "local_single_user",
    "colab_local",
    "ci",
    "hosted_single_tenant",
    "hosted_multi_tenant",
}
HOSTED_DEPLOYMENT_MODES = {"hosted_single_tenant", "hosted_multi_tenant"}


@dataclass(frozen=True)
class DeploymentBlocker:
    code: str
    component: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "component": self.component, "message": self.message}


@dataclass(frozen=True)
class DeploymentComponent:
    status: str
    kind: str
    implemented: bool
    configured: bool
    hosted_ready: bool
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "kind": self.kind,
            "implemented": self.implemented,
            "configured": self.configured,
            "hostedReady": self.hosted_ready,
            "message": self.message,
        }


@dataclass(frozen=True)
class DeploymentProfile:
    mode: str
    profile_source: str
    components: dict[str, DeploymentComponent]
    blockers: list[DeploymentBlocker]
    mock_mode: bool = False

    @property
    def hosted_requested(self) -> bool:
        return self.mode in HOSTED_DEPLOYMENT_MODES

    @property
    def hosted_ready(self) -> bool:
        return self.hosted_requested and not self.blockers and all(
            component.hosted_ready for component in self.components.values()
        )

    def to_dict(self) -> dict[str, Any]:
        local_first = self.mode in {"local_single_user", "colab_local", "ci"}
        return {
            "format": DEPLOYMENT_READINESS_FORMAT,
            "mode": self.mode,
            "profileSource": self.profile_source,
            "localFirst": local_first,
            "hostedRequested": self.hosted_requested,
            "hostedReady": self.hosted_ready,
            "collaborativeReady": False,
            "mockMode": self.mock_mode,
            "components": {key: value.to_dict() for key, value in self.components.items()},
            "blockers": [blocker.to_dict() for blocker in self.blockers],
            "runtimeBoundaries": {
                "auth": "Local single-user adapter by default; hosted modes fail closed without an implemented auth provider.",
                "database": "SQLite is the local implementation. External hosted databases are not configured by default.",
                "storage": "Local file storage is authorized through API routes. Future object storage must use signed URLs.",
                "queue": "Local jobs use the SQLite queue and in-process worker. External queue workers are not configured.",
                "secrets": "Environment variables and local provider settings are server-side only; no browser secret storage.",
                "modelRuns": self.components["modelRuns"].kind,
                "workers": self.components["workers"].kind,
            },
            "safeDefaults": {
                "mockNoModelFirstRun": True,
                "hostedCallsRequireOptIn": True,
                "hostedModeFailsClosed": True,
                "browserSecrets": False,
            },
        }


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def deployment_mode_from_env(environ: Mapping[str, str] | None = None, *, explicit_mode: str | None = None) -> tuple[str, str]:
    env = os.environ if environ is None else environ
    requested = (explicit_mode or env.get("MOTIONJSON_DEPLOYMENT_PROFILE") or "").strip().lower()
    if requested:
        if requested not in DEPLOYMENT_MODES:
            raise ValueError(f"MOTIONJSON_DEPLOYMENT_PROFILE must be one of: {', '.join(sorted(DEPLOYMENT_MODES))}")
        return requested, "explicit"
    if _truthy(env.get("CI")):
        return "ci", "detected"
    if env.get("COLAB_RELEASE_TAG") or env.get("COLAB_GPU") or env.get("JPY_PARENT_PID"):
        return "colab_local", "detected"
    return "local_single_user", "default"


def build_deployment_profile(
    *,
    environ: Mapping[str, str] | None = None,
    explicit_mode: str | None = None,
    mock_mode: bool = False,
    model_run_store: str = "persistent_sqlite",
) -> DeploymentProfile:
    env = os.environ if environ is None else environ
    mode, source = deployment_mode_from_env(env, explicit_mode=explicit_mode)
    hosted = mode in HOSTED_DEPLOYMENT_MODES
    blockers: list[DeploymentBlocker] = []

    def local_component(status: str, kind: str, message: str, *, hosted_ready: bool = False) -> DeploymentComponent:
        return DeploymentComponent(
            status=status,
            kind=kind,
            implemented=True,
            configured=True,
            hosted_ready=hosted_ready,
            message=message,
        )

    if not hosted:
        components = {
            "auth": local_component(
                "implemented",
                "local_single_user_adapter",
                "Local UI uses a single local account boundary and existing per-project authorization checks.",
            ),
            "database": local_component("implemented", "local_sqlite", "Local SQLite is initialized on demand."),
            "storage": local_component("implemented", "local_files", "Local file storage is served through authorized API content routes."),
            "queue": local_component("implemented", "sqlite_queue", "Local jobs use the SQLite-backed queue."),
            "secrets": local_component("implemented", "environment_and_local_settings", "Provider secrets stay server-side and are redacted from public payloads."),
            "modelRuns": local_component("implemented", model_run_store, "Model planning runs are persisted for the local SQLite workspace."),
            "workers": local_component("implemented", "in_process_worker", "The Local UI starts an in-process worker for local jobs."),
            "teamMode": DeploymentComponent("not_implemented", "single_user_only", False, False, False, "Collaborative team workspaces are not implemented."),
            "billing": DeploymentComponent("not_implemented", "local_usage_summary", False, False, False, "Billing is not implemented; local usage summaries remain zero-cost/accounting-only."),
        }
        blockers.append(
            DeploymentBlocker(
                code="hosted_collaboration_not_enabled",
                component="deployment",
                message="This runtime is local-first. Hosted collaboration requires explicit auth, external storage, queue workers, secrets management, team boundaries, and billing work.",
            )
        )
        return DeploymentProfile(mode=mode, profile_source=source, components=components, blockers=blockers, mock_mode=mock_mode)

    components = {
        "auth": DeploymentComponent(
            "not_configured",
            env.get("MOTIONJSON_AUTH_PROVIDER") or "none",
            False,
            False,
            False,
            "Hosted auth is not implemented or configured; private routes fail closed.",
        ),
        "database": DeploymentComponent(
            "not_configured",
            env.get("MOTIONJSON_DATABASE_PROVIDER") or "none",
            False,
            False,
            False,
            "Hosted database abstraction is not configured; local SQLite is not a multi-tenant hosted database.",
        ),
        "storage": DeploymentComponent(
            "not_configured",
            env.get("MOTIONJSON_STORAGE_PROVIDER") or "none",
            False,
            False,
            False,
            "Object storage with signed URLs is not configured.",
        ),
        "queue": DeploymentComponent(
            "not_configured",
            env.get("MOTIONJSON_QUEUE_PROVIDER") or "none",
            False,
            False,
            False,
            "External queue service is not configured.",
        ),
        "secrets": DeploymentComponent(
            "not_configured",
            env.get("MOTIONJSON_SECRETS_PROVIDER") or "none",
            False,
            False,
            False,
            "Hosted secrets manager is not configured.",
        ),
        "modelRuns": DeploymentComponent(
            "implemented_local_only",
            model_run_store,
            True,
            True,
            False,
            "SQLite model-run persistence is local-workspace scoped, not hosted multi-tenant scoped.",
        ),
        "workers": DeploymentComponent(
            "not_configured",
            env.get("MOTIONJSON_WORKER_PROVIDER") or "none",
            False,
            False,
            False,
            "External worker fleet and GPU isolation are not configured.",
        ),
        "teamMode": DeploymentComponent("not_implemented", env.get("MOTIONJSON_TEAM_MODE") or "none", False, False, False, "Team workspaces are not implemented."),
        "billing": DeploymentComponent("not_implemented", env.get("MOTIONJSON_BILLING_PROVIDER") or "none", False, False, False, "Hosted billing is not implemented."),
    }
    for code, component, message in [
        ("hosted_auth_not_configured", "auth", "Hosted auth provider is required before private routes can run."),
        ("hosted_database_not_configured", "database", "A durable hosted database is required for collaborative deployment."),
        ("object_storage_not_configured", "storage", "Object storage with signed URLs is required for hosted artifacts."),
        ("external_queue_not_configured", "queue", "An external queue and worker service is required for hosted jobs."),
        ("secrets_manager_not_configured", "secrets", "A hosted secrets manager is required for provider credentials."),
        ("external_workers_not_configured", "workers", "External workers and GPU isolation are required for hosted model jobs."),
        ("team_mode_not_implemented", "teamMode", "Team/workspace membership is not implemented."),
        ("billing_not_implemented", "billing", "Hosted billing/cost controls are not implemented."),
    ]:
        blockers.append(DeploymentBlocker(code=code, component=component, message=message))
    return DeploymentProfile(mode=mode, profile_source=source, components=components, blockers=blockers, mock_mode=mock_mode)


def build_deployment_readiness(**kwargs: Any) -> dict[str, Any]:
    return build_deployment_profile(**kwargs).to_dict()
