from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Any, Mapping

from motionjson.config import DISCOVERY_MODES, MASK_PROVIDERS

from .projects import list_projects
from .usage import summarize_usage, utc_now


WORKSPACE_FORMAT = "motionjson.local_ui_workspace.v0.1"
PREFERENCES_FORMAT = "motionjson.local_ui_preferences.v0.1"
COMMERCIAL_READINESS_FORMAT = "motionjson.local_ui_commercial_readiness.v0.1"

WORKSPACE_NAMESPACE = "local_ui"
EXPORT_PRESETS = {"compact", "debug", "vector-heavy", "raster-fallback"}
GUIDED_TASKS = [
    {
        "id": "trace_one_object",
        "label": "Trace one object",
        "description": "Start with one visible object and review the track before export.",
        "safeDefault": True,
        "requires": ["project", "video"],
    },
    {
        "id": "text_detector",
        "label": "Find objects from text",
        "description": "Use mock detector candidates locally, or configure a real detector later.",
        "safeDefault": True,
        "requires": ["project", "video", "review"],
    },
    {
        "id": "motion_foreground",
        "label": "Find moving objects",
        "description": "Use CPU motion foreground when the camera is mostly stable.",
        "safeDefault": True,
        "requires": ["project", "video", "review"],
    },
    {
        "id": "review_existing",
        "label": "Review existing result",
        "description": "Import a previous MotionJSON output and inspect tracks before export.",
        "safeDefault": True,
        "requires": ["project", "output_folder"],
    },
]

DEFAULT_PREFERENCES: dict[str, Any] = {
    "defaultGoal": "trace_one_object",
    "defaultMaskProvider": "mock",
    "defaultExportPreset": "compact",
    "showAdvancedControls": False,
    "rememberLastProject": True,
    "lastProjectId": None,
}


def _row_json(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        return {}
    try:
        parsed = json.loads(row["preferences_json"] or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _normalize_preferences(payload: Mapping[str, Any]) -> dict[str, Any]:
    preferences = {**DEFAULT_PREFERENCES}
    raw = payload.get("preferences") if isinstance(payload.get("preferences"), Mapping) else payload
    if not isinstance(raw, Mapping):
        return preferences

    if "defaultGoal" in raw:
        goal = str(raw.get("defaultGoal") or "").strip()
        allowed_goals = set(DISCOVERY_MODES) | {"trace_one_object", "review_existing"}
        if goal not in allowed_goals:
            raise ValueError(f"defaultGoal must be one of: {', '.join(sorted(allowed_goals))}")
        preferences["defaultGoal"] = goal
    if "defaultMaskProvider" in raw:
        provider = str(raw.get("defaultMaskProvider") or "").strip()
        if provider not in MASK_PROVIDERS:
            raise ValueError(f"defaultMaskProvider must be one of: {', '.join(sorted(MASK_PROVIDERS))}")
        preferences["defaultMaskProvider"] = provider
    if "defaultExportPreset" in raw:
        preset = str(raw.get("defaultExportPreset") or "").strip()
        if preset not in EXPORT_PRESETS:
            raise ValueError(f"defaultExportPreset must be one of: {', '.join(sorted(EXPORT_PRESETS))}")
        preferences["defaultExportPreset"] = preset
    for key in ("showAdvancedControls", "rememberLastProject"):
        if key in raw:
            preferences[key] = bool(raw.get(key))
    if "lastProjectId" in raw:
        value = raw.get("lastProjectId")
        preferences["lastProjectId"] = str(value).strip() if value else None
    return preferences


def get_workspace_preferences(conn: sqlite3.Connection, *, user_id: str) -> dict[str, Any]:
    row = conn.execute(
        "SELECT * FROM user_preferences WHERE user_id = ? AND namespace = ?",
        (user_id, WORKSPACE_NAMESPACE),
    ).fetchone()
    preferences = _normalize_preferences(_row_json(row))
    return {
        "format": PREFERENCES_FORMAT,
        "namespace": WORKSPACE_NAMESPACE,
        "preferences": preferences,
        "updatedAt": row["updated_at"] if row else None,
    }


def save_workspace_preferences(conn: sqlite3.Connection, *, user_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    current = get_workspace_preferences(conn, user_id=user_id)["preferences"]
    requested = payload.get("preferences") if isinstance(payload.get("preferences"), Mapping) else payload
    preferences = _normalize_preferences({**current, **dict(requested or {})})
    now = utc_now()
    row = conn.execute(
        "SELECT id FROM user_preferences WHERE user_id = ? AND namespace = ?",
        (user_id, WORKSPACE_NAMESPACE),
    ).fetchone()
    data = {
        "id": row["id"] if row else uuid.uuid4().hex,
        "user_id": user_id,
        "namespace": WORKSPACE_NAMESPACE,
        "preferences_json": json.dumps(preferences, sort_keys=True),
        "created_at": now,
        "updated_at": now,
    }
    if row:
        conn.execute(
            "UPDATE user_preferences SET preferences_json = :preferences_json, updated_at = :updated_at WHERE id = :id",
            data,
        )
    else:
        conn.execute(
            """
            INSERT INTO user_preferences (id, user_id, namespace, preferences_json, created_at, updated_at)
            VALUES (:id, :user_id, :namespace, :preferences_json, :created_at, :updated_at)
            """,
            data,
        )
    conn.commit()
    return get_workspace_preferences(conn, user_id=user_id)


def _load_json(value: str | None) -> dict[str, Any]:
    try:
        parsed = json.loads(value or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def recent_videos(conn: sqlite3.Connection, *, user_id: str, limit: int = 5) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT assets.id, assets.project_id, assets.content_type, assets.byte_size, assets.metadata_json, assets.created_at
        FROM assets
        JOIN projects ON projects.id = assets.project_id
        WHERE projects.owner_user_id = ? AND projects.archived_at IS NULL AND assets.kind = 'source_video'
        ORDER BY assets.created_at DESC
        LIMIT ?
        """,
        (user_id, limit),
    ).fetchall()
    videos = []
    for row in rows:
        metadata = _load_json(row["metadata_json"])
        videos.append(
            {
                "id": row["id"],
                "projectId": row["project_id"],
                "filename": metadata.get("filename") or metadata.get("name") or row["id"],
                "contentType": row["content_type"],
                "byteSize": row["byte_size"],
                "createdAt": row["created_at"],
            }
        )
    return videos


def recent_jobs(conn: sqlite3.Connection, *, user_id: str, limit: int = 5) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT jobs.id, jobs.project_id, jobs.type, jobs.status, jobs.payload_json, jobs.created_at, jobs.updated_at
        FROM jobs
        JOIN projects ON projects.id = jobs.project_id
        WHERE projects.owner_user_id = ? AND projects.archived_at IS NULL
        ORDER BY jobs.created_at DESC
        LIMIT ?
        """,
        (user_id, limit),
    ).fetchall()
    jobs = []
    for row in rows:
        payload = _load_json(row["payload_json"])
        run_config = payload.get("run_config") if isinstance(payload.get("run_config"), dict) else {}
        provider = run_config.get("provider") if isinstance(run_config.get("provider"), dict) else {}
        discovery = run_config.get("discovery") if isinstance(run_config.get("discovery"), dict) else {}
        jobs.append(
            {
                "id": row["id"],
                "projectId": row["project_id"],
                "type": row["type"],
                "status": row["status"],
                "provider": provider.get("name") or payload.get("maskProvider"),
                "discovery": discovery.get("mode"),
                "createdAt": row["created_at"],
                "updatedAt": row["updated_at"],
            }
        )
    return jobs


def workspace_response(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    provider_settings: Mapping[str, Any],
    export_presets_payload: list[dict[str, Any]],
    deployment: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    projects = list_projects(conn, user_id=user_id)
    configured = [
        provider for provider in provider_settings.get("providers", [])
        if isinstance(provider, Mapping) and provider.get("configured")
    ]
    hosted = [
        provider for provider in provider_settings.get("providers", [])
        if isinstance(provider, Mapping) and provider.get("locality") == "hosted"
    ]
    return {
        "format": WORKSPACE_FORMAT,
        "projects": projects[:5],
        "recentVideos": recent_videos(conn, user_id=user_id),
        "recentJobs": recent_jobs(conn, user_id=user_id),
        "guidedTasks": GUIDED_TASKS,
        "preferences": get_workspace_preferences(conn, user_id=user_id),
        "providerSettingsSummary": {
            "configuredCount": len(configured),
            "hostedProviderCount": len(hosted),
            "mockNoModelDefault": True,
        },
        "exportPresets": export_presets_payload,
        "deployment": dict(deployment or {}),
    }


def _audit_events(conn: sqlite3.Connection, *, user_id: str, limit: int = 8) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT audit_events.id, audit_events.project_id, audit_events.job_id, audit_events.asset_id,
               audit_events.object_id, audit_events.event_type, audit_events.metadata_json, audit_events.created_at
        FROM audit_events
        LEFT JOIN projects ON projects.id = audit_events.project_id
        WHERE audit_events.user_id = ? OR projects.owner_user_id = ?
        ORDER BY audit_events.created_at DESC
        LIMIT ?
        """,
        (user_id, user_id, limit),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "projectId": row["project_id"],
            "jobId": row["job_id"],
            "assetId": row["asset_id"],
            "objectId": row["object_id"],
            "eventType": row["event_type"],
            "metadata": _load_json(row["metadata_json"]),
            "createdAt": row["created_at"],
        }
        for row in rows
    ]


def _export_history(conn: sqlite3.Connection, *, user_id: str, limit: int = 8) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT assets.id, assets.project_id, assets.kind, assets.content_type, assets.byte_size,
               assets.source_job_id, assets.metadata_json, assets.created_at
        FROM assets
        JOIN projects ON projects.id = assets.project_id
        WHERE projects.owner_user_id = ?
          AND assets.kind IN (
            'final_export_manifest',
            'motionjson_export_zip',
            'validated_motionjson_scene',
            'export_quality_routing',
            'mp4_preview'
          )
        ORDER BY assets.created_at DESC
        LIMIT ?
        """,
        (user_id, limit),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "projectId": row["project_id"],
            "kind": row["kind"],
            "contentType": row["content_type"],
            "byteSize": row["byte_size"],
            "sourceJobId": row["source_job_id"],
            "metadata": _load_json(row["metadata_json"]),
            "createdAt": row["created_at"],
        }
        for row in rows
    ]


def commercial_readiness_response(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    deployment: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    user = conn.execute("SELECT id, email, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
    usage = summarize_usage(conn, user_id=user_id)
    deployment_payload = dict(deployment or {})
    deployment_mode = str(deployment_payload.get("mode") or "local_single_user")
    hosted_ready = deployment_payload.get("hostedReady") is True
    provider_history = [
        {
            "eventType": event["event_type"],
            "quantity": event["quantity"],
            "unit": event["unit"],
            "projectId": event["project_id"],
            "jobId": event["job_id"],
            "metadata": _load_json(event["metadata_json"]),
            "createdAt": event["created_at"],
        }
        for event in usage["events"]
        if _load_json(event.get("metadata_json")).get("provider") or event["event_type"] in {"provider_attempts", "job_failures"}
    ][-12:]
    return {
        "format": COMMERCIAL_READINESS_FORMAT,
        "accountBoundary": {
            "mode": "local_single_user" if deployment_mode in {"local_single_user", "colab_local", "ci"} else "hosted_auth_required",
            "deploymentMode": deployment_mode,
            "hostedReady": hosted_ready,
            "teamMode": "placeholder_not_enabled",
            "userId": user["id"] if user else user_id,
            "email": user["email"] if user else "local-ui@motionjson.local",
            "billing": "not_implemented",
        },
        "deployment": deployment_payload,
        "usageCost": usage,
        "providerRunHistory": provider_history,
        "exportHistory": _export_history(conn, user_id=user_id),
        "auditEvents": _audit_events(conn, user_id=user_id),
        "privacyNotices": [
            "Local providers keep source frames on this machine.",
            "Hosted providers require explicit opt-in and may send frames, prompts, or frame-derived data to a third party.",
            "Provider keys are redacted from Local UI responses and are not included in exported settings.",
        ],
        "rightsReminders": [
            "Commercial-use status should be reviewed before publishing exports.",
            "Creator approval and attribution requirements are surfaced as export warnings when metadata is incomplete.",
            "Asset library creator packs are metadata packs; they are not a public marketplace or billing system.",
        ],
    }
