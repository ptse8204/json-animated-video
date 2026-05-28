from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import uuid
from importlib.util import find_spec
from pathlib import Path
from typing import Any, Callable, Mapping

from motionjson.backend.usage import utc_now
from motionjson.provider_settings import (
    diagnose_provider_settings,
    hosted_sam3_smoke_test,
    local_sam_smoke_test,
    provider_runtime_settings,
    record_provider_model_cache,
    redact_secret_payload,
    redact_secret_text,
    save_provider_settings,
    test_provider_settings,
)
from motionjson.providers.sam2 import SAM2_HF_AUTO_MASKS_DEFAULT_MODEL
from motionjson.providers.sam3 import SAM3_HF_REPO_ID


PROVIDER_SETUP_JOB_FORMAT = "motionjson.provider_setup_job.v0.1"
TERMINAL_SETUP_JOB_STATUSES = {"succeeded", "failed", "canceled", "blocked"}
LOCAL_SETUP_PATH_REDACTION = "[LOCAL_PATH_REDACTED]"
LOCAL_SETUP_PATH_KEYS = {
    "checkpointpath",
    "configpath",
    "custommodelpath",
    "localmodeldir",
    "localmodelpath",
    "localpath",
    "modeldir",
    "modeldirectory",
    "modelpath",
    "outputdir",
    "outputpath",
    "resolvedmodeldir",
    "resolvedmodelpath",
    "runtimeconfigpath",
    "runtimemodel",
    "sam2checkpointpath",
    "sam2configpath",
    "sam3modelpath",
    "videopath",
}
SetupProgressCallback = Callable[[str, str, int | float | None, bool], None]


def provider_setup_actions(provider_id: str) -> list[dict[str, Any]]:
    """Return server-owned setup actions the browser may request."""

    if provider_id == "sam3-local":
        return [
            {
                "id": "prepare_model",
                "label": "Prepare local model",
                "description": "Run the guided local setup path: diagnose, cache facebook/sam3 when confirmed, record the server-side path, then run a bounded smoke test.",
                "requiresConfirmation": True,
                "networkAttempted": True,
                "heavyLocalAttempted": True,
            },
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
                "id": "prepare_model",
                "label": "Prepare local model",
                "description": "Run the guided local setup path: diagnose, cache facebook/sam2.1-hiera-large when confirmed, record the server-side path, then run a bounded smoke test.",
                "requiresConfirmation": True,
                "networkAttempted": True,
                "heavyLocalAttempted": True,
            },
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
                "id": "prepare_model",
                "label": "Prepare local model",
                "description": "Run guided local setup diagnostics and a bounded smoke test when confirmed.",
                "requiresConfirmation": True,
                "networkAttempted": False,
                "heavyLocalAttempted": True,
            },
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
    _record_setup_event(
        conn,
        job_id=row["id"],
        event_type="queued",
        message=f"{provider_id} setup action queued.",
        metadata={"action": action, "progress": _progress_payload(known=False, percent=0, label="Queued")},
    )
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
    _record_setup_event(
        conn,
        job_id=job_id,
        event_type="started",
        message=f"{provider_id} setup action started.",
        metadata={"action": action, "progress": _progress_payload(known=False, percent=5, label=_started_progress_label(action))},
    )
    conn.commit()

    def emit_progress(event_type: str, label: str, percent: int | float | None = None, known: bool = False) -> None:
        _record_setup_event(
            conn,
            job_id=job_id,
            event_type=event_type,
            message=label,
            metadata={"action": action, "progress": _progress_payload(known=known, percent=percent, label=label)},
        )
        conn.commit()

    try:
        _raise_if_canceled(conn, job_id)
        result = _execute_setup_action(
            conn,
            user_id=user_id,
            provider_id=provider_id,
            action=action,
            payload=effective_payload,
            environ=environ,
            progress=emit_progress,
        )
        _raise_if_canceled(conn, job_id)
    except _SetupCanceled as exc:
        _finish_setup_job(conn, job_id=job_id, status="canceled", result={"message": str(exc)}, error=str(exc))
    except Exception as exc:
        message = redact_secret_text(str(exc) or type(exc).__name__)
        failed_result = {
            "message": message,
            "progress": _progress_payload(known=False, percent=0, label=_failed_progress_label(action)),
        }
        _record_setup_event(
            conn,
            job_id=job_id,
            event_type="failed",
            message=message,
            metadata={"action": action, "progress": failed_result["progress"]},
        )
        _finish_setup_job(conn, job_id=job_id, status="failed", result=failed_result, error=message)
    else:
        status = "succeeded" if _result_ready_or_ok(result) else str(result.get("status") or "blocked")
        if status not in TERMINAL_SETUP_JOB_STATUSES:
            status = "succeeded" if result.get("ready") is True else "blocked"
        terminal_progress = _normalized_progress(result.get("progress")) or _terminal_progress_for_action(action, status)
        _record_setup_event(
            conn,
            job_id=job_id,
            event_type=status,
            message=str(result.get("message") or f"{provider_id} setup action finished."),
            metadata={"action": action, "ready": result.get("ready"), "progress": terminal_progress},
        )
        _finish_setup_job(
            conn,
            job_id=job_id,
            status=status,
            result={**dict(result), "progress": terminal_progress},
            error=None if status == "succeeded" else result.get("message"),
        )
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
        "payload": _public_setup_payload(payload),
        "result": _public_setup_payload(result),
        "error": redact_secret_text(row["error"]) if row["error"] else "",
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "startedAt": row["started_at"],
        "finishedAt": row["finished_at"],
        "cancelRequestedAt": row["cancel_requested_at"],
        "terminal": row["status"] in TERMINAL_SETUP_JOB_STATUSES,
        "setupState": _setup_state_for_job(row["status"], row["action"], result),
    }
    public["progress"] = _setup_progress_for_job(conn, row, result)
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
    progress: SetupProgressCallback | None = None,
) -> dict[str, Any]:
    environ = environ or os.environ
    settings_payload = payload.get("settings") if isinstance(payload.get("settings"), Mapping) else payload
    if _truthy(payload.get("saveFirst", payload.get("save_first", True))) and action in {"diagnose", "test", "smoke", "check_access", "cache_model", "prepare_model"}:
        if any(key in settings_payload for key in ("selectedModel", "selected_model", "customModelId", "custom_model_id", "apiKey", "api_key", "hfToken", "hf_token", "sam2CheckpointPath", "sam2_checkpoint_path", "sam2Device", "sam2_device", "sam2HfDevice", "sam2_hf_device", "sam3ModelPath", "sam3_model_path", "sam3Device", "sam3_device", "endpoint", "allowHosted", "allow_hosted", "hostedProfileId", "hosted_profile_id")):
            save_provider_settings(conn, user_id=user_id, payload={**dict(settings_payload), "providerId": provider_id}, environ=environ)

    if action == "diagnose":
        return diagnose_provider_settings(conn, user_id=user_id, provider_id=provider_id, payload=settings_payload, environ=environ)
    if action == "test":
        return test_provider_settings(conn, user_id=user_id, provider_id=provider_id, environ=environ)
    if action == "smoke":
        if provider_id in {"sam2-local", "sam2-hf-auto-masks", "sam3-local"}:
            return local_sam_smoke_test(conn, user_id=user_id, provider_id=provider_id, payload=payload, environ=environ, progress=progress)
        return hosted_sam3_smoke_test(conn, user_id=user_id, payload={**dict(payload), "providerId": provider_id}, environ=environ)
    if action == "prepare_model":
        return _prepare_model_action(
            conn,
            user_id=user_id,
            provider_id=provider_id,
            payload=payload,
            environ=environ,
            progress=progress,
        )
    if action == "install":
        return _run_install_action(provider_id, payload)
    if action == "cache_model":
        runtime = provider_runtime_settings(conn, user_id=user_id, provider_id=provider_id, environ=environ)
        cache_payload = dict(payload)
        if not any(cache_payload.get(key) for key in ("model", "modelId", "model_id")):
            cache_payload["model"] = runtime.get("selected_model") or runtime.get("runtime_model")
        result = _cache_model_action(provider_id, cache_payload, token=str(runtime.get("hf_token") or ""), progress=progress)
        if result.get("ready") is True and result.get("localModelDir"):
            provider_settings = record_provider_model_cache(
                conn,
                user_id=user_id,
                provider_id=provider_id,
                model_id=str(result.get("model") or cache_payload.get("model") or ""),
                local_model_dir=str(result.get("localModelDir") or ""),
                environ=environ,
            )
            model_cache = _provider_model_cache_from_settings(provider_settings, provider_id)
            result = {
                **result,
                "localPathRecorded": True,
                "localPathDisplay": "[LOCAL_PATH_REDACTED]",
                "modelCache": model_cache,
                "message": f"{result.get('message') or 'Model cached.'} Resolved model path recorded server-side and redacted in the Local UI.",
            }
            if progress:
                progress("model_cache_recorded", "Model cache path recorded server-side", 100, True)
        return result
    if action == "check_access":
        runtime = provider_runtime_settings(conn, user_id=user_id, provider_id=provider_id, environ=environ)
        return _check_sam3_hf_access(payload, token=str(runtime.get("hf_token") or ""), environ=environ)
    raise ValueError(f"Setup action is not implemented for {provider_id}: {action}")


def _prepare_blocked_result(
    provider_id: str,
    *,
    message: str,
    next_action: str,
    diagnosis: Mapping[str, Any] | None = None,
    progress_label: str = "Waiting for user action",
) -> dict[str, Any]:
    return {
        "format": PROVIDER_SETUP_JOB_FORMAT,
        "providerId": provider_id,
        "action": "prepare_model",
        "status": "blocked",
        "ready": False,
        "networkAttempted": False,
        "heavyLocalAttempted": False,
        "message": redact_secret_text(message),
        "nextAction": next_action,
        "diagnosis": redact_secret_payload(dict(diagnosis or {})),
        "progress": _progress_payload(known=False, percent=0, label=progress_label),
    }


def _prepare_model_action(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    provider_id: str,
    payload: Mapping[str, Any],
    environ: Mapping[str, str],
    progress: SetupProgressCallback | None = None,
) -> dict[str, Any]:
    if provider_id not in {"sam2-local", "sam2-hf-auto-masks", "sam3-local"}:
        raise ValueError("Guided local model preparation is only available for local SAM providers.")

    if progress:
        progress("prepare_diagnose", "Checking local runtime setup", 10, True)
    diagnosis = diagnose_provider_settings(conn, user_id=user_id, provider_id=provider_id, payload=payload, environ=environ)
    setup_state = diagnosis.get("setupState") if isinstance(diagnosis.get("setupState"), Mapping) else {}
    preflight = setup_state.get("preflight") if isinstance(setup_state.get("preflight"), Mapping) else {}
    next_action = str(setup_state.get("nextAction") or "")
    checklist = diagnosis.get("checklist") if isinstance(diagnosis.get("checklist"), list) else []
    requested_model = str(payload.get("model") or payload.get("modelId") or payload.get("model_id") or "").strip()
    requested_model_is_local_dir = bool(requested_model and Path(requested_model).expanduser().is_dir())
    runtime_missing = _runtime_blockers_for_prepare(provider_id, checklist)
    runtime_ready = bool(diagnosis.get("ready") or preflight.get("runtimeAvailable")) and not runtime_missing

    if not runtime_ready and next_action != "cache_model":
        blocker_labels = ", ".join(str(item.get("label") or item.get("id")) for item in runtime_missing)
        return _prepare_blocked_result(
            provider_id,
            message=blocker_labels
            and f"Prepare local model needs runtime setup first: {blocker_labels}."
            or diagnosis.get("message")
            or "Install the optional runtime before preparing this local model.",
            next_action=_prepare_runtime_next_action(runtime_missing) or next_action or "install",
            diagnosis=diagnosis,
            progress_label="Runtime setup needed",
        )

    if provider_id == "sam3-local" and setup_state.get("status") == "needs_access" and not requested_model_is_local_dir:
        return _prepare_blocked_result(
            provider_id,
            message=setup_state.get("message") or "Hugging Face access is needed before caching facebook/sam3.",
            next_action="check_access",
            diagnosis=diagnosis,
            progress_label="Access check needed",
        )

    cached_model_cache = diagnosis.get("modelCache") if isinstance(diagnosis.get("modelCache"), Mapping) else {}
    cache_result: dict[str, Any] | None = None
    if provider_id in {"sam2-hf-auto-masks", "sam3-local"} and not cached_model_cache.get("cached"):
        if not _truthy(payload.get("allowNetwork", payload.get("allow_network"))):
            return _prepare_blocked_result(
                provider_id,
                message="Preparing this local model needs explicit network confirmation before caching weights.",
                next_action="cache_model",
                diagnosis=diagnosis,
                progress_label="Waiting for network confirmation",
            )
        if not _truthy(payload.get("allowDisk", payload.get("allow_disk", payload.get("allowDownload", payload.get("allow_download"))))):
            return _prepare_blocked_result(
                provider_id,
                message="Preparing this local model needs explicit disk/download confirmation before caching weights.",
                next_action="cache_model",
                diagnosis=diagnosis,
                progress_label="Waiting for disk confirmation",
            )
        runtime = provider_runtime_settings(conn, user_id=user_id, provider_id=provider_id, environ=environ)
        cache_payload = dict(payload)
        if not any(cache_payload.get(key) for key in ("model", "modelId", "model_id")):
            cache_payload["model"] = runtime.get("selected_model") or runtime.get("runtime_model")
        cache_progress = _prepare_cache_progress(progress) if progress else None
        cache_result = _cache_model_action(provider_id, cache_payload, token=str(runtime.get("hf_token") or ""), progress=cache_progress)
        if cache_result.get("ready") is True and cache_result.get("localModelDir"):
            provider_settings = record_provider_model_cache(
                conn,
                user_id=user_id,
                provider_id=provider_id,
                model_id=str(cache_result.get("model") or cache_payload.get("model") or ""),
                local_model_dir=str(cache_result.get("localModelDir") or ""),
                environ=environ,
            )
            cache_result = {
                **cache_result,
                "localPathRecorded": True,
                "localPathDisplay": LOCAL_SETUP_PATH_REDACTION,
                "modelCache": _provider_model_cache_from_settings(provider_settings, provider_id),
                "message": f"{cache_result.get('message') or 'Model cached.'} Resolved model path recorded server-side and redacted in the Local UI.",
            }
            if progress:
                progress("model_cache_recorded", "Model cache path recorded server-side", 82, True)
        diagnosis = diagnose_provider_settings(conn, user_id=user_id, provider_id=provider_id, payload=payload, environ=environ)

    if not _truthy(payload.get("allowHeavyLocal", payload.get("allow_heavy_local"))):
        return _prepare_blocked_result(
            provider_id,
            message="Preparing this local model needs explicit heavy-runtime confirmation before running the bounded smoke test.",
            next_action="smoke",
            diagnosis=diagnosis,
            progress_label="Waiting for smoke-test confirmation",
        )

    if progress:
        progress(
            "prepare_smoke",
            "Loading model on the selected device and running bounded warmup" if provider_id == "sam3-local" else "Running bounded local smoke test",
            88,
            True,
        )
    smoke_payload = {
        **dict(payload),
        "allowHeavyLocal": True,
        "sceneSweep": bool(provider_id == "sam3-local"),
    }
    smoke_result = local_sam_smoke_test(
        conn,
        user_id=user_id,
        provider_id=provider_id,
        payload=smoke_payload,
        environ=environ,
        progress=progress,
    )
    ready = bool(smoke_result.get("ready"))
    smoke_status = str(smoke_result.get("status") or "")
    return {
        "format": PROVIDER_SETUP_JOB_FORMAT,
        "providerId": provider_id,
        "action": "prepare_model",
        "status": "succeeded" if ready else "failed" if smoke_status == "failed" else "blocked",
        "ready": ready,
        "networkAttempted": bool(cache_result and cache_result.get("networkAttempted")),
        "heavyLocalAttempted": True,
        "message": smoke_result.get("message") or ("Local model is prepared." if ready else "Local model preparation is incomplete."),
        "nextAction": "continue" if ready else "smoke",
        "diagnosis": smoke_result.get("diagnosis") or diagnosis,
        "cacheResult": cache_result or {},
        "smokeTest": smoke_result.get("smokeTest"),
        "progress": _progress_payload(known=True, percent=100, label="Local model prepared" if ready else "Preparation blocked"),
    }


def _runtime_blockers_for_prepare(provider_id: str, checklist: list[Any]) -> list[Mapping[str, Any]]:
    runtime_ids = {
        "sam2-local": {"sam2_package", "torch_package", "checkpoint", "model_config", "device"},
        "sam2-hf-auto-masks": {"transformers_package", "torch_package", "device"},
        "sam3-local": {
            "transformers_package",
            "sam3_tracker_auto_masks",
            "sam3_tracker_video",
            "torch_package",
            "device",
        },
    }.get(provider_id, set())
    blockers: list[Mapping[str, Any]] = []
    for item in checklist:
        if not isinstance(item, Mapping):
            continue
        if item.get("required") is False or item.get("ok") is True:
            continue
        if str(item.get("id") or "") in runtime_ids:
            blockers.append(item)
    return blockers


def _prepare_runtime_next_action(blockers: list[Mapping[str, Any]]) -> str:
    ids = {str(item.get("id") or "") for item in blockers}
    if ids & {"checkpoint", "model_config", "device"}:
        return "choose_model"
    if ids:
        return "install"
    return ""


def _prepare_cache_progress(progress: SetupProgressCallback) -> SetupProgressCallback:
    def mapped(event_type: str, label: str, percent: int | float | None = None, known: bool = False) -> None:
        mapped_percent: int | float | None = None
        if percent is not None:
            try:
                bounded = min(max(float(percent), 0.0), 100.0)
            except (TypeError, ValueError):
                bounded = 0.0
            mapped_percent = round(20 + bounded * 0.58, 1)
        progress(event_type, label, mapped_percent, known)

    return mapped


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


def _cache_model_action(
    provider_id: str,
    payload: Mapping[str, Any],
    *,
    token: str = "",
    progress: SetupProgressCallback | None = None,
) -> dict[str, Any]:
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
            "progress": _progress_payload(known=False, percent=0, label="Waiting for network confirmation"),
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
            "progress": _progress_payload(known=False, percent=0, label="Waiting for disk confirmation"),
        }
    default_model = SAM3_HF_REPO_ID if provider_id == "sam3-local" else SAM2_HF_AUTO_MASKS_DEFAULT_MODEL
    model_id = str(payload.get("model") or payload.get("modelId") or payload.get("model_id") or default_model).strip() or default_model
    if progress:
        progress("resolving_model", "Resolving selected model", 10, False)
    if model_id.endswith(".pt") or Path(model_id).expanduser().is_file():
        raise ValueError(
            "Model caching expects a Hugging Face repo id or local model directory, not a single .pt checkpoint file."
        )
    local_candidate = Path(model_id).expanduser()
    if local_candidate.exists() and local_candidate.is_dir():
        if progress:
            progress("verifying_cache", "Verifying local model directory", 85, False)
        ok, detail = _local_from_pretrained_dir_status(local_candidate)
        if not ok:
            raise ValueError(_local_model_setup_error(provider_id, "cache_model", model_id, detail, network_attempted=False))
        if progress:
            progress("cached", "Model directory found", 100, True)
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
            "progress": _progress_payload(known=True, percent=100, label="Model directory found"),
        }
    if _truthy(payload.get("dryRun", payload.get("dry_run"))):
        if progress:
            progress("cached", "Cache dry run accepted", 100, True)
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
            "progress": _progress_payload(known=True, percent=100, label="Cache dry run accepted"),
        }
    if find_spec("huggingface_hub") is None:
        raise ValueError("huggingface_hub is not installed. Install the Transformers setup extra first.")
    from huggingface_hub import snapshot_download  # type: ignore
    try:
        if progress:
            progress("downloading_cache", "Downloading or resolving Hugging Face snapshot", 35, False)
        local_dir = snapshot_download(repo_id=model_id, token=token or None)
    except Exception as exc:
        raise ValueError(_local_model_setup_error(provider_id, "cache_model", model_id, exc, network_attempted=True)) from exc
    if progress:
        progress("verifying_cache", "Verifying cached model", 85, False)
    ok, detail = _local_from_pretrained_dir_status(Path(str(local_dir)).expanduser())
    if not ok:
        raise ValueError(_local_model_setup_error(provider_id, "cache_model", model_id, detail, network_attempted=True))
    if progress:
        progress("cached", "Model cached", 100, True)
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
        "progress": _progress_payload(known=True, percent=100, label="Model cached"),
    }


def _local_from_pretrained_dir_status(path: Path) -> tuple[bool, str]:
    try:
        if not path.exists():
            return False, "local model directory does not exist"
        if not path.is_dir():
            return False, "selected model path is not a directory"
        if not os.access(path, os.R_OK):
            return False, "local model directory is not readable"
        if any(path.rglob("*.incomplete")):
            return False, "local model directory contains incomplete download files"
        if not (path / "config.json").exists():
            return False, "local model directory is missing config.json for from_pretrained"
    except OSError as exc:
        return False, f"local model directory could not be inspected: {type(exc).__name__}: {exc}"
    return True, "local model directory is available"


def _local_model_setup_error(provider_id: str, action: str, model_id: str, error: Any, *, network_attempted: bool) -> str:
    text = redact_secret_text(str(error) or type(error).__name__)
    lowered = text.lower()
    next_action = "Retry Cache model after fixing local disk/cache access."
    if "permission" in lowered or "denied" in lowered:
        next_action = "Fix local file permissions or choose a readable model directory."
    elif "no space" in lowered or "enospc" in lowered or "disk" in lowered:
        next_action = "Free disk space or choose a Hugging Face cache location with more space."
    elif "incomplete" in lowered or "corrupt" in lowered:
        next_action = "Delete the partial cache entry and run Cache model again."
    elif "config.json" in lowered or "not a directory" in lowered or "does not exist" in lowered:
        next_action = "Choose a valid Hugging Face repo id or local from_pretrained directory."
    elif "offline" in lowered:
        next_action = "Disable offline mode or choose a model that is already cached locally."
    return (
        f"Local model setup failed during {action} for {provider_id} ({model_id}); "
        f"network attempted: {str(network_attempted).lower()}. {text} {next_action}"
    )


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


def _setup_progress_for_job(conn: sqlite3.Connection, row: sqlite3.Row, result: Mapping[str, Any]) -> dict[str, Any]:
    result_progress = _normalized_progress(result.get("progress"))
    if result_progress:
        return result_progress
    event_progress = _latest_setup_event_progress(conn, job_id=str(row["id"]))
    if event_progress:
        return event_progress
    return _default_progress_for_action(str(row["action"] or ""), str(row["status"] or "queued"))


def _latest_setup_event_progress(conn: sqlite3.Connection, *, job_id: str) -> dict[str, Any] | None:
    rows = conn.execute(
        """
        SELECT metadata_json
        FROM provider_setup_events
        WHERE setup_job_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 12
        """,
        (job_id,),
    ).fetchall()
    for row in rows:
        progress = _json_dict(row["metadata_json"]).get("progress")
        normalized = _normalized_progress(progress)
        if normalized:
            return normalized
    return None


def _normalized_progress(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    return _progress_payload(
        known=bool(value.get("known")),
        percent=value.get("percent"),
        label=str(value.get("label") or "Setup in progress"),
    )


def _progress_payload(*, known: bool, percent: Any, label: str) -> dict[str, Any]:
    try:
        numeric = float(percent if percent is not None else 0)
    except (TypeError, ValueError):
        numeric = 0.0
    numeric = min(max(numeric, 0.0), 100.0)
    percent_value: int | float = int(numeric) if numeric.is_integer() else numeric
    clean_label = redact_secret_text(label or "Setup in progress")
    if len(clean_label) > 180:
        clean_label = f"{clean_label[:177]}..."
    return {"known": bool(known), "percent": percent_value, "label": clean_label}


def _started_progress_label(action: str) -> str:
    return {
        "prepare_model": "Preparing local model",
        "cache_model": "Resolving selected model",
        "check_access": "Checking Hugging Face access",
        "install": "Installing optional runtime",
        "smoke": "Running setup smoke test",
        "diagnose": "Checking saved setup",
        "test": "Checking hosted setup",
    }.get(str(action or ""), "Setup running")


def _failed_progress_label(action: str) -> str:
    return {
        "prepare_model": "Local model preparation failed",
        "cache_model": "Model cache failed",
        "check_access": "Access check failed",
        "install": "Install failed",
        "smoke": "Smoke test failed",
        "diagnose": "Setup check failed",
        "test": "Hosted setup check failed",
    }.get(str(action or ""), "Setup failed")


def _terminal_progress_for_action(action: str, status: str) -> dict[str, Any]:
    if status == "succeeded":
        label = {
            "prepare_model": "Local model prepared",
            "cache_model": "Model cached",
            "check_access": "Access check complete",
            "install": "Runtime installed",
            "smoke": "Smoke test complete",
            "diagnose": "Setup check complete",
            "test": "Hosted setup check complete",
        }.get(str(action or ""), "Setup complete")
        return _progress_payload(known=True, percent=100, label=label)
    if status in {"failed", "blocked", "canceled"}:
        return _progress_payload(known=False, percent=0, label=_failed_progress_label(action) if status != "blocked" else "Setup needs confirmation")
    return _default_progress_for_action(action, status)


def _default_progress_for_action(action: str, status: str) -> dict[str, Any]:
    if status == "queued":
        return _progress_payload(known=False, percent=0, label="Queued")
    if status == "running":
        return _progress_payload(known=False, percent=5, label=_started_progress_label(action))
    if status == "succeeded":
        return _terminal_progress_for_action(action, status)
    if status in {"failed", "blocked", "canceled"}:
        return _terminal_progress_for_action(action, status)
    return _progress_payload(known=False, percent=0, label="Setup pending")


def _setup_state_for_job(status: str, action: str, result: Mapping[str, Any]) -> dict[str, Any]:
    normalized = str(status or "queued")
    action = str(action or "")
    if normalized == "succeeded" and result.get("ready") is True:
        return {"status": "ready", "label": "Ready", "message": result.get("message") or "Setup is ready."}
    if normalized in {"failed", "blocked", "canceled"}:
        return {"status": "failed_recoverable", "label": "Needs recovery", "message": result.get("message") or f"Setup {normalized}."}
    if action == "diagnose":
        return {"status": "checking_environment", "label": "Checking environment", "message": "Checking local imports and saved setup."}
    if action == "prepare_model":
        return {"status": "preparing_model", "label": "Preparing local model", "message": "Checking runtime, cache, recorded model path, and smoke-test readiness."}
    if action == "cache_model":
        return {"status": "caching_model", "label": "Caching model", "message": "Downloading or resolving the selected model cache."}
    if action == "install":
        return {"status": "installing_runtime", "label": "Installing runtime", "message": "Installing allowlisted optional runtime dependencies."}
    if action == "smoke":
        return {"status": "smoke_testing", "label": "Smoke testing", "message": "Running a bounded setup smoke test."}
    if action == "check_access":
        return {"status": "checking_environment", "label": "Checking access", "message": "Checking Hugging Face access."}
    return {"status": "checking_environment", "label": "Checking setup", "message": "Setup action is queued."}


def _finish_setup_job(
    conn: sqlite3.Connection,
    *,
    job_id: str,
    status: str,
    result: Mapping[str, Any],
    error: Any,
) -> None:
    current = conn.execute("SELECT status FROM provider_setup_jobs WHERE id = ?", (job_id,)).fetchone()
    if current is not None and str(current["status"]) in TERMINAL_SETUP_JOB_STATUSES:
        return
    now = utc_now()
    conn.execute(
        """
        UPDATE provider_setup_jobs
        SET status = ?, result_json = ?, error = ?, updated_at = ?, finished_at = ?
        WHERE id = ?
        """,
        (
            status,
            json.dumps(_public_setup_payload(dict(result)), sort_keys=True),
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


def _public_setup_payload(value: Any) -> Any:
    return _redact_local_setup_paths(redact_secret_payload(value))


def _redact_local_setup_paths(value: Any, known_local_paths: set[str] | None = None) -> Any:
    known_local_paths = set(known_local_paths or set())
    if isinstance(value, Mapping):
        local_values = {
            str(item)
            for key, item in value.items()
            if _is_local_setup_path_key(str(key)) and isinstance(item, str) and item
        }
        nested_known = known_local_paths | local_values
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if _is_local_setup_path_key(key_text):
                redacted[key] = LOCAL_SETUP_PATH_REDACTION if item else item
            elif _is_model_value_referencing_local_path(key_text, item, nested_known):
                redacted[key] = LOCAL_SETUP_PATH_REDACTION
            else:
                redacted[key] = _redact_local_setup_paths(item, nested_known)
        return redacted
    if isinstance(value, list):
        return [_redact_local_setup_paths(item, known_local_paths) for item in value]
    return value


def _is_local_setup_path_key(key: str) -> bool:
    normalized = key.replace("_", "").replace("-", "").lower()
    return normalized in LOCAL_SETUP_PATH_KEYS or normalized.endswith("path") or normalized.endswith("dir") or normalized.endswith("directory")


def _is_model_value_referencing_local_path(key: str, value: Any, known_local_paths: set[str]) -> bool:
    if not isinstance(value, str) or not value:
        return False
    normalized = key.replace("_", "").replace("-", "").lower()
    if normalized not in {"custommodelid", "model", "runtimemodel", "selectedmodel"}:
        return False
    if value in known_local_paths:
        return True
    if value.startswith(("/", "~", "./", "../")) or "\\" in value:
        return True
    if len(value) > 2 and value[1:3] == ":\\":
        return True
    try:
        return Path(value).expanduser().exists()
    except (OSError, RuntimeError):
        return False


def _provider_model_cache_from_settings(settings_response: Mapping[str, Any], provider_id: str) -> dict[str, Any]:
    for provider in settings_response.get("providers", []):
        if isinstance(provider, Mapping) and provider.get("id") == provider_id:
            cache = provider.get("modelCache")
            return dict(cache) if isinstance(cache, Mapping) else {}
    return {}


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
