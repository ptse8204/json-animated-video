from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

from motionjson.providers.local_storage import LocalStorageProvider

from .assets import register_upload
from .auth import authenticate_user, create_session, register_user, require_session
from .db import connect, initialize_database
from .jobs import enqueue_export_job, enqueue_extract_job, get_job
from .projects import create_project, get_project
from .usage import summarize_usage
from .worker import worker_once


def _default_db() -> str:
    return os.environ.get("MOTIONJSON_BACKEND_DB", ".motionjson/backend.sqlite")


def _default_storage_root() -> str:
    return os.environ.get("MOTIONJSON_STORAGE_ROOT", ".motionjson/storage")


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--db", default=_default_db(), help="SQLite database path")
    p.add_argument("--storage-root", default=_default_storage_root(), help="Local storage root")


def add_backend_parser(parser: argparse.ArgumentParser) -> None:
    sub = parser.add_subparsers(dest="backend_command")

    init = sub.add_parser("init", help="Initialize backend SQLite schema and storage root")
    _add_common(init)

    create_user = sub.add_parser("create-user", help="Create a local backend user")
    _add_common(create_user)
    create_user.add_argument("--email", required=True)
    create_user.add_argument("--password-stdin", action="store_true", required=True)

    login = sub.add_parser("login", help="Authenticate and create a session token")
    _add_common(login)
    login.add_argument("--email", required=True)
    login.add_argument("--password-stdin", action="store_true", required=True)

    project = sub.add_parser("create-project", help="Create a project for the session user")
    _add_common(project)
    project.add_argument("--session-token-env", required=True)
    project.add_argument("--name", required=True)
    project.add_argument("--description", default="")

    upload = sub.add_parser("upload-asset", help="Upload a project asset through StorageProvider")
    _add_common(upload)
    upload.add_argument("--session-token-env", default="MOTIONJSON_SESSION_TOKEN")
    upload.add_argument("--project-id", required=True)
    upload.add_argument("--path", required=True)
    upload.add_argument("--kind", required=True, choices=["source_video", "mask_sequence", "reference", "other"])

    extract = sub.add_parser("enqueue-extract", help="Queue deterministic local extraction")
    _add_common(extract)
    extract.add_argument("--session-token-env", default="MOTIONJSON_SESSION_TOKEN")
    extract.add_argument("--project-id", required=True)
    extract.add_argument("--asset-id", required=True)
    extract.add_argument("--mask-provider", default="threshold")
    extract.add_argument("--max-frames", type=int, default=None)
    extract.add_argument("--sample-fps", type=float, default=12.0)

    export = sub.add_parser("enqueue-export", help="Queue cached-asset website export")
    _add_common(export)
    export.add_argument("--session-token-env", default="MOTIONJSON_SESSION_TOKEN")
    export.add_argument("--project-id", required=True)
    export.add_argument("--source-job-id", required=True)
    export.add_argument("--format", required=True, choices=["website-zip"])

    worker = sub.add_parser("worker", help="Run backend worker")
    _add_common(worker)
    worker.add_argument("--once", action="store_true")

    status = sub.add_parser("job-status", help="Print job status by id")
    _add_common(status)
    status.add_argument("--session-token-env", default="MOTIONJSON_SESSION_TOKEN")
    status.add_argument("job_id")

    usage = sub.add_parser("usage", help="Print usage events and totals")
    _add_common(usage)
    usage.add_argument("--session-token-env", default="MOTIONJSON_SESSION_TOKEN")
    usage.add_argument("--project-id", required=True)


def _open(args: argparse.Namespace) -> tuple[sqlite3.Connection, LocalStorageProvider]:
    conn = initialize_database(connect(args.db))
    storage = LocalStorageProvider(args.storage_root)
    return conn, storage


def _password_from_stdin(args: argparse.Namespace) -> str:
    if not args.password_stdin:
        raise SystemExit("--password-stdin is required")
    return sys.stdin.read().rstrip("\n")


def _session(conn: sqlite3.Connection, env_name: str) -> dict[str, Any]:
    token = os.environ.get(env_name)
    if not token:
        raise SystemExit(f"{env_name} is not set")
    return require_session(conn, token)


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def run_backend_command(args: argparse.Namespace) -> None:
    if args.backend_command is None:
        raise SystemExit("backend command is required")
    conn, storage = _open(args)
    if args.backend_command == "init":
        Path(args.storage_root).mkdir(parents=True, exist_ok=True)
        _print_json({"db": str(args.db), "storageRoot": str(args.storage_root), "status": "ready"})
        return
    if args.backend_command == "create-user":
        user = register_user(conn, email=args.email, password=_password_from_stdin(args))
        _print_json({"id": user["id"], "email": user["email"]})
        return
    if args.backend_command == "login":
        user = authenticate_user(conn, email=args.email, password=_password_from_stdin(args))
        session = create_session(conn, user_id=user["id"])
        _print_json({"sessionToken": session.token, "expiresAt": session.session["expires_at"]})
        return
    if args.backend_command == "create-project":
        session = _session(conn, args.session_token_env)
        _print_json(create_project(conn, user_id=session["user_id"], name=args.name, description=args.description))
        return
    if args.backend_command == "upload-asset":
        session = _session(conn, args.session_token_env)
        _print_json(register_upload(conn, storage=storage, user_id=session["user_id"], project_id=args.project_id, path=args.path, kind=args.kind))
        return
    if args.backend_command == "enqueue-extract":
        session = _session(conn, args.session_token_env)
        _print_json(
            enqueue_extract_job(
                conn,
                user_id=session["user_id"],
                project_id=args.project_id,
                asset_id=args.asset_id,
                mask_provider=args.mask_provider,
                max_frames=args.max_frames,
                sample_fps=args.sample_fps,
            )
        )
        return
    if args.backend_command == "enqueue-export":
        session = _session(conn, args.session_token_env)
        _print_json(enqueue_export_job(conn, user_id=session["user_id"], project_id=args.project_id, source_job_id=args.source_job_id, format=args.format))
        return
    if args.backend_command == "worker":
        if not args.once:
            raise SystemExit("only --once is supported by the local backend worker")
        _print_json(worker_once(conn, storage=storage) or {"status": "idle"})
        return
    if args.backend_command == "job-status":
        session = _session(conn, args.session_token_env)
        _print_json(get_job(conn, user_id=session["user_id"], job_id=args.job_id))
        return
    if args.backend_command == "usage":
        session = _session(conn, args.session_token_env)
        get_project(conn, user_id=session["user_id"], project_id=args.project_id)
        _print_json(summarize_usage(conn, project_id=args.project_id))
        return
    raise SystemExit(f"unknown backend command: {args.backend_command}")
