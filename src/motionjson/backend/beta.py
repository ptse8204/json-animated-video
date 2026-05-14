from __future__ import annotations

import hashlib
import json
import re
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from .models import ForbiddenError, NotFoundError
from .usage import build_usage_cost_dashboard, list_usage_events, utc_now

BETA_ROLES = {"member", "admin"}
DASHBOARD_REDACTED_KEYS = {
    "apiKey",
    "api_key",
    "authorization",
    "dataBase64",
    "key_hash",
    "password",
    "secret",
    "signingSecret",
    "storageKey",
    "storage_key",
    "token",
    "token_hash",
    "webhookSecret",
}
DASHBOARD_API_KEY_PATTERN = re.compile(r"\b(?:mj_local_|mjb_|sk-|or-)[A-Za-z0-9._~+/=-]{12,}\b")
DASHBOARD_BEARER_PATTERN = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
DASHBOARD_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(api[_-]?key|authorization|data[_-]?base64|password|secret|storage[_-]?key|token)=([^\s&]+)"
)


def _normalized_key(key: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(key).lower())


def _is_dashboard_secret_key(key: Any) -> bool:
    normalized = _normalized_key(key)
    sensitive_names = {
        "apikey",
        "authorization",
        "database64",
        "keyhash",
        "password",
        "secret",
        "signingsecret",
        "storagekey",
        "token",
        "tokenhash",
        "webhooksecret",
    }
    return normalized in sensitive_names or any(part in normalized for part in ("apikey", "database64", "keyhash", "password", "secret", "storagekey", "token"))


def _normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if "@" not in normalized:
        raise ValueError("email must contain @")
    return normalized


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _new_invite_token() -> str:
    return f"mjb_{secrets.token_urlsafe(32)}"


def _public_invite(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    data.pop("token_hash", None)
    return data


def _public_member(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    return dict(row)


def _dashboard_safe(value: Any) -> Any:
    if isinstance(value, dict):
        safe: dict[str, Any] = {}
        redacted = False
        for key, item in value.items():
            key_text = str(key)
            if key_text in DASHBOARD_REDACTED_KEYS or _is_dashboard_secret_key(key_text):
                redacted = True
                continue
            safe[key_text] = _dashboard_safe(item)
        if redacted:
            safe["redacted"] = True
        return safe
    if isinstance(value, list):
        return [_dashboard_safe(item) for item in value]
    if isinstance(value, str):
        text = DASHBOARD_BEARER_PATTERN.sub("Bearer [REDACTED]", value)
        text = DASHBOARD_API_KEY_PATTERN.sub("[REDACTED]", text)
        text = DASHBOARD_ASSIGNMENT_PATTERN.sub("[REDACTED]", text)
        if len(text) > 1_000:
            return f"{text[:1_000]}...[truncated]"
        return text
    return value


def require_beta_admin(conn: sqlite3.Connection, *, user_id: str) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT * FROM beta_members
        WHERE user_id = ? AND role = 'admin' AND disabled_at IS NULL
        """,
        (user_id,),
    ).fetchone()
    if row is None:
        raise ForbiddenError("beta admin role is required")
    return _public_member(row)


def bootstrap_beta_admin(conn: sqlite3.Connection, *, user_id: str) -> dict[str, Any]:
    active_admins = conn.execute(
        "SELECT COUNT(*) FROM beta_members WHERE role = 'admin' AND disabled_at IS NULL"
    ).fetchone()[0]
    if active_admins:
        return require_beta_admin(conn, user_id=user_id)
    return create_beta_member(conn, user_id=user_id, role="admin")


def get_beta_status(conn: sqlite3.Connection, *, user_id: str) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT * FROM beta_members
        WHERE user_id = ? AND disabled_at IS NULL
        """,
        (user_id,),
    ).fetchone()
    if row is None:
        return {"member": False, "role": None}
    return {"member": True, "role": row["role"], "memberId": row["id"], "createdAt": row["created_at"]}


def create_beta_member(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    role: str = "member",
    invite_id: str | None = None,
) -> dict[str, Any]:
    if role not in BETA_ROLES:
        raise ValueError("beta role must be member or admin")
    user = conn.execute("SELECT id, email FROM users WHERE id = ? AND disabled_at IS NULL", (user_id,)).fetchone()
    if user is None:
        raise NotFoundError("user not found")
    now = utc_now()
    existing = conn.execute("SELECT * FROM beta_members WHERE user_id = ?", (user_id,)).fetchone()
    if existing is not None:
        conn.execute(
            """
            UPDATE beta_members
            SET role = ?, email = ?, invite_id = COALESCE(?, invite_id), disabled_at = NULL
            WHERE user_id = ?
            """,
            (role, user["email"], invite_id, user_id),
        )
        conn.commit()
        return _public_member(conn.execute("SELECT * FROM beta_members WHERE user_id = ?", (user_id,)).fetchone())
    member = {
        "id": uuid.uuid4().hex,
        "user_id": user_id,
        "email": user["email"],
        "role": role,
        "invite_id": invite_id,
        "created_at": now,
        "disabled_at": None,
    }
    conn.execute(
        """
        INSERT INTO beta_members (id, user_id, email, role, invite_id, created_at, disabled_at)
        VALUES (:id, :user_id, :email, :role, :invite_id, :created_at, :disabled_at)
        """,
        member,
    )
    conn.commit()
    return member


def create_beta_invite(
    conn: sqlite3.Connection,
    *,
    admin_user_id: str,
    email: str,
    role: str = "member",
    ttl_seconds: int = 7 * 24 * 60 * 60,
) -> dict[str, Any]:
    require_beta_admin(conn, user_id=admin_user_id)
    if role not in BETA_ROLES:
        raise ValueError("beta role must be member or admin")
    if ttl_seconds <= 0:
        raise ValueError("invite ttl must be positive")
    raw_token = _new_invite_token()
    now = datetime.now(timezone.utc)
    invite = {
        "id": uuid.uuid4().hex,
        "email": _normalize_email(email),
        "role": role,
        "token_hash": _hash_token(raw_token),
        "invited_by_user_id": admin_user_id,
        "accepted_by_user_id": None,
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=ttl_seconds)).isoformat(),
        "accepted_at": None,
        "revoked_at": None,
    }
    conn.execute(
        """
        INSERT INTO beta_invites
        (id, email, role, token_hash, invited_by_user_id, accepted_by_user_id, created_at, expires_at, accepted_at, revoked_at)
        VALUES (:id, :email, :role, :token_hash, :invited_by_user_id, :accepted_by_user_id, :created_at, :expires_at, :accepted_at, :revoked_at)
        """,
        invite,
    )
    conn.commit()
    public = _public_invite(invite)
    public["inviteToken"] = raw_token
    return public


def list_beta_invites(conn: sqlite3.Connection, *, admin_user_id: str, include_revoked: bool = False) -> list[dict[str, Any]]:
    require_beta_admin(conn, user_id=admin_user_id)
    revoked_clause = "" if include_revoked else "WHERE revoked_at IS NULL"
    rows = conn.execute(f"SELECT * FROM beta_invites {revoked_clause} ORDER BY created_at DESC, id").fetchall()
    return [_public_invite(row) for row in rows]


def list_beta_members(conn: sqlite3.Connection, *, admin_user_id: str, include_disabled: bool = False) -> list[dict[str, Any]]:
    require_beta_admin(conn, user_id=admin_user_id)
    disabled_clause = "" if include_disabled else "WHERE disabled_at IS NULL"
    rows = conn.execute(f"SELECT * FROM beta_members {disabled_clause} ORDER BY created_at DESC, id").fetchall()
    return [_public_member(row) for row in rows]


def revoke_beta_invite(conn: sqlite3.Connection, *, admin_user_id: str, invite_id: str) -> bool:
    require_beta_admin(conn, user_id=admin_user_id)
    result = conn.execute(
        """
        UPDATE beta_invites
        SET revoked_at = ?
        WHERE id = ? AND accepted_at IS NULL AND revoked_at IS NULL
        """,
        (utc_now(), invite_id),
    )
    conn.commit()
    return result.rowcount > 0


def accept_beta_invite(conn: sqlite3.Connection, *, user_id: str, token: str) -> dict[str, Any]:
    token_hash = _hash_token(token.strip())
    row = conn.execute("SELECT * FROM beta_invites WHERE token_hash = ?", (token_hash,)).fetchone()
    if row is None or row["accepted_at"] or row["revoked_at"]:
        raise ForbiddenError("invite is invalid or no longer available")
    expires_at = datetime.fromisoformat(row["expires_at"])
    if expires_at <= datetime.now(timezone.utc):
        raise ForbiddenError("invite has expired")
    user = conn.execute("SELECT id, email FROM users WHERE id = ? AND disabled_at IS NULL", (user_id,)).fetchone()
    if user is None:
        raise NotFoundError("user not found")
    if _normalize_email(user["email"]) != row["email"]:
        raise ForbiddenError("invite email does not match the authenticated user")
    now = utc_now()
    result = conn.execute(
        """
        UPDATE beta_invites
        SET accepted_at = ?, accepted_by_user_id = ?
        WHERE id = ? AND accepted_at IS NULL AND revoked_at IS NULL
        """,
        (now, user_id, row["id"]),
    )
    if result.rowcount == 0:
        raise ForbiddenError("invite is invalid or no longer available")
    member = create_beta_member(conn, user_id=user_id, role=row["role"], invite_id=row["id"])
    return {"invite": _public_invite(conn.execute("SELECT * FROM beta_invites WHERE id = ?", (row["id"],)).fetchone()), "member": member}


def build_admin_dashboard(conn: sqlite3.Connection, *, admin_user_id: str) -> dict[str, Any]:
    require_beta_admin(conn, user_id=admin_user_id)
    now = datetime.now(timezone.utc)
    invites = [_public_invite(row) for row in conn.execute("SELECT * FROM beta_invites ORDER BY created_at DESC, id LIMIT 25").fetchall()]
    members = [_public_member(row) for row in conn.execute("SELECT * FROM beta_members WHERE disabled_at IS NULL ORDER BY created_at DESC, id LIMIT 25").fetchall()]
    all_invites = conn.execute("SELECT * FROM beta_invites").fetchall()
    invite_counts = {"total": len(all_invites), "open": 0, "accepted": 0, "revoked": 0, "expired": 0}
    for invite in all_invites:
        if invite["accepted_at"]:
            invite_counts["accepted"] += 1
        elif invite["revoked_at"]:
            invite_counts["revoked"] += 1
        elif datetime.fromisoformat(invite["expires_at"]) <= now:
            invite_counts["expired"] += 1
        else:
            invite_counts["open"] += 1
    status_rows = conn.execute("SELECT status, COUNT(*) AS count FROM jobs GROUP BY status").fetchall()
    failures = [_dashboard_safe(dict(row)) for row in conn.execute("SELECT id, project_id, type, status, error, updated_at FROM jobs WHERE status = 'failed' ORDER BY updated_at DESC LIMIT 10").fetchall()]
    events = []
    for row in conn.execute(
        """
        SELECT job_events.id, job_events.job_id, job_events.event_type, job_events.message, job_events.metadata_json, job_events.created_at
        FROM job_events
        ORDER BY job_events.created_at DESC, job_events.id
        LIMIT 20
        """
    ).fetchall():
        event = dict(row)
        event["message"] = _dashboard_safe(event.get("message"))
        event["metadata"] = _dashboard_safe(json.loads(event.pop("metadata_json") or "{}"))
        events.append(event)
    usage_events = list_usage_events(conn)
    return {
        "schema": "motionjson.admin_dashboard.v0.1",
        "beta": {
            "invites": {**invite_counts, "recent": invites},
            "members": {
                "total": conn.execute("SELECT COUNT(*) FROM beta_members WHERE disabled_at IS NULL").fetchone()[0],
                "admins": conn.execute("SELECT COUNT(*) FROM beta_members WHERE role = 'admin' AND disabled_at IS NULL").fetchone()[0],
                "recent": members,
            },
        },
        "jobs": {
            "byStatus": {row["status"]: row["count"] for row in status_rows},
            "recentFailures": failures,
            "recentEvents": events,
        },
        "usage": {
            "eventCount": len(usage_events),
            "costDashboard": build_usage_cost_dashboard(usage_events),
        },
        "support": {
            "unresolvedFeedback": conn.execute("SELECT COUNT(*) FROM feedback_items WHERE status != 'resolved'").fetchone()[0],
            "unresolvedErrorReports": conn.execute("SELECT COUNT(*) FROM error_reports WHERE status != 'resolved'").fetchone()[0],
        },
    }
