from __future__ import annotations

import json
import re
import sqlite3
import uuid
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from .assets import get_asset
from .models import BackendError, NotFoundError
from .projects import get_project
from .rights import record_audit_event
from .usage import utc_now


LIBRARY_ASSET_TYPES = {"saved_asset", "motion_sticker"}
APPROVED_STATUS = "approved"
PUBLIC_MAX_TEXT_LENGTH = 2_000
PUBLIC_MAX_METADATA_ITEMS = 50
PUBLIC_MAX_METADATA_DEPTH = 4
PUBLIC_API_KEY_PATTERN = re.compile(r"\b(?:mj_local_|mjb_|sk-|or-)[A-Za-z0-9._~+/=-]{12,}\b")
PUBLIC_BEARER_PATTERN = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
PUBLIC_SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(api[_-]?key|authorization|data[_-]?base64|file[_-]?bytes|key[_-]?hash|password(?:[_-]?hash)?|secret|signing[_-]?secret|storage[_-]?key|token(?:[_-]?hash)?|webhook[_-]?secret)=([^\s&]+)"
)
PUBLIC_SENSITIVE_TERM_PATTERN = re.compile(
    r"(?i)\b(api[_-]?key|data[_-]?base64|file[_-]?bytes|key[_-]?hash|password[_-]?hash|signing[_-]?secret|storage[_-]?key|token[_-]?hash|webhook[_-]?secret)\b"
)
PUBLIC_URL_PATTERN = re.compile(r"https?://[^\s)\"']+")


def _dump(payload: dict[str, Any] | None) -> str:
    return json.dumps(payload or {}, sort_keys=True)


def _parse_json(raw: str | None) -> dict[str, Any]:
    parsed = json.loads(raw or "{}")
    return parsed if isinstance(parsed, dict) else {}


def _normalized_key(key: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(key).lower())


def _is_sensitive_public_key(key: Any) -> bool:
    normalized = _normalized_key(key)
    sensitive_names = {
        "apikey",
        "authorization",
        "bearer",
        "database64",
        "filebytes",
        "keyhash",
        "password",
        "passwordhash",
        "secret",
        "signingsecret",
        "storagekey",
        "token",
        "tokenhash",
        "webhooksecret",
    }
    return normalized in sensitive_names or any(part in normalized for part in ("apikey", "database64", "keyhash", "password", "secret", "storagekey", "token"))


def _truncate_public_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return f"{value[:limit]}...[truncated]"


def _strip_url_query(match: re.Match[str]) -> str:
    try:
        parts = urlsplit(match.group(0))
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    except ValueError:
        return "[REDACTED_URL]"


def _public_text(value: Any, *, limit: int = PUBLIC_MAX_TEXT_LENGTH) -> str:
    text = str(value or "")
    text = PUBLIC_BEARER_PATTERN.sub("Bearer [REDACTED]", text)
    text = PUBLIC_API_KEY_PATTERN.sub("[REDACTED_API_KEY]", text)
    text = PUBLIC_SECRET_ASSIGNMENT_PATTERN.sub("[REDACTED_FIELD]=[REDACTED]", text)
    text = PUBLIC_SENSITIVE_TERM_PATTERN.sub("[REDACTED_FIELD]", text)
    text = PUBLIC_URL_PATTERN.sub(_strip_url_query, text)
    return _truncate_public_text(text, limit)


def _public_metadata(value: Any, *, depth: int = 0) -> Any:
    if depth > PUBLIC_MAX_METADATA_DEPTH:
        return "[REDACTED_DEPTH]"
    if isinstance(value, dict):
        public: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= PUBLIC_MAX_METADATA_ITEMS:
                public["__truncated__"] = True
                break
            if _is_sensitive_public_key(key):
                continue
            public_key = _public_text(key, limit=120)
            if not public_key:
                continue
            public[public_key] = _public_metadata(item, depth=depth + 1)
        return public
    if isinstance(value, list):
        items = [_public_metadata(item, depth=depth + 1) for item in value[:PUBLIC_MAX_METADATA_ITEMS]]
        if len(value) > PUBLIC_MAX_METADATA_ITEMS:
            items.append("[TRUNCATED]")
        return items
    if isinstance(value, str):
        return _public_text(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return _public_text(value)


def _nullable_public_text(value: Any, *, limit: int = PUBLIC_MAX_TEXT_LENGTH) -> str | None:
    if value is None:
        return None
    return _public_text(value, limit=limit)


def _public_tag(value: Any) -> str | None:
    tag = str(value).strip().lower()
    if (
        not tag
        or _is_sensitive_public_key(tag)
        or PUBLIC_BEARER_PATTERN.search(tag)
        or PUBLIC_API_KEY_PATTERN.search(tag)
        or PUBLIC_SECRET_ASSIGNMENT_PATTERN.search(tag)
        or PUBLIC_SENSITIVE_TERM_PATTERN.search(tag)
    ):
        return None
    public = _public_text(tag, limit=120).strip().lower()
    if not public or "[redacted" in public:
        return None
    return public


def _normalize_tags(tags: Any) -> list[str]:
    if tags is None:
        return []
    if not isinstance(tags, list):
        raise ValueError("tags must be a list")
    normalized = []
    seen = set()
    for value in tags:
        tag = _public_tag(value)
        if not tag or tag in seen:
            continue
        seen.add(tag)
        normalized.append(tag)
    return normalized


def _bool_filter(value: str | bool | None) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    lowered = str(value).strip().lower()
    if lowered in {"1", "true", "yes"}:
        return True
    if lowered in {"0", "false", "no"}:
        return False
    raise ValueError("boolean filters must be true or false")


def _latest_asset_rights(conn: sqlite3.Connection, *, project_id: str, asset_id: str) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT * FROM rights_metadata
        WHERE project_id = ? AND asset_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (project_id, asset_id),
    ).fetchone()
    if row is None:
        return {
            "rights_metadata_id": None,
            "license": "user_uploaded_unverified",
            "license_name": "User uploaded - rights unverified",
            "license_url": None,
            "license_scope": "unknown",
            "creator_approved": 0,
            "creator_approval_status": "unverified",
            "commercial_use": 0,
            "commercial_use_status": "review_required",
        }

    data = dict(row)
    rights = _parse_json(data.get("rights_json"))
    license_details = rights.get("licenseDetails") if isinstance(rights.get("licenseDetails"), dict) else {}
    return {
        "rights_metadata_id": data["id"],
        "license": str(rights.get("license") or "user_uploaded_unverified"),
        "license_name": str(license_details.get("name") or ""),
        "license_url": license_details.get("url"),
        "license_scope": str(license_details.get("scope") or "unknown"),
        "creator_approved": int(data.get("creator_approved") or 0),
        "creator_approval_status": str(data.get("creator_approval_status") or "unverified"),
        "commercial_use": int(data.get("commercial_use") or 0),
        "commercial_use_status": str(data.get("commercial_use_status") or "review_required"),
    }


def _asset_summary(conn: sqlite3.Connection, *, asset_id: str) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT id, project_id, kind, uri, content_type, byte_size, source_job_id, created_at
        FROM assets
        WHERE id = ?
        """,
        (asset_id,),
    ).fetchone()
    if row is None:
        raise NotFoundError("asset not found")
    data = dict(row)
    return {
        "id": data["id"],
        "projectId": data["project_id"],
        "kind": data["kind"],
        "contentType": data["content_type"],
        "byteSize": data["byte_size"],
        "sourceJobId": data["source_job_id"],
        "createdAt": data["created_at"],
    }


def _tags_for(conn: sqlite3.Connection, *, library_asset_id: str) -> list[str]:
    rows = conn.execute(
        "SELECT tag FROM library_asset_tags WHERE library_asset_id = ? ORDER BY tag",
        (library_asset_id,),
    ).fetchall()
    tags: list[str] = []
    seen = set()
    for row in rows:
        tag = _public_tag(row["tag"])
        if tag and tag not in seen:
            seen.add(tag)
            tags.append(tag)
    return tags


def _public_library_asset(conn: sqlite3.Connection, row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    metadata = _parse_json(data.pop("metadata_json", "{}"))
    return {
        "id": data["id"],
        "type": data["type"],
        "projectId": data["project_id"],
        "assetId": data["asset_id"],
        "title": _public_text(data["title"], limit=200),
        "description": _public_text(data["description"]),
        "tags": _tags_for(conn, library_asset_id=data["id"]),
        "license": _public_text(data["license"], limit=120),
        "licenseName": _public_text(data["license_name"], limit=200),
        "licenseUrl": _nullable_public_text(data["license_url"], limit=500),
        "licenseScope": _public_text(data["license_scope"], limit=120),
        "creatorApproved": bool(data["creator_approved"]),
        "creatorApprovalStatus": _public_text(data["creator_approval_status"], limit=80),
        "commercialUse": bool(data["commercial_use"]),
        "commercialUseStatus": _public_text(data["commercial_use_status"], limit=80),
        "rightsMetadataId": data["rights_metadata_id"],
        "metadata": _public_metadata(metadata),
        "sourceAsset": _asset_summary(conn, asset_id=data["asset_id"]),
        "aiUsage": "none",
        "createdAt": data["created_at"],
        "updatedAt": data["updated_at"],
    }


def _get_library_asset_row(conn: sqlite3.Connection, *, user_id: str, library_asset_id: str) -> dict[str, Any]:
    row = conn.execute(
        "SELECT * FROM library_assets WHERE id = ? AND owner_user_id = ?",
        (library_asset_id, user_id),
    ).fetchone()
    if row is None:
        raise NotFoundError("library asset not found")
    return dict(row)


def save_library_asset(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    project_id: str,
    asset_id: str,
    type: str,
    title: str,
    description: str = "",
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if type not in LIBRARY_ASSET_TYPES:
        raise ValueError("library asset type must be saved_asset or motion_sticker")
    if not title.strip():
        raise ValueError("title is required")
    get_project(conn, user_id=user_id, project_id=project_id)
    asset = get_asset(conn, user_id=user_id, asset_id=asset_id)
    if asset["project_id"] != project_id:
        raise NotFoundError("asset not found in project")

    now = utc_now()
    row = {
        "id": uuid.uuid4().hex,
        "owner_user_id": user_id,
        "project_id": project_id,
        "asset_id": asset_id,
        "type": type,
        "title": title.strip(),
        "description": description,
        **_latest_asset_rights(conn, project_id=project_id, asset_id=asset_id),
        "metadata_json": _dump(metadata),
        "created_at": now,
        "updated_at": now,
    }
    conn.execute(
        """
        INSERT INTO library_assets
        (id, owner_user_id, project_id, asset_id, type, title, description, rights_metadata_id,
         license, license_name, license_url, license_scope, creator_approved, creator_approval_status,
         commercial_use, commercial_use_status, metadata_json, created_at, updated_at)
        VALUES
        (:id, :owner_user_id, :project_id, :asset_id, :type, :title, :description, :rights_metadata_id,
         :license, :license_name, :license_url, :license_scope, :creator_approved, :creator_approval_status,
         :commercial_use, :commercial_use_status, :metadata_json, :created_at, :updated_at)
        """,
        row,
    )
    for tag in _normalize_tags(tags):
        conn.execute(
            "INSERT INTO library_asset_tags (library_asset_id, tag, created_at) VALUES (?, ?, ?)",
            (row["id"], tag, now),
        )
    record_audit_event(
        conn,
        user_id=user_id,
        project_id=project_id,
        asset_id=asset_id,
        event_type="library_asset_saved",
        metadata={"libraryAssetId": row["id"], "type": type, "aiUsage": "none"},
    )
    conn.commit()
    return _public_library_asset(conn, row)


def get_library_asset(conn: sqlite3.Connection, *, user_id: str, library_asset_id: str) -> dict[str, Any]:
    return _public_library_asset(conn, _get_library_asset_row(conn, user_id=user_id, library_asset_id=library_asset_id))


def list_library_assets(conn: sqlite3.Connection, *, user_id: str, filters: dict[str, Any] | None = None) -> dict[str, Any]:
    filters = filters or {}
    joins: list[str] = []
    clauses = ["la.owner_user_id = :user_id"]
    params: dict[str, Any] = {"user_id": user_id}

    if filters.get("q"):
        clauses.append(
            """
            (
              lower(la.title) LIKE :q OR
              lower(la.description) LIKE :q OR
              lower(la.license) LIKE :q OR
              EXISTS (
                SELECT 1 FROM library_asset_tags qtag
                WHERE qtag.library_asset_id = la.id AND qtag.tag LIKE :q
              )
            )
            """
        )
        params["q"] = f"%{str(filters['q']).strip().lower()}%"
    if filters.get("type"):
        clauses.append("la.type = :type")
        params["type"] = str(filters["type"])
    if filters.get("tag"):
        tag = _public_tag(filters["tag"])
        if tag is None:
            return {"assets": [], "aiUsage": "none"}
        joins.append("JOIN library_asset_tags tag_filter ON tag_filter.library_asset_id = la.id")
        clauses.append("tag_filter.tag = :tag")
        params["tag"] = tag
    if filters.get("license"):
        clauses.append("la.license = :license")
        params["license"] = str(filters["license"])
    if filters.get("licenseScope"):
        clauses.append("la.license_scope = :license_scope")
        params["license_scope"] = str(filters["licenseScope"])
    creator_approved = _bool_filter(filters.get("creatorApproved"))
    if creator_approved is not None:
        clauses.append("la.creator_approved = :creator_approved")
        params["creator_approved"] = 1 if creator_approved else 0
    commercial_use = _bool_filter(filters.get("commercialUse"))
    if commercial_use is not None:
        clauses.append("la.commercial_use = :commercial_use")
        params["commercial_use"] = 1 if commercial_use else 0
    if filters.get("commercialUseStatus"):
        clauses.append("la.commercial_use_status = :commercial_use_status")
        params["commercial_use_status"] = str(filters["commercialUseStatus"])
    if filters.get("collectionId"):
        _get_collection_row(conn, user_id=user_id, collection_id=str(filters["collectionId"]))
        joins.append("JOIN brand_collection_items bci ON bci.library_asset_id = la.id")
        clauses.append("bci.collection_id = :collection_id")
        params["collection_id"] = str(filters["collectionId"])
    if filters.get("packId"):
        _get_pack_row(conn, user_id=user_id, pack_id=str(filters["packId"]))
        joins.append("JOIN creator_pack_items cpi ON cpi.library_asset_id = la.id")
        clauses.append("cpi.pack_id = :pack_id")
        params["pack_id"] = str(filters["packId"])

    rows = conn.execute(
        f"""
        SELECT DISTINCT la.*
        FROM library_assets la
        {' '.join(joins)}
        WHERE {' AND '.join(clauses)}
        ORDER BY la.created_at DESC, la.id DESC
        """,
        params,
    ).fetchall()
    return {"assets": [_public_library_asset(conn, row) for row in rows], "aiUsage": "none"}


def _public_collection(conn: sqlite3.Connection, row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    count = conn.execute(
        "SELECT COUNT(*) FROM brand_collection_items WHERE collection_id = ?",
        (data["id"],),
    ).fetchone()[0]
    return {
        "id": data["id"],
        "projectId": data["project_id"],
        "title": _public_text(data["title"], limit=200),
        "description": _public_text(data["description"]),
        "metadata": _public_metadata(_parse_json(data.get("metadata_json"))),
        "assetCount": count,
        "aiUsage": "none",
        "createdAt": data["created_at"],
        "updatedAt": data["updated_at"],
    }


def _get_collection_row(conn: sqlite3.Connection, *, user_id: str, collection_id: str) -> dict[str, Any]:
    row = conn.execute(
        "SELECT * FROM brand_collections WHERE id = ? AND owner_user_id = ?",
        (collection_id, user_id),
    ).fetchone()
    if row is None:
        raise NotFoundError("collection not found")
    return dict(row)


def create_collection(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    title: str,
    description: str = "",
    project_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not title.strip():
        raise ValueError("title is required")
    if project_id:
        get_project(conn, user_id=user_id, project_id=project_id)
    now = utc_now()
    row = {
        "id": uuid.uuid4().hex,
        "owner_user_id": user_id,
        "project_id": project_id,
        "title": title.strip(),
        "description": description,
        "metadata_json": _dump(metadata),
        "created_at": now,
        "updated_at": now,
    }
    conn.execute(
        """
        INSERT INTO brand_collections
        (id, owner_user_id, project_id, title, description, metadata_json, created_at, updated_at)
        VALUES (:id, :owner_user_id, :project_id, :title, :description, :metadata_json, :created_at, :updated_at)
        """,
        row,
    )
    record_audit_event(
        conn,
        user_id=user_id,
        project_id=project_id,
        event_type="collection_created",
        metadata={"collectionId": row["id"], "aiUsage": "none"},
    )
    conn.commit()
    return _public_collection(conn, row)


def list_collections(conn: sqlite3.Connection, *, user_id: str) -> dict[str, Any]:
    rows = conn.execute(
        "SELECT * FROM brand_collections WHERE owner_user_id = ? ORDER BY created_at DESC, id DESC",
        (user_id,),
    ).fetchall()
    return {"collections": [_public_collection(conn, row) for row in rows], "aiUsage": "none"}


def add_asset_to_collection(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    collection_id: str,
    library_asset_id: str,
) -> dict[str, Any]:
    collection = _get_collection_row(conn, user_id=user_id, collection_id=collection_id)
    library_asset = _get_library_asset_row(conn, user_id=user_id, library_asset_id=library_asset_id)
    now = utc_now()
    conn.execute(
        """
        INSERT OR IGNORE INTO brand_collection_items (collection_id, library_asset_id, created_at)
        VALUES (?, ?, ?)
        """,
        (collection_id, library_asset_id, now),
    )
    record_audit_event(
        conn,
        user_id=user_id,
        project_id=collection.get("project_id") or library_asset["project_id"],
        asset_id=library_asset["asset_id"],
        event_type="collection_asset_added",
        metadata={"collectionId": collection_id, "libraryAssetId": library_asset_id, "aiUsage": "none"},
    )
    conn.commit()
    return {"collectionId": collection_id, "libraryAssetId": library_asset_id, "aiUsage": "none"}


def list_collection_assets(conn: sqlite3.Connection, *, user_id: str, collection_id: str) -> dict[str, Any]:
    _get_collection_row(conn, user_id=user_id, collection_id=collection_id)
    rows = conn.execute(
        """
        SELECT la.*
        FROM library_assets la
        JOIN brand_collection_items bci ON bci.library_asset_id = la.id
        WHERE bci.collection_id = ? AND la.owner_user_id = ?
        ORDER BY bci.created_at DESC, la.id DESC
        """,
        (collection_id, user_id),
    ).fetchall()
    return {"assets": [_public_library_asset(conn, row) for row in rows], "aiUsage": "none"}


def _public_pack(conn: sqlite3.Connection, row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    count = conn.execute(
        "SELECT COUNT(*) FROM creator_pack_items WHERE pack_id = ?",
        (data["id"],),
    ).fetchone()[0]
    return {
        "id": data["id"],
        "collectionId": data["collection_id"],
        "title": _public_text(data["title"], limit=200),
        "description": _public_text(data["description"]),
        "metadata": _public_metadata(_parse_json(data.get("metadata_json"))),
        "assetCount": count,
        "aiUsage": "none",
        "createdAt": data["created_at"],
        "updatedAt": data["updated_at"],
    }


def _get_pack_row(conn: sqlite3.Connection, *, user_id: str, pack_id: str) -> dict[str, Any]:
    row = conn.execute(
        "SELECT * FROM creator_packs WHERE id = ? AND owner_user_id = ?",
        (pack_id, user_id),
    ).fetchone()
    if row is None:
        raise NotFoundError("pack not found")
    return dict(row)


def create_creator_pack(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    collection_id: str,
    title: str,
    description: str = "",
    library_asset_ids: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not title.strip():
        raise ValueError("title is required")
    collection = _get_collection_row(conn, user_id=user_id, collection_id=collection_id)
    if library_asset_ids is None:
        rows = conn.execute(
            "SELECT library_asset_id FROM brand_collection_items WHERE collection_id = ? ORDER BY created_at, library_asset_id",
            (collection_id,),
        ).fetchall()
        asset_ids = [row["library_asset_id"] for row in rows]
    else:
        asset_ids = list(dict.fromkeys(str(value) for value in library_asset_ids))
    if not asset_ids:
        raise BackendError("creator-approved packs require at least one collection asset")

    collection_members = {
        row["library_asset_id"]
        for row in conn.execute(
            "SELECT library_asset_id FROM brand_collection_items WHERE collection_id = ?",
            (collection_id,),
        ).fetchall()
    }
    rows = []
    for library_asset_id in asset_ids:
        if library_asset_id not in collection_members:
            raise BackendError("creator packs can only include assets already attached to the collection")
        asset = _get_library_asset_row(conn, user_id=user_id, library_asset_id=library_asset_id)
        if not (
            asset["creator_approved"]
            and asset["creator_approval_status"] == APPROVED_STATUS
            and asset["commercial_use"]
            and asset["commercial_use_status"] == APPROVED_STATUS
        ):
            raise BackendError("creator-approved packs require approved creator and commercial-use asset rights")
        rows.append(asset)

    now = utc_now()
    pack = {
        "id": uuid.uuid4().hex,
        "owner_user_id": user_id,
        "collection_id": collection_id,
        "title": title.strip(),
        "description": description,
        "metadata_json": _dump(metadata),
        "created_at": now,
        "updated_at": now,
    }
    conn.execute(
        """
        INSERT INTO creator_packs
        (id, owner_user_id, collection_id, title, description, metadata_json, created_at, updated_at)
        VALUES (:id, :owner_user_id, :collection_id, :title, :description, :metadata_json, :created_at, :updated_at)
        """,
        pack,
    )
    for asset in rows:
        conn.execute(
            "INSERT INTO creator_pack_items (pack_id, library_asset_id, created_at) VALUES (?, ?, ?)",
            (pack["id"], asset["id"], now),
        )
    record_audit_event(
        conn,
        user_id=user_id,
        project_id=collection.get("project_id"),
        event_type="creator_pack_created",
        metadata={"packId": pack["id"], "collectionId": collection_id, "assetCount": len(rows), "aiUsage": "none"},
    )
    conn.commit()
    return _public_pack(conn, pack)


def list_creator_packs(conn: sqlite3.Connection, *, user_id: str) -> dict[str, Any]:
    rows = conn.execute(
        "SELECT * FROM creator_packs WHERE owner_user_id = ? ORDER BY created_at DESC, id DESC",
        (user_id,),
    ).fetchall()
    return {"packs": [_public_pack(conn, row) for row in rows], "aiUsage": "none"}
