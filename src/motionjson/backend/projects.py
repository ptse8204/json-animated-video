from __future__ import annotations

import sqlite3
import uuid

from .models import NotFoundError
from .usage import utc_now


def create_project(conn: sqlite3.Connection, *, user_id: str, name: str, description: str = "") -> dict:
    now = utc_now()
    project = {
        "id": uuid.uuid4().hex,
        "owner_user_id": user_id,
        "name": name.strip() or "Untitled Project",
        "description": description,
        "created_at": now,
        "updated_at": now,
        "archived_at": None,
    }
    conn.execute(
        """
        INSERT INTO projects (id, owner_user_id, name, description, created_at, updated_at, archived_at)
        VALUES (:id, :owner_user_id, :name, :description, :created_at, :updated_at, :archived_at)
        """,
        project,
    )
    conn.commit()
    return project


def get_project(conn: sqlite3.Connection, *, user_id: str, project_id: str, include_archived: bool = False) -> dict:
    archived_clause = "" if include_archived else "AND archived_at IS NULL"
    row = conn.execute(
        f"SELECT * FROM projects WHERE id = ? AND owner_user_id = ? {archived_clause}",
        (project_id, user_id),
    ).fetchone()
    if row is None:
        raise NotFoundError("project not found")
    return dict(row)


def list_projects(conn: sqlite3.Connection, *, user_id: str, include_archived: bool = False) -> list[dict]:
    archived_clause = "" if include_archived else "AND archived_at IS NULL"
    rows = conn.execute(
        f"SELECT * FROM projects WHERE owner_user_id = ? {archived_clause} ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def archive_project(conn: sqlite3.Connection, *, user_id: str, project_id: str) -> dict:
    project = get_project(conn, user_id=user_id, project_id=project_id)
    now = utc_now()
    conn.execute("UPDATE projects SET archived_at = ?, updated_at = ? WHERE id = ?", (now, now, project_id))
    conn.commit()
    project["archived_at"] = now
    project["updated_at"] = now
    return project
