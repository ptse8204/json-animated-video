from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
import uuid
from typing import Any, Protocol
from urllib.parse import urlparse

from .models import NotFoundError
from .usage import utc_now


class WebhookTransport(Protocol):
    def post(self, url: str, *, headers: dict[str, str], body: bytes) -> dict[str, Any]:
        ...


class RecordingWebhookTransport:
    """Deterministic no-network transport used by default and in tests."""

    def post(self, url: str, *, headers: dict[str, str], body: bytes) -> dict[str, Any]:
        return {"status": "recorded", "status_code": 202, "response_body": "recorded locally; no network call made"}


def _dump(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _loads_list(value: str) -> list[str]:
    parsed = json.loads(value or "[]")
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def _public_webhook(row: sqlite3.Row | dict[str, Any], *, include_secret: bool = False) -> dict[str, Any]:
    data = dict(row)
    events = data.pop("event_types_json", "[]")
    secret = data.pop("secret", None)
    data["eventTypes"] = _loads_list(events)
    if include_secret:
        data["signingSecret"] = secret
    return data


def create_webhook(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    url: str,
    event_types: list[str] | None = None,
    description: str = "",
) -> dict[str, Any]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("webhook url must be http or https")
    events = event_types or ["job.succeeded", "job.failed"]
    now = utc_now()
    row = {
        "id": uuid.uuid4().hex,
        "user_id": user_id,
        "url": url,
        "description": description,
        "event_types_json": json.dumps(events, sort_keys=True),
        "secret": f"whsec_{secrets.token_urlsafe(32)}",
        "created_at": now,
        "disabled_at": None,
    }
    conn.execute(
        """
        INSERT INTO webhook_endpoints
        (id, user_id, url, description, event_types_json, secret, created_at, disabled_at)
        VALUES (:id, :user_id, :url, :description, :event_types_json, :secret, :created_at, :disabled_at)
        """,
        row,
    )
    conn.commit()
    return _public_webhook(row, include_secret=True)


def list_webhooks(conn: sqlite3.Connection, *, user_id: str, include_disabled: bool = False) -> list[dict[str, Any]]:
    disabled_clause = "" if include_disabled else "AND disabled_at IS NULL"
    rows = conn.execute(
        f"""
        SELECT * FROM webhook_endpoints
        WHERE user_id = ? {disabled_clause}
        ORDER BY created_at DESC, id
        """,
        (user_id,),
    ).fetchall()
    return [_public_webhook(row) for row in rows]


def disable_webhook(conn: sqlite3.Connection, *, user_id: str, webhook_id: str) -> bool:
    result = conn.execute(
        """
        UPDATE webhook_endpoints
        SET disabled_at = ?
        WHERE id = ? AND user_id = ? AND disabled_at IS NULL
        """,
        (utc_now(), webhook_id, user_id),
    )
    conn.commit()
    return result.rowcount > 0


def sign_webhook_payload(secret: str, payload_body: bytes, *, timestamp: str) -> str:
    signed = f"{timestamp}.".encode("utf-8") + payload_body
    digest = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


def verify_webhook_signature(secret: str, payload_body: bytes, signature: str, *, tolerance_seconds: int | None = None) -> bool:
    del tolerance_seconds
    parts = dict(part.split("=", 1) for part in signature.split(",") if "=" in part)
    timestamp = parts.get("t")
    expected = parts.get("v1")
    if not timestamp or not expected:
        return False
    actual = sign_webhook_payload(secret, payload_body, timestamp=timestamp).split("v1=", 1)[1]
    return hmac.compare_digest(actual, expected)


def record_delivery(
    conn: sqlite3.Connection,
    *,
    webhook_id: str,
    user_id: str,
    event_type: str,
    payload: dict[str, Any],
    signature: str,
    status: str,
    status_code: int | None = None,
    response_body: str | None = None,
) -> dict[str, Any]:
    row = {
        "id": uuid.uuid4().hex,
        "webhook_id": webhook_id,
        "user_id": user_id,
        "event_type": event_type,
        "payload_json": _dump(payload),
        "signature": signature,
        "status": status,
        "status_code": status_code,
        "response_body": response_body,
        "created_at": utc_now(),
    }
    conn.execute(
        """
        INSERT INTO webhook_deliveries
        (id, webhook_id, user_id, event_type, payload_json, signature, status, status_code, response_body, created_at)
        VALUES (:id, :webhook_id, :user_id, :event_type, :payload_json, :signature, :status, :status_code, :response_body, :created_at)
        """,
        row,
    )
    conn.commit()
    return row


def deliver_event(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    event_type: str,
    payload: dict[str, Any],
    transport: WebhookTransport | None = None,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM webhook_endpoints
        WHERE user_id = ? AND disabled_at IS NULL
        ORDER BY created_at, id
        """,
        (user_id,),
    ).fetchall()
    transport = transport or RecordingWebhookTransport()
    deliveries: list[dict[str, Any]] = []
    body = _dump({"type": event_type, "data": payload}).encode("utf-8")
    timestamp = utc_now()
    for row in rows:
        event_types = set(_loads_list(row["event_types_json"]))
        if "*" not in event_types and event_type not in event_types:
            continue
        signature = sign_webhook_payload(row["secret"], body, timestamp=timestamp)
        headers = {
            "content-type": "application/json",
            "user-agent": "MotionJSON-Webhooks/0.1",
            "motionjson-signature": signature,
        }
        try:
            response = transport.post(row["url"], headers=headers, body=body)
            status = str(response.get("status") or "delivered")
            status_code = response.get("status_code")
            response_body = response.get("response_body")
        except Exception as exc:
            status = "failed"
            status_code = None
            response_body = str(exc)
        deliveries.append(
            record_delivery(
                conn,
                webhook_id=row["id"],
                user_id=user_id,
                event_type=event_type,
                payload={"type": event_type, "data": payload},
                signature=signature,
                status=status,
                status_code=int(status_code) if status_code is not None else None,
                response_body=str(response_body) if response_body is not None else None,
            )
        )
    return deliveries


def list_webhook_deliveries(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    webhook_id: str | None = None,
) -> list[dict[str, Any]]:
    params: list[str] = [user_id]
    clause = "WHERE user_id = ?"
    if webhook_id:
        exists = conn.execute("SELECT 1 FROM webhook_endpoints WHERE id = ? AND user_id = ?", (webhook_id, user_id)).fetchone()
        if exists is None:
            raise NotFoundError("webhook not found")
        clause += " AND webhook_id = ?"
        params.append(webhook_id)
    rows = conn.execute(
        f"SELECT * FROM webhook_deliveries {clause} ORDER BY created_at DESC, id",
        params,
    ).fetchall()
    return [dict(row) for row in rows]
