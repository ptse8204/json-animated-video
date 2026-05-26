from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import uuid
from importlib.util import find_spec
from pathlib import Path
from typing import Any, Mapping

from motionjson.backend.usage import utc_now
from motionjson.provider_settings import (
    diagnose_provider_settings,
    hosted_sam3_smoke_test,
    local_sam_smoke_test,
    provider_runtime_settings,
    redact_secret_payload,
    redact_secret_text,
    save_provider_settings,
    test_provider_settings,
)
from motionjson.providers.sam2 import SAM2_HF_AUTO_MASKS_DEFAULT_MODEL
from motionjson.providers.sam3 import SAM3_HF_REPO_ID


PROVIDER_SETUP_JOB_FORMAT = "motionjson.provider_setup_job.v0.1"
TERMINAL_SETUP_JOB_STATUSES = {"succeeded", "failed", "canceled", "blocked"}


def provider_setup_actions(provider_id: str) -> list[dict[str, Any]]:
    """Return server-owned setup actions the browser may request."""

    if provider_id == "sam3-local":
        return [
            {
                "id": "install",
                "label": "Install scene sweep",
                "description": "Install MotionJSON's independent SAM3 Transformers runtime. SAM2 is not required.",
                "requiresConfirmation": True,
                "networkAttempted": True,
                "heavyLocalAttempted": True,
            },
            {
                "id": "cache_model",
                "label": "Cache model",
                "description": "Download/cache facebook/sam3 for SAM3 Scene Sweep after explicit network and disk confirmation.",
                "requiresConfirmation": True,
                "networkAttempted": True,
                "heavyLocalAttempted": False,
            },
            {
                "id": "check_access",
                "label": "Check Hugging Face access",
                "description": "Verify that the runtime can access facebook/sam3 after the user confirms network use.",
                "requiresConfirmation": True,
                "networkAttempted": True,
                "heavyLocalAttempted": False,
            },
            {
                "id": "diagnose",
                "label": "Diagnose",
                "description": "Check saved SAM3 settings without importing heavy runtimes or making network calls.",
                "networkAttempted": False,
                "heavyLocalAttempted": False,
            },
            {
                "id": "smoke",
                "label": "Run smoke test",
                "description": "Run a bounded local smoke test after explicit heavy-runtime confirmation.",
                "requiresConfirmation": True,
                "networkAttempted": False,
                "heavyLocalAttempted": True,
            },
        ]
    if provider_id == "sam2-hf-auto-masks":
        return [
            {
                "id": "install",
                "label": "Install SAM2 HF fallback",
                "description": "Install MotionJSON's independent SAM2 Transformers fallback. Official SAM2 checkpoint/config is not required.",
                "requiresConfirmation": True,
                "networkAttempted": True,
                "heavyLocalAttempted": True,
            },
            {
                "id": "cache_model",
                "label": "Cache model",
                "description": "Download/cache facebook/sam2.1-hiera-large after explicit network and disk confirmation.",
                "requiresConfirmation": True,
                "networkAttempted": True,
                "heavyLocalAttempted": False,
            },
            {
                "id": "diagnose",
                "label": "Diagnose",
                "description": "Check Transformers and torch imports without network or model load.",
                "networkAttempted": False,
                "heavyLocalAttempted": False,
            },
            {
                "id": "smoke",
                "label": "Run smoke test",
                "description": "Run a bounded local smoke test after explicit heavy-runtime confirmation.",
                "requiresConfirmation": True,
                "networkAttempted": False,
                "heavyLocalAttempted": True,
            },
        ]
    if provider_id == "sam2-local":
        return [
            {
                "id": "install",
                "label": "Install SAM2 fallback",
                "description": "Install MotionJSON's optional local SAM2 fallback dependencies.",
                "requiresConfirmation": True,
                "networkAttempted": True,
                "heavyLocalAttempted": True,
            },
            {
                "id": "diagnose",
                "label": "Diagnose",
                "description": "Check saved SAM2 paths without importing heavy runtimes or making network calls.",
                "networkAttempted": False,
                "heavyLocalAttempted": False,
            },
            {
                "id": "smoke",
                "label": "Run smoke test",
                "description": "Run a bounded local smoke test after explicit heavy-runtime confirmation.",
                "requiresConfirmation": True,
                "networkAttempted": False,
                "heavyLocalAttempted": True,
            },
        ]
    if provider_id in {"sam2-hosted", "sam3-hosted"}:
        return [
            {
                "id": "diagnose",
                "label": "Diagnose",
                "description": "Check saved hosted settings without a network request.",
                "networkAttempted": False,
                "heavyLocalAttempted": False,
            },
            {
                "id": "test",
                "label": "Check access",
                "description": "Validate hosted credentials and endpoint format without a provider request.",
                "networkAttempted": False,
                "heavyLocalAttempted": False,
            },
            {
                "id": "smoke",
                "label": "Run hosted smoke test",
                "description": "Run a hosted smoke test only after cost, privacy, and network confirmation.",
                "requiresConfirmation": True,
                "networkAttempted": True,
                "heavyLocalAttempted": False,
            },
        ]
    return [
        {
            "id": "diagnose",
            "label": "Diagnose",
            "description": "Check provider registration and saved settings.",
            "networkAttempted": False,
            "heavyLocalAttempted": False,
        }
    ]


def create_provider_setup_job(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    provider_id: str,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = dict(payload or {})
    action = _normalize_action(provider_id, payload.get("action") or payload.get("setupAction") or "diagnose")
    now = utc_now()
    row = {
        "id": uuid.uuid4().hex,
        "user_id": user_id,
        "provider_id": provider_id,
        "action": action,
        "status": "queued",
        "payload_json": json.dumps(redact_secret_payload(payload), sort_keys=True),
        "result_json": "{}",
        "error": None,
        "created_at": now,
        "updated_at": now,
        "started_at": None,
        "finished_at": None,
        "cancel_requested_at": None,
    }
    conn.execute(
        """
        INSERT INTO provider_setup_jobs
        (id, user_id, provider_id, action, status, payload_json, result_json, error, created_at, updated_at, started_at, finished_at, cancel_requested_at)
        VALUES
        (:id, :user_id, :provider_id, :action, :status, :payload_json, :result_json, :error, :created_at, :updated_at, :started_at, :finished_at, :cancel_requested_at)
        """,
        row,
    )
    _record_setup_event(conn, job_id=row["id"], event_type="queued", message=f"{provider_id} setup action queued.", metadata={"action": action})
    conn.commit()
    return public_provider_setup_job(conn, user_id=user_id, job_id=row["id"], include_events=True)


def run_provider_setup_job(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    job_id: str,
    payload: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    row = _setup_job_row(conn, user_id=user_id, job_id=job_id)
    if row["status"] in TERMINAL_SETUP_JOB_STATUSES:
        return public_provider_setup_job(conn, user_id=user_id, job_id=job_id, include_events=True)
    provider_id = str(row["provider_id"])
    action = str(row["action"])
    runtime_payload = dict(payload or {})
    stored_payload = _json_dict(row["payload_json"])
    effective_payload = {**stored_payload, **runtime_payload}
    now = utc_now()
    conn.execute(
        "UPDATE provider_setup_jobs SET status = 'running', started_at = COALESCE(started_at, ?), updated_at = ? WHERE id = ?",
        (now, now, job_id),
    )
    _record_setup_event(conn, job_id=job_id, event_type="started", message=f"{provider_id} setup action started.", metadata={"action": action})
    conn.commit()

    try:
        _raise_if_canceled(conn, job_id)
        result = _execute_setup_action(conn, user_id=user_id, provider_id=provider_id, action=action, payload=effective_payload, environ=environ)
        _raise_if_canceled(conn, job_id)
    except _SetupCanceled as exc:
        _finish_setup_job(conn, job_id=job_id, status="canceled", result={"message": str(exc)}, error=str(exc))
    except Exception as exc:
        message = redact_secret_text(str(exc) or type(exc).__name__)
        _record_setup_event(conn, job_id=job_id, event_type="failed", message=message, metadata={"action": action})
        _finish_setup_job(conn, job_id=job_id, status="failed", result={"message": message}, error=message)
    else:
        status = "succeeded" if _result_ready_or_ok(result) else str(result.get("status") or "blocked")
        if status not in TERMINAL_SETUP_JOB_STATUSES:
            status = "succeeded" if result.get("ready") is True else "blocked"
        _record_setup_event(
            conn,
            job_id=job_id,
            event_type=status,
            message=str(result.get("message") or f"{provider_id} setup action finished."),
            metadata={"action": action, "ready": result.get("ready")},
        )
        _finish_setup_job(conn, job_id=job_id, status=status, result=result, error=None if status == "succeeded" else result.get("message"))
    return public_provider_setup_job(conn, user_id=user_id, job_id=job_id, include_events=True)


def public_provider_setup_job(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    job_id: str,
    include_events: bool = False,
) -> dict[str, Any]:
    row = _setup_job_row(conn, user_id=user_id, job_id=job_id)
    payload = _json_dict(row["payload_json"])
    result = _json_dict(row["result_json"])
    public = {
        "id": row["id"],
        "providerId": row["provider_id"],
        "action": row["action"],
        "status": row["status"],
        "payload": redact_secret_payload(payload),
        "result": redact_secret_payload(result),
        "error": redact_secret_text(row["error"]) if row["error"] else "",
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "startedAt": row["started_at"],
        "finishedAt": row["finished_at"],
        "cancelRequestedAt": row["cancel_requested_at"],
        "terminal": row["status"] in TERMINAL_SETUP_JOB_STATUSES,
        "setupState": _setup_state_for_job(row["status"], row["action"], result),
    }
    if include_events:
        public["events"] = list_provider_setup_events(conn, user_id=user_id, job_id=job_id)
    return public


def list_provider_setup_events(conn: sqlite3.Connection, *, user_id: str, job_id: str) -> list[dict[str, Any]]:
    _setup_job_row(conn, user_id=user_id, job_id=job_id)
    rows = conn.execute(
        """
        SELECT *
        FROM provider_setup_events
        WHERE setup_job_id = ?
        ORDER BY created_at, id
        """,
        (job_id,),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "type": row["event_type"],
            "message": redact_secret_text(row["message"]),
            "metadata": redact_secret_payload(_json_dict(row["metadata_json"])),
            "createdAt": row["created_at"],
        }
        for row in rows
    ]


def cancel_provider_setup_job(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    job_id: str,
    reason: str = "user_canceled",
) -> dict[str, Any]:
    row = _setup_job_row(conn, user_id=user_id, job_id=job_id)
    if row["status"] in TERMINAL_SETUP_JOB_STATUSES:
        return public_provider_setup_job(conn, user_id=user_id, job_id=job_id, include_events=True)
    now = utc_now()
    message = redact_secret_text(reason or "user_canceled")
    conn.execute(
        """
        UPDATE provider_setup_jobs
        SET status = 'canceled', error = ?, cancel_requested_at = ?, finished_at = ?, updated_at = ?
        WHERE id = ?
        """,
        (message, now, now, now, job_id),
    )
    _record_setup_event(conn, job_id=job_id, event_type="canceled", message=message, metadata={"reason": message})
    conn.commit()
    return public_provider_setup_job(conn, user_id=user_id, job_id=job_id, include_events=True)


def _execute_setup_action(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    provider_id: str,
    action: str,
    payload: Mapping[str, Any],
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    environ = environ or os.environ
    settings_payload = payload.get("settings") if isinstance(payload.get("settings"), Mapping) else payload
    if _truthy(payload.get("saveFirst", payload.get("save_first", True))) and action in {"diagnose", "test", "smoke", "check_access", "cache_model"}:
        if any(key in settings_payload for key in ("selectedModel", "selected_model", "customModelId", "custom_model_id", "apiKey", "api_key", "hfToken", "hf_token", "sam2CheckpointPath", "sam2_checkpoint_path", "sam2HfDevice", "sam2_hf_device", "sam3ModelPath", "sam3_model_path", "endpoint", "allowHosted", "allow_hosted", "hostedProfileId", "hosted_profile_id")):
            save_provider_settings(conn, user_id=user_id, payload={**dict(settings_payload), "providerId": provider_id}, environ=environ)

    if action == "diagnose":
        return diagnose_provider_settings(conn, user_id=user_id, provider_id=provider_id, payload=settings_payload, environ=environ)
    if action == "test":
        return test_provider_settings(conn, user_id=user_id, provider_id=provider_id, environ=environ)
    if action == "smoke":
        if provider_id in {"sam2-local", "sam2-hf-auto-masks", "sam3-local"}:
            return local_sam_smoke_test(conn, user_id=user_id, provider_id=provider_id, payload=payload, environ=environ)
        return hosted_sam3_smoke_test(conn, user_id=user_id, payload={**dict(payload), "providerId": provider_id}, environ=environ)
    if action == "install":
        return _run_install_action(provider_id, payload)
    if action == "cache_model":
        runtime = provider_runtime_settings(conn, user_id=user_id, provider_id=provider_id, environ=environ)
        return _cache_model_action(provider_id, payload, token=str(runtime.get("hf_token") or ""))
    if action == "check_access":
        runtime = provider_runtime_settings(conn, user_id=user_id, provider_id=provider_id, environ=environ)
        return _check_sam3_hf_access(payload, token=str(runtime.get("hf_token") or ""), environ=environ)
    raise ValueError(f"Setup action is not implemented for {provider_id}: {action}")


def _run_install_action(provider_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    command = _install_command(provider_id)
    command_display = " ".join(command)
    if _truthy(payload.get("dryRun", payload.get("dry_run"))):
        return {
            "format": PROVIDER_SETUP_JOB_FORMAT,
            "providerId": provider_id,
            "action": "install",
            "status": "succeeded",
            "ready": True,
            "dryRun": True,
            "networkAttempted": False,
            "heavyLocalAttempted": False,
            "message": f"Install dry run accepted for {provider_id}.",
            "command": command_display,
        }

    timeout_seconds = min(max(int(payload.get("timeoutSeconds") or payload.get("timeout_seconds") or 1800), 30), 7200)
    completed = subprocess.run(
        command,
        cwd=str(_repo_root()),
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    output = redact_secret_text((completed.stdout or "") + ("\n" if completed.stdout and completed.stderr else "") + (completed.stderr or ""))
    tail = output[-6000:]
    if completed.returncode != 0:
        raise ValueError(f"Install command failed with exit code {completed.returncode}: {tail or command_display}")
    return {
        "format": PROVIDER_SETUP_JOB_FORMAT,
        "providerId": provider_id,
        "action": "install",
        "status": "succeeded",
        "ready": True,
        "networkAttempted": True,
        "heavyLocalAttempted": True,
        "message": f"{provider_id} optional dependencies installed.",
        "command": command_display,
        "outputTail": tail,
    }


def _install_command(provider_id: str) -> list[str]:
    extras = {
        "sam3-local": "sam3-transformers",
        "sam2-hf-auto-masks": "sam2-transformers",
        "sam2-local": "sam2",
    }
    extra = extras.get(provider_id)
    if not extra:
        raise ValueError(f"{provider_id} does not have a local install action.")
    root = _repo_root()
    if (root / "pyproject.toml").exists():
        return [sys.executable, "-m", "pip", "install", "-e", f".[{extra}]"]
    return [sys.executable, "-m", "pip", "install", f"motionjson[{extra}]"]


def _cache_model_action(provider_id: str, payload: Mapping[str, Any], *, token: str = "") -> dict[str, Any]:
    if not _truthy(payload.get("allowNetwork", payload.get("allow_network"))):
        return {
            "format": PROVIDER_SETUP_JOB_FORMAT,
            "providerId": provider_id,
            "action": "cache_model",
            "status": "blocked",
            "ready": False,
            "networkAttempted": False,
            "heavyLocalAttempted": False,
            "message": "Model caching needs explicit network confirmation.",
        }
    if not _truthy(payload.get("allowDisk", payload.get("allow_disk", payload.get("allowDownload", payload.get("allow_download"))))):
        return {
            "format": PROVIDER_SETUP_JOB_FORMAT,
            "providerId": provider_id,
            "action": "cache_model",
            "status": "blocked",
            "ready": False,
            "networkAttempted": False,
            "heavyLocalAttempted": False,
            "message": "Model caching needs explicit disk/download confirmation.",
        }
    default_model = SAM3_HF_REPO_ID if provider_id == "sam3-local" else SAM2_HF_AUTO_MASKS_DEFAULT_MODEL
    model_id = str(payload.get("model") or payload.get("modelId") or payload.get("model_id") or default_model).strip() or default_model
    if model_id.endswith(".pt") or Path(model_id).expanduser().is_file():
        raise ValueError(
            "Model caching expects a Hugging Face repo id or local model directory, not a single .pt checkpoint file."
        )
    local_candidate = Path(model_id).expanduser()
    if local_candidate.exists() and local_candidate.is_dir():
        return {
            "format": PROVIDER_SETUP_JOB_FORMAT,
            "providerId": provider_id,
            "action": "cache_model",
            "status": "succeeded",
            "ready": True,
            "networkAttempted": False,
            "heavyLocalAttempted": False,
            "message": "Selected local model directory is available.",
            "model": model_id,
            "localModelDir": str(local_candidate),
            "progress": {"percent": 100, "known": True, "label": "Model directory found"},
        }
    if _truthy(payload.get("dryRun", payload.get("dry_run"))):
        return {
            "format": PROVIDER_SETUP_JOB_FORMAT,
            "providerId": provider_id,
            "action": "cache_model",
            "status": "succeeded",
            "ready": True,
            "dryRun": True,
            "networkAttempted": False,
            "heavyLocalAttempted": False,
            "message": f"Cache dry run accepted for {model_id}.",
            "model": model_id,
        }
    if find_spec("huggingface_hub") is None:
        raise ValueError("huggingface_hub is not installed. Install the Transformers setup extra first.")
    from huggingface_hub import snapshot_download  # type: ignore
    local_dir = snapshot_download(repo_id=model_id, token=token or None)
    return {
        "format": PROVIDER_SETUP_JOB_FORMAT,
        "providerId": provider_id,
        "action": "cache_model",
        "status": "succeeded",
        "ready": True,
        "networkAttempted": True,
        "heavyLocalAttempted": False,
        "message": f"Cached {model_id}. Use this model from the UI; local paths are redacted in browser responses.",
        "model": model_id,
        "localModelDir": str(local_dir),
        "progress": {"percent": 100, "known": True, "label": "Model cached"},
    }


def _check_sam3_hf_access(payload: Mapping[str, Any], *, token: str = "", environ: Mapping[str, str]) -> dict[str, Any]:
    token = str(token or environ.get("HF_TOKEN") or environ.get("HUGGINGFACE_HUB_TOKEN") or "").strip()
    if not _truthy(payload.get("allowNetwork", payload.get("allow_network"))):
        return {
            "format": PROVIDER_SETUP_JOB_FORMAT,
            "providerId": "sam3-local",
            "action": "check_access",
            "status": "blocked",
            "ready": False,
            "networkAttempted": False,
            "heavyLocalAttempted": False,
            "message": "Hugging Face access check needs explicit network confirmation.",
            "tokenConfigured": bool(token),
        }
    if not token:
        return {
            "format": PROVIDER_SETUP_JOB_FORMAT,
            "providerId": "sam3-local",
            "action": "check_access",
            "status": "blocked",
            "ready": False,
            "networkAttempted": False,
            "heavyLocalAttempted": False,
            "message": "Paste a Hugging Face token in Model setup after Meta approves facebook/sam3 access, then run Check access again.",
            "tokenConfigured": False,
        }
    if find_spec("huggingface_hub") is None:
        raise ValueError("huggingface_hub is not installed. Install the sam3-transformers extra first.")
    from huggingface_hub import HfApi  # type: ignore

    HfApi().model_info("facebook/sam3", token=token)
    return {
        "format": PROVIDER_SETUP_JOB_FORMAT,
        "providerId": "sam3-local",
        "action": "check_access",
        "status": "succeeded",
        "ready": True,
        "networkAttempted": True,
        "heavyLocalAttempted": False,
        "message": "facebook/sam3 access check completed with the configured Hugging Face token.",
        "tokenConfigured": True,
    }


def _normalize_action(provider_id: str, action: Any) -> str:
    normalized = str(action or "diagnose").strip().lower().replace("-", "_")
    aliases = {
        "check": "test",
        "check_setup": "test",
        "smoke_test": "smoke",
        "install_scene_sweep": "install",
        "install_fallback": "install",
        "check_hf_access": "check_access",
        "cache": "cache_model",
        "cache-model": "cache_model",
    }
    normalized = aliases.get(normalized, normalized)
    allowed = {entry["id"] for entry in provider_setup_actions(provider_id)}
    if normalized not in allowed:
        raise ValueError(f"{provider_id} setup action must be one of: {', '.join(sorted(allowed))}.")
    return normalized


def _setup_job_row(conn: sqlite3.Connection, *, user_id: str, job_id: str) -> sqlite3.Row:
    row = conn.execute(
        """
        SELECT *
        FROM provider_setup_jobs
        WHERE id = ? AND user_id = ?
        """,
        (job_id, user_id),
    ).fetchone()
    if row is None:
        raise ValueError(f"Unknown provider setup job: {job_id}")
    return row


def _record_setup_event(
    conn: sqlite3.Connection,
    *,
    job_id: str,
    event_type: str,
    message: str,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO provider_setup_events (id, setup_job_id, event_type, message, metadata_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            uuid.uuid4().hex,
            job_id,
            event_type,
            redact_secret_text(message),
            json.dumps(redact_secret_payload(dict(metadata or {})), sort_keys=True),
            utc_now(),
        ),
    )


def _setup_state_for_job(status: str, action: str, result: Mapping[str, Any]) -> dict[str, Any]:
    normalized = str(status or "queued")
    action = str(action or "")
    if normalized == "succeeded" and result.get("ready") is True:
        return {"status": "ready", "label": "Ready", "message": result.get("message") or "Setup is ready."}
    if normalized in {"failed", "blocked", "canceled"}:
        return {"status": "failed_recoverable", "label": "Needs recovery", "message": result.get("message") or f"Setup {normalized}."}
    if action == "diagnose":
        return {"status": "checking_environment", "label": "Checking environment", "message": "Checking local imports and saved setup."}
    if action == "cache_model":
        return {"status": "caching_model", "label": "Caching model", "message": "Downloading or resolving the selected model cache."}
    if action == "install":
        return {"status": "installing_runtime", "label": "Installing runtime", "message": "Installing allowlisted optional runtime dependencies."}
    if action == "smoke":
        return {"status": "smoke_testing", "label": "Smoke testing", "message": "Running a bounded setup smoke test."}
    if action == "check_access":
        return {"status": "needs_access", "label": "Checking access", "message": "Checking Hugging Face access."}
    return {"status": "checking_environment", "label": "Checking setup", "message": "Setup action is queued."}


def _finish_setup_job(
    conn: sqlite3.Connection,
    *,
    job_id: str,
    status: str,
    result: Mapping[str, Any],
    error: Any,
) -> None:
    now = utc_now()
    conn.execute(
        """
        UPDATE provider_setup_jobs
        SET status = ?, result_json = ?, error = ?, updated_at = ?, finished_at = ?
        WHERE id = ?
        """,
        (
            status,
            json.dumps(redact_secret_payload(dict(result)), sort_keys=True),
            redact_secret_text(error) if error else None,
            now,
            now,
            job_id,
        ),
    )
    conn.commit()


def _raise_if_canceled(conn: sqlite3.Connection, job_id: str) -> None:
    row = conn.execute("SELECT status, cancel_requested_at FROM provider_setup_jobs WHERE id = ?", (job_id,)).fetchone()
    if row and (row["status"] == "canceled" or row["cancel_requested_at"]):
        raise _SetupCanceled("Provider setup job was canceled.")


def _json_dict(value: Any) -> dict[str, Any]:
    try:
        parsed = json.loads(value or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "run", "start"}
    return bool(value)


def _result_ready_or_ok(result: Mapping[str, Any]) -> bool:
    return result.get("ready") is True or str(result.get("status") or "").lower() in {"ready", "ok", "configured", "succeeded"}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


class _SetupCanceled(RuntimeError):
    pass
