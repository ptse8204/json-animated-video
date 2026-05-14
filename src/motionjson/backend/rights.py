from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Any

from .usage import utc_now


def _dump(payload: dict[str, Any] | None) -> str:
    return json.dumps(payload or {}, sort_keys=True)


def record_rights_metadata(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    rights: dict[str, Any],
    asset_id: str | None = None,
    object_id: str | None = None,
    job_id: str | None = None,
) -> dict[str, Any]:
    row = {
        "id": uuid.uuid4().hex,
        "project_id": project_id,
        "asset_id": asset_id,
        "object_id": object_id,
        "job_id": job_id,
        "rights_json": _dump(rights),
        "creator_approved": 1 if rights.get("creatorApproval", {}).get("approved") else 0,
        "creator_approval_status": rights.get("creatorApproval", {}).get("status", "unverified"),
        "commercial_use": 1 if rights.get("commercialUse") else 0,
        "commercial_use_status": rights.get("commercialUseStatus", "review_required"),
        "created_at": utc_now(),
    }
    conn.execute(
        """
        INSERT INTO rights_metadata
        (id, project_id, asset_id, object_id, job_id, rights_json, creator_approved, creator_approval_status, commercial_use, commercial_use_status, created_at)
        VALUES (:id, :project_id, :asset_id, :object_id, :job_id, :rights_json, :creator_approved, :creator_approval_status, :commercial_use, :commercial_use_status, :created_at)
        """,
        row,
    )
    conn.commit()
    return row


def record_asset_lineage(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    source_asset_id: str | None,
    derived_asset_id: str,
    job_id: str | None,
    operation: str,
    object_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = {
        "id": uuid.uuid4().hex,
        "project_id": project_id,
        "source_asset_id": source_asset_id,
        "derived_asset_id": derived_asset_id,
        "job_id": job_id,
        "operation": operation,
        "object_id": object_id,
        "metadata_json": _dump(metadata),
        "created_at": utc_now(),
    }
    conn.execute(
        """
        INSERT INTO asset_lineage
        (id, project_id, source_asset_id, derived_asset_id, job_id, operation, object_id, metadata_json, created_at)
        VALUES (:id, :project_id, :source_asset_id, :derived_asset_id, :job_id, :operation, :object_id, :metadata_json, :created_at)
        """,
        row,
    )
    conn.commit()
    return row


def record_audit_event(
    conn: sqlite3.Connection,
    *,
    event_type: str,
    project_id: str | None = None,
    user_id: str | None = None,
    job_id: str | None = None,
    asset_id: str | None = None,
    object_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = {
        "id": uuid.uuid4().hex,
        "user_id": user_id,
        "project_id": project_id,
        "job_id": job_id,
        "asset_id": asset_id,
        "object_id": object_id,
        "event_type": event_type,
        "metadata_json": _dump(metadata),
        "created_at": utc_now(),
    }
    conn.execute(
        """
        INSERT INTO audit_events
        (id, user_id, project_id, job_id, asset_id, object_id, event_type, metadata_json, created_at)
        VALUES (:id, :user_id, :project_id, :job_id, :asset_id, :object_id, :event_type, :metadata_json, :created_at)
        """,
        row,
    )
    conn.commit()
    return row


def list_asset_rights(conn: sqlite3.Connection, *, asset_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM rights_metadata WHERE asset_id = ? ORDER BY created_at, id",
        (asset_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def list_asset_lineage(conn: sqlite3.Connection, *, asset_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM asset_lineage
        WHERE source_asset_id = ? OR derived_asset_id = ?
        ORDER BY created_at, id
        """,
        (asset_id, asset_id),
    ).fetchall()
    return [dict(row) for row in rows]


def list_audit_events(
    conn: sqlite3.Connection,
    *,
    project_id: str | None = None,
    job_id: str | None = None,
    asset_id: str | None = None,
) -> list[dict[str, Any]]:
    clauses = []
    params: list[str] = []
    if project_id:
        clauses.append("project_id = ?")
        params.append(project_id)
    if job_id:
        clauses.append("job_id = ?")
        params.append(job_id)
    if asset_id:
        clauses.append("asset_id = ?")
        params.append(asset_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(f"SELECT * FROM audit_events {where} ORDER BY created_at, id", params).fetchall()
    return [dict(row) for row in rows]
