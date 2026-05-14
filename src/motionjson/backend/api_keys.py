from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import uuid
from typing import Any

from .models import UnauthorizedError
from .usage import utc_now


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def _new_raw_key() -> str:
    return f"mj_local_{secrets.token_urlsafe(32)}"


def create_api_key(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    name: str,
    scopes: list[str] | None = None,
) -> dict[str, Any]:
    raw_key = _new_raw_key()
    prefix = raw_key[:16]
    now = utc_now()
    row = {
        "id": uuid.uuid4().hex,
        "user_id": user_id,
        "name": name.strip() or "Local API key",
        "key_prefix": prefix,
        "key_hash": _hash_key(raw_key),
        "scopes_json": json.dumps(scopes or ["api:read", "api:write"], sort_keys=True),
        "created_at": now,
        "last_used_at": None,
        "revoked_at": None,
    }
    conn.execute(
        """
        INSERT INTO api_keys
        (id, user_id, name, key_prefix, key_hash, scopes_json, created_at, last_used_at, revoked_at)
        VALUES (:id, :user_id, :name, :key_prefix, :key_hash, :scopes_json, :created_at, :last_used_at, :revoked_at)
        """,
        row,
    )
    conn.commit()
    public = _public_key_row(row)
    public["apiKey"] = raw_key
    return public


def _public_key_row(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    data.pop("key_hash", None)
    scopes = data.pop("scopes_json", "[]")
    data["scopes"] = json.loads(scopes or "[]")
    return data


def list_api_keys(conn: sqlite3.Connection, *, user_id: str, include_revoked: bool = False) -> list[dict[str, Any]]:
    revoked_clause = "" if include_revoked else "AND revoked_at IS NULL"
    rows = conn.execute(
        f"""
        SELECT * FROM api_keys
        WHERE user_id = ? {revoked_clause}
        ORDER BY created_at DESC, id
        """,
        (user_id,),
    ).fetchall()
    return [_public_key_row(row) for row in rows]


def revoke_api_key(conn: sqlite3.Connection, *, user_id: str, key_id: str) -> bool:
    result = conn.execute(
        """
        UPDATE api_keys
        SET revoked_at = ?
        WHERE id = ? AND user_id = ? AND revoked_at IS NULL
        """,
        (utc_now(), key_id, user_id),
    )
    conn.commit()
    return result.rowcount > 0


def require_api_key(conn: sqlite3.Connection, raw_key: str) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT api_keys.*, users.email, users.disabled_at AS user_disabled_at
        FROM api_keys
        JOIN users ON users.id = api_keys.user_id
        WHERE api_keys.key_hash = ?
        """,
        (_hash_key(raw_key),),
    ).fetchone()
    if row is None or row["revoked_at"] or row["user_disabled_at"]:
        raise UnauthorizedError("invalid api key")
    conn.execute("UPDATE api_keys SET last_used_at = ? WHERE id = ?", (utc_now(), row["id"]))
    conn.commit()
    result = _public_key_row(row)
    result["user_id"] = row["user_id"]
    return result
