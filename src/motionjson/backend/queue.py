from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from .jobs import record_job_event
from .usage import record_usage_event, utc_now


def claim_next(conn: sqlite3.Connection, *, worker_id: str, now: str | None = None) -> dict[str, Any] | None:
    current = now or utc_now()
    row = conn.execute(
        """
        SELECT queue_items.id AS queue_item_id, jobs.*
        FROM queue_items
        JOIN jobs ON jobs.id = queue_items.job_id
        WHERE queue_items.status = 'pending' AND queue_items.run_after <= ?
        ORDER BY queue_items.priority DESC, queue_items.created_at ASC
        LIMIT 1
        """,
        (current,),
    ).fetchone()
    if row is None:
        return None
    conn.execute(
        "UPDATE queue_items SET status = 'locked', locked_by = ?, locked_at = ? WHERE id = ? AND status = 'pending'",
        (worker_id, current, row["queue_item_id"]),
    )
    conn.commit()
    return dict(row)


def mark_running(conn: sqlite3.Connection, *, job_id: str) -> dict:
    now = utc_now()
    conn.execute(
        "UPDATE jobs SET status = 'running', updated_at = ?, started_at = COALESCE(started_at, ?) WHERE id = ?",
        (now, now, job_id),
    )
    conn.execute("UPDATE queue_items SET status = 'running' WHERE job_id = ?", (job_id,))
    conn.commit()
    record_job_event(conn, job_id=job_id, event_type="running", message="job started")
    return dict(conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone())


def mark_succeeded(conn: sqlite3.Connection, *, job_id: str, result: dict[str, Any] | None = None) -> dict:
    now = utc_now()
    conn.execute(
        """
        UPDATE jobs
        SET status = 'succeeded', result_json = ?, error = NULL, updated_at = ?, finished_at = ?
        WHERE id = ?
        """,
        (json.dumps(result or {}, sort_keys=True), now, now, job_id),
    )
    conn.execute("UPDATE queue_items SET status = 'succeeded' WHERE job_id = ?", (job_id,))
    conn.commit()
    record_job_event(conn, job_id=job_id, event_type="succeeded", message="job completed", metadata=result or {})
    return dict(conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone())


def mark_canceled(conn: sqlite3.Connection, *, job_id: str, reason: str = "user_canceled") -> dict:
    now = utc_now()
    conn.execute(
        """
        UPDATE jobs
        SET status = 'canceled', error = ?, updated_at = ?, finished_at = COALESCE(finished_at, ?)
        WHERE id = ?
        """,
        (reason, now, now, job_id),
    )
    conn.execute("UPDATE queue_items SET status = 'canceled', locked_by = NULL, locked_at = NULL WHERE job_id = ?", (job_id,))
    conn.commit()
    record_job_event(conn, job_id=job_id, event_type="canceled", message=reason, metadata={"reason": reason})
    canceled = conn.execute("SELECT created_by_user_id, project_id FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if canceled is not None:
        record_usage_event(
            conn,
            user_id=canceled["created_by_user_id"],
            project_id=canceled["project_id"],
            job_id=job_id,
            event_type="job_cancellations",
            quantity=1,
            unit="cancellation",
            metadata={"reason": reason},
        )
    return dict(conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone())


def request_cancel_job(conn: sqlite3.Connection, *, job_id: str, reason: str = "user_canceled") -> dict:
    job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if job is None:
        raise ValueError(f"job not found: {job_id}")
    if job["status"] in {"succeeded", "failed", "canceled"}:
        return dict(job)
    if job["status"] in {"pending", "queued"}:
        return mark_canceled(conn, job_id=job_id, reason=reason)
    if job["status"] == "running":
        now = utc_now()
        conn.execute(
            "UPDATE jobs SET status = 'cancel_requested', error = ?, updated_at = ? WHERE id = ?",
            (reason, now, job_id),
        )
        conn.commit()
    record_job_event(conn, job_id=job_id, event_type="cancellation_requested", message=reason, metadata={"reason": reason})
    return dict(conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone())


def mark_failed(
    conn: sqlite3.Connection,
    *,
    job_id: str,
    error: str,
    retry_delay_seconds: int = 30,
    max_attempts: int = 3,
) -> dict:
    job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if job is None:
        raise ValueError(f"job not found: {job_id}")
    attempts = int(job["attempts"]) + 1
    now = utc_now()
    if attempts < max_attempts:
        run_after = (datetime.now(timezone.utc) + timedelta(seconds=retry_delay_seconds)).isoformat()
        conn.execute(
            "UPDATE jobs SET status = 'pending', attempts = ?, error = ?, updated_at = ? WHERE id = ?",
            (attempts, error, now, job_id),
        )
        conn.execute(
            "UPDATE queue_items SET status = 'pending', run_after = ?, locked_by = NULL, locked_at = NULL WHERE job_id = ?",
            (run_after, job_id),
        )
        conn.commit()
        record_job_event(conn, job_id=job_id, event_type="retry", message=error, metadata={"attempts": attempts, "maxAttempts": max_attempts})
    else:
        conn.execute(
            "UPDATE jobs SET status = 'failed', attempts = ?, error = ?, updated_at = ?, finished_at = ? WHERE id = ?",
            (attempts, error, now, now, job_id),
        )
        conn.execute("UPDATE queue_items SET status = 'failed' WHERE job_id = ?", (job_id,))
        conn.commit()
        record_job_event(conn, job_id=job_id, event_type="failed", message=error, metadata={"attempts": attempts, "maxAttempts": max_attempts})
        failed = conn.execute("SELECT created_by_user_id, project_id FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if failed is not None:
            record_usage_event(
                conn,
                user_id=failed["created_by_user_id"],
                project_id=failed["project_id"],
                job_id=job_id,
                event_type="job_failures",
                quantity=1,
                unit="failure",
                metadata={"error": error},
            )
    return dict(conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone())
