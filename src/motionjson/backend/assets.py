from __future__ import annotations

import io
import json
import mimetypes
import re
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from motionjson.providers.base import StorageProvider
from motionjson.rights import build_object_rights

from .models import NotFoundError
from .projects import get_project
from .rights import record_audit_event, record_rights_metadata
from .usage import record_usage_event, utc_now

SAFE_SEGMENT_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_name(name: str) -> str:
    cleaned = SAFE_SEGMENT_RE.sub("_", name.strip()).strip("._-")
    return cleaned or "asset"


def _asset_row(conn: sqlite3.Connection, asset_id: str) -> dict:
    row = conn.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone()
    if row is None:
        raise NotFoundError("asset not found")
    return dict(row)


def get_asset(conn: sqlite3.Connection, *, user_id: str, asset_id: str) -> dict:
    asset = _asset_row(conn, asset_id)
    get_project(conn, user_id=user_id, project_id=asset["project_id"])
    return asset


def list_project_assets(conn: sqlite3.Connection, *, user_id: str, project_id: str, kind: str | None = None) -> list[dict]:
    get_project(conn, user_id=user_id, project_id=project_id)
    if kind:
        rows = conn.execute(
            "SELECT * FROM assets WHERE project_id = ? AND kind = ? ORDER BY created_at, id",
            (project_id, kind),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM assets WHERE project_id = ? ORDER BY created_at, id", (project_id,)).fetchall()
    return [dict(row) for row in rows]


def list_assets_for_job(conn: sqlite3.Connection, *, project_id: str, source_job_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM assets WHERE project_id = ? AND source_job_id = ? ORDER BY created_at, id",
        (project_id, source_job_id),
    ).fetchall()
    return [dict(row) for row in rows]


def _insert_asset(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    kind: str,
    storage_key: str,
    uri: str,
    content_type: str | None,
    byte_size: int,
    source_job_id: str | None,
    metadata: dict[str, Any] | None,
) -> dict:
    asset = {
        "id": uuid.uuid4().hex,
        "project_id": project_id,
        "kind": kind,
        "storage_key": storage_key,
        "uri": uri,
        "content_type": content_type,
        "byte_size": int(byte_size),
        "source_job_id": source_job_id,
        "metadata_json": json.dumps(metadata or {}, sort_keys=True),
        "created_at": utc_now(),
    }
    conn.execute(
        """
        INSERT INTO assets
        (id, project_id, kind, storage_key, uri, content_type, byte_size, source_job_id, metadata_json, created_at)
        VALUES (:id, :project_id, :kind, :storage_key, :uri, :content_type, :byte_size, :source_job_id, :metadata_json, :created_at)
        """,
        asset,
    )
    conn.commit()
    return asset


def register_upload(
    conn: sqlite3.Connection,
    *,
    storage: StorageProvider,
    user_id: str,
    project_id: str,
    path: str | Path,
    kind: str,
    content_type: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict:
    get_project(conn, user_id=user_id, project_id=project_id)
    source_path = Path(path)
    input_metadata = dict(metadata or {})
    data = source_path.read_bytes()
    guessed_type = content_type or mimetypes.guess_type(source_path.name)[0] or "application/octet-stream"
    key = f"projects/{project_id}/uploads/{uuid.uuid4().hex}_{_safe_name(source_path.name)}"
    uri = storage.save_bytes(key, data, content_type=guessed_type)
    asset = _insert_asset(
        conn,
        project_id=project_id,
        kind=kind,
        storage_key=key,
        uri=uri,
        content_type=guessed_type,
        byte_size=len(data),
        source_job_id=None,
        metadata={"filename": source_path.name, **input_metadata},
    )
    rights_context = input_metadata.get("rights_context") if isinstance(input_metadata.get("rights_context"), dict) else input_metadata
    rights = build_object_rights(
        object_id="source",
        context=rights_context,
        operations=[],
        fallback_source_uri=str(source_path),
    )
    record_rights_metadata(conn, project_id=project_id, asset_id=asset["id"], rights=rights)
    record_audit_event(
        conn,
        user_id=user_id,
        project_id=project_id,
        asset_id=asset["id"],
        event_type="asset_uploaded",
        metadata={"kind": kind, "filename": source_path.name},
    )
    record_usage_event(conn, user_id=user_id, project_id=project_id, event_type="uploads", quantity=1, unit="asset", metadata={"assetId": asset["id"], "kind": kind})
    record_usage_event(conn, user_id=user_id, project_id=project_id, event_type="bytes_stored", quantity=len(data), unit="byte", metadata={"assetId": asset["id"], "kind": kind})
    return asset


def register_generated_asset(
    conn: sqlite3.Connection,
    *,
    storage: StorageProvider,
    project_id: str,
    kind: str,
    source_job_id: str,
    data: bytes | None = None,
    path: str | Path | None = None,
    rel_path: str | None = None,
    content_type: str | None = None,
    metadata: dict[str, Any] | None = None,
    user_id: str | None = None,
) -> dict:
    if user_id is not None:
        get_project(conn, user_id=user_id, project_id=project_id)
    if data is None:
        if path is None:
            raise ValueError("data or path is required")
        file_path = Path(path)
        data = file_path.read_bytes()
        rel_path = rel_path or file_path.name
        content_type = content_type or mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    if not rel_path:
        rel_path = f"{kind}.bin"
    safe_rel = "/".join(_safe_name(part) for part in Path(rel_path.replace("\\", "/")).parts if part not in {"", "."})
    key = f"projects/{project_id}/jobs/{source_job_id}/{safe_rel}"
    uri = storage.save_bytes(key, data, content_type=content_type)
    asset = _insert_asset(
        conn,
        project_id=project_id,
        kind=kind,
        storage_key=key,
        uri=uri,
        content_type=content_type,
        byte_size=len(data),
        source_job_id=source_job_id,
        metadata={"rel_path": rel_path, **(metadata or {})},
    )
    row = conn.execute("SELECT created_by_user_id FROM jobs WHERE id = ?", (source_job_id,)).fetchone()
    if row is not None:
        record_usage_event(
            conn,
            user_id=row["created_by_user_id"],
            project_id=project_id,
            job_id=source_job_id,
            event_type="bytes_stored",
            quantity=len(data),
            unit="byte",
            metadata={"assetId": asset["id"], "kind": kind},
        )
    return asset


def generated_asset_for_rel_path(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    source_job_id: str,
    rel_path: str,
) -> dict | None:
    rows = conn.execute(
        "SELECT * FROM assets WHERE project_id = ? AND source_job_id = ? ORDER BY created_at, id",
        (project_id, source_job_id),
    ).fetchall()
    for row in rows:
        asset = dict(row)
        try:
            metadata = json.loads(asset.get("metadata_json") or "{}")
        except json.JSONDecodeError:
            continue
        if metadata.get("rel_path") == rel_path:
            return asset
    return None


def register_generated_asset_once(
    conn: sqlite3.Connection,
    *,
    storage: StorageProvider,
    project_id: str,
    kind: str,
    source_job_id: str,
    data: bytes | None = None,
    path: str | Path | None = None,
    rel_path: str | None = None,
    content_type: str | None = None,
    metadata: dict[str, Any] | None = None,
    user_id: str | None = None,
    replace_existing: bool = False,
) -> tuple[dict, bool]:
    if not rel_path and path is not None:
        rel_path = Path(path).name
    if not rel_path:
        rel_path = f"{kind}.bin"
    existing = generated_asset_for_rel_path(
        conn,
        project_id=project_id,
        source_job_id=source_job_id,
        rel_path=rel_path,
    )
    if existing is not None:
        if replace_existing:
            if data is None:
                if path is None:
                    raise ValueError("data or path is required")
                file_path = Path(path)
                data = file_path.read_bytes()
                content_type = content_type or mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
            safe_rel = "/".join(_safe_name(part) for part in Path(rel_path.replace("\\", "/")).parts if part not in {"", "."})
            key = f"projects/{project_id}/jobs/{source_job_id}/{safe_rel}"
            uri = storage.save_bytes(key, data, content_type=content_type)
            updated = {
                **existing,
                "kind": kind,
                "storage_key": key,
                "uri": uri,
                "content_type": content_type,
                "byte_size": len(data),
                "metadata_json": json.dumps({"rel_path": rel_path, **(metadata or {})}, sort_keys=True),
                "created_at": utc_now(),
            }
            conn.execute(
                """
                UPDATE assets
                SET kind = :kind,
                    storage_key = :storage_key,
                    uri = :uri,
                    content_type = :content_type,
                    byte_size = :byte_size,
                    metadata_json = :metadata_json,
                    created_at = :created_at
                WHERE id = :id
                """,
                updated,
            )
            conn.commit()
            return updated, False
        return existing, False
    return (
        register_generated_asset(
            conn,
            storage=storage,
            project_id=project_id,
            kind=kind,
            source_job_id=source_job_id,
            data=data,
            path=path,
            rel_path=rel_path,
            content_type=content_type,
            metadata=metadata,
            user_id=user_id,
        ),
        True,
    )


def load_asset_bytes(conn: sqlite3.Connection, *, storage: StorageProvider, user_id: str, asset_id: str) -> bytes:
    asset = get_asset(conn, user_id=user_id, asset_id=asset_id)
    return storage.load_bytes(asset["storage_key"])


def open_asset(conn: sqlite3.Connection, *, storage: StorageProvider, user_id: str, asset_id: str) -> io.BytesIO:
    return io.BytesIO(load_asset_bytes(conn, storage=storage, user_id=user_id, asset_id=asset_id))


def update_asset_metadata(
    conn: sqlite3.Connection,
    *,
    asset_id: str,
    metadata: dict[str, Any],
) -> dict:
    asset = _asset_row(conn, asset_id)
    current = json.loads(asset.get("metadata_json") or "{}")
    if not isinstance(current, dict):
        current = {}
    merged = {**current, **metadata}
    conn.execute("UPDATE assets SET metadata_json = ? WHERE id = ?", (json.dumps(merged, sort_keys=True), asset_id))
    conn.commit()
    return _asset_row(conn, asset_id)
