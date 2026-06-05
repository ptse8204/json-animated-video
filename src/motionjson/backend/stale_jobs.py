from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from .jobs import record_job_event
from .queue import mark_failed, mark_succeeded
from .usage import utc_now


ASSET_PREPARATION_STALL_REASON = "asset_preparation_stalled"
ASSET_PREPARATION_FRAME_TIMEOUT_REASON = "asset_preparation_frame_timeout"
WORKER_HEARTBEAT_STALE_REASON = "worker_heartbeat_stale"
DEFAULT_ASSET_PREPARATION_STALL_SECONDS = 4 * 60
_FRAME_PROGRESS_RE = re.compile(r"frame\s+(\d+)\s*/\s*(\d+)", re.IGNORECASE)


def asset_preparation_stall_threshold_seconds() -> float:
    raw = os.environ.get("MOTIONJSON_ASSET_PREP_STALL_SECONDS", "").strip()
    if not raw:
        return float(DEFAULT_ASSET_PREPARATION_STALL_SECONDS)
    try:
        return max(30.0, float(raw))
    except ValueError:
        return float(DEFAULT_ASSET_PREPARATION_STALL_SECONDS)


def asset_preparation_frame_timeout_seconds() -> float:
    raw = os.environ.get("MOTIONJSON_ASSET_PREP_FRAME_TIMEOUT_SECONDS", "").strip()
    if not raw:
        return asset_preparation_stall_threshold_seconds()
    try:
        return max(30.0, float(raw))
    except ValueError:
        return asset_preparation_stall_threshold_seconds()


def worker_heartbeat_stale_seconds() -> float:
    raw = os.environ.get("MOTIONJSON_WORKER_HEARTBEAT_STALE_SECONDS", "").strip()
    if not raw:
        return asset_preparation_stall_threshold_seconds()
    try:
        return max(30.0, float(raw))
    except ValueError:
        return asset_preparation_stall_threshold_seconds()


def reconcile_stale_asset_preparation_job(
    conn: sqlite3.Connection,
    *,
    job_id: str,
    now: str | datetime | None = None,
    threshold_seconds: float | None = None,
) -> dict[str, Any] | None:
    """Fail a running extraction job that is stale inside raster asset prep.

    Local UI workers are process-local. If an artifact-writing stage blocks or
    the worker dies after emitting an asset-preparation progress event, the UI
    can keep polling a forever-running row. This reconciles that specific
    backend state into a terminal failure when the API is polled.
    """

    job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if job is None or str(job["status"] or "").lower() != "running":
        return dict(job) if job is not None else None
    events = conn.execute("SELECT * FROM job_events WHERE job_id = ? ORDER BY created_at, id", (job_id,)).fetchall()
    event_dicts = [dict(event) for event in events]
    diagnostic = asset_preparation_stall_diagnostic(
        dict(job),
        event_dicts,
        now=now,
        threshold_seconds=threshold_seconds,
    )
    if not diagnostic:
        return dict(job)

    partial_summary = _partial_artifact_summary(conn, job=dict(job), diagnostic=diagnostic)
    runtime_proof = _runtime_proof_from_events(event_dicts)
    if partial_summary["reviewableObjectCount"] > 0:
        recovery_diagnostic = {
            **diagnostic,
            "artifactsAvailable": True,
            "partialSuccess": True,
            "reviewableObjectCount": partial_summary["reviewableObjectCount"],
            "artifactCount": partial_summary["artifactCount"],
            "assetKindCounts": partial_summary["assetKindCounts"],
            "reviewableObjectIds": partial_summary["reviewableObjectIds"],
            "runtimeProof": runtime_proof,
            "message": _partial_success_message(diagnostic, partial_summary),
            "suggestedAction": "Review the completed objects, then rerun with a lower sampling rate or stricter object filters for the missing object.",
        }
        record_job_event(
            conn,
            job_id=job_id,
            event_type=diagnostic["reasonCode"],
            message=diagnostic["message"],
            metadata=recovery_diagnostic,
        )
        if recovery_diagnostic.get("objectId"):
            record_job_event(
                conn,
                job_id=job_id,
                event_type="asset_preparation_object_failed",
                message=recovery_diagnostic["message"],
                metadata={
                    **recovery_diagnostic,
                    "eventSource": "watchdog",
                    "failureScope": "object",
                },
            )
        result = {
            "format": "motionjson.extract.partial_success.v0.1",
            "status": "partial_success",
            "partialSuccess": True,
            "reasonCode": diagnostic["reasonCode"],
            "compatibilityReasonCode": diagnostic["compatibilityReasonCode"],
            "phase": "asset_preparation",
            "progress": {"overallRatio": 1.0, "ratio": 1.0},
            "message": recovery_diagnostic["message"],
            "assetPreparationDiagnostic": recovery_diagnostic,
            "runtimeProof": runtime_proof,
            "reviewableObjectCount": partial_summary["reviewableObjectCount"],
            "artifactCount": partial_summary["artifactCount"],
            "reviewableObjectIds": partial_summary["reviewableObjectIds"],
            "failedObjects": [
                {
                    "objectId": recovery_diagnostic.get("objectId"),
                    "reasonCode": recovery_diagnostic.get("reasonCode"),
                    "frame": recovery_diagnostic.get("frame"),
                    "position": recovery_diagnostic.get("position"),
                    "preparedFrames": recovery_diagnostic.get("preparedFrames"),
                    "totalFrames": recovery_diagnostic.get("totalFrames"),
                    "message": diagnostic["message"],
                }
            ] if recovery_diagnostic.get("objectId") else [],
        }
        succeeded = mark_succeeded(conn, job_id=job_id, result=result)
        record_job_event(
            conn,
            job_id=job_id,
            event_type="asset_preparation_partial_success",
            message=recovery_diagnostic["message"],
            metadata=result,
        )
        return dict(conn.execute("SELECT * FROM jobs WHERE id = ?", (succeeded["id"],)).fetchone())

    record_job_event(
        conn,
        job_id=job_id,
        event_type=diagnostic["reasonCode"],
        message=diagnostic["message"],
        metadata=diagnostic,
    )
    return mark_failed(conn, job_id=job_id, error=diagnostic["message"], max_attempts=1)


def _runtime_proof_from_events(events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    for event in reversed(events):
        metadata = _event_metadata(event)
        nested = metadata.get("metadata") if isinstance(metadata.get("metadata"), Mapping) else {}
        for candidate in (
            metadata.get("runtimeProof"),
            metadata.get("runtimeContract"),
            nested.get("runtimeProof") if isinstance(nested, Mapping) else None,
            nested.get("runtimeContract") if isinstance(nested, Mapping) else None,
        ):
            if isinstance(candidate, Mapping) and candidate:
                return dict(candidate)
    return {}


def _partial_artifact_summary(
    conn: sqlite3.Connection,
    *,
    job: Mapping[str, Any],
    diagnostic: Mapping[str, Any],
) -> dict[str, Any]:
    project_id = str(job.get("project_id") or job.get("projectId") or "")
    job_id = str(job.get("id") or "")
    rows = conn.execute(
        "SELECT kind, metadata_json FROM assets WHERE project_id = ? AND source_job_id = ? ORDER BY created_at, id",
        (project_id, job_id),
    ).fetchall()
    kind_counts: dict[str, int] = {}
    reviewable_ids: set[str] = set()
    failed_object_id = str(diagnostic.get("objectId") or "").strip()
    for row in rows:
        kind = str(row["kind"] or "")
        kind_counts[kind] = int(kind_counts.get(kind, 0)) + 1
        if kind != "object_manifest":
            continue
        rel_path = ""
        try:
            metadata = json.loads(row["metadata_json"] or "{}")
        except json.JSONDecodeError:
            metadata = {}
        if isinstance(metadata, Mapping):
            rel_path = str(metadata.get("rel_path") or "")
        object_id = _object_id_from_rel_path(rel_path)
        if object_id and object_id != failed_object_id:
            reviewable_ids.add(object_id)
    return {
        "artifactCount": len(rows),
        "assetKindCounts": kind_counts,
        "reviewableObjectCount": len(reviewable_ids),
        "reviewableObjectIds": sorted(reviewable_ids),
    }


def _object_id_from_rel_path(rel_path: str) -> str | None:
    parts = [part for part in rel_path.replace("\\", "/").split("/") if part]
    if len(parts) >= 3 and parts[0] == "objects" and parts[2] == "object_manifest.json":
        return parts[1]
    return None


def _partial_success_message(diagnostic: Mapping[str, Any], summary: Mapping[str, Any]) -> str:
    base = str(diagnostic.get("message") or "Asset preparation stopped before all objects finished.")
    object_count = int(summary.get("reviewableObjectCount") or 0)
    artifact_count = int(summary.get("artifactCount") or 0)
    return f"{base} Kept {object_count} completed object{'s' if object_count != 1 else ''} and {artifact_count} artifact{'s' if artifact_count != 1 else ''} for review."


def asset_preparation_stall_diagnostic(
    job: Mapping[str, Any],
    events: Sequence[Mapping[str, Any]],
    *,
    now: str | datetime | None = None,
    threshold_seconds: float | None = None,
) -> dict[str, Any] | None:
    if str(job.get("status") or "").lower() != "running":
        return None
    current_time = _parse_dt(now or utc_now())
    if current_time is None:
        return None
    inflight_frame = _inflight_asset_preparation_frame(events)
    if inflight_frame is not None:
        frame_started_at = _parse_dt(
            inflight_frame.get("created_at")
            or inflight_frame.get("createdAt")
            or inflight_frame.get("timestamp")
        )
        threshold = threshold_seconds if threshold_seconds is not None else asset_preparation_frame_timeout_seconds()
        if frame_started_at is not None and current_time > frame_started_at:
            age_seconds = (current_time - frame_started_at).total_seconds()
            if age_seconds >= threshold:
                return _stall_diagnostic_from_event(
                    inflight_frame,
                    reason_code=ASSET_PREPARATION_FRAME_TIMEOUT_REASON,
                    detected_at=current_time,
                    age_seconds=age_seconds,
                    threshold_seconds=threshold,
                )
    latest = _latest_event(events)
    if latest is None:
        return None
    if _event_type(latest) in {ASSET_PREPARATION_STALL_REASON, ASSET_PREPARATION_FRAME_TIMEOUT_REASON, WORKER_HEARTBEAT_STALE_REASON, "failed", "canceled", "cancelled"}:
        return None
    stage = _event_stage(latest)
    if stage != "asset_preparation":
        return None
    latest_at = _parse_dt(latest.get("created_at") or latest.get("createdAt") or latest.get("timestamp"))
    if latest_at is None or current_time <= latest_at:
        return None
    event_type = _event_type(latest)
    reason_code = ASSET_PREPARATION_FRAME_TIMEOUT_REASON if event_type == ASSET_PREPARATION_FRAME_TIMEOUT_REASON or event_type == "asset_preparation_frame_started" else WORKER_HEARTBEAT_STALE_REASON
    threshold = threshold_seconds if threshold_seconds is not None else (
        asset_preparation_frame_timeout_seconds() if reason_code == ASSET_PREPARATION_FRAME_TIMEOUT_REASON else worker_heartbeat_stale_seconds()
    )
    age_seconds = (current_time - latest_at).total_seconds()
    if age_seconds < threshold:
        return None
    return _stall_diagnostic_from_event(
        latest,
        reason_code=reason_code,
        detected_at=current_time,
        age_seconds=age_seconds,
        threshold_seconds=threshold,
    )


def _stall_diagnostic_from_event(
    event: Mapping[str, Any],
    *,
    reason_code: str,
    detected_at: datetime,
    age_seconds: float,
    threshold_seconds: float,
) -> dict[str, Any]:
    event_at = _parse_dt(event.get("created_at") or event.get("createdAt") or event.get("timestamp"))
    if event_at is None:
        event_at = detected_at

    metadata = _event_metadata(event)
    nested_metadata = metadata.get("metadata") if isinstance(metadata.get("metadata"), Mapping) else {}
    progress = metadata.get("progress") if isinstance(metadata.get("progress"), Mapping) else {}
    object_id = str(nested_metadata.get("objectId") or metadata.get("objectId") or "").strip()
    frame_current, frame_total = _frame_progress(event, progress, nested_metadata)
    message = _stall_message(reason_code=reason_code, object_id=object_id, frame_current=frame_current, frame_total=frame_total)
    return {
        "format": "motionjson.asset_preparation_stall.v0.1",
        "reasonCode": reason_code,
        "compatibilityReasonCode": ASSET_PREPARATION_STALL_REASON,
        "phase": "asset_preparation",
        "stage": "asset_preparation",
        "objectId": object_id or None,
        "frame": _int_or_none(nested_metadata.get("frame")),
        "position": _int_or_none(nested_metadata.get("position")) or frame_current,
        "preparedFrames": frame_current,
        "totalFrames": frame_total,
        "lastEventAt": event_at.isoformat(),
        "detectedAt": detected_at.isoformat(),
        "ageSeconds": int(age_seconds),
        "thresholdSeconds": int(threshold_seconds),
        "latestEventMessage": str(event.get("message") or ""),
        "message": message,
        "suggestedAction": "Cancel is no longer needed; retry asset preparation from the same setup or return to Model setup before starting a new run.",
        "artifactsAvailable": False,
    }


def _inflight_asset_preparation_frame(events: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    starts: dict[tuple[str, int | None, int | None], Mapping[str, Any]] = {}
    for event in events:
        if _event_stage(event) != "asset_preparation":
            continue
        event_type = _event_type(event)
        if event_type not in {"asset_preparation_frame_started", "asset_preparation_frame_finished"}:
            continue
        metadata = _event_metadata(event)
        nested_metadata = metadata.get("metadata") if isinstance(metadata.get("metadata"), Mapping) else {}
        progress = metadata.get("progress") if isinstance(metadata.get("progress"), Mapping) else {}
        object_id = str(nested_metadata.get("objectId") or metadata.get("objectId") or "").strip()
        position, _total = _frame_progress(event, progress, nested_metadata)
        frame = _int_or_none(nested_metadata.get("frame"))
        key = (object_id, position, frame)
        if event_type == "asset_preparation_frame_started":
            starts[key] = event
        elif event_type == "asset_preparation_frame_finished":
            starts.pop(key, None)
    if not starts:
        return None
    return list(starts.values())[-1]


def _latest_event(events: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    if not events:
        return None
    return events[-1]


def _event_type(event: Mapping[str, Any]) -> str:
    return str(event.get("event_type") or event.get("type") or "").lower()


def _event_metadata(event: Mapping[str, Any]) -> dict[str, Any]:
    raw = event.get("metadata")
    if isinstance(raw, Mapping):
        return dict(raw)
    raw_json = event.get("metadata_json")
    if isinstance(raw_json, str) and raw_json.strip():
        try:
            parsed = json.loads(raw_json)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, Mapping):
            return dict(parsed)
    return {}


def _event_stage(event: Mapping[str, Any]) -> str:
    metadata = _event_metadata(event)
    return str(event.get("stage") or metadata.get("stage") or "").strip().lower()


def _frame_progress(event: Mapping[str, Any], progress: Mapping[str, Any], metadata: Mapping[str, Any] | None = None) -> tuple[int | None, int | None]:
    metadata = metadata or {}
    current = _int_or_none(metadata.get("position")) or _int_or_none(progress.get("current"))
    total = _int_or_none(metadata.get("totalFrames")) or _int_or_none(progress.get("total"))
    if current is not None or total is not None:
        return current, total
    match = _FRAME_PROGRESS_RE.search(str(event.get("message") or ""))
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def _stall_message(*, reason_code: str, object_id: str, frame_current: int | None, frame_total: int | None) -> str:
    object_text = f" for {object_id}" if object_id else ""
    if reason_code == ASSET_PREPARATION_FRAME_TIMEOUT_REASON:
        if frame_current is not None and frame_total is not None:
            return f"Raster asset preparation timed out on frame {frame_current}/{frame_total}{object_text}. No frame-finished event arrived."
        return f"Raster asset preparation timed out{object_text}. No frame-finished event arrived."
    if frame_current is not None and frame_total is not None:
        return f"Worker heartbeat stopped during asset preparation after frame {frame_current}/{frame_total}{object_text}. No export artifacts were produced."
    return f"Worker heartbeat stopped during asset preparation{object_text}. No export artifacts were produced."


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_dt(value: str | datetime | None) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
