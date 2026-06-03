from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from .jobs import record_job_event
from .queue import mark_failed
from .usage import utc_now


ASSET_PREPARATION_STALL_REASON = "asset_preparation_stalled"
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
    diagnostic = asset_preparation_stall_diagnostic(
        dict(job),
        [dict(event) for event in events],
        now=now,
        threshold_seconds=threshold_seconds,
    )
    if not diagnostic:
        return dict(job)

    record_job_event(
        conn,
        job_id=job_id,
        event_type=ASSET_PREPARATION_STALL_REASON,
        message=diagnostic["message"],
        metadata=diagnostic,
    )
    return mark_failed(conn, job_id=job_id, error=diagnostic["message"], max_attempts=1)


def asset_preparation_stall_diagnostic(
    job: Mapping[str, Any],
    events: Sequence[Mapping[str, Any]],
    *,
    now: str | datetime | None = None,
    threshold_seconds: float | None = None,
) -> dict[str, Any] | None:
    if str(job.get("status") or "").lower() != "running":
        return None
    latest = _latest_event(events)
    if latest is None:
        return None
    if _event_type(latest) in {ASSET_PREPARATION_STALL_REASON, "failed", "canceled", "cancelled"}:
        return None
    stage = _event_stage(latest)
    if stage != "asset_preparation":
        return None
    latest_at = _parse_dt(latest.get("created_at") or latest.get("createdAt") or latest.get("timestamp"))
    current_time = _parse_dt(now or utc_now())
    if latest_at is None or current_time is None or current_time <= latest_at:
        return None
    threshold = threshold_seconds if threshold_seconds is not None else asset_preparation_stall_threshold_seconds()
    age_seconds = (current_time - latest_at).total_seconds()
    if age_seconds < threshold:
        return None

    metadata = _event_metadata(latest)
    nested_metadata = metadata.get("metadata") if isinstance(metadata.get("metadata"), Mapping) else {}
    progress = metadata.get("progress") if isinstance(metadata.get("progress"), Mapping) else {}
    object_id = str(nested_metadata.get("objectId") or metadata.get("objectId") or "").strip()
    frame_current, frame_total = _frame_progress(latest, progress)
    message = _stall_message(object_id=object_id, frame_current=frame_current, frame_total=frame_total)
    return {
        "format": "motionjson.asset_preparation_stall.v0.1",
        "reasonCode": ASSET_PREPARATION_STALL_REASON,
        "phase": "asset_preparation",
        "stage": "asset_preparation",
        "objectId": object_id or None,
        "preparedFrames": frame_current,
        "totalFrames": frame_total,
        "lastEventAt": latest_at.isoformat(),
        "detectedAt": current_time.isoformat(),
        "ageSeconds": int(age_seconds),
        "thresholdSeconds": int(threshold),
        "latestEventMessage": str(latest.get("message") or ""),
        "message": message,
        "suggestedAction": "Cancel is no longer needed; retry asset preparation from the same setup or return to Model setup before starting a new run.",
        "artifactsAvailable": False,
    }


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


def _frame_progress(event: Mapping[str, Any], progress: Mapping[str, Any]) -> tuple[int | None, int | None]:
    current = _int_or_none(progress.get("current"))
    total = _int_or_none(progress.get("total"))
    if current is not None or total is not None:
        return current, total
    match = _FRAME_PROGRESS_RE.search(str(event.get("message") or ""))
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def _stall_message(*, object_id: str, frame_current: int | None, frame_total: int | None) -> str:
    object_text = f" for {object_id}" if object_id else ""
    if frame_current is not None and frame_total is not None:
        return f"Raster asset preparation stalled after frame {frame_current}/{frame_total}{object_text}. No export artifacts were produced."
    return f"Raster asset preparation stalled{object_text}. No export artifacts were produced."


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
