from __future__ import annotations

import hashlib
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

from .models import SessionResult, UnauthorizedError
from .usage import utc_now

PBKDF2_ITERATIONS = 210_000


def _normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if "@" not in normalized:
        raise ValueError("email must contain @")
    return normalized


def _hash_password(password: str, salt_hex: str) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), PBKDF2_ITERATIONS)
    return digest.hex()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def register_user(conn: sqlite3.Connection, *, email: str, password: str) -> dict:
    if not password:
        raise ValueError("password is required")
    salt = secrets.token_bytes(16).hex()
    now = utc_now()
    user = {
        "id": uuid.uuid4().hex,
        "email": _normalize_email(email),
        "password_hash": _hash_password(password, salt),
        "password_salt": salt,
        "created_at": now,
        "disabled_at": None,
    }
    conn.execute(
        """
        INSERT INTO users (id, email, password_hash, password_salt, created_at, disabled_at)
        VALUES (:id, :email, :password_hash, :password_salt, :created_at, :disabled_at)
        """,
        user,
    )
    conn.commit()
    return user


def authenticate_user(conn: sqlite3.Connection, *, email: str, password: str) -> dict:
    row = conn.execute("SELECT * FROM users WHERE email = ?", (_normalize_email(email),)).fetchone()
    if row is None or row["disabled_at"]:
        raise UnauthorizedError("invalid email or password")
    expected = _hash_password(password, row["password_salt"])
    if not secrets.compare_digest(expected, row["password_hash"]):
        raise UnauthorizedError("invalid email or password")
    return dict(row)


def create_session(conn: sqlite3.Connection, *, user_id: str, ttl_seconds: int = 86_400) -> SessionResult:
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    session = {
        "id": uuid.uuid4().hex,
        "user_id": user_id,
        "token_hash": _hash_token(token),
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=ttl_seconds)).isoformat(),
        "revoked_at": None,
    }
    conn.execute(
        """
        INSERT INTO sessions (id, user_id, token_hash, created_at, expires_at, revoked_at)
        VALUES (:id, :user_id, :token_hash, :created_at, :expires_at, :revoked_at)
        """,
        session,
    )
    conn.commit()
    return SessionResult(token=token, session=session)


def require_session(conn: sqlite3.Connection, token: str) -> dict:
    token_hash = _hash_token(token)
    row = conn.execute(
        """
        SELECT sessions.*, users.email, users.disabled_at AS user_disabled_at
        FROM sessions
        JOIN users ON users.id = sessions.user_id
        WHERE sessions.token_hash = ?
        """,
        (token_hash,),
    ).fetchone()
    if row is None or row["revoked_at"] or row["user_disabled_at"]:
        raise UnauthorizedError("invalid session")
    expires_at = datetime.fromisoformat(row["expires_at"])
    if expires_at <= datetime.now(timezone.utc):
        raise UnauthorizedError("session expired")
    return dict(row)


def revoke_session(conn: sqlite3.Connection, token: str) -> bool:
    result = conn.execute(
        "UPDATE sessions SET revoked_at = ? WHERE token_hash = ? AND revoked_at IS NULL",
        (utc_now(), _hash_token(token)),
    )
    conn.commit()
    return result.rowcount > 0
