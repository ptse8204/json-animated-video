from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_usage_event(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    event_type: str,
    quantity: float,
    unit: str,
    project_id: str | None = None,
    job_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event = {
        "id": uuid.uuid4().hex,
        "user_id": user_id,
        "project_id": project_id,
        "job_id": job_id,
        "event_type": event_type,
        "quantity": float(quantity),
        "unit": unit,
        "metadata_json": json.dumps(metadata or {}, sort_keys=True),
        "created_at": utc_now(),
    }
    conn.execute(
        """
        INSERT INTO usage_events
        (id, user_id, project_id, job_id, event_type, quantity, unit, metadata_json, created_at)
        VALUES (:id, :user_id, :project_id, :job_id, :event_type, :quantity, :unit, :metadata_json, :created_at)
        """,
        event,
    )
    conn.commit()
    return event


def list_usage_events(conn: sqlite3.Connection, *, project_id: str | None = None, user_id: str | None = None) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: dict[str, str] = {}
    if project_id:
        clauses.append("project_id = :project_id")
        params["project_id"] = project_id
    if user_id:
        clauses.append("user_id = :user_id")
        params["user_id"] = user_id
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(f"SELECT * FROM usage_events {where} ORDER BY created_at, id", params).fetchall()
    return [dict(row) for row in rows]


def summarize_usage(conn: sqlite3.Connection, *, project_id: str | None = None, user_id: str | None = None) -> dict[str, Any]:
    events = list_usage_events(conn, project_id=project_id, user_id=user_id)
    totals: dict[str, dict[str, float]] = {}
    for event in events:
        bucket = totals.setdefault(event["event_type"], {})
        bucket[event["unit"]] = bucket.get(event["unit"], 0.0) + float(event["quantity"])
    return {"events": events, "totals": totals}
