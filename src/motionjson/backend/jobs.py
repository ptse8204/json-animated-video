from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Any

from .assets import get_asset
from .models import NotFoundError, validate_extract_provider_policy
from .projects import get_project
from .usage import record_usage_event, utc_now


def record_job_event(
    conn: sqlite3.Connection,
    *,
    job_id: str,
    event_type: str,
    message: str,
    metadata: dict[str, Any] | None = None,
) -> dict:
    event = {
        "id": uuid.uuid4().hex,
        "job_id": job_id,
        "event_type": event_type,
        "message": message,
        "metadata_json": json.dumps(metadata or {}, sort_keys=True),
        "created_at": utc_now(),
    }
    conn.execute(
        """
        INSERT INTO job_events (id, job_id, event_type, message, metadata_json, created_at)
        VALUES (:id, :job_id, :event_type, :message, :metadata_json, :created_at)
        """,
        event,
    )
    conn.commit()
    return event


def _insert_job(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    project_id: str,
    job_type: str,
    payload: dict[str, Any],
    priority: int = 0,
) -> dict:
    now = utc_now()
    job = {
        "id": uuid.uuid4().hex,
        "project_id": project_id,
        "created_by_user_id": user_id,
        "type": job_type,
        "status": "pending",
        "payload_json": json.dumps(payload, sort_keys=True),
        "result_json": "{}",
        "error": None,
        "attempts": 0,
        "created_at": now,
        "updated_at": now,
        "started_at": None,
        "finished_at": None,
    }
    conn.execute(
        """
        INSERT INTO jobs
        (id, project_id, created_by_user_id, type, status, payload_json, result_json, error, attempts, created_at, updated_at, started_at, finished_at)
        VALUES (:id, :project_id, :created_by_user_id, :type, :status, :payload_json, :result_json, :error, :attempts, :created_at, :updated_at, :started_at, :finished_at)
        """,
        job,
    )
    conn.execute(
        """
        INSERT INTO queue_items (id, job_id, status, priority, run_after, locked_by, locked_at, created_at)
        VALUES (?, ?, 'pending', ?, ?, NULL, NULL, ?)
        """,
        (uuid.uuid4().hex, job["id"], int(priority), now, now),
    )
    conn.commit()
    record_job_event(conn, job_id=job["id"], event_type="queued", message=f"{job_type} job queued")
    record_usage_event(conn, user_id=user_id, project_id=project_id, job_id=job["id"], event_type="jobs_created", quantity=1, unit="job", metadata={"type": job_type})
    return job


def enqueue_extract_job(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    project_id: str,
    asset_id: str,
    mask_provider: str = "threshold",
    max_frames: int | None = None,
    sample_fps: float = 12.0,
    lower_hsv: tuple[int, int, int] = (0, 80, 80),
    upper_hsv: tuple[int, int, int] = (12, 255, 255),
    mask_dir: str | None = None,
    priority: int = 0,
) -> dict:
    get_project(conn, user_id=user_id, project_id=project_id)
    asset = get_asset(conn, user_id=user_id, asset_id=asset_id)
    if asset["project_id"] != project_id:
        raise NotFoundError("asset not found in project")
    mask_provider = validate_extract_provider_policy(mask_provider)
    payload = {
        "asset_id": asset_id,
        "mask_provider": mask_provider,
        "max_frames": max_frames,
        "sample_fps": sample_fps,
        "lower_hsv": list(lower_hsv),
        "upper_hsv": list(upper_hsv),
        "mask_dir": mask_dir,
    }
    return _insert_job(conn, user_id=user_id, project_id=project_id, job_type="extract", payload=payload, priority=priority)


def enqueue_export_job(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    project_id: str,
    source_job_id: str,
    format: str = "website-zip",
    priority: int = 0,
) -> dict:
    get_project(conn, user_id=user_id, project_id=project_id)
    source = get_job(conn, user_id=user_id, job_id=source_job_id)
    if source["project_id"] != project_id:
        raise NotFoundError("source job not found in project")
    payload = {"source_job_id": source_job_id, "format": format}
    return _insert_job(conn, user_id=user_id, project_id=project_id, job_type="export", payload=payload, priority=priority)


def get_job(conn: sqlite3.Connection, *, user_id: str, job_id: str) -> dict:
    row = conn.execute(
        """
        SELECT jobs.*
        FROM jobs
        JOIN projects ON projects.id = jobs.project_id
        WHERE jobs.id = ? AND projects.owner_user_id = ?
        """,
        (job_id, user_id),
    ).fetchone()
    if row is None:
        raise NotFoundError("job not found")
    return dict(row)


def list_jobs(conn: sqlite3.Connection, *, user_id: str, project_id: str) -> list[dict]:
    get_project(conn, user_id=user_id, project_id=project_id)
    rows = conn.execute("SELECT * FROM jobs WHERE project_id = ? ORDER BY created_at DESC", (project_id,)).fetchall()
    return [dict(row) for row in rows]


def list_job_events(conn: sqlite3.Connection, *, job_id: str) -> list[dict]:
    rows = conn.execute("SELECT * FROM job_events WHERE job_id = ? ORDER BY created_at, id", (job_id,)).fetchall()
    return [dict(row) for row in rows]
