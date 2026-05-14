from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

from motionjson.providers.local_storage import LocalStorageProvider

from .api import serve
from .api_keys import create_api_key, list_api_keys, revoke_api_key
from .assets import get_asset, register_upload
from .auth import authenticate_user, create_session, register_user, require_session
from .beta import (
    accept_beta_invite,
    bootstrap_beta_admin,
    build_admin_dashboard,
    create_beta_invite,
    get_beta_status,
    list_beta_invites,
    list_beta_members,
    revoke_beta_invite,
)
from .db import connect, initialize_database
from .jobs import enqueue_export_job, enqueue_extract_job, get_job
from .projects import create_project, get_project
from .rights import list_asset_lineage, list_asset_rights
from .support import create_error_report, create_feedback_item, list_error_reports, list_feedback_items
from .usage import summarize_usage
from .worker import worker_once


def _default_db() -> str:
    return os.environ.get("MOTIONJSON_BACKEND_DB", ".motionjson/backend.sqlite")


def _default_storage_root() -> str:
    return os.environ.get("MOTIONJSON_STORAGE_ROOT", ".motionjson/storage")


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--db", default=_default_db(), help="SQLite database path")
    p.add_argument("--storage-root", default=_default_storage_root(), help="Local storage root")


def _add_rights_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument("--rights-source-type", default=None)
    p.add_argument("--rights-source-uri", default=None)
    p.add_argument("--rights-source-asset-id", default=None)
    p.add_argument("--rights-display-text", default=None)
    p.add_argument("--license", default=None)
    p.add_argument("--license-name", default=None)
    p.add_argument("--license-url", default=None)
    p.add_argument("--license-scope", default=None)
    p.add_argument("--creator-approved", action="store_true", default=None)
    p.add_argument("--creator-approval-status", default=None)
    p.add_argument("--commercial-use", action="store_true", default=None)
    p.add_argument("--commercial-use-status", default=None)


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
    _add_rights_flags(upload)

    extract = sub.add_parser("enqueue-extract", help="Queue deterministic local extraction")
    _add_common(extract)
    extract.add_argument("--session-token-env", default="MOTIONJSON_SESSION_TOKEN")
    extract.add_argument("--project-id", required=True)
    extract.add_argument("--asset-id", required=True)
    extract.add_argument("--mask-provider", default="threshold")
    extract.add_argument("--max-frames", type=int, default=None)
    extract.add_argument("--sample-fps", type=float, default=12.0)
    _add_rights_flags(extract)

    export = sub.add_parser("enqueue-export", help="Queue cached-asset website export")
    _add_common(export)
    export.add_argument("--session-token-env", default="MOTIONJSON_SESSION_TOKEN")
    export.add_argument("--project-id", required=True)
    export.add_argument("--source-job-id", required=True)
    export.add_argument("--format", required=True, choices=["website-zip"])

    worker = sub.add_parser("worker", help="Run backend worker")
    _add_common(worker)
    worker.add_argument("--once", action="store_true")

    server = sub.add_parser("serve-api", help="Serve the dependency-light local REST API")
    _add_common(server)
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=8765)

    api_key_create = sub.add_parser("create-api-key", help="Create a local API key and print the raw key once")
    _add_common(api_key_create)
    api_key_create.add_argument("--session-token-env", default="MOTIONJSON_SESSION_TOKEN")
    api_key_create.add_argument("--name", default="Local API key")
    api_key_create.add_argument("--scope", action="append", default=[])

    api_key_list = sub.add_parser("list-api-keys", help="List local API keys without raw key material")
    _add_common(api_key_list)
    api_key_list.add_argument("--session-token-env", default="MOTIONJSON_SESSION_TOKEN")
    api_key_list.add_argument("--include-revoked", action="store_true")

    api_key_revoke = sub.add_parser("revoke-api-key", help="Revoke a local API key by id")
    _add_common(api_key_revoke)
    api_key_revoke.add_argument("--session-token-env", default="MOTIONJSON_SESSION_TOKEN")
    api_key_revoke.add_argument("api_key_id")

    status = sub.add_parser("job-status", help="Print job status by id")
    _add_common(status)
    status.add_argument("--session-token-env", default="MOTIONJSON_SESSION_TOKEN")
    status.add_argument("job_id")

    usage = sub.add_parser("usage", help="Print usage events and totals")
    _add_common(usage)
    usage.add_argument("--session-token-env", default="MOTIONJSON_SESSION_TOKEN")
    usage.add_argument("--project-id", required=True)

    asset_rights = sub.add_parser("asset-rights", help="Print local rights and lineage rows for an asset")
    _add_common(asset_rights)
    asset_rights.add_argument("--session-token-env", default="MOTIONJSON_SESSION_TOKEN")
    asset_rights.add_argument("asset_id")

    beta_bootstrap = sub.add_parser("bootstrap-beta-admin", help="Grant the session user the local beta admin role")
    _add_common(beta_bootstrap)
    beta_bootstrap.add_argument("--session-token-env", default="MOTIONJSON_SESSION_TOKEN")

    beta_status = sub.add_parser("beta-status", help="Print beta membership status for the session user")
    _add_common(beta_status)
    beta_status.add_argument("--session-token-env", default="MOTIONJSON_SESSION_TOKEN")

    invite = sub.add_parser("create-beta-invite", help="Create a one-time closed beta invite as a beta admin")
    _add_common(invite)
    invite.add_argument("--session-token-env", default="MOTIONJSON_SESSION_TOKEN")
    invite.add_argument("--email", required=True)
    invite.add_argument("--role", choices=["member", "admin"], default="member")
    invite.add_argument("--ttl-seconds", type=int, default=7 * 24 * 60 * 60)

    accept_invite = sub.add_parser("accept-beta-invite", help="Accept a closed beta invite for the session user")
    _add_common(accept_invite)
    accept_invite.add_argument("--session-token-env", default="MOTIONJSON_SESSION_TOKEN")
    accept_invite.add_argument("--invite-token", required=True)

    invites = sub.add_parser("list-beta-invites", help="List closed beta invites as a beta admin")
    _add_common(invites)
    invites.add_argument("--session-token-env", default="MOTIONJSON_SESSION_TOKEN")
    invites.add_argument("--include-revoked", action="store_true")

    revoke_invite = sub.add_parser("revoke-beta-invite", help="Revoke an unused beta invite as a beta admin")
    _add_common(revoke_invite)
    revoke_invite.add_argument("--session-token-env", default="MOTIONJSON_SESSION_TOKEN")
    revoke_invite.add_argument("invite_id")

    members = sub.add_parser("list-beta-members", help="List beta members as a beta admin")
    _add_common(members)
    members.add_argument("--session-token-env", default="MOTIONJSON_SESSION_TOKEN")
    members.add_argument("--include-disabled", action="store_true")

    feedback = sub.add_parser("feedback", help="Create or list redacted feedback")
    _add_common(feedback)
    feedback.add_argument("--session-token-env", default="MOTIONJSON_SESSION_TOKEN")
    feedback.add_argument("--admin-list", action="store_true")
    feedback.add_argument("--include-resolved", action="store_true")
    feedback.add_argument("--project-id", default=None)
    feedback.add_argument("--type", default="general")
    feedback.add_argument("--severity", default="normal")
    feedback.add_argument("--subject", default="")
    feedback.add_argument("--message", default="")
    feedback.add_argument("--context-json", default="{}")

    error_report = sub.add_parser("error-report", help="Create or list redacted error reports")
    _add_common(error_report)
    error_report.add_argument("--session-token-env", default="MOTIONJSON_SESSION_TOKEN")
    error_report.add_argument("--admin-list", action="store_true")
    error_report.add_argument("--include-resolved", action="store_true")
    error_report.add_argument("--project-id", default=None)
    error_report.add_argument("--job-id", default=None)
    error_report.add_argument("--severity", default="error")
    error_report.add_argument("--message", default="")
    error_report.add_argument("--stack-trace", default="")
    error_report.add_argument("--context-json", default="{}")

    dashboard = sub.add_parser("admin-dashboard", help="Print beta admin dashboard without raw secrets")
    _add_common(dashboard)
    dashboard.add_argument("--session-token-env", default="MOTIONJSON_SESSION_TOKEN")


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


def _json_object(raw: str) -> dict[str, Any]:
    parsed = json.loads(raw or "{}")
    if not isinstance(parsed, dict):
        raise SystemExit("expected JSON object")
    return parsed


def _rights_context(args: argparse.Namespace) -> dict[str, Any]:
    creator_status = args.creator_approval_status
    if creator_status is None and args.creator_approved is True:
        creator_status = "approved"
    commercial_status = args.commercial_use_status
    if commercial_status is None and args.commercial_use is True and args.creator_approved is True:
        commercial_status = "approved"
    context = {
        "source_type": args.rights_source_type,
        "source_asset_id": args.rights_source_asset_id,
        "source_uri": args.rights_source_uri,
        "display_text": args.rights_display_text,
        "license": args.license,
        "license_name": args.license_name,
        "license_url": args.license_url,
        "license_scope": args.license_scope,
        "creator_approved": args.creator_approved,
        "creator_approval_status": creator_status,
        "commercial_use": args.commercial_use,
        "commercial_use_status": commercial_status,
    }
    return {key: value for key, value in context.items() if value is not None}


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
        metadata = {"rights_context": {**_rights_context(args), "source_uri": args.rights_source_uri or args.path}}
        _print_json(register_upload(conn, storage=storage, user_id=session["user_id"], project_id=args.project_id, path=args.path, kind=args.kind, metadata=metadata))
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
                rights_context=_rights_context(args),
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
    if args.backend_command == "serve-api":
        conn.close()
        serve(db_path=args.db, storage_root=args.storage_root, host=args.host, port=args.port)
        return
    if args.backend_command == "create-api-key":
        session = _session(conn, args.session_token_env)
        _print_json(create_api_key(conn, user_id=session["user_id"], name=args.name, scopes=args.scope or None))
        return
    if args.backend_command == "list-api-keys":
        session = _session(conn, args.session_token_env)
        _print_json({"apiKeys": list_api_keys(conn, user_id=session["user_id"], include_revoked=args.include_revoked)})
        return
    if args.backend_command == "revoke-api-key":
        session = _session(conn, args.session_token_env)
        _print_json({"revoked": revoke_api_key(conn, user_id=session["user_id"], key_id=args.api_key_id)})
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
    if args.backend_command == "asset-rights":
        session = _session(conn, args.session_token_env)
        asset = get_asset(conn, user_id=session["user_id"], asset_id=args.asset_id)
        _print_json(
            {
                "asset": asset,
                "rights": list_asset_rights(conn, asset_id=args.asset_id),
                "lineage": list_asset_lineage(conn, asset_id=args.asset_id),
            }
        )
        return
    if args.backend_command == "bootstrap-beta-admin":
        session = _session(conn, args.session_token_env)
        _print_json(bootstrap_beta_admin(conn, user_id=session["user_id"]))
        return
    if args.backend_command == "beta-status":
        session = _session(conn, args.session_token_env)
        _print_json(get_beta_status(conn, user_id=session["user_id"]))
        return
    if args.backend_command == "create-beta-invite":
        session = _session(conn, args.session_token_env)
        _print_json(create_beta_invite(conn, admin_user_id=session["user_id"], email=args.email, role=args.role, ttl_seconds=args.ttl_seconds))
        return
    if args.backend_command == "accept-beta-invite":
        session = _session(conn, args.session_token_env)
        _print_json(accept_beta_invite(conn, user_id=session["user_id"], token=args.invite_token))
        return
    if args.backend_command == "list-beta-invites":
        session = _session(conn, args.session_token_env)
        _print_json({"invites": list_beta_invites(conn, admin_user_id=session["user_id"], include_revoked=args.include_revoked)})
        return
    if args.backend_command == "revoke-beta-invite":
        session = _session(conn, args.session_token_env)
        _print_json({"revoked": revoke_beta_invite(conn, admin_user_id=session["user_id"], invite_id=args.invite_id)})
        return
    if args.backend_command == "list-beta-members":
        session = _session(conn, args.session_token_env)
        _print_json({"members": list_beta_members(conn, admin_user_id=session["user_id"], include_disabled=args.include_disabled)})
        return
    if args.backend_command == "feedback":
        session = _session(conn, args.session_token_env)
        if args.admin_list:
            _print_json({"feedback": list_feedback_items(conn, admin_user_id=session["user_id"], include_resolved=args.include_resolved)})
        else:
            _print_json(
                create_feedback_item(
                    conn,
                    user_id=session["user_id"],
                    project_id=args.project_id,
                    type=args.type,
                    severity=args.severity,
                    subject=args.subject,
                    message=args.message,
                    context=_json_object(args.context_json),
                )
            )
        return
    if args.backend_command == "error-report":
        session = _session(conn, args.session_token_env)
        if args.admin_list:
            _print_json({"errorReports": list_error_reports(conn, admin_user_id=session["user_id"], include_resolved=args.include_resolved)})
        else:
            _print_json(
                create_error_report(
                    conn,
                    user_id=session["user_id"],
                    project_id=args.project_id,
                    job_id=args.job_id,
                    severity=args.severity,
                    message=args.message,
                    stack_trace=args.stack_trace,
                    context=_json_object(args.context_json),
                )
            )
        return
    if args.backend_command == "admin-dashboard":
        session = _session(conn, args.session_token_env)
        _print_json(build_admin_dashboard(conn, admin_user_id=session["user_id"]))
        return
    raise SystemExit(f"unknown backend command: {args.backend_command}")
