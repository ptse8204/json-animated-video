from __future__ import annotations

import json
import mimetypes
import re
import sqlite3
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from motionjson import __version__
from motionjson.backend.assets import list_assets_for_job, list_project_assets, register_upload
from motionjson.backend.auth import register_user
from motionjson.backend.db import connect, initialize_database
from motionjson.backend.jobs import enqueue_extract_job, get_job, list_job_events, list_jobs
from motionjson.backend.models import BackendError, NotFoundError
from motionjson.backend.projects import create_project, list_projects
from motionjson.capabilities import build_capability_report
from motionjson.config import DISCOVERY_MODES, MASK_PROVIDERS
from motionjson.providers.discovery import discovery_provider_schemas
from motionjson.providers.local_storage import LocalStorageProvider


LOCAL_UI_EMAIL = "local-ui@motionjson.local"
LOCAL_UI_FORMAT = "motionjson.local_ui.v0.1"
STORAGE_KEY_ASSIGNMENT_RE = re.compile(r"(?i)\bstorage[_-]?key=([^\s&]+)")


def _json_loads(data: bytes) -> dict[str, Any]:
    if not data:
        return {}
    parsed = json.loads(data.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("request body must be a JSON object")
    return parsed


def _json_response(payload: Any, status: HTTPStatus = HTTPStatus.OK) -> tuple[int, dict[str, str], bytes]:
    return int(status), {"content-type": "application/json; charset=utf-8"}, json.dumps(payload, sort_keys=True).encode("utf-8")


def _parse_json_field(row: dict[str, Any], field: str) -> None:
    if field in row:
        row[field.removesuffix("_json")] = json.loads(row.pop(field) or "{}")


def _is_storage_key_field(key: Any) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
    return normalized == "storagekey"


def _public_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _public_value(item) for key, item in value.items() if not _is_storage_key_field(key)}
    if isinstance(value, list):
        return [_public_value(item) for item in value]
    if isinstance(value, str):
        return STORAGE_KEY_ASSIGNMENT_RE.sub("[REDACTED]", value)
    return value


def _public_asset(row: dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    data.pop("storage_key", None)
    data.pop("uri", None)
    _parse_json_field(data, "metadata_json")
    return _public_value(data)


def _public_job(row: dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    _parse_json_field(data, "payload_json")
    _parse_json_field(data, "result_json")
    return _public_value(data)


def _public_event(row: dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    _parse_json_field(data, "metadata_json")
    return _public_value(data)


def _optional_int_payload(payload: dict[str, Any], key: str) -> int | None:
    value = payload.get(key)
    if value in {None, ""}:
        return None
    return int(value)


class LocalUIApp:
    """Small local-only UI app over the existing SQLite backend."""

    def __init__(self, *, db_path: str | Path, storage_root: str | Path, mock_mode: bool = False):
        self.db_path = Path(db_path)
        self.storage_root = Path(storage_root)
        self.mock_mode = mock_mode

    def connection(self) -> sqlite3.Connection:
        return initialize_database(connect(self.db_path))

    def storage(self) -> LocalStorageProvider:
        return LocalStorageProvider(self.storage_root)

    def handle(self, method: str, raw_path: str, headers: dict[str, str] | None = None, body: bytes = b"") -> tuple[int, dict[str, str], bytes]:
        del headers
        parsed = urlparse(raw_path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)
        if method == "GET" and path in {"/", "/ui"}:
            return self._static("index.html")
        if method == "GET" and path.startswith("/ui/"):
            return self._static(path.removeprefix("/ui/"))

        if not path.startswith("/api/"):
            return self._error(HTTPStatus.NOT_FOUND, "route not found")

        try:
            payload = _json_loads(body) if method in {"POST", "PATCH", "PUT", "DELETE"} else {}
            return _json_response(self._route(method, path, query, payload))
        except json.JSONDecodeError as exc:
            return self._error(HTTPStatus.BAD_REQUEST, f"invalid json: {exc}")
        except NotFoundError as exc:
            return self._error(HTTPStatus.NOT_FOUND, str(exc))
        except (ValueError, BackendError) as exc:
            return self._error(HTTPStatus.BAD_REQUEST, str(exc))

    def _route(self, method: str, path: str, query: dict[str, list[str]], payload: dict[str, Any]) -> Any:
        if path == "/api/health" and method == "GET":
            return {
                "format": LOCAL_UI_FORMAT,
                "status": "ok",
                "version": __version__,
                "localFirst": True,
                "mockModeAvailable": True,
                "mockMode": self.mock_mode,
                "routes": [
                    "/api/health",
                    "/api/capabilities",
                    "/api/projects",
                    "/api/videos",
                    "/api/run-config/defaults",
                    "/api/jobs",
                    "/api/jobs/{jobId}",
                    "/api/jobs/{jobId}/events",
                    "/api/jobs/{jobId}/artifacts",
                    "/api/progress",
                    "/api/artifacts",
                    "/api/exports/formats",
                ],
            }
        if path == "/api/capabilities" and method == "GET":
            return build_capability_report()
        if path == "/api/run-config/defaults" and method == "GET":
            return {
                "format": "motionjson.local_ui_run_config_defaults.v0.1",
                "maskProviders": sorted(MASK_PROVIDERS),
                "discoveryProviders": sorted(DISCOVERY_MODES),
                "discoveryProviderSchemas": discovery_provider_schemas(),
                "defaults": {
                    "maskProvider": "mock" if self.mock_mode else "threshold",
                    "discoveryProvider": "manual_prompt",
                    "sampleFps": 12.0,
                    "maxFrames": 48,
                    "minArea": 100.0,
                    "outputMode": "authoring",
                },
            }
        if path == "/api/exports/formats" and method == "GET":
            return {
                "format": "motionjson.local_ui_export_formats.v0.1",
                "exports": [
                    {"id": "mp4", "label": "MP4 final video", "requires": ["ffmpeg"]},
                    {"id": "webm-alpha", "label": "Transparent WebM object", "requires": ["ffmpeg"]},
                    {"id": "website-zip", "label": "Website package", "requires": []},
                    {"id": "remotion-plan", "label": "Remotion adapter plan", "requires": []},
                ],
            }

        conn = self.connection()
        try:
            user = self._local_user(conn)
            user_id = user["id"]
            if path == "/api/projects" and method == "GET":
                return {"projects": list_projects(conn, user_id=user_id)}
            if path == "/api/projects" and method == "POST":
                return {
                    "project": create_project(
                        conn,
                        user_id=user_id,
                        name=str(payload.get("name") or "Untitled MotionJSON Project"),
                        description=str(payload.get("description") or ""),
                    )
                }
            if path == "/api/videos" and method == "GET":
                project_id = self._query_one(query, "projectId")
                if not project_id:
                    projects = list_projects(conn, user_id=user_id)
                    project_id = projects[0]["id"] if projects else None
                if not project_id:
                    return {"videos": []}
                videos = list_project_assets(conn, user_id=user_id, project_id=project_id, kind="source_video")
                return {"videos": [_public_asset(asset) for asset in videos]}
            if path == "/api/videos" and method == "POST":
                project_id = str(payload.get("projectId") or "")
                source_path = Path(str(payload.get("path") or "")).expanduser()
                if not project_id:
                    raise ValueError("projectId is required")
                if not source_path.exists() or not source_path.is_file():
                    raise ValueError("path must point to an existing local file")
                asset = register_upload(
                    conn,
                    storage=self.storage(),
                    user_id=user_id,
                    project_id=project_id,
                    path=source_path,
                    kind="source_video",
                    metadata={"rights_context": {"source_uri": str(source_path), "source_type": "user_upload"}},
                )
                return {"video": _public_asset(asset)}
            if path == "/api/jobs" and method == "GET":
                project_id = self._query_one(query, "projectId")
                if not project_id:
                    return {"jobs": []}
                return {"jobs": [_public_job(job) for job in list_jobs(conn, user_id=user_id, project_id=project_id)]}
            if path == "/api/jobs" and method == "POST":
                project_id = str(payload.get("projectId") or "")
                asset_id = str(payload.get("assetId") or payload.get("videoId") or "")
                if not project_id:
                    raise ValueError("projectId is required")
                if not asset_id:
                    raise ValueError("assetId or videoId is required")
                job = enqueue_extract_job(
                    conn,
                    user_id=user_id,
                    project_id=project_id,
                    asset_id=asset_id,
                    mask_provider=str(payload.get("maskProvider") or ("mock" if self.mock_mode else "threshold")),
                    max_frames=_optional_int_payload(payload, "maxFrames"),
                    sample_fps=float(payload.get("sampleFps") or 12.0),
                    rights_context=payload.get("rightsContext") if isinstance(payload.get("rightsContext"), dict) else {},
                )
                return {"job": _public_job(job)}
            if path == "/api/progress" and method == "GET":
                project_id = self._query_one(query, "projectId")
                if not project_id:
                    return {"progress": []}
                progress = []
                for job in list_jobs(conn, user_id=user_id, project_id=project_id):
                    public_job = _public_job(job)
                    public_job["events"] = [_public_event(event) for event in list_job_events(conn, job_id=job["id"])]
                    progress.append(public_job)
                return {"progress": progress}
            if path.startswith("/api/jobs/") and method == "GET":
                parts = [part for part in path.split("/") if part]
                if len(parts) == 3:
                    return {"job": _public_job(get_job(conn, user_id=user_id, job_id=parts[2]))}
                if len(parts) == 4 and parts[3] == "events":
                    get_job(conn, user_id=user_id, job_id=parts[2])
                    return {"events": [_public_event(event) for event in list_job_events(conn, job_id=parts[2])]}
                if len(parts) == 4 and parts[3] == "artifacts":
                    job = get_job(conn, user_id=user_id, job_id=parts[2])
                    assets = list_assets_for_job(conn, project_id=job["project_id"], source_job_id=parts[2])
                    return {"artifacts": [_public_asset(asset) for asset in assets]}
            if path == "/api/artifacts" and method == "GET":
                job_id = self._query_one(query, "jobId")
                if not job_id:
                    return {"artifacts": []}
                job = get_job(conn, user_id=user_id, job_id=job_id)
                assets = list_assets_for_job(conn, project_id=job["project_id"], source_job_id=job_id)
                return {"artifacts": [_public_asset(asset) for asset in assets]}
            raise NotFoundError("route not found")
        finally:
            conn.close()

    def _local_user(self, conn: sqlite3.Connection) -> dict[str, Any]:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (LOCAL_UI_EMAIL,)).fetchone()
        if row is not None:
            return dict(row)
        try:
            return register_user(conn, email=LOCAL_UI_EMAIL, password="local-ui-unusable-password")
        except sqlite3.IntegrityError:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (LOCAL_UI_EMAIL,)).fetchone()
            if row is not None:
                return dict(row)
            raise

    def _static(self, rel_path: str) -> tuple[int, dict[str, str], bytes]:
        safe_path = Path(rel_path)
        if safe_path.is_absolute() or ".." in safe_path.parts:
            return self._error(HTTPStatus.NOT_FOUND, "static asset not found")
        if rel_path in {"", "."}:
            safe_path = Path("index.html")
        root = resources.files("motionjson.ui").joinpath("static")
        target = root.joinpath(*safe_path.parts)
        if not target.is_file():
            return self._error(HTTPStatus.NOT_FOUND, "static asset not found")
        data = target.read_bytes()
        content_type = mimetypes.guess_type(str(safe_path))[0] or "application/octet-stream"
        if safe_path.name.endswith(".js"):
            content_type = "text/javascript"
        return HTTPStatus.OK, {"content-type": f"{content_type}; charset=utf-8"}, data

    def _error(self, status: HTTPStatus, message: str) -> tuple[int, dict[str, str], bytes]:
        return _json_response({"error": message}, status=status)

    @staticmethod
    def _query_one(query: dict[str, list[str]], key: str) -> str | None:
        values = query.get(key) or []
        return values[0] if values else None


def make_handler(app: LocalUIApp) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "MotionJSONLocalUI/0.1"

        def do_GET(self) -> None:
            self._handle()

        def do_POST(self) -> None:
            self._handle()

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _handle(self) -> None:
            length = int(self.headers.get("content-length") or 0)
            body = self.rfile.read(length) if length else b""
            status, headers, response_body = app.handle(self.command, self.path, dict(self.headers.items()), body)
            self.send_response(int(status))
            for key, value in headers.items():
                self.send_header(key, value)
            self.send_header("content-length", str(len(response_body)))
            self.end_headers()
            self.wfile.write(response_body)

    return Handler


def serve_ui(
    *,
    db_path: str | Path,
    storage_root: str | Path,
    host: str = "127.0.0.1",
    port: int = 8766,
    open_browser: bool = True,
    mock_mode: bool = False,
) -> None:
    app = LocalUIApp(db_path=db_path, storage_root=storage_root, mock_mode=mock_mode)
    server = ThreadingHTTPServer((host, port), make_handler(app))
    url = f"http://{host}:{server.server_port}/"
    print(f"MotionJSON UI: {url}", flush=True)
    if open_browser:
        webbrowser.open(url)
    server.serve_forever()
