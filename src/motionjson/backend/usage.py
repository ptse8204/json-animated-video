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
    return {"events": events, "totals": totals, "costDashboard": build_usage_cost_dashboard(events)}


def build_usage_cost_dashboard(events: list[dict[str, Any]]) -> dict[str, Any]:
    provider_events: dict[str, dict[str, Any]] = {}
    cache = {"hits": 0, "misses": 0, "readBytes": 0, "writtenBytes": 0}
    latency_ms = 0.0
    latency_count = 0
    for event in events:
        metadata = json.loads(event.get("metadata_json") or "{}")
        provider = metadata.get("provider")
        if isinstance(provider, str) and provider:
            bucket = provider_events.setdefault(
                provider,
                {
                    "provider": provider,
                    "attempts": 0,
                    "estimatedCostUnits": 0.0,
                    "unitCostUsd": 0.0 if metadata.get("costStatus") == "zero_local_provider_cost" else None,
                    "costStatus": metadata.get("costStatus") or "unknown_provider_cost",
                },
            )
            if event.get("event_type") == "provider_attempts":
                bucket["attempts"] += int(float(event.get("quantity") or 0))
            bucket["estimatedCostUnits"] += float(metadata.get("estimatedCostUnits") or 0.0)
        if event.get("event_type") == "cache_hits":
            cache["hits"] += int(float(event.get("quantity") or 0))
            cache["readBytes"] += int(metadata.get("readBytes") or 0)
        if event.get("event_type") == "cache_misses":
            cache["misses"] += int(float(event.get("quantity") or 0))
            cache["writtenBytes"] += int(metadata.get("writtenBytes") or 0)
        if event.get("event_type") == "latency_ms":
            latency_ms += float(event.get("quantity") or 0.0)
            latency_count += 1
    requests = cache["hits"] + cache["misses"]
    return {
        "schema": "motionjson.backend_cost_dashboard.v0.1",
        "aiUsage": "none_for_preview_edits",
        "policy": "Local deterministic providers report zero provider cost; custom hosted costs are explicit unknowns unless supplied by the provider.",
        "providers": list(provider_events.values()),
        "cache": {**cache, "hitRate": round(cache["hits"] / requests, 4) if requests else None},
        "latency": {"totalMs": round(latency_ms, 3), "eventCount": latency_count},
    }
