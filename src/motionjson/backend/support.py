from __future__ import annotations

import json
import re
import sqlite3
import uuid
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from .beta import require_beta_admin
from .jobs import get_job
from .projects import get_project
from .usage import utc_now

SECRET_KEYS = {
    "authorization",
    "api_key",
    "apikey",
    "apiKey",
    "bearer",
    "dataBase64",
    "fileBytes",
    "password",
    "secret",
    "signingSecret",
    "storage_key",
    "token",
    "webhookSecret",
}
API_KEY_PATTERN = re.compile(r"\b(?:mj_local_|mjb_|sk-|or-)[A-Za-z0-9._~+/=-]{12,}\b")
BEARER_PATTERN = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(api[_-]?key|authorization|data[_-]?base64|password|secret|storage[_-]?key|token)=([^\s&]+)"
)
URL_PATTERN = re.compile(r"https?://[^\s)\"']+")
MAX_TEXT_LENGTH = 2_000
MAX_STACK_LENGTH = 4_000
MAX_CONTEXT_ITEMS = 50


def _normalized_key(key: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(key).lower())


def _is_secret_key(key: Any) -> bool:
    normalized = _normalized_key(key)
    sensitive_names = {
        "apikey",
        "authorization",
        "bearer",
        "database64",
        "filebytes",
        "keyhash",
        "password",
        "secret",
        "signingsecret",
        "storagekey",
        "token",
        "webhooksecret",
    }
    return normalized in sensitive_names or any(part in normalized for part in ("apikey", "database64", "keyhash", "password", "secret", "storagekey", "token"))


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return f"{value[:limit]}...[truncated]"


def _redact_url(match: re.Match[str]) -> str:
    try:
        parts = urlsplit(match.group(0))
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    except ValueError:
        return "[REDACTED_URL]"


def redact_text(value: Any, *, limit: int = MAX_TEXT_LENGTH) -> str:
    text = str(value or "")
    text = BEARER_PATTERN.sub("Bearer [REDACTED]", text)
    text = API_KEY_PATTERN.sub("[REDACTED_API_KEY]", text)
    text = SECRET_ASSIGNMENT_PATTERN.sub(lambda match: f"{match.group(1)}=[REDACTED]", text)
    text = URL_PATTERN.sub(_redact_url, text)
    return _truncate(text, limit)


def redact_context(value: Any, *, depth: int = 0) -> Any:
    if depth > 4:
        return "[REDACTED_DEPTH]"
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= MAX_CONTEXT_ITEMS:
                redacted["__truncated__"] = True
                break
            if str(key) in SECRET_KEYS or _is_secret_key(key):
                redacted[str(key)] = "[REDACTED]"
            else:
                redacted[str(key)] = redact_context(item, depth=depth + 1)
        return redacted
    if isinstance(value, list):
        items = value[:MAX_CONTEXT_ITEMS]
        result = [redact_context(item, depth=depth + 1) for item in items]
        if len(value) > MAX_CONTEXT_ITEMS:
            result.append("[TRUNCATED]")
        return result
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return redact_text(value)


def _public_feedback(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    data["context"] = json.loads(data.pop("context_json") or "{}")
    return data


def _public_error_report(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    data["context"] = json.loads(data.pop("context_json") or "{}")
    return data


def create_feedback_item(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    project_id: str | None = None,
    type: str = "general",
    severity: str = "normal",
    subject: str = "",
    message: str = "",
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if project_id:
        get_project(conn, user_id=user_id, project_id=project_id)
    now = utc_now()
    row = {
        "id": uuid.uuid4().hex,
        "user_id": user_id,
        "project_id": project_id,
        "type": redact_text(type, limit=80) or "general",
        "severity": redact_text(severity, limit=40) or "normal",
        "subject": redact_text(subject, limit=200) or "Untitled feedback",
        "message": redact_text(message),
        "context_json": json.dumps(redact_context(context or {}), sort_keys=True),
        "status": "open",
        "created_at": now,
        "resolved_at": None,
    }
    conn.execute(
        """
        INSERT INTO feedback_items
        (id, user_id, project_id, type, severity, subject, message, context_json, status, created_at, resolved_at)
        VALUES (:id, :user_id, :project_id, :type, :severity, :subject, :message, :context_json, :status, :created_at, :resolved_at)
        """,
        row,
    )
    conn.commit()
    return _public_feedback(row)


def create_error_report(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    project_id: str | None = None,
    job_id: str | None = None,
    severity: str = "error",
    message: str = "",
    stack_trace: str = "",
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if project_id:
        get_project(conn, user_id=user_id, project_id=project_id)
    if job_id:
        job = get_job(conn, user_id=user_id, job_id=job_id)
        if project_id and job["project_id"] != project_id:
            raise ValueError("job does not belong to project")
        if project_id is None:
            project_id = job["project_id"]
    now = utc_now()
    row = {
        "id": uuid.uuid4().hex,
        "user_id": user_id,
        "project_id": project_id,
        "job_id": job_id,
        "severity": redact_text(severity, limit=40) or "error",
        "message": redact_text(message),
        "stack_trace": redact_text(stack_trace, limit=MAX_STACK_LENGTH),
        "context_json": json.dumps(redact_context(context or {}), sort_keys=True),
        "status": "open",
        "created_at": now,
        "resolved_at": None,
    }
    conn.execute(
        """
        INSERT INTO error_reports
        (id, user_id, project_id, job_id, severity, message, stack_trace, context_json, status, created_at, resolved_at)
        VALUES (:id, :user_id, :project_id, :job_id, :severity, :message, :stack_trace, :context_json, :status, :created_at, :resolved_at)
        """,
        row,
    )
    conn.commit()
    return _public_error_report(row)


def list_feedback_items(conn: sqlite3.Connection, *, admin_user_id: str, include_resolved: bool = False) -> list[dict[str, Any]]:
    require_beta_admin(conn, user_id=admin_user_id)
    status_clause = "" if include_resolved else "WHERE status != 'resolved'"
    rows = conn.execute(f"SELECT * FROM feedback_items {status_clause} ORDER BY created_at DESC, id").fetchall()
    return [_public_feedback(row) for row in rows]


def list_error_reports(conn: sqlite3.Connection, *, admin_user_id: str, include_resolved: bool = False) -> list[dict[str, Any]]:
    require_beta_admin(conn, user_id=admin_user_id)
    status_clause = "" if include_resolved else "WHERE status != 'resolved'"
    rows = conn.execute(f"SELECT * FROM error_reports {status_clause} ORDER BY created_at DESC, id").fetchall()
    return [_public_error_report(row) for row in rows]
