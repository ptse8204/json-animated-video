from __future__ import annotations

import json
import mimetypes
import re
import sqlite3
import threading
import time
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from motionjson import __version__
from motionjson.backend.assets import get_asset, list_assets_for_job, list_project_assets, register_upload
from motionjson.backend.auth import register_user
from motionjson.backend.corrections import (
    apply_track_edit,
    apply_track_correction_state,
    build_track_correction_state,
    list_track_corrections,
    record_track_edit_action,
)
from motionjson.backend.db import connect, initialize_database
from motionjson.backend.jobs import enqueue_extract_job, get_job, list_job_events, list_jobs, record_job_event
from motionjson.backend.models import BackendError, NotFoundError, validate_extract_provider_policy
from motionjson.backend.projects import create_project, list_projects
from motionjson.backend.worker import worker_once
from motionjson.capabilities import build_capability_report
from motionjson.config import DISCOVERY_MODES, MASK_PROVIDERS, ConfigValidationError, ExtractionRunConfig
from motionjson.providers.discovery import discovery_provider_schemas
from motionjson.providers.local_storage import LocalStorageProvider


LOCAL_UI_EMAIL = "local-ui@motionjson.local"
LOCAL_UI_FORMAT = "motionjson.local_ui.v0.1"
STORAGE_KEY_ASSIGNMENT_RE = re.compile(r"(?i)\bstorage[_-]?key=([^\s&]+)")
STORAGE_KEY_PATH_RE = re.compile(r"\bprojects/[A-Za-z0-9._~!$&'()*+,;=:@%/-]+")
LOCAL_FILE_URI_RE = re.compile(r"(?i)\bfile://[^\s\"']+")
LOCAL_UI_ASSET_URI_RE = re.compile(r"^(?:local-ui|motionjson)://assets/([^/?#]+)$")
LOCAL_ABSOLUTE_PATH_RE = re.compile(r"(?<![\w:])/(?:Users|private|var|tmp|Volumes|home)/[^\s\"']+")
LOCAL_PATH_FIELD_NAMES = {"sourceuri", "sourcepath", "localpath"}
TERMINAL_JOB_STATUSES = {"succeeded", "failed", "canceled"}
PUBLIC_ARTIFACT_CONTENT_TYPES = ("image/", "video/")
REVIEW_JSON_ARTIFACT_KINDS = {
    "candidate_summary",
    "fallback_diagnostics",
    "failure_diagnostics",
    "job_metrics",
    "job_state",
    "provider_diagnostics",
    "scene_graph",
    "track_summary",
}


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


def _is_local_path_field(key: Any) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
    return normalized in LOCAL_PATH_FIELD_NAMES


def _redact_public_text(value: str) -> str:
    return LOCAL_ABSOLUTE_PATH_RE.sub(
        "[LOCAL_PATH_REDACTED]",
        LOCAL_FILE_URI_RE.sub(
            "[LOCAL_FILE_URI_REDACTED]",
            STORAGE_KEY_PATH_RE.sub(
                "[STORAGE_KEY_REDACTED]",
                STORAGE_KEY_ASSIGNMENT_RE.sub("[REDACTED]", value),
            ),
        ),
    )


def _public_value(value: Any, *, key: Any | None = None) -> Any:
    if _is_local_path_field(key) and isinstance(value, str) and (
        value.startswith("/") or value.lower().startswith("file://")
    ):
        return "[LOCAL_PATH_REDACTED]"
    if isinstance(value, dict):
        return {
            str(key): _public_value(item, key=key)
            for key, item in value.items()
            if not _is_storage_key_field(key)
        }
    if isinstance(value, list):
        return [_public_value(item) for item in value]
    if isinstance(value, str):
        return _redact_public_text(value)
    return value


def _public_asset(row: dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    data.pop("storage_key", None)
    data.pop("uri", None)
    _parse_json_field(data, "metadata_json")
    return _public_value(data)


def _public_video(row: dict[str, Any]) -> dict[str, Any]:
    data = _public_asset(row)
    data["contentUrl"] = f"/api/videos/{data['id']}/content"
    return data


def _public_job(row: dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    _parse_json_field(data, "payload_json")
    _parse_json_field(data, "result_json")
    return _public_value(data)


def _public_event(row: dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    _parse_json_field(data, "metadata_json")
    return _public_value(data)


def _public_review_value(value: Any, *, key: Any | None = None) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _public_review_value(item, key=key)
            for key, item in value.items()
            if not _is_storage_key_field(key)
        }
    if isinstance(value, list):
        return [_public_review_value(item) for item in value]
    if isinstance(value, str):
        redacted = _redact_public_text(value)
        if redacted.startswith("/") or redacted.lower().startswith("file://"):
            return "[LOCAL_PATH_REDACTED]"
        if _is_local_path_field(key) and (redacted.startswith("/") or redacted.lower().startswith("file://")):
            return "[LOCAL_PATH_REDACTED]"
        return redacted
    return value


def _truthy_payload(payload: dict[str, Any], *keys: str) -> bool:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, bool):
            if value:
                return True
            continue
        if isinstance(value, str) and value.strip().lower() in {"1", "true", "yes", "on", "run", "start"}:
            return True
    return False


def _is_export_inclusion_action(payload: dict[str, Any]) -> bool:
    action = payload.get("action") if isinstance(payload.get("action"), dict) else payload
    action_type = str(action.get("type") or action.get("operation") or "").strip().lower().replace("-", "_")
    return action_type in {"set_export_inclusion", "include_in_export", "set_track_export", "exclude_track"}


def _asset_id_from_uri(value: Any) -> str | None:
    match = LOCAL_UI_ASSET_URI_RE.match(str(value or ""))
    if not match:
        return None
    candidate = match.group(1)
    if candidate in {"source", "source-video", "source_video"}:
        return None
    return candidate


def _latest_progress_ratio(events: list[dict[str, Any]]) -> float | None:
    latest: float | None = None
    for event in events:
        metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
        progress = metadata.get("progress") if isinstance(metadata.get("progress"), dict) else {}
        ratio = progress.get("overallRatio", progress.get("ratio"))
        if isinstance(ratio, (int, float)):
            latest = max(latest or 0.0, min(float(ratio), 1.0))
    return latest


def _public_job_snapshot(row: dict[str, Any], *, events: list[dict[str, Any]] | None = None, include_events: bool = False) -> dict[str, Any]:
    data = _public_job(row)
    public_events = [_public_event(event) for event in events or []]
    ratio = _latest_progress_ratio(public_events)
    status = str(data.get("status") or "")
    if ratio is None:
        if status in TERMINAL_JOB_STATUSES:
            ratio = 1.0
        elif status == "running":
            ratio = 0.25
        else:
            ratio = 0.0
    percent = int(round(ratio * 100))
    data["progress"] = percent
    data["percent"] = percent
    if public_events:
        data["message"] = public_events[-1].get("message")
        data["latestEventType"] = public_events[-1].get("event_type")
    if include_events:
        data["events"] = public_events
    return data


def _optional_int_payload(payload: dict[str, Any], key: str) -> int | None:
    value = payload.get(key)
    if value in {None, ""}:
        return None
    return int(value)


def _header_value(headers: dict[str, str], key: str) -> str | None:
    target = key.lower()
    for name, value in headers.items():
        if name.lower() == target:
            return value
    return None


def _parse_single_byte_range(value: str, size: int) -> tuple[int, int]:
    if not value.startswith("bytes=") or "," in value:
        raise ValueError("invalid range")
    start_text, separator, end_text = value.removeprefix("bytes=").partition("-")
    if separator != "-" or (not start_text and not end_text):
        raise ValueError("invalid range")
    if start_text:
        start = int(start_text)
        end = int(end_text) if end_text else size - 1
    else:
        suffix_length = int(end_text)
        if suffix_length <= 0:
            raise ValueError("invalid range")
        start = max(size - suffix_length, 0)
        end = size - 1
    if size <= 0 or start < 0 or start >= size or end < start:
        raise ValueError("unsatisfiable range")
    return start, min(end, size - 1)


def _track_review_summary(track: dict[str, Any]) -> dict[str, Any]:
    frames = track.get("frames") if isinstance(track.get("frames"), list) else []
    return {
        "objectId": track.get("objectId"),
        "label": track.get("label"),
        "source": track.get("source"),
        "providerName": track.get("providerName"),
        "confidence": track.get("confidence"),
        "zIndex": track.get("zIndex"),
        "frameCount": track.get("frameCount"),
        "visibleFrameCount": track.get("visibleFrameCount"),
        "exportStatus": track.get("exportStatus"),
        "warnings": track.get("warnings", []),
        "metadata": track.get("metadata", {}),
        "frames": [
            {
                "frame": frame.get("frame"),
                "sourceFrameIndex": frame.get("sourceFrameIndex"),
                "outIndex": frame.get("outIndex"),
                "t": frame.get("t"),
                "visible": frame.get("visible"),
                "area": frame.get("area"),
                "bbox": frame.get("bbox"),
                "centroid": frame.get("centroid"),
                "mask": frame.get("mask"),
                "asset": frame.get("asset"),
                "contourPoints": frame.get("contourPoints"),
                "polygon": frame.get("polygon"),
            }
            for frame in frames
            if isinstance(frame, dict)
        ],
    }


def _scene_object_review_summary(item: dict[str, Any]) -> dict[str, Any]:
    motion = item.get("motion") if isinstance(item.get("motion"), list) else []
    visible_motion = [frame for frame in motion if isinstance(frame, dict) and frame.get("visible")]
    return {
        "objectId": item.get("id") or item.get("objectId"),
        "label": item.get("label"),
        "renderMode": item.get("renderMode"),
        "recommendedOutput": item.get("recommendedOutput"),
        "zIndex": item.get("zIndex"),
        "frameCount": len(motion),
        "visibleFrameCount": len(visible_motion),
        "quality": item.get("quality", {}),
        "firstVisibleFrame": visible_motion[0].get("frame") if visible_motion else None,
        "lastVisibleFrame": visible_motion[-1].get("frame") if visible_motion else None,
    }


def _append_unique_fallback(review: dict[str, Any], item: Any, seen: set[str]) -> None:
    if not isinstance(item, dict):
        return
    public_item = _public_review_value(item)
    key = json.dumps(public_item, sort_keys=True)
    if key in seen:
        return
    seen.add(key)
    review["fallbackDiagnostics"].append(public_item)


class LocalUIApp:
    """Small local-only UI app over the existing SQLite backend."""

    def __init__(self, *, db_path: str | Path, storage_root: str | Path, mock_mode: bool = False):
        self.db_path = Path(db_path)
        self.storage_root = Path(storage_root)
        self.mock_mode = mock_mode
        self._worker_lock = threading.Lock()
        self._worker_thread: threading.Thread | None = None

    def connection(self) -> sqlite3.Connection:
        return initialize_database(connect(self.db_path))

    def storage(self) -> LocalStorageProvider:
        return LocalStorageProvider(self.storage_root)

    def handle(self, method: str, raw_path: str, headers: dict[str, str] | None = None, body: bytes = b"") -> tuple[int, dict[str, str], bytes]:
        request_headers = headers or {}
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
            if method in {"GET", "HEAD"} and path.startswith("/api/videos/") and path.endswith("/content"):
                parts = [part for part in path.split("/") if part]
                if len(parts) == 4:
                    return self._video_content(parts[2], headers=request_headers, head=method == "HEAD")
            if method in {"GET", "HEAD"} and path.startswith("/api/artifacts/") and path.endswith("/content"):
                parts = [part for part in path.split("/") if part]
                if len(parts) == 4:
                    return self._artifact_content(parts[2], head=method == "HEAD")
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
                    "/api/videos/{videoId}/content",
                    "/api/run-config/defaults",
                    "/api/run-config/validate",
                    "/api/jobs",
                    "/api/jobs/{jobId}",
                    "/api/jobs/{jobId}/events",
                    "/api/jobs/{jobId}/artifacts",
                    "/api/jobs/{jobId}/review",
                    "/api/jobs/{jobId}/corrections",
                    "/api/jobs/{jobId}/track-edits",
                    "/api/jobs/{jobId}/run",
                    "/api/progress",
                    "/api/artifacts",
                    "/api/artifacts/{artifactId}/content",
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
        if path == "/api/run-config/validate" and method == "POST":
            return self._validate_run_config(payload)
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
                return {"videos": [_public_video(asset) for asset in videos]}
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
                return {"video": _public_video(asset)}
            if path == "/api/jobs" and method == "GET":
                project_id = self._query_one(query, "projectId")
                if not project_id:
                    return {"jobs": []}
                jobs = []
                for job in list_jobs(conn, user_id=user_id, project_id=project_id):
                    jobs.append(_public_job_snapshot(job, events=list_job_events(conn, job_id=job["id"])))
                return {"jobs": jobs}
            if path == "/api/jobs" and method == "POST":
                job = self._enqueue_extract_from_ui_payload(conn, user_id=user_id, payload=payload)
                response: dict[str, Any] = {
                    "job": _public_job_snapshot(job, events=list_job_events(conn, job_id=job["id"]))
                }
                if self._payload_requests_worker(payload):
                    record_job_event(
                        conn,
                        job_id=job["id"],
                        event_type="worker_start_requested",
                        message="local UI worker start requested",
                        metadata={"source": "local_ui"},
                    )
                    response["worker"] = self._start_worker()
                    response["job"] = _public_job_snapshot(
                        get_job(conn, user_id=user_id, job_id=job["id"]),
                        events=list_job_events(conn, job_id=job["id"]),
                    )
                return response
            if path == "/api/progress" and method == "GET":
                project_id = self._query_one(query, "projectId")
                if not project_id:
                    return {"progress": []}
                progress = []
                for job in list_jobs(conn, user_id=user_id, project_id=project_id):
                    events = list_job_events(conn, job_id=job["id"])
                    public_job = _public_job_snapshot(job, events=events, include_events=True)
                    progress.append(public_job)
                return {"progress": progress}
            if path.startswith("/api/jobs/") and method == "POST":
                parts = [part for part in path.split("/") if part]
                if len(parts) == 4 and parts[3] == "run":
                    job = get_job(conn, user_id=user_id, job_id=parts[2])
                    if job["status"] in TERMINAL_JOB_STATUSES:
                        return {
                            "job": _public_job_snapshot(job, events=list_job_events(conn, job_id=job["id"])),
                            "worker": {"status": "not_started", "reason": "job is already terminal"},
                        }
                    record_job_event(
                        conn,
                        job_id=job["id"],
                        event_type="worker_start_requested",
                        message="local UI worker start requested",
                        metadata={"source": "local_ui"},
                    )
                    return {
                        "job": _public_job_snapshot(
                            get_job(conn, user_id=user_id, job_id=job["id"]),
                            events=list_job_events(conn, job_id=job["id"]),
                        ),
                        "worker": self._start_worker(),
                    }
                if len(parts) == 4 and parts[3] in {"corrections", "track-edits"}:
                    job = get_job(conn, user_id=user_id, job_id=parts[2])
                    action_payload = payload.get("action") or payload.get("correction") or payload
                    if parts[3] == "track-edits" and not _is_export_inclusion_action(payload):
                        edit_result = apply_track_edit(
                            conn,
                            storage=self.storage(),
                            user_id=user_id,
                            job_id=parts[2],
                            payload=payload,
                        )
                        correction = edit_result.get("correction") if isinstance(edit_result.get("correction"), dict) else {}
                    else:
                        edit_result = {}
                        correction = record_track_edit_action(
                            conn,
                            user_id=user_id,
                            job_id=parts[2],
                            action=action_payload,
                        )
                    job = get_job(conn, user_id=user_id, job_id=parts[2])
                    assets = list_assets_for_job(conn, project_id=job["project_id"], source_job_id=parts[2])
                    corrections = list_track_corrections(conn, user_id=user_id, job_id=parts[2])
                    correction_state = build_track_correction_state(corrections, job_id=parts[2])
                    history = correction_state.get("history") if isinstance(correction_state.get("history"), list) else []
                    if history and correction:
                        correction = {**correction, "operation": history[-1].get("type") or correction.get("operation")}
                    response: dict[str, Any] = {
                        **_public_review_value(edit_result),
                        "correction": _public_review_value(correction),
                        "correctionState": _public_review_value(correction_state),
                        "corrections": _public_review_value(correction_state),
                        "review": self._review_metadata(assets, corrections=corrections, job_id=parts[2]),
                    }
                    result = correction.get("result") if isinstance(correction.get("result"), dict) else {}
                    if isinstance(result.get("repairDiagnostics"), dict):
                        response["repairDiagnostics"] = _public_review_value(result["repairDiagnostics"])
                    if isinstance(result.get("partialRerun"), dict):
                        response["partialRerun"] = _public_review_value(result["partialRerun"])
                    return response
            if path.startswith("/api/jobs/") and method == "GET":
                parts = [part for part in path.split("/") if part]
                if len(parts) == 3:
                    job = get_job(conn, user_id=user_id, job_id=parts[2])
                    return {"job": _public_job_snapshot(job, events=list_job_events(conn, job_id=job["id"]))}
                if len(parts) == 4 and parts[3] == "events":
                    get_job(conn, user_id=user_id, job_id=parts[2])
                    return {"events": [_public_event(event) for event in list_job_events(conn, job_id=parts[2])]}
                if len(parts) == 4 and parts[3] == "artifacts":
                    job = get_job(conn, user_id=user_id, job_id=parts[2])
                    assets = list_assets_for_job(conn, project_id=job["project_id"], source_job_id=parts[2])
                    corrections = list_track_corrections(conn, user_id=user_id, job_id=parts[2])
                    return self._artifacts_response(assets, corrections=corrections, job_id=parts[2])
                if len(parts) == 4 and parts[3] == "review":
                    job = get_job(conn, user_id=user_id, job_id=parts[2])
                    assets = list_assets_for_job(conn, project_id=job["project_id"], source_job_id=parts[2])
                    corrections = list_track_corrections(conn, user_id=user_id, job_id=parts[2])
                    return {"review": self._review_metadata(assets, corrections=corrections, job_id=parts[2])}
                if len(parts) == 4 and parts[3] == "corrections":
                    get_job(conn, user_id=user_id, job_id=parts[2])
                    corrections = list_track_corrections(conn, user_id=user_id, job_id=parts[2])
                    correction_state = build_track_correction_state(corrections, job_id=parts[2])
                    return {
                        "correctionState": _public_review_value(correction_state),
                        "corrections": _public_review_value(correction_state),
                    }
            if path == "/api/artifacts" and method == "GET":
                job_id = self._query_one(query, "jobId")
                if not job_id:
                    return {"artifacts": [], "review": self._review_metadata([])}
                job = get_job(conn, user_id=user_id, job_id=job_id)
                assets = list_assets_for_job(conn, project_id=job["project_id"], source_job_id=job_id)
                corrections = list_track_corrections(conn, user_id=user_id, job_id=job_id)
                return self._artifacts_response(assets, corrections=corrections, job_id=job_id)
            raise NotFoundError("route not found")
        finally:
            conn.close()

    def _validate_run_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        run_config_payload = payload.get("runConfig", payload)
        if not isinstance(run_config_payload, dict):
            raise ValueError("runConfig must be a JSON object")

        response: dict[str, Any] = {
            "format": "motionjson.local_ui_run_config_validation.v0.1",
            "valid": False,
            "errors": [],
            "warnings": [],
        }
        try:
            config = ExtractionRunConfig.from_dict(run_config_payload)
        except ConfigValidationError as exc:
            response["errors"] = [{"message": str(exc)}]
            return response

        response["valid"] = True
        response["runConfig"] = _public_value(config.to_dict())
        response["warnings"] = self._run_config_warnings(config)
        return response

    def _run_config_warnings(self, config: ExtractionRunConfig) -> list[dict[str, Any]]:
        warnings: list[dict[str, Any]] = []
        providers = {
            (str(provider.get("kind") or ""), str(provider.get("name") or "")): provider
            for provider in build_capability_report().get("providers", [])
            if isinstance(provider, dict)
        }
        self._append_provider_warning(
            warnings,
            providers,
            kind="mask_provider",
            name=config.provider.name,
            field="provider.name",
        )
        if config.discovery.mode:
            self._append_provider_warning(
                warnings,
                providers,
                kind="discovery_provider",
                name=config.discovery.mode,
                field="discovery.mode",
            )

        try:
            validate_extract_provider_policy(config.provider.name)
        except BackendError as exc:
            warnings.append(
                {
                    "code": "local_job_policy",
                    "field": "provider.name",
                    "provider": config.provider.name,
                    "message": str(exc),
                }
            )
        return warnings

    @staticmethod
    def _append_provider_warning(
        warnings: list[dict[str, Any]],
        providers: dict[tuple[str, str], dict[str, Any]],
        *,
        kind: str,
        name: str,
        field: str,
    ) -> None:
        provider = providers.get((kind, name))
        if not provider or provider.get("available") is not False:
            return
        warnings.append(
            {
                "code": "provider_unavailable",
                "field": field,
                "provider": name,
                "kind": kind,
                "status": provider.get("status"),
                "message": f"{name} is not available on this machine.",
                "reasons": _public_value(provider.get("reasons") or []),
                "installHint": provider.get("installHint"),
            }
        )

    def _enqueue_extract_from_ui_payload(
        self,
        conn: sqlite3.Connection,
        *,
        user_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        run_config_payload = payload.get("runConfig", payload.get("run_config"))
        if isinstance(run_config_payload, dict):
            config = ExtractionRunConfig.from_dict(run_config_payload)
            project_id = str(payload.get("projectId") or payload.get("project_id") or "")
            asset_id = self._asset_id_for_run_config(config, payload)
            rights_context = config.rights.to_dict()

            if not asset_id:
                if not project_id:
                    raise ValueError("projectId is required when runConfig.input.path is not a local UI asset")
                source_path = Path(config.input_video.path).expanduser()
                if not source_path.exists() or not source_path.is_file():
                    raise ValueError("runConfig input must reference assetId, videoId, or local-ui://assets/{assetId}")
                asset = register_upload(
                    conn,
                    storage=self.storage(),
                    user_id=user_id,
                    project_id=project_id,
                    path=source_path,
                    kind="source_video",
                    metadata={"rights_context": rights_context},
                )
                asset_id = asset["id"]

            if not project_id:
                project_id = get_asset(conn, user_id=user_id, asset_id=asset_id)["project_id"]

            mask_dir = config.provider.external.mask_dir or next(
                (obj.mask_dir for obj in config.objects if obj.mask_dir),
                None,
            )
            return enqueue_extract_job(
                conn,
                user_id=user_id,
                project_id=project_id,
                asset_id=asset_id,
                mask_provider=config.provider.name,
                max_frames=config.sampling.max_frames,
                sample_fps=float(config.sampling.sample_fps if config.sampling.sample_fps is not None else 12.0),
                lower_hsv=config.provider.threshold.lower_hsv,
                upper_hsv=config.provider.threshold.upper_hsv,
                mask_dir=mask_dir,
                rights_context=rights_context,
            )

        project_id = str(payload.get("projectId") or payload.get("project_id") or "")
        asset_id = str(
            payload.get("assetId")
            or payload.get("videoId")
            or payload.get("asset_id")
            or payload.get("video_id")
            or ""
        )
        if not project_id:
            raise ValueError("projectId is required")
        if not asset_id:
            raise ValueError("assetId or videoId is required")
        return enqueue_extract_job(
            conn,
            user_id=user_id,
            project_id=project_id,
            asset_id=asset_id,
            mask_provider=str(payload.get("maskProvider") or payload.get("mask_provider") or ("mock" if self.mock_mode else "threshold")),
            max_frames=self._optional_int_payload_alias(payload, "maxFrames", "max_frames"),
            sample_fps=float(payload.get("sampleFps") or payload.get("sample_fps") or 12.0),
            lower_hsv=self._hsv_payload_alias(payload, "lowerHsv", "lower_hsv", (0, 80, 80)),
            upper_hsv=self._hsv_payload_alias(payload, "upperHsv", "upper_hsv", (12, 255, 255)),
            mask_dir=payload.get("maskDir") or payload.get("mask_dir"),
            rights_context=self._dict_payload_alias(payload, "rightsContext", "rights_context"),
        )

    @staticmethod
    def _asset_id_for_run_config(config: ExtractionRunConfig, payload: dict[str, Any]) -> str | None:
        for value in (
            payload.get("assetId"),
            payload.get("videoId"),
            payload.get("asset_id"),
            payload.get("video_id"),
            config.rights.source_asset_id,
            _asset_id_from_uri(config.input_video.path),
        ):
            if value:
                return _asset_id_from_uri(value) or str(value)
        return None

    @staticmethod
    def _optional_int_payload_alias(payload: dict[str, Any], camel_key: str, snake_key: str) -> int | None:
        if camel_key in payload:
            return _optional_int_payload(payload, camel_key)
        return _optional_int_payload(payload, snake_key)

    @staticmethod
    def _hsv_payload_alias(
        payload: dict[str, Any],
        camel_key: str,
        snake_key: str,
        fallback: tuple[int, int, int],
    ) -> tuple[int, int, int]:
        value = payload.get(camel_key, payload.get(snake_key, fallback))
        if value is None or value == "":
            value = fallback
        if not isinstance(value, (list, tuple)) or len(value) != 3:
            raise ValueError(f"{camel_key} must contain three HSV values")
        return tuple(int(part) for part in value)

    @staticmethod
    def _dict_payload_alias(payload: dict[str, Any], camel_key: str, snake_key: str) -> dict[str, Any]:
        value = payload.get(camel_key) if isinstance(payload.get(camel_key), dict) else payload.get(snake_key)
        return dict(value) if isinstance(value, dict) else {}

    @staticmethod
    def _payload_requests_worker(payload: dict[str, Any]) -> bool:
        return _truthy_payload(payload, "run", "start", "startWorker", "runWorker", "runImmediately")

    def _start_worker(self) -> dict[str, Any]:
        with self._worker_lock:
            if self._worker_thread is not None and self._worker_thread.is_alive():
                return {"status": "already_running"}
            self._worker_thread = None
            thread = threading.Thread(target=self._worker_loop, name="motionjson-local-ui-worker", daemon=True)
            self._worker_thread = thread
            thread.start()
        return {"status": "started"}

    def _worker_loop(self) -> None:
        conn = self.connection()
        try:
            idle_checks = 0
            while idle_checks < 5:
                processed = worker_once(
                    conn,
                    storage=self.storage(),
                    worker_id=f"local-ui-{threading.get_ident()}",
                    max_attempts=1,
                )
                if processed:
                    idle_checks = 0
                    continue
                idle_checks += 1
                time.sleep(0.05)
        except Exception as exc:
            try:
                row = conn.execute(
                    """
                    SELECT id
                    FROM jobs
                    WHERE status IN ('pending', 'running', 'cancel_requested')
                    ORDER BY created_at, id
                    LIMIT 1
                    """
                ).fetchone()
                if row is not None:
                    record_job_event(
                        conn,
                        job_id=row["id"],
                        event_type="worker_error",
                        message=str(exc) or type(exc).__name__,
                        metadata={"errorType": type(exc).__name__},
                    )
            except Exception:
                pass
            raise
        finally:
            conn.close()

    def _artifacts_response(
        self,
        assets: list[dict[str, Any]],
        *,
        corrections: list[dict[str, Any]] | None = None,
        job_id: str | None = None,
    ) -> dict[str, Any]:
        return {
            "artifacts": [self._public_artifact(asset) for asset in assets],
            "review": self._review_metadata(assets, corrections=corrections, job_id=job_id),
        }

    def _public_artifact(self, row: dict[str, Any]) -> dict[str, Any]:
        data = _public_asset(row)
        if self._has_public_artifact_content(data):
            data["contentUrl"] = f"/api/artifacts/{data['id']}/content"
        return data

    @staticmethod
    def _has_public_artifact_content(asset: dict[str, Any]) -> bool:
        content_type = str(asset.get("content_type") or "")
        return content_type.startswith(PUBLIC_ARTIFACT_CONTENT_TYPES)

    def _review_metadata(
        self,
        assets: list[dict[str, Any]],
        *,
        corrections: list[dict[str, Any]] | None = None,
        job_id: str | None = None,
    ) -> dict[str, Any]:
        review: dict[str, Any] = {
            "format": "motionjson.local_ui_review.v0.1",
            "artifactCountsByKind": {},
            "tracks": [],
            "objects": [],
            "fallbackDiagnostics": [],
            "diagnostics": [],
            "rasterFallback": False,
        }
        storage = self.storage()
        seen_fallback: set[str] = set()
        for asset in assets:
            kind = str(asset.get("kind") or "")
            counts = review["artifactCountsByKind"]
            counts[kind] = int(counts.get(kind, 0)) + 1
            document, error = self._read_review_json(storage, asset)
            if error is not None:
                review["diagnostics"].append(error)
                continue
            if document is None:
                continue
            if kind == "track_summary":
                self._apply_track_review(review, document, seen_fallback)
            elif kind == "fallback_diagnostics":
                self._apply_fallback_review(review, document, seen_fallback)
            elif kind == "scene_graph":
                self._apply_scene_review(review, document)
            elif kind == "failure_diagnostics":
                review["failure"] = _public_review_value(document)
            elif kind == "provider_diagnostics":
                review["providerDiagnostics"] = _public_review_value(document.get("diagnostics", document))
            elif kind == "job_metrics":
                review["metrics"] = _public_review_value(document)
            elif kind == "candidate_summary":
                review["candidateSummary"] = _public_review_value(document)

        review["rasterFallback"] = bool(review["fallbackDiagnostics"])
        if review["fallbackDiagnostics"]:
            first = review["fallbackDiagnostics"][0]
            review["rasterFallbackReason"] = first.get("reasonCode") or first.get("message")
        accepted_tracks = [
            track
            for track in review["tracks"]
            if str(track.get("exportStatus") or "accepted") == "accepted"
        ]
        if not accepted_tracks and review["fallbackDiagnostics"]:
            first = review["fallbackDiagnostics"][0]
            review["vectorUnavailableReason"] = first.get("reasonCode") or first.get("message")
        correction_state = build_track_correction_state(corrections or [], job_id=job_id or "")
        if corrections is not None:
            review = apply_track_correction_state(review, correction_state)
        return _public_review_value(review)

    def _read_review_json(
        self,
        storage: LocalStorageProvider,
        asset: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        kind = str(asset.get("kind") or "")
        if kind not in REVIEW_JSON_ARTIFACT_KINDS:
            return None, None
        if int(asset.get("byte_size") or 0) > 5_000_000:
            return None, {
                "code": "artifact_review_too_large",
                "artifactId": asset.get("id"),
                "kind": kind,
                "message": "artifact is too large to inline for local UI review",
            }
        try:
            document = json.loads(storage.load_bytes(asset["storage_key"]).decode("utf-8"))
        except Exception as exc:
            return None, {
                "code": "artifact_review_unavailable",
                "artifactId": asset.get("id"),
                "kind": kind,
                "message": str(exc) or type(exc).__name__,
                "errorType": type(exc).__name__,
            }
        if not isinstance(document, dict):
            return None, {
                "code": "artifact_review_invalid_json",
                "artifactId": asset.get("id"),
                "kind": kind,
                "message": "artifact JSON must be an object",
            }
        return document, None

    @staticmethod
    def _apply_track_review(review: dict[str, Any], document: dict[str, Any], seen_fallback: set[str]) -> None:
        filter_report = document.get("filterReport") if isinstance(document.get("filterReport"), dict) else {}
        if filter_report:
            review["trackSummary"] = _public_review_value(filter_report.get("summary", filter_report))
            review["mergeSuggestions"] = _public_review_value(filter_report.get("mergeSuggestions", []))
        tracks = document.get("tracks") if isinstance(document.get("tracks"), list) else []
        review["tracks"] = [_public_review_value(_track_review_summary(track)) for track in tracks if isinstance(track, dict)]
        fallback = document.get("fallbackDiagnostics") if isinstance(document.get("fallbackDiagnostics"), list) else []
        for item in fallback:
            _append_unique_fallback(review, item, seen_fallback)

    @staticmethod
    def _apply_fallback_review(review: dict[str, Any], document: dict[str, Any], seen_fallback: set[str]) -> None:
        summary = document.get("summary") if isinstance(document.get("summary"), dict) else {}
        if summary:
            review["fallbackSummary"] = _public_review_value(summary)
        diagnostics = document.get("diagnostics") if isinstance(document.get("diagnostics"), list) else []
        for item in diagnostics:
            _append_unique_fallback(review, item, seen_fallback)

    @staticmethod
    def _apply_scene_review(review: dict[str, Any], document: dict[str, Any]) -> None:
        source = document.get("source") if isinstance(document.get("source"), dict) else {}
        canvas = document.get("canvas") if isinstance(document.get("canvas"), dict) else {}
        review["source"] = _public_review_value(
            {
                "width": source.get("width") or canvas.get("width"),
                "height": source.get("height") or canvas.get("height"),
                "fps": source.get("sampleFps") or canvas.get("fps"),
                "frameCount": source.get("sampledFrameCount") or canvas.get("frame_count"),
            }
        )
        objects = document.get("objects") if isinstance(document.get("objects"), list) else []
        review["objects"] = [
            _public_review_value(_scene_object_review_summary(item))
            for item in objects
            if isinstance(item, dict)
        ]

    def _video_content(self, asset_id: str, *, headers: dict[str, str], head: bool = False) -> tuple[int, dict[str, str], bytes]:
        conn = self.connection()
        try:
            user = self._local_user(conn)
            asset = get_asset(conn, user_id=user["id"], asset_id=asset_id)
            if asset["kind"] != "source_video":
                raise NotFoundError("video not found")
            try:
                data = self.storage().load_bytes(asset["storage_key"])
            except FileNotFoundError as exc:
                raise NotFoundError("video content not found in local storage") from exc
            content_type = asset["content_type"] or "application/octet-stream"
            response_headers = {"content-type": content_type, "cache-control": "no-store", "accept-ranges": "bytes"}
            range_header = _header_value(headers, "range")
            if range_header:
                try:
                    start, end = _parse_single_byte_range(range_header, len(data))
                except ValueError:
                    return (
                        HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE,
                        {**response_headers, "content-range": f"bytes */{len(data)}", "content-length": "0"},
                        b"",
                    )
                response_headers["content-range"] = f"bytes {start}-{end}/{len(data)}"
                if head:
                    response_headers["content-length"] = str(end - start + 1)
                    return HTTPStatus.PARTIAL_CONTENT, response_headers, b""
                return HTTPStatus.PARTIAL_CONTENT, response_headers, data[start : end + 1]
            if head:
                response_headers["content-length"] = str(len(data))
                return HTTPStatus.OK, response_headers, b""
            return HTTPStatus.OK, response_headers, data
        finally:
            conn.close()

    def _artifact_content(self, asset_id: str, *, head: bool = False) -> tuple[int, dict[str, str], bytes]:
        conn = self.connection()
        try:
            user = self._local_user(conn)
            asset = get_asset(conn, user_id=user["id"], asset_id=asset_id)
            if not asset.get("source_job_id"):
                raise NotFoundError("artifact not found")
            if not self._has_public_artifact_content(_public_asset(asset)):
                raise NotFoundError("artifact content is not public through the local UI")
            try:
                data = self.storage().load_bytes(asset["storage_key"])
            except FileNotFoundError as exc:
                raise NotFoundError("artifact content not found in local storage") from exc
            content_type = asset["content_type"] or "application/octet-stream"
            response_headers = {
                "content-type": content_type,
                "cache-control": "no-store",
                "content-length": str(len(data)),
            }
            return HTTPStatus.OK, response_headers, b"" if head else data
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

        def do_HEAD(self) -> None:
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
            if not any(key.lower() == "content-length" for key in headers):
                self.send_header("content-length", str(len(response_body)))
            self.end_headers()
            if self.command != "HEAD":
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
