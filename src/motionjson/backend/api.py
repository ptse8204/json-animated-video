from __future__ import annotations

import base64
import binascii
import json
import sqlite3
import tempfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from motionjson.providers.local_storage import LocalStorageProvider

from .api_keys import require_api_key
from .assets import get_asset, list_assets_for_job, list_project_assets, load_asset_bytes, register_upload
from .beta import (
    accept_beta_invite,
    build_admin_dashboard,
    create_beta_invite,
    get_beta_status,
    list_beta_invites,
    list_beta_members,
    revoke_beta_invite,
)
from .billing import get_billing_status, list_plan_catalog
from .db import connect, initialize_database
from .jobs import enqueue_asset_package_job, enqueue_extract_job, enqueue_render_job, get_job, list_job_events, list_jobs
from .library import (
    add_asset_to_collection,
    create_collection,
    create_creator_pack,
    get_library_asset,
    list_collection_assets,
    list_collections,
    list_creator_packs,
    list_library_assets,
    save_library_asset,
)
from .models import BackendError, ForbiddenError, NotFoundError, ProviderPolicyError, UnauthorizedError
from .projects import create_project, get_project, list_projects
from .queue import request_cancel_job
from .support import create_error_report, create_feedback_item, list_error_reports, list_feedback_items
from .webhooks import create_webhook, disable_webhook, list_webhook_deliveries, list_webhooks

ALLOWED_UPLOAD_KINDS = {"source_video", "mask_sequence", "reference", "other"}


def _json_loads(data: bytes) -> dict[str, Any]:
    if not data:
        return {}
    parsed = json.loads(data.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("request body must be a JSON object")
    return parsed


def _parse_json_field(row: dict[str, Any], field: str) -> None:
    if field in row:
        row[field.removesuffix("_json")] = json.loads(row.pop(field) or "{}")


def _public_asset(row: dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    data.pop("storage_key", None)
    _parse_json_field(data, "metadata_json")
    return data


def _public_job(row: dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    _parse_json_field(data, "payload_json")
    _parse_json_field(data, "result_json")
    return data


def _public_event(row: dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    _parse_json_field(data, "metadata_json")
    return data


class MotionJSONAPI:
    def __init__(self, *, db_path: str | Path, storage_root: str | Path):
        self.db_path = Path(db_path)
        self.storage_root = Path(storage_root)

    def connection(self) -> sqlite3.Connection:
        return initialize_database(connect(self.db_path))

    def storage(self) -> LocalStorageProvider:
        return LocalStorageProvider(self.storage_root)

    def handle(self, method: str, raw_path: str, headers: dict[str, str], body: bytes) -> tuple[int, dict[str, str], bytes]:
        parsed = urlparse(raw_path)
        path = parsed.path.rstrip("/") or "/"
        parts = [part for part in path.split("/") if part]
        query = parse_qs(parsed.query)
        conn = self.connection()
        try:
            user_id = self._require_bearer(conn, headers)["user_id"]
            payload = _json_loads(body) if method in {"POST", "PATCH", "PUT", "DELETE"} else {}
            result = self._route(conn, user_id=user_id, method=method, parts=parts, query=query, payload=payload)
            if isinstance(result, tuple):
                status, content_type, data = result
                return status, {"content-type": content_type}, data
            return HTTPStatus.OK, {"content-type": "application/json"}, json.dumps(result, sort_keys=True).encode("utf-8")
        except json.JSONDecodeError as exc:
            return self._error(HTTPStatus.BAD_REQUEST, f"invalid json: {exc}")
        except (ValueError, binascii.Error, ProviderPolicyError) as exc:
            return self._error(HTTPStatus.BAD_REQUEST, str(exc))
        except UnauthorizedError as exc:
            return self._error(HTTPStatus.UNAUTHORIZED, str(exc))
        except ForbiddenError as exc:
            return self._error(HTTPStatus.FORBIDDEN, str(exc))
        except NotFoundError as exc:
            return self._error(HTTPStatus.NOT_FOUND, str(exc))
        except BackendError as exc:
            return self._error(HTTPStatus.BAD_REQUEST, str(exc))
        finally:
            conn.close()

    def _require_bearer(self, conn: sqlite3.Connection, headers: dict[str, str]) -> dict[str, Any]:
        authorization = headers.get("authorization") or headers.get("Authorization") or ""
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise UnauthorizedError("bearer api key is required")
        return require_api_key(conn, token.strip())

    def _route(
        self,
        conn: sqlite3.Connection,
        *,
        user_id: str,
        method: str,
        parts: list[str],
        query: dict[str, list[str]],
        payload: dict[str, Any],
    ) -> Any:
        if parts[:1] != ["v1"]:
            raise NotFoundError("route not found")

        if parts == ["v1", "billing", "plans"] and method == "GET":
            return list_plan_catalog()
        if parts == ["v1", "billing", "status"] and method == "GET":
            return get_billing_status(user_id=user_id)

        if parts == ["v1", "beta", "status"] and method == "GET":
            return get_beta_status(conn, user_id=user_id)
        if parts == ["v1", "beta", "accept"] and method == "POST":
            return accept_beta_invite(conn, user_id=user_id, token=str(payload["inviteToken"]))

        if parts == ["v1", "feedback"] and method == "POST":
            status = HTTPStatus.CREATED
            created = create_feedback_item(
                conn,
                user_id=user_id,
                project_id=payload.get("projectId"),
                type=str(payload.get("type") or "general"),
                severity=str(payload.get("severity") or "normal"),
                subject=str(payload.get("subject") or ""),
                message=str(payload.get("message") or ""),
                context=payload.get("context") if isinstance(payload.get("context"), dict) else {},
            )
            return status, "application/json", json.dumps(created, sort_keys=True).encode("utf-8")
        if parts == ["v1", "error-reports"] and method == "POST":
            status = HTTPStatus.CREATED
            created = create_error_report(
                conn,
                user_id=user_id,
                project_id=payload.get("projectId"),
                job_id=payload.get("jobId"),
                severity=str(payload.get("severity") or "error"),
                message=str(payload.get("message") or ""),
                stack_trace=str(payload.get("stackTrace") or payload.get("stack_trace") or ""),
                context=payload.get("context") if isinstance(payload.get("context"), dict) else {},
            )
            return status, "application/json", json.dumps(created, sort_keys=True).encode("utf-8")

        if parts == ["v1", "admin", "dashboard"] and method == "GET":
            return build_admin_dashboard(conn, admin_user_id=user_id)
        if parts == ["v1", "admin", "beta", "invites"] and method == "GET":
            return {"invites": list_beta_invites(conn, admin_user_id=user_id, include_revoked=query.get("includeRevoked", ["false"])[0] == "true")}
        if parts == ["v1", "admin", "beta", "invites"] and method == "POST":
            status = HTTPStatus.CREATED
            created = create_beta_invite(
                conn,
                admin_user_id=user_id,
                email=str(payload["email"]),
                role=str(payload.get("role") or "member"),
                ttl_seconds=int(payload.get("ttlSeconds") or 7 * 24 * 60 * 60),
            )
            return status, "application/json", json.dumps(created, sort_keys=True).encode("utf-8")
        if len(parts) == 5 and parts[:4] == ["v1", "admin", "beta", "invites"] and method == "DELETE":
            return {"revoked": revoke_beta_invite(conn, admin_user_id=user_id, invite_id=parts[4])}
        if parts == ["v1", "admin", "beta", "members"] and method == "GET":
            return {"members": list_beta_members(conn, admin_user_id=user_id, include_disabled=query.get("includeDisabled", ["false"])[0] == "true")}
        if parts == ["v1", "admin", "feedback"] and method == "GET":
            return {"feedback": list_feedback_items(conn, admin_user_id=user_id, include_resolved=query.get("includeResolved", ["false"])[0] == "true")}
        if parts == ["v1", "admin", "error-reports"] and method == "GET":
            return {"errorReports": list_error_reports(conn, admin_user_id=user_id, include_resolved=query.get("includeResolved", ["false"])[0] == "true")}

        if parts == ["v1", "projects"] and method == "GET":
            return {"projects": list_projects(conn, user_id=user_id)}
        if parts == ["v1", "projects"] and method == "POST":
            status = HTTPStatus.CREATED
            project = create_project(conn, user_id=user_id, name=str(payload.get("name") or ""), description=str(payload.get("description") or ""))
            return status, "application/json", json.dumps(project, sort_keys=True).encode("utf-8")
        if len(parts) == 3 and parts[:2] == ["v1", "projects"] and method == "GET":
            return get_project(conn, user_id=user_id, project_id=parts[2])

        if len(parts) == 4 and parts[:2] == ["v1", "projects"] and parts[3] == "library-assets" and method == "POST":
            created = save_library_asset(
                conn,
                user_id=user_id,
                project_id=parts[2],
                asset_id=str(payload["assetId"]),
                type=str(payload.get("type") or "saved_asset"),
                title=str(payload.get("title") or ""),
                description=str(payload.get("description") or ""),
                tags=payload.get("tags") if isinstance(payload.get("tags"), list) else None,
                metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
            )
            return HTTPStatus.CREATED, "application/json", json.dumps(created, sort_keys=True).encode("utf-8")
        if parts == ["v1", "library", "assets"] and method == "GET":
            filters = {key: values[0] for key, values in query.items() if values}
            return list_library_assets(conn, user_id=user_id, filters=filters)
        if len(parts) == 4 and parts[:3] == ["v1", "library", "assets"] and method == "GET":
            return get_library_asset(conn, user_id=user_id, library_asset_id=parts[3])

        if parts == ["v1", "library", "collections"] and method == "POST":
            created = create_collection(
                conn,
                user_id=user_id,
                title=str(payload.get("title") or payload.get("name") or ""),
                description=str(payload.get("description") or ""),
                project_id=payload.get("projectId"),
                metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
            )
            return HTTPStatus.CREATED, "application/json", json.dumps(created, sort_keys=True).encode("utf-8")
        if parts == ["v1", "library", "collections"] and method == "GET":
            return list_collections(conn, user_id=user_id)
        if len(parts) == 5 and parts[:3] == ["v1", "library", "collections"] and parts[4] == "assets" and method == "POST":
            added = add_asset_to_collection(
                conn,
                user_id=user_id,
                collection_id=parts[3],
                library_asset_id=str(payload["libraryAssetId"]),
            )
            return HTTPStatus.CREATED, "application/json", json.dumps(added, sort_keys=True).encode("utf-8")
        if len(parts) == 5 and parts[:3] == ["v1", "library", "collections"] and parts[4] == "assets" and method == "GET":
            return list_collection_assets(conn, user_id=user_id, collection_id=parts[3])

        if parts == ["v1", "library", "packs"] and method == "POST":
            created = create_creator_pack(
                conn,
                user_id=user_id,
                collection_id=str(payload["collectionId"]),
                title=str(payload.get("title") or payload.get("name") or ""),
                description=str(payload.get("description") or ""),
                library_asset_ids=payload.get("libraryAssetIds") if isinstance(payload.get("libraryAssetIds"), list) else None,
                metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
            )
            return HTTPStatus.CREATED, "application/json", json.dumps(created, sort_keys=True).encode("utf-8")
        if parts == ["v1", "library", "packs"] and method == "GET":
            return list_creator_packs(conn, user_id=user_id)

        if len(parts) == 4 and parts[:2] == ["v1", "projects"] and parts[3] == "assets" and method == "GET":
            kind = query.get("kind", [None])[0]
            return {"assets": [_public_asset(asset) for asset in list_project_assets(conn, user_id=user_id, project_id=parts[2], kind=kind)]}
        if len(parts) == 4 and parts[:2] == ["v1", "projects"] and parts[3] == "assets" and method == "POST":
            return self._upload_asset(conn, user_id=user_id, project_id=parts[2], payload=payload)
        if len(parts) == 3 and parts[:2] == ["v1", "assets"] and method == "GET":
            return _public_asset(get_asset(conn, user_id=user_id, asset_id=parts[2]))
        if len(parts) == 4 and parts[:2] == ["v1", "assets"] and parts[3] == "download" and method == "GET":
            asset = get_asset(conn, user_id=user_id, asset_id=parts[2])
            return HTTPStatus.OK, asset.get("content_type") or "application/octet-stream", load_asset_bytes(conn, storage=self.storage(), user_id=user_id, asset_id=parts[2])

        if len(parts) == 4 and parts[:2] == ["v1", "projects"] and parts[3] == "extractions" and method == "POST":
            job = enqueue_extract_job(
                conn,
                user_id=user_id,
                project_id=parts[2],
                asset_id=str(payload["assetId"]),
                mask_provider=str(payload.get("maskProvider") or "threshold"),
                max_frames=payload.get("maxFrames"),
                sample_fps=float(payload.get("sampleFps") or 12.0),
                rights_context=payload.get("rightsContext") if isinstance(payload.get("rightsContext"), dict) else {},
            )
            return HTTPStatus.ACCEPTED, "application/json", json.dumps(_public_job(job), sort_keys=True).encode("utf-8")
        if len(parts) == 4 and parts[:2] == ["v1", "projects"] and parts[3] == "jobs" and method == "GET":
            return {"jobs": [_public_job(job) for job in list_jobs(conn, user_id=user_id, project_id=parts[2])]}
        if len(parts) == 3 and parts[:2] == ["v1", "jobs"] and method == "GET":
            return _public_job(get_job(conn, user_id=user_id, job_id=parts[2]))
        if len(parts) == 4 and parts[:2] == ["v1", "jobs"] and parts[3] == "events" and method == "GET":
            get_job(conn, user_id=user_id, job_id=parts[2])
            return {"events": [_public_event(event) for event in list_job_events(conn, job_id=parts[2])]}
        if len(parts) == 4 and parts[:2] == ["v1", "jobs"] and parts[3] == "cancel" and method == "POST":
            get_job(conn, user_id=user_id, job_id=parts[2])
            canceled = request_cancel_job(conn, job_id=parts[2], reason=str(payload.get("reason") or "user_canceled"))
            return _public_job(canceled)
        if len(parts) == 4 and parts[:2] == ["v1", "jobs"] and parts[3] == "artifacts" and method == "GET":
            job = get_job(conn, user_id=user_id, job_id=parts[2])
            return {"artifacts": [_public_asset(asset) for asset in list_assets_for_job(conn, project_id=job["project_id"], source_job_id=parts[2])]}
        if len(parts) == 4 and parts[:2] == ["v1", "projects"] and parts[3] == "asset-packages" and method == "POST":
            job = enqueue_asset_package_job(
                conn,
                user_id=user_id,
                project_id=parts[2],
                source_job_id=str(payload["sourceJobId"]),
                format=str(payload.get("format") or "website-zip"),
            )
            return HTTPStatus.ACCEPTED, "application/json", json.dumps(_public_job(job), sort_keys=True).encode("utf-8")
        if len(parts) == 4 and parts[:2] == ["v1", "projects"] and parts[3] == "renders" and method == "POST":
            job = enqueue_render_job(
                conn,
                user_id=user_id,
                project_id=parts[2],
                source_job_id=str(payload["sourceJobId"]),
                format=str(payload.get("format") or "remotion-plan"),
                object_id=payload.get("objectId"),
                background_color=str(payload.get("backgroundColor") or "#fbfaf6"),
                editor_state=payload.get("editorState") if isinstance(payload.get("editorState"), dict) else None,
            )
            return HTTPStatus.ACCEPTED, "application/json", json.dumps(_public_job(job), sort_keys=True).encode("utf-8")

        if parts == ["v1", "webhooks"] and method == "GET":
            return {"webhooks": list_webhooks(conn, user_id=user_id)}
        if parts == ["v1", "webhooks"] and method == "POST":
            created = create_webhook(
                conn,
                user_id=user_id,
                url=str(payload["url"]),
                event_types=[str(item) for item in payload.get("eventTypes", [])] if isinstance(payload.get("eventTypes"), list) else None,
                description=str(payload.get("description") or ""),
            )
            return HTTPStatus.CREATED, "application/json", json.dumps(created, sort_keys=True).encode("utf-8")
        if len(parts) == 3 and parts[:2] == ["v1", "webhooks"] and method == "DELETE":
            disabled = disable_webhook(conn, user_id=user_id, webhook_id=parts[2])
            if not disabled:
                raise NotFoundError("webhook not found")
            return {"deleted": True}
        if parts == ["v1", "webhook-deliveries"] and method == "GET":
            webhook_id = query.get("webhookId", [None])[0]
            return {"deliveries": list_webhook_deliveries(conn, user_id=user_id, webhook_id=webhook_id)}

        raise NotFoundError("route not found")

    def _upload_asset(self, conn: sqlite3.Connection, *, user_id: str, project_id: str, payload: dict[str, Any]) -> tuple[int, str, bytes]:
        data_b64 = payload.get("dataBase64")
        if not isinstance(data_b64, str) or not data_b64:
            raise ValueError("dataBase64 is required")
        data = base64.b64decode(data_b64, validate=True)
        filename = str(payload.get("filename") or "asset.bin")
        kind = str(payload.get("kind") or "source_video")
        if kind not in ALLOWED_UPLOAD_KINDS:
            raise ValueError("asset kind must be source_video, mask_sequence, reference, or other")
        with tempfile.TemporaryDirectory(prefix="motionjson_api_upload_") as tmp:
            path = Path(tmp) / Path(filename).name
            path.write_bytes(data)
            asset = register_upload(
                conn,
                storage=self.storage(),
                user_id=user_id,
                project_id=project_id,
                path=path,
                kind=kind,
                content_type=payload.get("contentType"),
                metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
            )
        return HTTPStatus.CREATED, "application/json", json.dumps(_public_asset(asset), sort_keys=True).encode("utf-8")

    def _error(self, status: HTTPStatus, message: str) -> tuple[int, dict[str, str], bytes]:
        return status, {"content-type": "application/json"}, json.dumps({"error": message}, sort_keys=True).encode("utf-8")


def make_handler(api: MotionJSONAPI) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "MotionJSONAPI/0.1"

        def do_GET(self) -> None:
            self._handle()

        def do_POST(self) -> None:
            self._handle()

        def do_DELETE(self) -> None:
            self._handle()

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _handle(self) -> None:
            length = int(self.headers.get("content-length") or 0)
            body = self.rfile.read(length) if length else b""
            status, headers, response_body = api.handle(self.command, self.path, dict(self.headers.items()), body)
            self.send_response(int(status))
            for key, value in headers.items():
                self.send_header(key, value)
            self.send_header("content-length", str(len(response_body)))
            self.end_headers()
            self.wfile.write(response_body)

    return Handler


def serve(*, db_path: str | Path, storage_root: str | Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    api = MotionJSONAPI(db_path=db_path, storage_root=storage_root)
    server = HTTPServer((host, port), make_handler(api))
    server.serve_forever()
