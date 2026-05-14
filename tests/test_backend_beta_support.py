from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from motionjson.backend.api import MotionJSONAPI
from motionjson.backend.api_keys import create_api_key
from motionjson.backend.auth import create_session, register_user
from motionjson.backend.beta import accept_beta_invite, bootstrap_beta_admin, create_beta_invite, create_beta_member, list_beta_invites, revoke_beta_invite
from motionjson.backend.db import initialize_database
from motionjson.backend.models import ForbiddenError
from motionjson.backend.projects import create_project
from motionjson.backend.support import create_error_report, create_feedback_item
from motionjson.cli import main


def backend(tmp_path):
    conn = sqlite3.connect(tmp_path / "backend.sqlite")
    conn.row_factory = sqlite3.Row
    initialize_database(conn)
    admin = register_user(conn, email="admin@example.com", password="pw")
    member = register_user(conn, email="member@example.com", password="pw")
    create_beta_member(conn, user_id=admin["id"], role="admin")
    project = create_project(conn, user_id=member["id"], name="Beta Project")
    return conn, admin, member, project


def test_beta_invites_are_hashed_one_time_expirable_and_admin_only(tmp_path):
    conn, admin, member, _project = backend(tmp_path)
    invite = create_beta_invite(conn, admin_user_id=admin["id"], email=member["email"], ttl_seconds=60)
    stored = conn.execute("SELECT * FROM beta_invites WHERE id = ?", (invite["id"],)).fetchone()

    assert invite["inviteToken"].startswith("mjb_")
    assert stored["token_hash"] != invite["inviteToken"]
    assert invite["inviteToken"] not in dict(stored).values()
    assert "token_hash" not in list_beta_invites(conn, admin_user_id=admin["id"])[0]

    accepted = accept_beta_invite(conn, user_id=member["id"], token=invite["inviteToken"])
    assert accepted["member"]["role"] == "member"
    assert "inviteToken" not in accepted["invite"]
    with pytest.raises(ForbiddenError):
        accept_beta_invite(conn, user_id=member["id"], token=invite["inviteToken"])
    with pytest.raises(ForbiddenError):
        create_beta_invite(conn, admin_user_id=member["id"], email="other@example.com")

    revoked = create_beta_invite(conn, admin_user_id=admin["id"], email=member["email"], ttl_seconds=60)
    assert revoke_beta_invite(conn, admin_user_id=admin["id"], invite_id=revoked["id"])
    with pytest.raises(ForbiddenError):
        accept_beta_invite(conn, user_id=member["id"], token=revoked["inviteToken"])

    expired = create_beta_invite(conn, admin_user_id=admin["id"], email=member["email"], ttl_seconds=60)
    conn.execute(
        "UPDATE beta_invites SET expires_at = ? WHERE id = ?",
        ((datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(), expired["id"]),
    )
    conn.commit()
    with pytest.raises(ForbiddenError):
        accept_beta_invite(conn, user_id=member["id"], token=expired["inviteToken"])


def test_beta_admin_bootstrap_only_seeds_first_admin(tmp_path):
    conn = sqlite3.connect(tmp_path / "backend.sqlite")
    conn.row_factory = sqlite3.Row
    initialize_database(conn)
    first = register_user(conn, email="first@example.com", password="pw")
    second = register_user(conn, email="second@example.com", password="pw")

    seeded = bootstrap_beta_admin(conn, user_id=first["id"])

    assert seeded["role"] == "admin"
    assert bootstrap_beta_admin(conn, user_id=first["id"])["role"] == "admin"
    with pytest.raises(ForbiddenError):
        bootstrap_beta_admin(conn, user_id=second["id"])


def test_feedback_error_reports_and_dashboard_are_redacted_and_admin_scoped(tmp_path):
    conn, admin, member, project = backend(tmp_path)
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO jobs
        (id, project_id, created_by_user_id, type, status, payload_json, result_json, error, attempts, created_at, updated_at, started_at, finished_at)
        VALUES ('failed_job', ?, ?, 'render', 'failed', '{}', '{}', 'storageKey=projects/private.mov storage-key=projects/other.mov', 1, ?, ?, NULL, NULL)
        """,
        (project["id"], member["id"], now, now),
    )
    conn.execute(
        """
        INSERT INTO job_events (id, job_id, event_type, message, metadata_json, created_at)
        VALUES ('event_with_secret', 'failed_job', 'failed', 'failed', ?, ?)
        """,
        (json.dumps({"storage-key": "projects/private.mov", "storageKey": "projects/private2.mov", "data-base64": "AAAA", "ok": True}), now),
    )
    conn.execute(
        """
        INSERT INTO job_events (id, job_id, event_type, message, metadata_json, created_at)
        VALUES ('event_message_secret', 'failed_job', 'failed', 'storageKey=projects/event.mov storage-key=projects/event2.mov dataBase64=EVENT_PAYLOAD Authorization=Bearer secret-token', '{}', ?)
        """,
        (now,),
    )
    conn.commit()
    feedback = create_feedback_item(
        conn,
        user_id=member["id"],
        project_id=project["id"],
        subject="Need help",
        message="Bearer secret-token with storage_key=projects/private.mov storageKey=projects/private2.mov at https://example.test/path?token=abc",
        context={
            "apiKey": "mj_local_supersecretvalue",
            "storageKey": "projects/private.mov",
            "storage-key": "projects/private2.mov",
            "data-base64": "AAAA",
            "nested": {"url": "https://example.test/private?x=1"},
        },
    )
    report = create_error_report(
        conn,
        user_id=member["id"],
        job_id="failed_job",
        message="Failed with api_key=secret storage-key=projects/private.mov",
        stack_trace="Traceback\nFile app.py\nAuthorization=Bearer secret-token\nstorageKey=projects/private2.mov",
        context={"storageKey": "projects/p1/uploads/private.mov", "storage-key": "projects/p1/uploads/private2.mov", "dataBase64": "AAAA", "ok": "visible"},
    )
    assert "secret-token" not in json.dumps(feedback)
    assert "api_key=secret" not in json.dumps(report)
    assert "projects/private" not in json.dumps(feedback)
    assert "projects/private" not in json.dumps(report)
    assert "AAAA" not in json.dumps(feedback)
    assert "AAAA" not in json.dumps(report)
    assert report["project_id"] == project["id"]
    assert feedback["context"]["apiKey"] == "[REDACTED]"
    assert feedback["context"]["storageKey"] == "[REDACTED]"
    assert feedback["context"]["storage-key"] == "[REDACTED]"
    assert feedback["context"]["data-base64"] == "[REDACTED]"
    assert report["context"]["storageKey"] == "[REDACTED]"
    assert report["context"]["storage-key"] == "[REDACTED]"
    assert report["context"]["dataBase64"] == "[REDACTED]"

    admin_key = create_api_key(conn, user_id=admin["id"], name="admin")["apiKey"]
    member_key = create_api_key(conn, user_id=member["id"], name="member")["apiKey"]
    conn.close()
    api = MotionJSONAPI(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage")

    status, _headers, body = api.handle("GET", "/v1/admin/dashboard", {"authorization": f"Bearer {admin_key}"}, b"")
    assert status == 200
    dashboard = json.loads(body)
    assert dashboard["support"]["unresolvedFeedback"] == 1
    assert dashboard["support"]["unresolvedErrorReports"] == 1
    assert "token_hash" not in json.dumps(dashboard)
    assert "storage_key" not in json.dumps(dashboard)
    assert "projects/private" not in json.dumps(dashboard)
    assert "projects/event" not in json.dumps(dashboard)
    assert "AAAA" not in json.dumps(dashboard)
    assert "EVENT_PAYLOAD" not in json.dumps(dashboard)
    assert "secret-token" not in json.dumps(dashboard)

    status, _headers, body = api.handle("GET", "/v1/admin/feedback", {"authorization": f"Bearer {admin_key}"}, b"")
    assert status == 200
    assert "projects/private" not in body.decode("utf-8")
    assert "AAAA" not in body.decode("utf-8")
    status, _headers, body = api.handle("GET", "/v1/admin/error-reports", {"authorization": f"Bearer {admin_key}"}, b"")
    assert status == 200
    assert "projects/private" not in body.decode("utf-8")
    assert "AAAA" not in body.decode("utf-8")

    status, _headers, body = api.handle("GET", "/v1/admin/dashboard", {"authorization": f"Bearer {member_key}"}, b"")
    assert status == 403


def test_phase17_api_and_cli_closed_beta_flow(tmp_path, monkeypatch, capsys):
    db_path = tmp_path / "backend.sqlite"
    storage_root = tmp_path / "storage"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    initialize_database(conn)
    admin = register_user(conn, email="cli-admin@example.com", password="pw")
    member = register_user(conn, email="cli-member@example.com", password="pw")
    admin_session = create_session(conn, user_id=admin["id"])
    member_session = create_session(conn, user_id=member["id"])
    conn.close()

    common = ["--db", str(db_path), "--storage-root", str(storage_root), "--session-token-env", "MJ_TEST_TOKEN"]
    monkeypatch.setenv("MJ_TEST_TOKEN", admin_session.token)
    main(["backend", "bootstrap-beta-admin", *common])
    capsys.readouterr()
    main(["backend", "create-beta-invite", *common, "--email", member["email"]])
    invite = json.loads(capsys.readouterr().out)
    assert invite["inviteToken"].startswith("mjb_")

    monkeypatch.setenv("MJ_TEST_TOKEN", member_session.token)
    main(["backend", "accept-beta-invite", *common, "--invite-token", invite["inviteToken"]])
    main(["backend", "beta-status", *common])
    assert '"member": true' in capsys.readouterr().out
