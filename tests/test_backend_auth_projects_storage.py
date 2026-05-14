from __future__ import annotations

import sqlite3

import pytest

from motionjson.backend.assets import get_asset, register_upload
from motionjson.backend.auth import authenticate_user, create_session, register_user, require_session, revoke_session
from motionjson.backend.db import initialize_database
from motionjson.backend.jobs import enqueue_extract_job
from motionjson.backend.models import NotFoundError, UnauthorizedError
from motionjson.backend.projects import create_project
from motionjson.backend.usage import summarize_usage
from motionjson.cli import main
from motionjson.providers.local_storage import LocalStorageProvider


def backend(tmp_path):
    conn = sqlite3.connect(tmp_path / "backend.sqlite")
    conn.row_factory = sqlite3.Row
    initialize_database(conn)
    storage = LocalStorageProvider(tmp_path / "storage")
    return conn, storage


def test_auth_hashes_passwords_and_session_tokens_and_revokes(tmp_path):
    conn, _storage = backend(tmp_path)

    user = register_user(conn, email="User@Example.com", password="correct horse")
    assert user["email"] == "user@example.com"
    assert user["password_hash"] != "correct horse"
    assert "correct horse" not in user["password_hash"]

    authenticated = authenticate_user(conn, email="user@example.com", password="correct horse")
    session = create_session(conn, user_id=authenticated["id"])
    stored_session = conn.execute("SELECT * FROM sessions WHERE id = ?", (session.session["id"],)).fetchone()

    assert stored_session["token_hash"] != session.token
    assert session.token not in dict(stored_session).values()
    assert require_session(conn, session.token)["user_id"] == user["id"]
    assert revoke_session(conn, session.token)
    with pytest.raises(UnauthorizedError):
        require_session(conn, session.token)


def test_project_ownership_prevents_cross_user_asset_and_job_access(tmp_path):
    conn, storage = backend(tmp_path)
    owner = register_user(conn, email="owner@example.com", password="pw")
    other = register_user(conn, email="other@example.com", password="pw")
    project = create_project(conn, user_id=owner["id"], name="Owner Project")
    source = tmp_path / "source.mp4"
    source.write_bytes(b"not a real video")
    asset = register_upload(conn, storage=storage, user_id=owner["id"], project_id=project["id"], path=source, kind="source_video")

    with pytest.raises(NotFoundError):
        get_asset(conn, user_id=other["id"], asset_id=asset["id"])
    with pytest.raises(NotFoundError):
        enqueue_extract_job(conn, user_id=other["id"], project_id=project["id"], asset_id=asset["id"])


def test_local_storage_saves_loads_and_rejects_unsafe_keys(tmp_path):
    storage = LocalStorageProvider(tmp_path / "storage")
    uri = storage.save_bytes("projects/p1/uploads/source.bin", b"abc", content_type="application/octet-stream")

    assert uri.startswith("file:")
    assert storage.exists("projects/p1/uploads/source.bin")
    assert storage.load_bytes("projects/p1/uploads/source.bin") == b"abc"
    for key in ("../escape", "/absolute/path", "projects/p1/../../escape", "bad key"):
        with pytest.raises(ValueError):
            storage.save_bytes(key, b"x")


def test_asset_upload_records_upload_and_byte_usage(tmp_path):
    conn, storage = backend(tmp_path)
    user = register_user(conn, email="usage@example.com", password="pw")
    project = create_project(conn, user_id=user["id"], name="Usage")
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"abcdef")

    asset = register_upload(conn, storage=storage, user_id=user["id"], project_id=project["id"], path=source, kind="source_video")
    usage = summarize_usage(conn, project_id=project["id"])

    assert asset["byte_size"] == 6
    assert usage["totals"]["uploads"]["asset"] == 1.0
    assert usage["totals"]["bytes_stored"]["byte"] == 6.0


def test_backend_cli_job_status_and_usage_are_session_scoped(tmp_path, monkeypatch, capsys):
    db_path = tmp_path / "backend.sqlite"
    storage_root = tmp_path / "storage"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    initialize_database(conn)
    storage = LocalStorageProvider(storage_root)
    owner = register_user(conn, email="cli-owner@example.com", password="pw")
    other = register_user(conn, email="cli-other@example.com", password="pw")
    project = create_project(conn, user_id=owner["id"], name="CLI Project")
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"video")
    asset = register_upload(conn, storage=storage, user_id=owner["id"], project_id=project["id"], path=source, kind="source_video")
    job = enqueue_extract_job(conn, user_id=owner["id"], project_id=project["id"], asset_id=asset["id"], max_frames=1)
    owner_session = create_session(conn, user_id=owner["id"])
    other_session = create_session(conn, user_id=other["id"])
    conn.close()

    common = ["--db", str(db_path), "--storage-root", str(storage_root), "--session-token-env", "MJ_TEST_TOKEN"]
    monkeypatch.setenv("MJ_TEST_TOKEN", owner_session.token)
    main(["backend", "job-status", *common, job["id"]])
    assert job["id"] in capsys.readouterr().out
    main(["backend", "usage", *common, "--project-id", project["id"]])
    assert "bytes_stored" in capsys.readouterr().out

    monkeypatch.setenv("MJ_TEST_TOKEN", other_session.token)
    with pytest.raises(NotFoundError):
        main(["backend", "job-status", *common, job["id"]])
    with pytest.raises(NotFoundError):
        main(["backend", "usage", *common, "--project-id", project["id"]])
