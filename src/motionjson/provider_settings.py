from __future__ import annotations

import copy
import json
import os
import re
import sqlite3
import uuid
from typing import Any, Mapping
from urllib.parse import urlparse

from motionjson.backend.usage import utc_now


PROVIDER_SETTINGS_FORMAT = "motionjson.local_provider_settings.v0.1"
PROVIDER_CATALOG_FORMAT = "motionjson.provider_registry.v0.1"

CUSTOM_MODEL_ID = "__custom__"

SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(api[_-]?key|authorization|password|secret|token)\s*[:=]\s*([^\s,;&]+)"
)
BEARER_RE = re.compile(r"(?i)\bBearer\s+([A-Za-z0-9._~+/=-]{8,})")
SIGNED_URL_QUERY_RE = re.compile(r"\b(https?://[^\s?#\"'<>]+)\?([^\s\"'<>]+)")
SECRET_VALUE_PATTERNS = [
    re.compile(r"\bsk-or-v1-[A-Za-z0-9._~-]{8,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9._~-]{8,}\b"),
    re.compile(r"\bmj_local_[A-Za-z0-9._~-]{8,}\b"),
]


PROVIDER_DEFINITIONS: list[dict[str, Any]] = [
    {
        "id": "mock",
        "name": "Mock no-model",
        "capabilityName": "mock",
        "kind": "mask_provider",
        "locality": "local",
        "implemented": True,
        "runsInLocalWorker": True,
        "credentialRequired": False,
        "credentialFields": [],
        "modelOptions": [{"id": "mock/no-model", "label": "Mock no-model"}],
        "defaultModel": "mock/no-model",
        "customModelAllowed": False,
        "capabilities": ["segmentation", "tracking smoke", "review smoke"],
        "hardware": "CPU",
        "cost": {"status": "zero_local", "label": "Free local"},
        "privacy": "Frames stay on this machine.",
        "warning": "",
        "docs": "docs/local_ui.md",
    },
    {
        "id": "threshold",
        "name": "HSV threshold",
        "capabilityName": "threshold",
        "kind": "mask_provider",
        "locality": "local",
        "implemented": True,
        "runsInLocalWorker": True,
        "credentialRequired": False,
        "credentialFields": [],
        "modelOptions": [{"id": "threshold/cpu", "label": "CPU color threshold"}],
        "defaultModel": "threshold/cpu",
        "customModelAllowed": False,
        "capabilities": ["segmentation", "binary masks"],
        "hardware": "CPU",
        "cost": {"status": "zero_local", "label": "Free local"},
        "privacy": "Frames stay on this machine.",
        "warning": "",
        "docs": "docs/provider_capabilities.md",
    },
    {
        "id": "motion",
        "name": "Motion foreground",
        "capabilityName": "motion",
        "kind": "mask_provider",
        "locality": "local",
        "implemented": True,
        "runsInLocalWorker": True,
        "credentialRequired": False,
        "credentialFields": [],
        "modelOptions": [{"id": "motion/cpu", "label": "CPU frame differencing"}],
        "defaultModel": "motion/cpu",
        "customModelAllowed": False,
        "capabilities": ["moving object proposals", "binary masks"],
        "hardware": "CPU",
        "cost": {"status": "zero_local", "label": "Free local"},
        "privacy": "Frames stay on this machine.",
        "warning": "",
        "docs": "docs/provider_capabilities.md",
    },
    {
        "id": "external",
        "name": "External masks",
        "capabilityName": "external",
        "kind": "mask_provider",
        "locality": "local",
        "implemented": True,
        "runsInLocalWorker": True,
        "credentialRequired": False,
        "credentialFields": [],
        "modelOptions": [{"id": "external/mask-directory", "label": "Mask directory"}],
        "defaultModel": "external/mask-directory",
        "customModelAllowed": False,
        "capabilities": ["mask import", "multi-object review"],
        "hardware": "CPU",
        "cost": {"status": "zero_local", "label": "Free local"},
        "privacy": "Imported masks stay on this machine.",
        "warning": "",
        "docs": "docs/provider_capabilities.md",
    },
    {
        "id": "sam2-local",
        "name": "SAM2 local",
        "capabilityName": "sam2-local",
        "kind": "mask_provider",
        "locality": "local",
        "implemented": True,
        "runsInLocalWorker": False,
        "credentialRequired": False,
        "credentialFields": [],
        "modelOptions": [
            {"id": "sam2/hiera-tiny", "label": "SAM2 Hiera tiny"},
            {"id": "sam2/hiera-small", "label": "SAM2 Hiera small"},
            {"id": "sam2/hiera-base-plus", "label": "SAM2 Hiera base+"},
            {"id": "sam2/hiera-large", "label": "SAM2 Hiera large"},
            {"id": CUSTOM_MODEL_ID, "label": "Custom local model id"},
        ],
        "defaultModel": "sam2/hiera-tiny",
        "customModelAllowed": True,
        "capabilities": ["prompt segmentation", "video propagation"],
        "hardware": "CPU, MPS, or CUDA depending on torch/SAM2 setup",
        "cost": {"status": "zero_local", "label": "Free local runtime"},
        "privacy": "Frames stay on this machine when SAM2 is installed locally.",
        "warning": "Requires local SAM2 and model paths. It is not part of the default CPU install.",
        "docs": "docs/sam2_segmentation.md",
    },
    {
        "id": "sam2-hosted",
        "name": "Hosted SAM2-compatible",
        "capabilityName": "sam2-hosted",
        "kind": "mask_provider",
        "locality": "hosted",
        "implemented": True,
        "runsInLocalWorker": False,
        "credentialRequired": True,
        "credentialFields": [
            {"name": "api_key", "label": "API key", "env": "HOSTED_SEGMENTATION_API_KEY", "required": True},
        ],
        "endpointField": {"name": "endpoint", "label": "Endpoint URL", "env": "HOSTED_SEGMENTATION_URL", "required": True},
        "modelOptions": [
            {"id": "auto", "label": "Provider default"},
            {"id": "sam2/hiera-large", "label": "SAM2 Hiera large"},
            {"id": CUSTOM_MODEL_ID, "label": "Custom hosted model id"},
        ],
        "defaultModel": "auto",
        "customModelAllowed": True,
        "capabilities": ["prompt segmentation", "hosted mask generation"],
        "hardware": "Remote provider",
        "cost": {"status": "unknown_provider_cost", "label": "Provider billed"},
        "privacy": "Frames or frame-derived data may leave this machine when hosted calls are enabled.",
        "warning": "Hosted segmentation is opt-in. Confirm cost and privacy before sending frames off-device.",
        "docs": "docs/security/api_keys.md",
    },
    {
        "id": "openrouter",
        "name": "OpenRouter LLM/VLM",
        "capabilityName": "openrouter",
        "kind": "llm_provider",
        "locality": "hosted",
        "implemented": True,
        "runsInLocalWorker": False,
        "credentialRequired": True,
        "credentialFields": [
            {"name": "api_key", "label": "API key", "env": "OPENROUTER_API_KEY", "required": True},
        ],
        "baseUrlField": {"name": "base_url", "label": "Base URL", "env": "OPENROUTER_BASE_URL", "required": False},
        "modelOptions": [
            {"id": "openrouter/auto", "label": "OpenRouter auto"},
            {"id": CUSTOM_MODEL_ID, "label": "Custom OpenRouter model id"},
        ],
        "defaultModel": "openrouter/auto",
        "customModelAllowed": True,
        "capabilities": ["LLM reasoning", "VLM/object identification", "labels"],
        "hardware": "Remote provider",
        "cost": {"status": "unknown_provider_cost", "label": "Provider billed"},
        "privacy": "Text prompts and any future VLM payloads are sent to a hosted provider.",
        "warning": "OpenRouter is for reasoning only. It is not a segmentation or mask provider.",
        "docs": "docs/ai_provider_architecture.md",
    },
    {
        "id": "text_detector",
        "name": "Text detector",
        "capabilityName": "text_detector",
        "kind": "discovery_provider",
        "locality": "local",
        "implemented": False,
        "runsInLocalWorker": False,
        "credentialRequired": False,
        "credentialFields": [],
        "modelOptions": [{"id": "detector/local-model-path", "label": "Configured local detector"}],
        "defaultModel": "detector/local-model-path",
        "customModelAllowed": True,
        "capabilities": ["text-guided boxes", "object candidates"],
        "hardware": "CPU/GPU depending on detector package",
        "cost": {"status": "zero_local", "label": "Free local runtime"},
        "privacy": "Frames stay on this machine when a local detector is configured.",
        "warning": "The current text detector path is scaffolded and remains capability-gated.",
        "docs": "docs/provider_capabilities.md",
    },
    {
        "id": "class_detector",
        "name": "Known-class detector",
        "capabilityName": "class_detector",
        "kind": "discovery_provider",
        "locality": "local",
        "implemented": False,
        "runsInLocalWorker": False,
        "credentialRequired": False,
        "credentialFields": [],
        "modelOptions": [{"id": "yolo/local-model-path", "label": "Configured local class model"}],
        "defaultModel": "yolo/local-model-path",
        "customModelAllowed": True,
        "capabilities": ["known-class boxes", "object candidates"],
        "hardware": "CPU/GPU depending on detector package",
        "cost": {"status": "zero_local", "label": "Free local runtime"},
        "privacy": "Frames stay on this machine when a local detector is configured.",
        "warning": "The current class detector path is scaffolded and remains capability-gated.",
        "docs": "docs/provider_capabilities.md",
    },
]

PROVIDER_BY_ID = {provider["id"]: provider for provider in PROVIDER_DEFINITIONS}


def provider_catalog() -> dict[str, Any]:
    return {"format": PROVIDER_CATALOG_FORMAT, "providers": copy.deepcopy(PROVIDER_DEFINITIONS)}


def redact_secret_value(value: str | None, *, provider_id: str = "secret") -> str:
    text = str(value or "")
    if not text:
        return ""
    if len(text) < 9:
        return f"<redacted:{provider_id}>"
    return f"{text[:3]}...{text[-4:]}"


def redact_secret_text(value: Any) -> str:
    text = str(value)
    text = SIGNED_URL_QUERY_RE.sub(lambda match: f"{match.group(1)}?[REDACTED_QUERY]", text)
    text = BEARER_RE.sub("Bearer [REDACTED]", text)
    text = SECRET_ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}=[REDACTED]", text)
    for pattern in SECRET_VALUE_PATTERNS:
        text = pattern.sub(lambda match: redact_secret_value(match.group(0)), text)
    return text


def redact_secret_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): ("[REDACTED]" if _is_secret_key(key) else redact_secret_payload(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_secret_payload(item) for item in value]
    if isinstance(value, str):
        return redact_secret_text(value)
    return value


def provider_settings_for_capabilities(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    environ: Mapping[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
    environ = environ or os.environ
    rows = _settings_rows(conn, user_id=user_id)
    return {
        provider_id: _capability_override(provider_id, rows.get(provider_id), environ)
        for provider_id in PROVIDER_BY_ID
    }


def provider_settings_response(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    environ = environ or os.environ
    rows = _settings_rows(conn, user_id=user_id)
    providers = [
        _public_provider_state(provider, rows.get(provider["id"]), environ)
        for provider in PROVIDER_DEFINITIONS
    ]
    return {
        "format": PROVIDER_SETTINGS_FORMAT,
        "catalogFormat": PROVIDER_CATALOG_FORMAT,
        "providers": providers,
        "defaults": {
            "safeMaskProvider": "mock",
            "safeReasoningProvider": "none",
            "hostedCallsDefault": "disabled",
            "credentialPrecedence": ["environment", "local_settings", "unset"],
        },
        "redaction": {
            "policy": "Raw keys are never returned by the Local UI API.",
            "displayExample": "sk-...abcd",
            "environmentOverridesLocal": True,
        },
    }


def save_provider_settings(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    payload: Mapping[str, Any],
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    provider_id = str(payload.get("providerId") or payload.get("provider_id") or "").strip()
    definition = _definition(provider_id)
    row = _settings_rows(conn, user_id=user_id).get(provider_id)
    settings, secrets = _row_payloads(row)

    if "enabled" in payload:
        settings["enabled"] = bool(payload.get("enabled"))
    if "selectedModel" in payload or "selected_model" in payload:
        settings["selected_model"] = _optional_text(payload.get("selectedModel", payload.get("selected_model")))
    if "customModelId" in payload or "custom_model_id" in payload:
        settings["custom_model_id"] = _optional_text(payload.get("customModelId", payload.get("custom_model_id")))
    if "endpoint" in payload:
        settings["endpoint"] = _optional_url(payload.get("endpoint"), "endpoint")
    if "baseUrl" in payload or "base_url" in payload:
        settings["base_url"] = _optional_url(payload.get("baseUrl", payload.get("base_url")), "baseUrl")
    if "allowHosted" in payload or "allow_hosted" in payload:
        settings["allow_hosted"] = bool(payload.get("allowHosted", payload.get("allow_hosted")))

    api_key = payload.get("apiKey", payload.get("api_key"))
    clear_key = bool(payload.get("clearApiKey") or payload.get("clear_api_key") or payload.get("apiKeyAction") == "clear")
    if clear_key:
        secrets.pop("api_key", None)
    elif isinstance(api_key, str) and api_key.strip():
        _ensure_accepts_credentials(definition)
        secrets["api_key"] = _clean_api_key(provider_id, api_key)

    _validate_model_settings(definition, settings)
    _upsert_provider_settings(conn, user_id=user_id, provider_id=provider_id, settings=settings, secrets=secrets, existing=row)
    return provider_settings_response(conn, user_id=user_id, environ=environ)


def reset_provider_settings(conn: sqlite3.Connection, *, user_id: str, provider_id: str) -> dict[str, Any]:
    _definition(provider_id)
    conn.execute("DELETE FROM provider_settings WHERE user_id = ? AND provider_id = ?", (user_id, provider_id))
    conn.commit()
    return {"reset": True, "providerId": provider_id}


def test_provider_settings(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    provider_id: str,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    environ = environ or os.environ
    definition = _definition(provider_id)
    row = _settings_rows(conn, user_id=user_id).get(provider_id)
    settings, secrets = _row_payloads(row)

    missing: list[str] = []
    invalid: list[str] = []
    for field in definition.get("credentialFields", []):
        name = str(field["name"])
        env = str(field.get("env") or "")
        value = environ.get(env) or secrets.get(name)
        if field.get("required") and not value:
            missing.append(env or name)
        elif value and not _api_key_plausible(value):
            invalid.append(env or name)

    endpoint_field = definition.get("endpointField")
    if endpoint_field:
        env = str(endpoint_field.get("env") or "")
        endpoint = environ.get(env) or settings.get("endpoint")
        if endpoint_field.get("required") and not endpoint:
            missing.append(env or "endpoint")
        elif endpoint and not _valid_http_url(str(endpoint)):
            invalid.append(env or "endpoint")

    model_status = _model_status(definition, settings)
    if model_status.get("status") == "missing_model":
        missing.append("model")

    if invalid:
        status = "invalid_key"
        message = f"{definition['name']} has a credential with an invalid local format."
    elif missing:
        status = "missing_configuration"
        message = f"{definition['name']} needs setup: {', '.join(missing)}."
    elif definition.get("locality") == "hosted":
        status = "configured"
        message = f"{definition['name']} is configured. No hosted network request was made by this safety check."
    else:
        status = "ready"
        message = f"{definition['name']} does not require API credentials."

    return {
        "format": "motionjson.provider_settings_test.v0.1",
        "providerId": provider_id,
        "status": status,
        "ready": status in {"ready", "configured"},
        "networkAttempted": False,
        "message": redact_secret_text(message),
        "missing": missing,
        "invalid": invalid,
        "model": model_status,
    }


def _definition(provider_id: str) -> dict[str, Any]:
    if provider_id not in PROVIDER_BY_ID:
        raise ValueError(f"Unknown provider settings id: {provider_id}")
    return PROVIDER_BY_ID[provider_id]


def _settings_rows(conn: sqlite3.Connection, *, user_id: str) -> dict[str, sqlite3.Row]:
    rows = conn.execute(
        """
        SELECT *
        FROM provider_settings
        WHERE user_id = ?
        ORDER BY provider_id
        """,
        (user_id,),
    ).fetchall()
    return {str(row["provider_id"]): row for row in rows}


def _row_payloads(row: sqlite3.Row | None) -> tuple[dict[str, Any], dict[str, str]]:
    if row is None:
        return {}, {}
    settings = json.loads(row["settings_json"] or "{}")
    secrets = json.loads(row["secret_json"] or "{}")
    if not isinstance(settings, dict):
        settings = {}
    if not isinstance(secrets, dict):
        secrets = {}
    return settings, {str(key): str(value) for key, value in secrets.items() if value}


def _upsert_provider_settings(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    provider_id: str,
    settings: Mapping[str, Any],
    secrets: Mapping[str, str],
    existing: sqlite3.Row | None,
) -> None:
    now = utc_now()
    row = {
        "id": existing["id"] if existing is not None else uuid.uuid4().hex,
        "user_id": user_id,
        "provider_id": provider_id,
        "settings_json": json.dumps(dict(settings), sort_keys=True),
        "secret_json": json.dumps(dict(secrets), sort_keys=True),
        "created_at": existing["created_at"] if existing is not None else now,
        "updated_at": now,
    }
    conn.execute(
        """
        INSERT INTO provider_settings
        (id, user_id, provider_id, settings_json, secret_json, created_at, updated_at)
        VALUES (:id, :user_id, :provider_id, :settings_json, :secret_json, :created_at, :updated_at)
        ON CONFLICT(user_id, provider_id)
        DO UPDATE SET
            settings_json = excluded.settings_json,
            secret_json = excluded.secret_json,
            updated_at = excluded.updated_at
        """,
        row,
    )
    conn.commit()


def _public_provider_state(
    definition: Mapping[str, Any],
    row: sqlite3.Row | None,
    environ: Mapping[str, str],
) -> dict[str, Any]:
    provider = copy.deepcopy(dict(definition))
    settings, secrets = _row_payloads(row)
    provider["settings"] = {
        "enabled": bool(settings.get("enabled", definition.get("locality") != "hosted")),
        "selectedModel": settings.get("selected_model") or definition.get("defaultModel"),
        "customModelId": settings.get("custom_model_id") or "",
        "endpoint": settings.get("endpoint") or "",
        "baseUrl": settings.get("base_url") or "",
        "allowHosted": bool(settings.get("allow_hosted", False)),
        "updatedAt": row["updated_at"] if row is not None else None,
        "source": "local_settings" if row is not None else "default",
    }
    provider["credentials"] = _credential_states(definition, settings, secrets, environ)
    provider["readiness"] = _readiness(definition, settings, secrets, environ)
    provider["effectiveModel"] = _effective_model(definition, settings)
    return provider


def _capability_override(
    provider_id: str,
    row: sqlite3.Row | None,
    environ: Mapping[str, str],
) -> dict[str, Any]:
    definition = PROVIDER_BY_ID[provider_id]
    settings, secrets = _row_payloads(row)
    credential_states = _credential_states(definition, settings, secrets, environ)
    api_credential = next((item for item in credential_states if item.get("name") == "api_key"), None)
    endpoint_field = definition.get("endpointField")
    base_url_field = definition.get("baseUrlField")
    endpoint = None
    base_url = None
    endpoint_source = "unset"
    base_url_source = "unset"
    endpoint_valid = True
    base_url_valid = True
    if endpoint_field:
        env = str(endpoint_field.get("env") or "")
        endpoint = environ.get(env) or settings.get("endpoint")
        endpoint_source = "environment" if environ.get(env) else "local_settings" if endpoint else "unset"
        endpoint_valid = not endpoint or _valid_http_url(str(endpoint))
    if base_url_field:
        env = str(base_url_field.get("env") or "")
        base_url = environ.get(env) or settings.get("base_url")
        base_url_source = "environment" if environ.get(env) else "local_settings" if base_url else "unset"
        base_url_valid = not base_url or _valid_http_url(str(base_url))
    selected_model = _effective_model(definition, settings)
    if provider_id == "openrouter" and not settings.get("selected_model") and environ.get("OPENROUTER_DEFAULT_MODEL"):
        selected_model = str(environ["OPENROUTER_DEFAULT_MODEL"])
    return {
        "configured": _readiness(definition, settings, secrets, environ)["configured"],
        "api_key_configured": bool(api_credential and api_credential.get("configured")),
        "credential_source": api_credential.get("source") if api_credential else "none",
        "endpoint_configured": bool(endpoint),
        "endpoint_source": endpoint_source,
        "endpoint_valid": endpoint_valid,
        "base_url_configured": bool(base_url),
        "base_url_source": base_url_source,
        "base_url_valid": base_url_valid,
        "settings_only": bool(endpoint_source == "local_settings" or (api_credential and api_credential.get("source") == "local_settings")),
        "allow_hosted": bool(settings.get("allow_hosted", False)),
        "selected_model": selected_model,
        "settings_source": "local_settings" if row is not None else "default",
    }


def _credential_states(
    definition: Mapping[str, Any],
    settings: Mapping[str, Any],
    secrets: Mapping[str, str],
    environ: Mapping[str, str],
) -> list[dict[str, Any]]:
    states: list[dict[str, Any]] = []
    for field in definition.get("credentialFields", []):
        name = str(field["name"])
        env = str(field.get("env") or "")
        env_value = environ.get(env)
        local_value = secrets.get(name)
        source = "environment" if env_value else "local_settings" if local_value else "unset"
        raw_value = env_value or local_value or ""
        states.append(
            {
                "name": name,
                "label": field.get("label") or name,
                "env": env,
                "required": bool(field.get("required")),
                "configured": bool(raw_value),
                "source": source,
                "display": redact_secret_value(raw_value, provider_id=str(definition["id"])) if raw_value else "",
            }
        )
    endpoint = definition.get("endpointField")
    if endpoint:
        env = str(endpoint.get("env") or "")
        value = environ.get(env) or settings.get("endpoint")
        states.append(
            {
                "name": "endpoint",
                "label": endpoint.get("label") or "Endpoint",
                "env": env,
                "required": bool(endpoint.get("required")),
                "configured": bool(value),
                "source": "environment" if environ.get(env) else "local_settings" if value else "unset",
                "display": value or "",
            }
        )
    return states


def _readiness(
    definition: Mapping[str, Any],
    settings: Mapping[str, Any],
    secrets: Mapping[str, str],
    environ: Mapping[str, str],
) -> dict[str, Any]:
    missing = []
    for field in definition.get("credentialFields", []):
        env = str(field.get("env") or "")
        name = str(field["name"])
        if field.get("required") and not (environ.get(env) or secrets.get(name)):
            missing.append(env or name)
    endpoint = definition.get("endpointField")
    if endpoint and endpoint.get("required"):
        env = str(endpoint.get("env") or "")
        value = environ.get(env) or settings.get("endpoint")
        if not value:
            missing.append(env or "endpoint")
        elif not _valid_http_url(str(value)):
            missing.append(f"{env or 'endpoint'} valid URL")
    model_status = _model_status(definition, settings)
    if model_status.get("status") == "missing_model":
        missing.append("model")
    if missing:
        status = "missing_key" if any("KEY" in item or "key" in item for item in missing) else "not_configured"
        message = f"Needs setup: {', '.join(missing)}."
    elif definition.get("locality") == "hosted" and not settings.get("allow_hosted"):
        status = "needs_hosted_confirmation"
        message = "Configured, but hosted calls remain disabled until you confirm cost and privacy."
    elif definition.get("locality") == "hosted":
        status = "configured"
        message = "Configured for hosted use. Local UI job execution still gates model-backed providers."
    elif definition.get("implemented"):
        status = "ready"
        message = "No API key required. Capability diagnostics still decide runtime availability."
    else:
        status = "planned"
        message = "Provider surface is planned or scaffolded and remains capability-gated."
    return {"status": status, "configured": not missing, "missing": missing, "message": message}


def _model_status(definition: Mapping[str, Any], settings: Mapping[str, Any]) -> dict[str, Any]:
    selected = settings.get("selected_model") or definition.get("defaultModel")
    custom = str(settings.get("custom_model_id") or "").strip()
    if selected == CUSTOM_MODEL_ID and not custom:
        return {"status": "missing_model", "selectedModel": selected, "effectiveModel": ""}
    return {"status": "ready", "selectedModel": selected, "effectiveModel": custom if selected == CUSTOM_MODEL_ID else selected}


def _effective_model(definition: Mapping[str, Any], settings: Mapping[str, Any]) -> str:
    status = _model_status(definition, settings)
    return str(status.get("effectiveModel") or definition.get("defaultModel") or "")


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_url(value: Any, field_name: str) -> str | None:
    text = _optional_text(value)
    if text is None:
        return None
    if not _valid_http_url(text):
        raise ValueError(f"{field_name}: expected an http:// or https:// URL.")
    return text


def _valid_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _ensure_accepts_credentials(definition: Mapping[str, Any]) -> None:
    if not definition.get("credentialFields"):
        raise ValueError(f"{definition['name']} does not use API keys. Leave mock/local providers credential-free.")


def _clean_api_key(provider_id: str, value: str) -> str:
    text = value.strip()
    if not _api_key_plausible(text):
        raise ValueError(f"{provider_id} API key is invalid or too short. Paste the key without spaces.")
    return text


def _api_key_plausible(value: str) -> bool:
    text = str(value or "").strip()
    return len(text) >= 8 and not re.search(r"\s", text)


def _validate_model_settings(definition: Mapping[str, Any], settings: Mapping[str, Any]) -> None:
    selected = settings.get("selected_model")
    if not selected:
        return
    allowed = {option["id"] for option in definition.get("modelOptions", [])}
    if selected not in allowed:
        raise ValueError(f"{definition['name']} model selection is not in the provider registry.")
    if selected == CUSTOM_MODEL_ID and not definition.get("customModelAllowed"):
        raise ValueError(f"{definition['name']} does not allow custom model ids.")


def _is_secret_key(key: Any) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
    return any(part in normalized for part in ("apikey", "authorization", "password", "secret", "token"))
