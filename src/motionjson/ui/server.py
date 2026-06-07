from __future__ import annotations

import json
import mimetypes
import re
import sqlite3
import tempfile
import threading
import time
import webbrowser
from email.parser import BytesParser
from email.policy import default as email_policy_default
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path, PurePosixPath
from typing import Any, Mapping
from urllib.parse import parse_qs, unquote, urlparse

from motionjson import __version__
from motionjson.backend.assets import get_asset, list_assets_for_job, list_project_assets, register_upload
from motionjson.backend.browser_preview import prepare_browser_preview
from motionjson.backend.auth import register_user
from motionjson.backend.corrections import (
    apply_track_edit,
    apply_track_correction_state,
    build_track_correction_state,
    list_track_corrections,
    record_track_edit_action,
    write_review_state_manifest,
)
from motionjson.backend.db import connect, initialize_database
from motionjson.backend.export_workflows import (
    export_motionjson_job,
    export_presets,
    import_motionjson_result,
    validate_motionjson_export_job,
)
from motionjson.backend.jobs import enqueue_extract_job, get_job, list_job_events, list_jobs, record_job_event
from motionjson.backend.job_lifecycle import job_lifecycle_summary, review_lifecycle_summary
from motionjson.backend.library import (
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
from motionjson.backend.models import BackendError, NotFoundError, validate_extract_provider_policy
from motionjson.backend.projects import create_project, list_projects
from motionjson.backend.provider_setup_jobs import (
    cancel_provider_setup_job,
    create_provider_setup_job,
    provider_setup_actions,
    public_provider_setup_job,
    run_provider_setup_job,
)
from motionjson.backend.queue import request_cancel_job
from motionjson.backend.readiness import job_readiness, review_tool_statuses
from motionjson.backend.selected_tracking import track_selected_candidates
from motionjson.backend.stale_jobs import asset_preparation_stall_diagnostic
from motionjson.backend.workspace import (
    commercial_readiness_response,
    get_workspace_preferences,
    save_workspace_preferences,
    workspace_response,
)
from motionjson.backend.worker import worker_once
from motionjson.capabilities import build_capability_report
from motionjson.candidate_review import candidate_review_payload
from motionjson.config import DISCOVERY_MODES, MASK_PROVIDERS, ConfigValidationError, ExtractionRunConfig
from motionjson.model_connectors import (
    MODEL_CONNECTOR_FORMAT,
    MODEL_RUN_FORMAT,
    ModelConnectorRegistry,
    ModelPlanRequest,
    ModelPlanResult,
    VolatileModelRunStore,
)
from motionjson.provider_settings import (
    diagnose_provider_settings,
    hosted_sam3_smoke_test,
    local_sam_smoke_test,
    provider_advanced_local_paths,
    provider_runtime_proof,
    provider_runtime_settings,
    provider_settings_for_capabilities,
    provider_settings_response,
    redact_secret_text,
    reset_provider_settings,
    save_provider_settings,
    test_provider_settings,
)
from motionjson.provider_registry import registry_public_payload
from motionjson.providers.discovery import discovery_provider_schemas
from motionjson.providers.local_storage import LocalStorageProvider
from motionjson.review_timeline import review_timeline_payload
from motionjson.rights import build_rights_review_report, rights_review_summary


LOCAL_UI_EMAIL = "local-ui@motionjson.local"
LOCAL_UI_FORMAT = "motionjson.local_ui.v0.1"
STORAGE_KEY_ASSIGNMENT_RE = re.compile(r"(?i)\bstorage[_-]?key=([^\s&]+)")
STORAGE_KEY_PATH_RE = re.compile(r"\bprojects/[A-Za-z0-9._~!$&'()*+,;=:@%/-]+")
LOCAL_FILE_URI_RE = re.compile(r"(?i)\bfile://[^\r\n]+")
LOCAL_UI_ASSET_URI_RE = re.compile(r"^(?:local-ui|motionjson)://assets/([^/?#]+)$")
LOCAL_ABSOLUTE_PATH_RE = re.compile(
    r"(?<![\w:])(?:/(?:root|content)(?:/[^\s,;:)\]}\"']*)*|/(?:Users|private|var|tmp|Volumes|home)/[^\r\n]+)"
)
WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"(?i)(?<![\w:])(?:[A-Z]:[\\/]|\\\\)[^\r\n\"'<>|]+")
LOCAL_PATH_FIELD_NAMES = {"sourceuri", "sourcepath", "localpath"}
TERMINAL_JOB_STATUSES = {"succeeded", "failed", "canceled"}
PUBLIC_ARTIFACT_CONTENT_TYPES = ("image/", "video/")
PUBLIC_DOWNLOAD_ARTIFACT_KINDS = {
    "contours_boxes",
    "export_quality_routing",
    "export_validation_report",
    "final_export_manifest",
    "mp4_preview",
    "motionjson_export_zip",
    "object_layer_pack",
    "preview_overlay",
    "review_state_manifest",
    "validated_motionjson_scene",
    "website_package",
}
REVIEW_JSON_ARTIFACT_KINDS = {
    "candidate_summary",
    "fallback_diagnostics",
    "failure_diagnostics",
    "job_metrics",
    "job_state",
    "object_manifest",
    "partial_review",
    "provider_diagnostics",
    "review_state_manifest",
    "scene_graph",
    "selected_candidate_tracking",
    "track_summary",
}
PREVIEW_FILE_JSON_PATHS = {
    "scene_graph.json",
    "web_asset_manifest.json",
    "object_motion.json",
    "object_layer_pack.json",
    "resource_profile.json",
    "rights_manifest.json",
    "package_manifest.json",
}
PREVIEW_FILE_EXACT_PATHS = {
    "index.html",
    "preview/index.html",
    "preview/canvas_player.html",
    "preview/object_selection_workflow.html",
    "preview/object_selection_workflow.js",
    "preview/timeline_editor.html",
    "preview/timeline_editor.js",
    "preview/pixi_player.html",
    "preview/plain_js_embed.html",
    "preview/website_graphics_hero.html",
}
PREVIEW_FILE_JS_PREFIXES = ("runtime/", "preview/runtime/")
PREVIEW_FILE_TEMPLATE_PREFIXES = ("templates/", "snippets/", "preview/website_templates/", "preview/website_snippets/")
PREVIEW_FILE_OBJECT_JSON_NAMES = {"object_manifest.json", "object_motion.json", "web_asset_manifest.json"}
PREVIEW_FILE_OBJECT_ASSET_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".avif"}


def _json_loads(data: bytes) -> dict[str, Any]:
    if not data:
        return {}
    parsed = json.loads(data.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("request body must be a JSON object")
    return parsed


def _safe_upload_filename(value: str) -> str:
    name = Path(value or "uploaded-video").name.strip() or "uploaded-video"
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return safe or "uploaded-video"


def _parse_multipart_form(content_type: str, body: bytes) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
    if "multipart/form-data" not in content_type.lower():
        raise ValueError("video upload must use multipart/form-data")
    header = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8")
    message = BytesParser(policy=email_policy_default).parsebytes(header + body)
    if not message.is_multipart():
        raise ValueError("invalid multipart upload body")
    fields: dict[str, str] = {}
    files: dict[str, dict[str, Any]] = {}
    for part in message.iter_parts():
        if not part.get("content-disposition"):
            continue
        name = part.get_param("name", header="content-disposition")
        if not name:
            continue
        data = part.get_payload(decode=True) or b""
        filename = part.get_filename()
        if filename:
            files[str(name)] = {
                "filename": _safe_upload_filename(filename),
                "contentType": part.get_content_type() or "application/octet-stream",
                "bytes": data,
            }
        else:
            fields[str(name)] = data.decode(part.get_content_charset() or "utf-8", "replace")
    return fields, files


def _json_response(payload: Any, status: HTTPStatus = HTTPStatus.OK) -> tuple[int, dict[str, str], bytes]:
    return (
        int(status),
        {"content-type": "application/json; charset=utf-8", "cache-control": "no-store"},
        json.dumps(payload, sort_keys=True).encode("utf-8"),
    )


def _parse_json_field(row: dict[str, Any], field: str) -> None:
    if field in row:
        row[field.removesuffix("_json")] = json.loads(row.pop(field) or "{}")


def _is_storage_key_field(key: Any) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
    return normalized == "storagekey"


def _is_local_path_field(key: Any) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
    return normalized in LOCAL_PATH_FIELD_NAMES


def _is_secret_field(key: Any) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
    return normalized in {"apikey", "authorization", "password", "secret", "token", "hftoken"} or normalized.endswith("token")


def _redact_public_text(value: str) -> str:
    return redact_secret_text(
        WINDOWS_ABSOLUTE_PATH_RE.sub(
            "[LOCAL_PATH_REDACTED]",
            LOCAL_ABSOLUTE_PATH_RE.sub(
                "[LOCAL_PATH_REDACTED]",
                LOCAL_FILE_URI_RE.sub(
                    "[LOCAL_FILE_URI_REDACTED]",
                    STORAGE_KEY_PATH_RE.sub(
                        "[STORAGE_KEY_REDACTED]",
                        STORAGE_KEY_ASSIGNMENT_RE.sub("[REDACTED]", value),
                    ),
                ),
            ),
        )
    )


def _public_value(value: Any, *, key: Any | None = None) -> Any:
    if _is_secret_field(key) and value not in (None, "", False):
        return "[REDACTED]"
    if _is_local_path_field(key) and isinstance(value, str) and (
        value.startswith("/") or value.lower().startswith("file://") or WINDOWS_ABSOLUTE_PATH_RE.match(value)
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
    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    preview = metadata.get("browser_preview") if isinstance(metadata.get("browser_preview"), dict) else {}
    if preview:
        public_preview = {key: value for key, value in preview.items() if key not in {"contentAssetId", "posterAssetId"}}
        content_asset_id = str(preview.get("contentAssetId") or "").strip()
        poster_asset_id = str(preview.get("posterAssetId") or "").strip()
        if content_asset_id:
            public_preview["contentUrl"] = (
                f"/api/videos/{data['id']}/content" if content_asset_id == data["id"] else f"/api/assets/{content_asset_id}/content"
            )
        if poster_asset_id:
            public_preview["posterUrl"] = f"/api/assets/{poster_asset_id}/content"
        data["browserPreview"] = public_preview
    else:
        data["browserPreview"] = {
            "status": "blocked",
            "kind": "source",
            "contentUrl": f"/api/videos/{data['id']}/content",
            "posterUrl": "",
            "width": 0,
            "height": 0,
            "duration": 0.0,
            "codec": "",
            "reason": "Browser preview has not been prepared yet.",
            "errorMessage": "Browser preview has not been prepared yet.",
        }
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
    if _is_secret_field(key) and value not in (None, "", False):
        return "[REDACTED]"
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


def _event_type_set(events: list[dict[str, Any]]) -> set[str]:
    return {str(event.get("event_type") or event.get("type") or "").strip().lower() for event in events if isinstance(event, dict)}


def _public_job_snapshot(
    row: dict[str, Any],
    *,
    events: list[dict[str, Any]] | None = None,
    include_events: bool = False,
    review: dict[str, Any] | None = None,
    readiness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = _public_job(row)
    public_events = [_public_event(event) for event in events or []]
    watchdog = asset_preparation_stall_diagnostic(row, events or [])
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
    if readiness is not None and readiness.get("readyForReview") is not True and status in TERMINAL_JOB_STATUSES:
        percent = min(percent, 99)
    data["progress"] = percent
    data["percent"] = percent
    if public_events:
        data["message"] = public_events[-1].get("message")
        data["latestEventType"] = public_events[-1].get("event_type")
        data["lastEventAt"] = public_events[-1].get("created_at") or public_events[-1].get("createdAt")
    if include_events:
        data["events"] = public_events
    if readiness is not None:
        data["readiness"] = _public_review_value(readiness)
    if watchdog is not None:
        data["watchdog"] = _public_review_value({"stale": True, **watchdog})
    data["lifecycle"] = job_lifecycle_summary(data, events=public_events, review=review or {})
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


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _bbox_values(value: Any) -> tuple[float, float, float, float] | None:
    if isinstance(value, dict):
        return (
            _number(value.get("x")),
            _number(value.get("y")),
            _number(value.get("w") or value.get("width")),
            _number(value.get("h") or value.get("height")),
        )
    if isinstance(value, list) and len(value) >= 4:
        return (_number(value[0]), _number(value[1]), _number(value[2]), _number(value[3]))
    return None


def _track_source_text(track: dict[str, Any]) -> str:
    metadata = track.get("metadata") if isinstance(track.get("metadata"), dict) else {}
    discovery = track.get("discovery") if isinstance(track.get("discovery"), dict) else {}
    metadata_discovery = metadata.get("discovery") if isinstance(metadata.get("discovery"), dict) else {}
    values = [
        track.get("trackClass"),
        track.get("exportStatus"),
        track.get("exportBlockReason"),
        track.get("fallbackReason"),
        track.get("reasonCode"),
        metadata.get("fallbackReason"),
        metadata.get("fallback_reason"),
        metadata.get("reasonCode"),
        metadata.get("reason_code"),
        discovery.get("trackingProvider"),
        discovery.get("tracking_provider"),
        discovery.get("reason"),
        metadata_discovery.get("trackingProvider"),
        metadata_discovery.get("tracking_provider"),
        metadata_discovery.get("reason"),
    ]
    warnings = track.get("warnings") if isinstance(track.get("warnings"), list) else []
    metadata_warnings = metadata.get("warnings") if isinstance(metadata.get("warnings"), list) else []
    return " ".join(str(value) for value in [*values, *warnings, *metadata_warnings] if value).lower()


def _track_uses_static_keyframe_fallback(track: dict[str, Any]) -> bool:
    return bool(re.search(r"keyframe_seed_sequence|static_keyframe|keyframe proposal mask sequence", _track_source_text(track)))


def _track_motion_metrics(frames: list[dict[str, Any]]) -> dict[str, Any]:
    centers: list[tuple[float, float, int]] = []
    for frame in frames:
        if not isinstance(frame, dict) or frame.get("visible") is False:
            continue
        bbox = _bbox_values(frame.get("bbox"))
        if bbox is None:
            continue
        x, y, w, h = bbox
        centers.append((x + w / 2.0, y + h / 2.0, int(_number(frame.get("frame") or frame.get("outIndex")))))
    max_center_shift = 0.0
    path_length = 0.0
    if centers:
        first_x, first_y, _first_frame = centers[0]
        max_center_shift = max(((x - first_x) ** 2 + (y - first_y) ** 2) ** 0.5 for x, y, _frame in centers)
        path_length = sum(
            ((right[0] - left[0]) ** 2 + (right[1] - left[1]) ** 2) ** 0.5
            for left, right in zip(centers, centers[1:])
        )
    frame_span = centers[-1][2] - centers[0][2] if len(centers) >= 2 else 0
    return {
        "visibleCenterCount": len(centers),
        "trackingMotionPx": round(max_center_shift, 3),
        "centerPathLengthPx": round(path_length, 3),
        "frameSpan": frame_span,
    }


def _mask_quality_for_track(track: dict[str, Any]) -> dict[str, Any]:
    frames = track.get("frames") if isinstance(track.get("frames"), list) else []
    visible = [frame for frame in frames if isinstance(frame, dict) and frame.get("visible") is not False]
    bbox_fill_ratios: list[float] = []
    mask_area_ratios: list[float] = []
    contour_frames = 0
    outline_frames = 0
    for frame in visible:
        mask_area = _number(frame.get("maskArea") or frame.get("area"))
        bbox = _bbox_values(frame.get("bbox"))
        if bbox is not None:
            _x, _y, w, h = bbox
            bbox_area = max(1.0, w * h)
            if mask_area > 0:
                bbox_fill_ratios.append(max(0.0, min(mask_area / bbox_area, 1.0)))
        shape = frame.get("maskShape")
        if isinstance(shape, list) and len(shape) >= 2:
            frame_area = max(1.0, _number(shape[0]) * _number(shape[1]))
            if mask_area > 0:
                mask_area_ratios.append(max(0.0, min(mask_area / frame_area, 1.0)))
        contour_points = int(_number(frame.get("contourPoints")))
        polygon = frame.get("polygon") if isinstance(frame.get("polygon"), list) else []
        if contour_points > 0 or polygon:
            outline_frames += 1
        if contour_points > 8 or len(polygon) > 4:
            contour_frames += 1
    frame_count = max(1, len(frames))
    visible_ratio = len(visible) / frame_count
    bbox_fill_ratio = sum(bbox_fill_ratios) / len(bbox_fill_ratios) if bbox_fill_ratios else 0.0
    mask_area_ratio = sum(mask_area_ratios) / len(mask_area_ratios) if mask_area_ratios else 0.0
    outline_tightness = 0.0 if not visible else outline_frames / len(visible)
    motion = _track_motion_metrics([frame for frame in frames if isinstance(frame, dict)])
    status = "good"
    if _track_uses_static_keyframe_fallback(track):
        status = "needs_refinement"
    elif not outline_frames:
        status = "needs_refinement"
    elif mask_area_ratio >= 0.45 or bbox_fill_ratio >= 0.96:
        status = "needs_refinement"
    elif track.get("confidence") is not None and _number(track.get("confidence"), 1.0) < 0.45:
        status = "needs_refinement"
    return {
        "outlineTightness": round(outline_tightness, 4),
        "bboxFillRatio": round(bbox_fill_ratio, 4),
        "maskAreaRatio": round(mask_area_ratio, 4),
        "temporalStability": round(visible_ratio, 4),
        "trackingMotionPx": motion["trackingMotionPx"],
        "centerPathLengthPx": motion["centerPathLengthPx"],
        "qualityStatus": status,
        "outlineFrameCount": outline_frames,
        "realContourFrameCount": contour_frames,
    }


def _enrich_track_review_summary(track: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(track)
    metadata = enriched.get("metadata") if isinstance(enriched.get("metadata"), dict) else {}
    status = str(enriched.get("exportStatus") or "accepted").lower()
    static_fallback = _track_uses_static_keyframe_fallback(enriched)
    mask_quality = _mask_quality_for_track(enriched)
    if static_fallback:
        track_class = "static_fallback"
        export_eligibility = "blocked"
        export_block_reason = "static_keyframe_mask_sequence"
    elif re.search(r"deleted|rejected|failed|fallback_raster", status):
        track_class = "rejected_candidate" if "rejected" in status else "diagnostic_only"
        export_eligibility = "blocked"
        export_block_reason = status
    elif re.search(r"pending|needs_review|review_pending|awaiting_review", status):
        track_class = "needs_refinement" if mask_quality["qualityStatus"] == "needs_refinement" else "moving_track"
        export_eligibility = "needs_review"
        export_block_reason = ""
    else:
        track_class = "needs_refinement" if mask_quality["qualityStatus"] == "needs_refinement" else "moving_track"
        export_eligibility = "eligible"
        export_block_reason = ""
    enriched["trackClass"] = track_class
    enriched["exportEligibility"] = export_eligibility
    if export_block_reason:
        enriched["exportBlockReason"] = export_block_reason
    enriched["maskQuality"] = mask_quality
    if static_fallback:
        enriched["exportIncluded"] = False
        enriched["metadata"] = {
            **metadata,
            "fallbackReason": "static_keyframe_mask_sequence",
            "diagnosticOnly": True,
        }
    return enriched


def _track_review_summary(track: dict[str, Any]) -> dict[str, Any]:
    frames = track.get("frames") if isinstance(track.get("frames"), list) else []
    return _enrich_track_review_summary({
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
                "sampleIndex": frame.get("sampleIndex"),
                "sourceFrameIndex": frame.get("sourceFrameIndex"),
                "outIndex": frame.get("outIndex"),
                "sampleFps": frame.get("sampleFps"),
                "t": frame.get("t"),
                "visible": frame.get("visible"),
                "area": frame.get("area"),
                "bbox": frame.get("bbox"),
                "sourceBbox": frame.get("sourceBbox"),
                "centroid": frame.get("centroid"),
                "mask": frame.get("mask"),
                "maskArea": frame.get("maskArea"),
                "maskShape": frame.get("maskShape"),
                "asset": frame.get("asset"),
                "contourPoints": frame.get("contourPoints"),
                "outlineStatus": frame.get("outlineStatus"),
                "outlineSource": frame.get("outlineSource"),
                "polygon": frame.get("polygon"),
            }
            for frame in frames
            if isinstance(frame, dict)
        ],
    })


def _scene_object_review_summary(item: dict[str, Any]) -> dict[str, Any]:
    motion = item.get("motion") if isinstance(item.get("motion"), list) else []
    visible_motion = [frame for frame in motion if isinstance(frame, dict) and frame.get("visible")]
    rights = item.get("rights") if isinstance(item.get("rights"), dict) else {}
    return {
        "objectId": item.get("id") or item.get("objectId"),
        "label": item.get("label"),
        "renderMode": item.get("renderMode"),
        "recommendedOutput": item.get("recommendedOutput"),
        "zIndex": item.get("zIndex"),
        "frameCount": len(motion),
        "visibleFrameCount": len(visible_motion),
        "quality": item.get("quality", {}),
        "rightsSummary": rights_review_summary(rights),
        "firstVisibleFrame": visible_motion[0].get("frame") if visible_motion else None,
        "lastVisibleFrame": visible_motion[-1].get("frame") if visible_motion else None,
    }


def _object_manifest_review_summary(item: dict[str, Any]) -> dict[str, Any]:
    motion = item.get("motion") if isinstance(item.get("motion"), list) else []
    visible_motion = [frame for frame in motion if isinstance(frame, dict) and frame.get("visible")]
    return {
        "objectId": item.get("objectId"),
        "label": item.get("label"),
        "renderMode": item.get("renderMode"),
        "recommendedOutput": item.get("recommendedOutput"),
        "frameCount": len(motion),
        "visibleFrameCount": len(visible_motion),
        "quality": item.get("quality", {}),
        "firstVisibleFrame": visible_motion[0].get("frame") if visible_motion else None,
        "lastVisibleFrame": visible_motion[-1].get("frame") if visible_motion else None,
    }


def _object_manifest_track_summary(item: dict[str, Any]) -> dict[str, Any]:
    manifest_frames = item.get("frames") if isinstance(item.get("frames"), list) else []
    motion = manifest_frames or (item.get("motion") if isinstance(item.get("motion"), list) else [])
    visible_motion = [frame for frame in motion if isinstance(frame, dict) and frame.get("visible")]
    discovery = item.get("discovery") if isinstance(item.get("discovery"), dict) else {}
    return _enrich_track_review_summary({
        "objectId": item.get("objectId"),
        "label": item.get("label"),
        "source": "object_manifest",
        "providerName": discovery.get("trackingProvider") or discovery.get("candidateProvider"),
        "frameCount": len(motion),
        "visibleFrameCount": len(visible_motion),
        "exportStatus": discovery.get("exportStatus") or item.get("exportStatus") or "accepted",
        "warnings": item.get("warnings", []),
        "metadata": {
            "partialObjectManifest": True,
            "recommendedOutput": item.get("recommendedOutput"),
            "frameMap": item.get("frameMap") if isinstance(item.get("frameMap"), list) else [],
            "discovery": discovery,
        },
        "discovery": discovery,
        "frames": [
            {
                "frame": frame.get("frame"),
                "sampleIndex": frame.get("sampleIndex"),
                "sourceFrameIndex": frame.get("sourceFrameIndex"),
                "outIndex": frame.get("outIndex"),
                "sampleFps": frame.get("sampleFps"),
                "t": frame.get("t"),
                "visible": frame.get("visible"),
                "area": frame.get("area"),
                "bbox": frame.get("bbox") or ([frame.get("x"), frame.get("y"), frame.get("w"), frame.get("h")] if frame.get("visible") else None),
                "sourceBbox": frame.get("sourceBbox"),
                "centroid": frame.get("centroid"),
                "mask": frame.get("mask"),
                "maskArea": frame.get("maskArea"),
                "maskShape": frame.get("maskShape"),
                "asset": frame.get("asset"),
                "contourPoints": frame.get("contourPoints"),
                "outlineStatus": frame.get("outlineStatus"),
                "outlineSource": frame.get("outlineSource"),
                "polygon": frame.get("polygon"),
            }
            for frame in motion
            if isinstance(frame, dict)
        ],
    })


def _append_unique_by_object_id(items: list[dict[str, Any]], item: dict[str, Any]) -> None:
    object_id = item.get("objectId")
    if object_id and any(existing.get("objectId") == object_id for existing in items if isinstance(existing, dict)):
        return
    items.append(item)


def _append_unique_fallback(review: dict[str, Any], item: Any, seen: set[str]) -> None:
    if not isinstance(item, dict):
        return
    public_item = _public_review_value(item)
    key = json.dumps(public_item, sort_keys=True)
    if key in seen:
        return
    seen.add(key)
    review["fallbackDiagnostics"].append(public_item)


def _artifact_ids_by_rel_path(assets: list[dict[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for asset in assets:
        try:
            metadata = json.loads(asset.get("metadata_json") or "{}")
        except (TypeError, json.JSONDecodeError):
            metadata = {}
        if not isinstance(metadata, dict):
            continue
        rel_path = metadata.get("rel_path")
        if isinstance(rel_path, str) and rel_path:
            result[rel_path.replace("\\", "/")] = str(asset.get("id") or "")
    return {key: value for key, value in result.items() if value}


def _asset_rel_path(asset: dict[str, Any]) -> str:
    try:
        metadata = json.loads(asset.get("metadata_json") or "{}")
    except (TypeError, json.JSONDecodeError):
        metadata = {}
    if not isinstance(metadata, dict):
        return ""
    rel_path = metadata.get("rel_path")
    return rel_path.replace("\\", "/").lstrip("/") if isinstance(rel_path, str) else ""


def _normalize_preview_rel_path(value: str) -> str:
    rel_path = unquote(value).replace("\\", "/")
    if rel_path.startswith("/"):
        raise NotFoundError("preview file not found")
    while rel_path.startswith("./"):
        rel_path = rel_path[2:]
    parsed = PurePosixPath(rel_path)
    if not rel_path or parsed.is_absolute() or any(part in {"", ".", ".."} for part in parsed.parts):
        raise NotFoundError("preview file not found")
    return parsed.as_posix()


def _is_allowed_preview_rel_path(rel_path: str) -> bool:
    path = PurePosixPath(rel_path)
    name = path.name
    suffix = path.suffix.lower()
    if rel_path in PREVIEW_FILE_JSON_PATHS or rel_path in PREVIEW_FILE_EXACT_PATHS:
        return True
    if any(rel_path.startswith(prefix) for prefix in PREVIEW_FILE_JS_PREFIXES) and suffix == ".js":
        return True
    if any(rel_path.startswith(prefix) for prefix in PREVIEW_FILE_TEMPLATE_PREFIXES) and suffix in {".html", ".jsx"}:
        return True
    if len(path.parts) >= 3 and path.parts[0] == "objects":
        if name in PREVIEW_FILE_OBJECT_JSON_NAMES:
            return True
        if name == "spritesheet.webp":
            return True
        if "cutouts" in path.parts and suffix in PREVIEW_FILE_OBJECT_ASSET_EXTS:
            return True
    return False


class LocalUIApp:
    """Small local-only UI app over the existing SQLite backend."""

    def __init__(self, *, db_path: str | Path, storage_root: str | Path, mock_mode: bool = False):
        self.db_path = Path(db_path)
        self.storage_root = Path(storage_root)
        self.mock_mode = mock_mode
        self._worker_lock = threading.Lock()
        self._worker_thread: threading.Thread | None = None
        self._provider_setup_lock = threading.Lock()
        self._provider_setup_threads: dict[str, threading.Thread] = {}
        self.model_connectors = ModelConnectorRegistry()
        self.model_runs = VolatileModelRunStore(max_runs=128)

    def connection(self) -> sqlite3.Connection:
        return initialize_database(connect(self.db_path))

    def storage(self) -> LocalStorageProvider:
        return LocalStorageProvider(self.storage_root)

    def _public_video_payload(self, conn: sqlite3.Connection, *, user_id: str, asset: dict[str, Any], prepare_preview: bool = False, force_preview: bool = False) -> dict[str, Any]:
        if prepare_preview:
            try:
                prepare_browser_preview(
                    conn,
                    storage=self.storage(),
                    user_id=user_id,
                    source_asset_id=str(asset["id"]),
                    force=force_preview,
                )
                asset = get_asset(conn, user_id=user_id, asset_id=str(asset["id"]))
            except Exception as exc:
                metadata = json.loads(asset.get("metadata_json") or "{}")
                if not isinstance(metadata, dict):
                    metadata = {}
                metadata["browser_preview"] = {
                    "status": "failed",
                    "kind": "source",
                    "contentAssetId": str(asset["id"]),
                    "posterAssetId": "",
                    "width": 0,
                    "height": 0,
                    "duration": 0.0,
                    "codec": "",
                    "reason": _redact_public_text(str(exc)),
                    "errorMessage": _redact_public_text(str(exc)),
                    "contentType": asset.get("content_type") or "video/mp4",
                }
                asset["metadata_json"] = json.dumps(metadata, sort_keys=True)
        return _public_video(asset)

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
            if method in {"GET", "HEAD"} and path.startswith("/api/assets/") and path.endswith("/content"):
                parts = [part for part in path.split("/") if part]
                if len(parts) == 4:
                    return self._asset_content(parts[2], head=method == "HEAD")
            if method in {"GET", "HEAD"} and path.startswith("/api/artifacts/") and path.endswith("/content"):
                parts = [part for part in path.split("/") if part]
                if len(parts) == 4:
                    return self._artifact_content(parts[2], head=method == "HEAD")
            if method in {"GET", "HEAD"} and path.startswith("/api/jobs/") and "/preview-files/" in path:
                parts = [part for part in path.split("/") if part]
                if len(parts) >= 5 and parts[0] == "api" and parts[1] == "jobs" and parts[3] == "preview-files":
                    return self._preview_file_content(parts[2], "/".join(parts[4:]), head=method == "HEAD")
            if method == "POST" and path == "/api/videos/upload":
                content_type = next((value for key, value in request_headers.items() if key.lower() == "content-type"), "")
                fields, files = _parse_multipart_form(content_type, body)
                conn = self.connection()
                try:
                    user = self._local_user(conn)
                    return _json_response(self._upload_video_form(conn, user_id=user["id"], fields=fields, files=files))
                finally:
                    conn.close()
            payload = _json_loads(body) if method in {"POST", "PATCH", "PUT", "DELETE"} else {}
            return _json_response(self._route(method, path, query, payload))
        except json.JSONDecodeError as exc:
            return self._error(HTTPStatus.BAD_REQUEST, f"invalid json: {exc}")
        except NotFoundError as exc:
            return self._error(HTTPStatus.NOT_FOUND, str(exc))
        except FileNotFoundError as exc:
            return self._error(HTTPStatus.BAD_REQUEST, str(exc))
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
                    "/api/workspace",
                    "/api/preferences",
                    "/api/commercial-readiness",
                    "/api/capabilities",
                    "/api/provider-registry",
                    "/api/provider-settings",
                    "/api/provider-settings/{providerId}",
                    "/api/provider-settings/{providerId}/test",
                    "/api/provider-settings/{providerId}/diagnose",
                    "/api/provider-settings/{providerId}/smoke-test",
                    "/api/provider-settings/{providerId}/advanced-local-paths",
                    "/api/provider-settings/{providerId}/setup/start",
                    "/api/provider-settings/setup-jobs/{jobId}",
                    "/api/provider-settings/setup-jobs/{jobId}/cancel",
                    "/api/model-providers",
                    "/api/model-providers/{providerId}",
                    "/api/model-providers/{providerId}/test",
                    "/api/model-providers/{providerId}/estimate",
                    "/api/model-runs",
                    "/api/model-runs/{runId}",
                    "/api/model-runs/{runId}/events",
                    "/api/model-runs/{runId}/cancel",
                    "/api/model-runs/{runId}/confirm-job",
                    "/api/projects",
                    "/api/videos",
                    "/api/videos/upload",
                    "/api/videos/{videoId}/content",
                    "/api/videos/{videoId}/prepare-browser-preview",
                    "/api/run-config/defaults",
                    "/api/run-config/validate",
                    "/api/jobs",
                    "/api/jobs/{jobId}",
                    "/api/jobs/{jobId}/events",
                    "/api/jobs/{jobId}/artifacts",
                    "/api/jobs/{jobId}/preview-files/{relPath}",
                    "/api/jobs/{jobId}/review-tools",
                    "/api/jobs/{jobId}/review",
                    "/api/jobs/{jobId}/corrections",
                    "/api/jobs/{jobId}/track-edits",
                    "/api/jobs/{jobId}/track-selected",
                    "/api/jobs/{jobId}/cancel",
                    "/api/jobs/{jobId}/validate",
                    "/api/jobs/{jobId}/exports",
                    "/api/jobs/{jobId}/exports/motionjson",
                    "/api/jobs/{jobId}/model-plan",
                    "/api/jobs/{jobId}/run",
                    "/api/progress",
                    "/api/artifacts",
                    "/api/assets/{assetId}/content",
                    "/api/artifacts/{artifactId}/content",
                    "/api/exports/formats",
                    "/api/library/assets",
                    "/api/library/assets/{libraryAssetId}",
                    "/api/library/collections",
                    "/api/library/collections/{collectionId}/assets",
                    "/api/library/packs",
                    "/api/projects/{projectId}/library-assets",
                    "/api/projects/{projectId}/imports/motionjson",
                ],
            }
        if path == "/api/capabilities" and method == "GET":
            return _public_value(
                self._capability_report(
                    video_path=self._query_one(query, "video") or self._query_one(query, "videoPath"),
                    output_dir=self._query_one(query, "outputDir") or self._query_one(query, "output"),
                )
            )
        if path == "/api/provider-registry" and method == "GET":
            return _public_value(registry_public_payload())
        if path == "/api/provider-settings" and method == "GET":
            return self._provider_settings_response()
        if path == "/api/provider-settings" and method == "POST":
            return self._save_provider_settings(payload)
        if path.startswith("/api/provider-settings/"):
            parts = [part for part in path.split("/") if part]
            if len(parts) == 4 and parts[2] == "setup-jobs" and method == "GET":
                return self._provider_setup_job_response(parts[3])
            if len(parts) == 5 and parts[2] == "setup-jobs" and parts[4] == "cancel" and method == "POST":
                return self._cancel_provider_setup_job(parts[3], payload)
            if len(parts) == 5 and parts[3] == "setup" and parts[4] == "start" and method == "POST":
                return self._start_provider_setup_job(parts[2], payload)
            if len(parts) == 3 and method == "DELETE":
                return self._reset_provider_settings(parts[2])
            if len(parts) == 4 and parts[3] == "test" and method == "POST":
                return self._test_provider_settings(parts[2])
            if len(parts) == 4 and parts[3] == "diagnose" and method == "POST":
                return self._diagnose_provider_settings(parts[2], payload)
            if len(parts) == 4 and parts[3] == "smoke-test" and method == "POST":
                return self._smoke_test_provider_settings(parts[2], payload)
            if len(parts) == 4 and parts[3] == "advanced-local-paths" and method == "GET":
                return self._advanced_local_paths(parts[2])
        if path == "/api/model-providers" and method == "GET":
            return self._model_providers_response()
        if path.startswith("/api/model-providers/"):
            parts = [part for part in path.split("/") if part]
            if len(parts) == 3 and method == "GET":
                return self._model_provider_response(parts[2])
            if len(parts) == 4 and parts[3] == "test" and method == "POST":
                return self._test_model_provider(parts[2], payload)
            if len(parts) == 4 and parts[3] == "estimate" and method == "POST":
                return self._estimate_model_provider(parts[2], payload)
        if path == "/api/model-runs" and method == "POST":
            return self._start_model_run(payload)
        if path.startswith("/api/model-runs/"):
            parts = [part for part in path.split("/") if part]
            if len(parts) == 3 and method == "GET":
                return self._model_run_response(parts[2])
            if len(parts) == 4 and parts[3] == "events" and method == "GET":
                return self._model_run_events_response(parts[2])
            if len(parts) == 4 and parts[3] == "cancel" and method == "POST":
                return self._cancel_model_run(parts[2], payload)
            if len(parts) == 4 and parts[3] == "confirm-job" and method == "POST":
                return self._confirm_model_plan_job(parts[2], payload)
        if path == "/api/run-config/defaults" and method == "GET":
            return {
                "format": "motionjson.local_ui_run_config_defaults.v0.1",
                "maskProviders": sorted(MASK_PROVIDERS),
                "discoveryProviders": sorted(DISCOVERY_MODES),
                "discoveryProviderSchemas": discovery_provider_schemas(),
                "defaults": {
                    "maskProvider": "mock" if self.mock_mode else "sam2-local",
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
                    {"id": "motionjson", "label": "Validated MotionJSON", "requires": []},
                    {"id": "mp4", "label": "MP4 final video", "requires": ["ffmpeg"]},
                    {"id": "webm-alpha", "label": "Transparent WebM object", "requires": ["ffmpeg"]},
                    {"id": "website-zip", "label": "Website package", "requires": []},
                    {"id": "remotion-plan", "label": "Remotion adapter plan", "requires": []},
                ],
                "presets": export_presets(),
            }

        conn = self.connection()
        try:
            user = self._local_user(conn)
            user_id = user["id"]
            if path == "/api/workspace" and method == "GET":
                settings = provider_settings_response(conn, user_id=user_id)
                workspace = workspace_response(
                    conn,
                    user_id=user_id,
                    provider_settings=settings,
                    export_presets_payload=export_presets(),
                )
                workspace["jobCenter"] = self._job_center_payload(conn, user_id=user_id)
                return _public_value(workspace)
            if path == "/api/preferences" and method == "GET":
                return _public_value(get_workspace_preferences(conn, user_id=user_id))
            if path == "/api/preferences" and method == "POST":
                return _public_value(save_workspace_preferences(conn, user_id=user_id, payload=payload))
            if path == "/api/commercial-readiness" and method == "GET":
                return _public_value(commercial_readiness_response(conn, user_id=user_id))
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
            if path == "/api/library/assets" and method == "GET":
                return _public_value(list_library_assets(conn, user_id=user_id, filters=self._library_filters(query)))
            if path.startswith("/api/library/assets/") and method == "GET":
                parts = [part for part in path.split("/") if part]
                if len(parts) == 4:
                    return {"libraryAsset": _public_value(get_library_asset(conn, user_id=user_id, library_asset_id=parts[3]))}
            if path == "/api/library/collections" and method == "GET":
                return _public_value(list_collections(conn, user_id=user_id))
            if path == "/api/library/collections" and method == "POST":
                collection = create_collection(
                    conn,
                    user_id=user_id,
                    title=str(payload.get("title") or payload.get("name") or ""),
                    description=str(payload.get("description") or ""),
                    project_id=payload.get("projectId"),
                    metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
                )
                return {"collection": _public_value(collection)}
            if path.startswith("/api/library/collections/"):
                parts = [part for part in path.split("/") if part]
                if len(parts) == 5 and parts[4] == "assets" and method == "GET":
                    return _public_value(list_collection_assets(conn, user_id=user_id, collection_id=parts[3]))
                if len(parts) == 5 and parts[4] == "assets" and method == "POST":
                    added = add_asset_to_collection(
                        conn,
                        user_id=user_id,
                        collection_id=parts[3],
                        library_asset_id=str(payload.get("libraryAssetId") or ""),
                    )
                    return {"collectionAsset": _public_value(added)}
            if path == "/api/library/packs" and method == "GET":
                return _public_value(list_creator_packs(conn, user_id=user_id))
            if path == "/api/library/packs" and method == "POST":
                pack = create_creator_pack(
                    conn,
                    user_id=user_id,
                    collection_id=str(payload.get("collectionId") or ""),
                    title=str(payload.get("title") or payload.get("name") or ""),
                    description=str(payload.get("description") or ""),
                    library_asset_ids=payload.get("libraryAssetIds") if isinstance(payload.get("libraryAssetIds"), list) else None,
                    metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
                )
                return {"pack": _public_value(pack)}
            if path.startswith("/api/projects/") and method == "POST":
                parts = [part for part in path.split("/") if part]
                if len(parts) == 4 and parts[3] == "library-assets":
                    library_asset = save_library_asset(
                        conn,
                        user_id=user_id,
                        project_id=parts[2],
                        asset_id=str(payload.get("assetId") or ""),
                        type=str(payload.get("type") or "saved_asset"),
                        title=str(payload.get("title") or ""),
                        description=str(payload.get("description") or ""),
                        tags=payload.get("tags") if isinstance(payload.get("tags"), list) else None,
                        metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
                    )
                    public_asset = _public_value(library_asset)
                    return {"libraryAsset": public_asset, "asset": public_asset}
                if len(parts) == 5 and parts[3] == "imports" and parts[4] == "motionjson":
                    imported = import_motionjson_result(
                        conn,
                        storage=self.storage(),
                        user_id=user_id,
                        project_id=parts[2],
                        path=str(payload.get("path") or ""),
                    )
                    assets = [_public_value(self._public_artifact(asset)) for asset in imported["assets"]]
                    return {
                        "import": _public_value(
                            {
                                **imported,
                                "job": self._public_job_snapshot_for_job(conn, imported["job"]),
                                "assets": assets,
                            }
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
                return {"videos": [self._public_video_payload(conn, user_id=user_id, asset=asset, prepare_preview=True) for asset in videos]}
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
                return {"video": self._public_video_payload(conn, user_id=user_id, asset=asset, prepare_preview=True, force_preview=True)}
            if path.startswith("/api/videos/"):
                parts = [part for part in path.split("/") if part]
                if len(parts) == 4 and parts[3] == "prepare-browser-preview" and method == "POST":
                    asset = get_asset(conn, user_id=user_id, asset_id=parts[2])
                    return {
                        "video": self._public_video_payload(
                            conn,
                            user_id=user_id,
                            asset=asset,
                            prepare_preview=True,
                            force_preview=True,
                        )
                    }
            if path == "/api/jobs" and method == "GET":
                project_id = self._query_one(query, "projectId")
                if not project_id:
                    return {"jobs": []}
                jobs = []
                for job in list_jobs(conn, user_id=user_id, project_id=project_id):
                    jobs.append(self._public_job_snapshot_for_job(conn, job))
                return {"jobs": jobs}
            if path == "/api/jobs" and method == "POST":
                job = self._enqueue_extract_from_ui_payload(conn, user_id=user_id, payload=payload)
                response: dict[str, Any] = {
                    "job": self._public_job_snapshot_for_job(conn, job)
                }
                if self._payload_requests_worker(payload):
                    record_job_event(
                        conn,
                        job_id=job["id"],
                        event_type="worker_start_requested",
                        message="workspace worker start requested",
                        metadata={"source": "workspace"},
                    )
                    response["worker"] = self._start_worker()
                    response["job"] = self._public_job_snapshot_for_job(conn, get_job(conn, user_id=user_id, job_id=job["id"]))
                return response
            if path == "/api/progress" and method == "GET":
                project_id = self._query_one(query, "projectId")
                if not project_id:
                    return {"progress": [], "jobCenter": self._job_center_payload(conn, user_id=user_id)}
                progress = []
                for job in list_jobs(conn, user_id=user_id, project_id=project_id):
                    public_job = self._public_job_snapshot_for_job(conn, job, include_events=True)
                    progress.append(public_job)
                return {"progress": progress, "jobCenter": self._job_center_payload(conn, user_id=user_id, project_id=project_id)}
            if path.startswith("/api/jobs/") and method == "POST":
                parts = [part for part in path.split("/") if part]
                if len(parts) == 4 and parts[3] == "model-plan":
                    return self._attach_model_plan_to_job(conn, user_id=user_id, job_id=parts[2], payload=payload)
                if len(parts) == 4 and parts[3] == "cancel":
                    get_job(conn, user_id=user_id, job_id=parts[2])
                    canceled = request_cancel_job(conn, job_id=parts[2], reason=str(payload.get("reason") or "user_canceled"))
                    return {"job": self._public_job_snapshot_for_job(conn, canceled, include_events=True)}
                if len(parts) == 4 and parts[3] == "run":
                    job = get_job(conn, user_id=user_id, job_id=parts[2])
                    if job["status"] in TERMINAL_JOB_STATUSES:
                        return {
                            "job": self._public_job_snapshot_for_job(conn, job),
                            "worker": {"status": "not_started", "reason": "job is already terminal"},
                        }
                    record_job_event(
                        conn,
                        job_id=job["id"],
                        event_type="worker_start_requested",
                        message="workspace worker start requested",
                        metadata={"source": "workspace"},
                    )
                    return {
                        "job": self._public_job_snapshot_for_job(conn, get_job(conn, user_id=user_id, job_id=job["id"])),
                        "worker": self._start_worker(),
                    }
                if len(parts) == 4 and parts[3] == "track-selected":
                    result = track_selected_candidates(
                        conn,
                        storage=self.storage(),
                        user_id=user_id,
                        job_id=parts[2],
                        payload=payload,
                    )
                    assets = result.pop("assets")
                    corrections = list_track_corrections(conn, user_id=user_id, job_id=parts[2])
                    response = self._artifacts_response(assets, corrections=corrections, job_id=parts[2])
                    response["trackSelected"] = _public_review_value(result)
                    return response
                if len(parts) == 4 and parts[3] in {"corrections", "track-edits"}:
                    job = get_job(conn, user_id=user_id, job_id=parts[2])
                    action_payload = payload.get("action") or payload.get("correction") or payload
                    if parts[3] == "track-edits":
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
                    review = self._review_metadata(assets, corrections=corrections, job_id=parts[2])
                    review_manifest = write_review_state_manifest(
                        conn,
                        storage=self.storage(),
                        user_id=user_id,
                        job_id=parts[2],
                        review=review,
                    )
                    assets = list_assets_for_job(conn, project_id=job["project_id"], source_job_id=parts[2])
                    review = self._review_metadata(assets, corrections=corrections, job_id=parts[2])
                    response: dict[str, Any] = {
                        **_public_review_value(edit_result),
                        "correction": _public_review_value(correction),
                        "correctionState": _public_review_value(correction_state),
                        "corrections": _public_review_value(correction_state),
                        "reviewStateManifest": _public_value(self._public_artifact(review_manifest["asset"])),
                        "review": review,
                    }
                    result = correction.get("result") if isinstance(correction.get("result"), dict) else {}
                    if isinstance(result.get("repairDiagnostics"), dict):
                        response["repairDiagnostics"] = _public_review_value(result["repairDiagnostics"])
                    if isinstance(result.get("partialRerun"), dict):
                        response["partialRerun"] = _public_review_value(result["partialRerun"])
                    return response
                if len(parts) == 4 and parts[3] == "validate":
                    get_job(conn, user_id=user_id, job_id=parts[2])
                    validation = validate_motionjson_export_job(
                        conn,
                        storage=self.storage(),
                        user_id=user_id,
                        job_id=parts[2],
                        preset=str(payload.get("preset") or "compact"),
                        include_masks=payload.get("includeMasks"),
                        include_contours=payload.get("includeContours"),
                        include_preview=payload.get("includePreview"),
                    )
                    return _public_value(validation)
                if (len(parts) == 4 and parts[3] == "exports") or (
                    len(parts) == 5 and parts[3] == "exports" and parts[4] == "motionjson"
                ):
                    job = get_job(conn, user_id=user_id, job_id=parts[2])
                    exported = export_motionjson_job(
                        conn,
                        storage=self.storage(),
                        user_id=user_id,
                        job_id=parts[2],
                        preset=str(payload.get("preset") or "compact"),
                        include_masks=payload.get("includeMasks"),
                        include_contours=payload.get("includeContours"),
                        include_preview=payload.get("includePreview"),
                    )
                    corrections = list_track_corrections(conn, user_id=user_id, job_id=parts[2])
                    assets = [_public_value(self._public_artifact(asset)) for asset in exported["assets"]]
                    return _public_value(
                        {
                            "export": {**exported, "assets": assets},
                            "artifacts": assets,
                            "review": self._review_metadata(
                                list_assets_for_job(conn, project_id=job["project_id"], source_job_id=parts[2]),
                                corrections=corrections,
                                job_id=parts[2],
                            ),
                        }
                    )
            if path.startswith("/api/jobs/") and method == "GET":
                parts = [part for part in path.split("/") if part]
                if len(parts) == 3:
                    job = get_job(conn, user_id=user_id, job_id=parts[2])
                    return {"job": self._public_job_snapshot_for_job(conn, job, include_events=True)}
                if len(parts) == 4 and parts[3] == "events":
                    job = get_job(conn, user_id=user_id, job_id=parts[2])
                    return {
                        "job": self._public_job_snapshot_for_job(conn, job),
                        "events": [_public_event(event) for event in list_job_events(conn, job_id=parts[2])],
                    }
                if len(parts) == 4 and parts[3] == "artifacts":
                    job = get_job(conn, user_id=user_id, job_id=parts[2])
                    assets = list_assets_for_job(conn, project_id=job["project_id"], source_job_id=parts[2])
                    corrections = list_track_corrections(conn, user_id=user_id, job_id=parts[2])
                    return self._artifacts_response(assets, corrections=corrections, job_id=parts[2])
                if len(parts) == 4 and parts[3] == "review-tools":
                    job = get_job(conn, user_id=user_id, job_id=parts[2])
                    events = list_job_events(conn, job_id=parts[2])
                    assets = list_assets_for_job(conn, project_id=job["project_id"], source_job_id=parts[2])
                    corrections = list_track_corrections(conn, user_id=user_id, job_id=parts[2])
                    review = self._review_metadata(assets, corrections=corrections, job_id=parts[2])
                    readiness = self._job_readiness_for_assets(job, assets=assets, events=events, review=review)
                    active = str(job.get("status") or "").lower() in {"pending", "queued", "running", "cancel_requested"}
                    return {
                        "jobId": parts[2],
                        "readiness": readiness,
                        "tools": review_tool_statuses(
                            job_id=parts[2],
                            rel_paths=[_asset_rel_path(asset) for asset in assets],
                            job_active=active,
                        ),
                    }
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

    def _model_provider_id_from_payload(self, payload: dict[str, Any]) -> str:
        return str(
            payload.get("providerId")
            or payload.get("provider_id")
            or self.model_connectors.default_provider_id()
        )

    def _model_plan_request_from_payload(self, payload: dict[str, Any]) -> ModelPlanRequest:
        request_payload = payload.get("request") if isinstance(payload.get("request"), dict) else payload
        return ModelPlanRequest.from_dict(request_payload)

    def _model_provider_settings_snapshot(self) -> dict[str, Any]:
        conn = self.connection()
        try:
            user = self._local_user(conn)
            return provider_settings_response(conn, user_id=user["id"])
        finally:
            conn.close()

    @staticmethod
    def _settings_provider_state(settings_payload: dict[str, Any], provider_id: str) -> dict[str, Any]:
        for provider in settings_payload.get("providers", []):
            if isinstance(provider, dict) and provider.get("id") == provider_id:
                return provider
        raise ValueError(f"Unknown provider settings id for model connector: {provider_id}")

    def _model_connector_readiness(self, connector: Any, settings_payload: dict[str, Any] | None = None) -> dict[str, Any]:
        base = dict(connector.readiness())
        base.setdefault("networkAttempted", False)
        base.setdefault("hostedCallsRequired", connector.provider.hosted_calls_required)
        settings_provider_id = connector.provider.settings_provider_id
        if not settings_provider_id:
            return base

        settings_payload = settings_payload or self._model_provider_settings_snapshot()
        settings_state = self._settings_provider_state(settings_payload, settings_provider_id)
        provider_readiness = settings_state.get("readiness") if isinstance(settings_state.get("readiness"), dict) else {}
        provider_settings = settings_state.get("settings") if isinstance(settings_state.get("settings"), dict) else {}
        provider_proof = settings_state.get("runtimeProof") if isinstance(settings_state.get("runtimeProof"), dict) else {}
        credentials = settings_state.get("credentials") if isinstance(settings_state.get("credentials"), list) else []
        configured = bool(provider_readiness.get("configured"))
        hosted_allowed = bool(provider_settings.get("allowHosted"))
        hosted_required = bool(connector.provider.hosted_calls_required)

        status = str(provider_readiness.get("status") or base.get("status") or "not_configured")
        message = str(provider_readiness.get("message") or base.get("message") or "")
        if configured and hosted_required and not hosted_allowed:
            status = "hosted_opt_in_required"
            message = (
                f"{settings_state.get('name') or settings_provider_id} settings are configured, "
                "but hosted calls remain disabled until cost and privacy are confirmed."
            )
        elif configured and not connector.provider.implemented:
            status = "configured_settings_only"
            message = (
                f"{settings_state.get('name') or settings_provider_id} settings are configured. "
                "This hosted planning connector is not implemented yet, so no hosted network call will be made."
            )
        elif configured:
            status = str(base.get("status") or "ready")
            message = str(base.get("message") or message)

        runnable = bool(
            connector.provider.implemented
            and configured
            and (not hosted_required or hosted_allowed)
            and (not provider_proof or provider_proof.get("allowsRun") is True)
            and base.get("runnable", True)
        )
        return {
            **base,
            "status": status,
            "configured": configured,
            "runnable": runnable,
            "networkAttempted": False,
            "networkRequired": connector.provider.network_required,
            "hostedCallsRequired": hosted_required,
            "hostedCallsAllowed": hosted_allowed,
            "settingsProviderId": settings_provider_id,
            "settingsProvider": {
                "id": settings_state.get("id"),
                "name": settings_state.get("name"),
                "locality": settings_state.get("locality"),
                "readiness": provider_readiness,
                "runtimeProof": provider_proof,
            },
            "runtimeProof": provider_proof,
            "credentials": credentials,
            "effectiveModel": settings_state.get("effectiveModel"),
            "plannedConnector": not connector.provider.implemented,
            "message": message,
        }

    def _model_providers_response(self) -> dict[str, Any]:
        settings_payload = self._model_provider_settings_snapshot()
        providers = []
        for connector in self.model_connectors.list():
            providers.append(
                {
                    **connector.provider.to_dict(),
                    "readiness": self._model_connector_readiness(connector, settings_payload=settings_payload),
                }
            )
        return _public_value(
            {
                "format": f"{MODEL_CONNECTOR_FORMAT}.providers",
                "defaultProviderId": self.model_connectors.default_provider_id(),
                "providers": providers,
            }
        )

    def _model_provider_response(self, provider_id: str) -> dict[str, Any]:
        connector = self.model_connectors.get(provider_id)
        settings_payload = self._model_provider_settings_snapshot()
        return _public_value(
            {
                "format": MODEL_CONNECTOR_FORMAT,
                "provider": connector.provider.to_dict(),
                "readiness": self._model_connector_readiness(connector, settings_payload=settings_payload),
            }
        )

    def _test_model_provider(self, provider_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        connector = self.model_connectors.get(provider_id)
        if connector.provider.settings_provider_id:
            conn = self.connection()
            try:
                user = self._local_user(conn)
                settings_check = test_provider_settings(
                    conn,
                    user_id=user["id"],
                    provider_id=connector.provider.settings_provider_id,
                )
                settings_payload = provider_settings_response(conn, user_id=user["id"])
            finally:
                conn.close()
            readiness = self._model_connector_readiness(connector, settings_payload=settings_payload)
            return _public_value(
                {
                    "format": "motionjson.model_provider_test.v0.1",
                    "providerId": connector.provider.id,
                    "settingsProviderId": connector.provider.settings_provider_id,
                    "status": readiness.get("status"),
                    "ready": readiness.get("runnable") is True,
                    "configured": settings_check.get("ready") is True,
                    "networkAttempted": False,
                    "hostedCallsRequired": connector.provider.hosted_calls_required,
                    "hostedCallsAllowed": readiness.get("hostedCallsAllowed") is True,
                    "message": readiness.get("message"),
                    "settingsCheck": settings_check,
                    "readiness": readiness,
                }
            )
        return _public_value(connector.test(payload))

    def _estimate_model_provider(self, provider_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        connector = self.model_connectors.get(provider_id)
        request = self._model_plan_request_from_payload(payload)
        estimate = connector.estimate(request).to_dict()
        if connector.provider.settings_provider_id:
            readiness = self._model_connector_readiness(connector)
            estimate.update(
                {
                    "networkAttempted": False,
                    "requiresUserConfirmation": True,
                    "hostedCallsAllowed": readiness.get("hostedCallsAllowed") is True,
                    "settingsProviderId": connector.provider.settings_provider_id,
                    "readiness": readiness,
                    "blocked": readiness.get("runnable") is not True,
                    "blockedReason": None if readiness.get("runnable") is True else readiness.get("message"),
                }
            )
        return _public_value(estimate)

    def _runtime_model_connector(self, connector: Any, payload: dict[str, Any]) -> Any:
        if not connector.provider.settings_provider_id or not hasattr(connector, "with_runtime_settings"):
            return connector
        conn = self.connection()
        try:
            user = self._local_user(conn)
            settings = provider_runtime_settings(
                conn,
                user_id=user["id"],
                provider_id=connector.provider.settings_provider_id,
            )
        finally:
            conn.close()
        return connector.with_runtime_settings(
            settings,
            allow_network=_truthy_payload(payload, "allowNetwork", "allow_network"),
        )

    def _require_hosted_model_run_confirmation(self, connector: Any, payload: dict[str, Any]) -> None:
        if not connector.provider.hosted_calls_required:
            return
        if not _truthy_payload(payload, "allowNetwork", "allow_network"):
            raise ValueError(
                f"{connector.provider.id} requires allowNetwork=true before making a hosted model request."
            )
        if not _truthy_payload(
            payload,
            "acknowledgeCostPrivacy",
            "acknowledge_cost_privacy",
            "costPrivacyAcknowledged",
            "cost_privacy_acknowledged",
        ):
            raise ValueError(
                f"{connector.provider.id} requires acknowledgeCostPrivacy=true before making a hosted model request."
            )

    def _start_model_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        provider_id = self._model_provider_id_from_payload(payload)
        connector = self.model_connectors.get(provider_id)
        readiness = self._model_connector_readiness(connector)
        if readiness.get("runnable") is False:
            raise ValueError(f"{provider_id} is not ready to run: {readiness.get('message')}")
        self._require_hosted_model_run_confirmation(connector, payload)
        runtime_connector = self._runtime_model_connector(connector, payload)
        request = self._model_plan_request_from_payload(payload)
        run = self.model_runs.create(provider_id=provider_id, request=request)
        auto_start = payload.get("autoStart", payload.get("auto_start", True))
        if auto_start is not False and not _truthy_payload(payload, "defer", "deferred"):
            self.model_runs.mark_running(run.id)
            try:
                result = runtime_connector.plan(request)
            except Exception as exc:
                run = self.model_runs.mark_failed(run.id, str(exc) or type(exc).__name__)
            else:
                run = self.model_runs.mark_succeeded(run.id, result)
        return _public_value({"format": MODEL_RUN_FORMAT, "modelRun": run.to_dict(include_events=True)})

    def _model_run_response(self, run_id: str) -> dict[str, Any]:
        run = self.model_runs.get(run_id)
        return _public_value({"format": MODEL_RUN_FORMAT, "modelRun": run.to_dict(include_events=True)})

    def _model_run_events_response(self, run_id: str) -> dict[str, Any]:
        events = [event.to_dict() for event in self.model_runs.events(run_id)]
        return _public_value({"format": f"{MODEL_RUN_FORMAT}.events", "events": events})

    def _cancel_model_run(self, run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        run = self.model_runs.cancel(run_id, reason=str(payload.get("reason") or "user_canceled"))
        return _public_value({"format": MODEL_RUN_FORMAT, "modelRun": run.to_dict(include_events=True)})

    def _model_plan_from_payload(self, payload: dict[str, Any]) -> ModelPlanResult:
        run_id = str(payload.get("modelRunId") or payload.get("model_run_id") or "")
        if run_id:
            run = self.model_runs.get(run_id)
            if run.result is None:
                raise ValueError("modelRunId does not reference a completed plan")
            return run.result
        plan_payload = payload.get("modelPlan") or payload.get("model_plan")
        if isinstance(plan_payload, dict):
            return ModelPlanResult.from_dict(plan_payload)
        raise ValueError("modelRunId or modelPlan is required")

    def _attach_model_plan_to_job(
        self,
        conn: sqlite3.Connection,
        *,
        user_id: str,
        job_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        job = get_job(conn, user_id=user_id, job_id=job_id)
        model_plan = self._model_plan_from_payload(payload)
        if model_plan.validation.get("valid") is not True:
            raise ValueError("model plan runConfig must validate before it can be attached to a job")
        plan_snapshot = _public_value(model_plan.to_dict())
        record_job_event(
            conn,
            job_id=job_id,
            event_type="model_plan_attached",
            message="model-generated plan attached for user review",
            metadata={
                "source": "local_ui",
                "modelRunId": payload.get("modelRunId") or payload.get("model_run_id"),
                "providerId": model_plan.provider_id,
                "requiresUserConfirmation": model_plan.requires_user_confirmation,
                "modelPlan": plan_snapshot,
            },
        )
        return _public_value(
            {
                "format": "motionjson.local_ui_model_plan_attachment.v0.1",
                "job": self._public_job_snapshot_for_job(conn, job, include_events=True),
                "modelPlan": plan_snapshot,
            }
        )

    def _validated_model_plan_for_enqueue(self, model_plan: ModelPlanResult) -> tuple[dict[str, Any], dict[str, Any]]:
        validation = self._validate_run_config({"runConfig": model_plan.run_config})
        errors = [str(item.get("message") or item) for item in validation.get("errors", [])]
        blocking_warnings = [
            str(item.get("message") or item)
            for item in validation.get("warnings", [])
            if isinstance(item, dict) and str(item.get("severity") or "").lower() == "error"
        ]
        if validation.get("valid") is not True or errors:
            raise ValueError("model plan runConfig did not pass backend validation: " + "; ".join(errors or ["invalid runConfig"]))
        if blocking_warnings:
            raise ValueError("model plan cannot start extraction: " + "; ".join(blocking_warnings))
        try:
            run_config = ExtractionRunConfig.from_dict(model_plan.run_config).to_dict()
        except ConfigValidationError as exc:
            raise ValueError(f"model plan runConfig did not pass backend validation: {exc}") from exc
        return run_config, validation

    @staticmethod
    def _payload_id(payload: dict[str, Any], *keys: str) -> str:
        for key in keys:
            value = payload.get(key)
            if value:
                return str(value)
        return ""

    @staticmethod
    def _model_plan_project_video(model_plan: ModelPlanResult, payload: dict[str, Any]) -> tuple[str, str]:
        payload_project_id = LocalUIApp._payload_id(payload, "projectId", "project_id")
        payload_video_id = LocalUIApp._payload_id(payload, "videoId", "assetId", "video_id", "asset_id")
        config = ExtractionRunConfig.from_dict(model_plan.run_config)
        config_asset_id = config.rights.source_asset_id or _asset_id_from_uri(config.input_video.path) or ""
        plan_project_id = model_plan.request.project_id or ""
        plan_video_id = config_asset_id or model_plan.request.video_id or ""

        if payload_project_id and plan_project_id and payload_project_id != plan_project_id:
            raise ValueError("selected project does not match the model plan project")
        if payload_video_id and plan_video_id and payload_video_id != plan_video_id:
            raise ValueError("selected video does not match the model plan source video")

        project_id = plan_project_id or payload_project_id
        video_id = plan_video_id or payload_video_id
        if not project_id:
            raise ValueError("projectId is required before confirming a model plan")
        if not video_id:
            raise ValueError("videoId is required before confirming a model plan")
        return project_id, video_id

    @staticmethod
    def _confirmed_job_for_model_run(conn: sqlite3.Connection, *, user_id: str, run_id: str) -> dict[str, Any] | None:
        rows = conn.execute(
            """
            SELECT job_id, metadata_json
            FROM job_events
            WHERE event_type = 'model_plan_attached'
            ORDER BY created_at, id
            """
        ).fetchall()
        for row in rows:
            try:
                metadata = json.loads(row["metadata_json"] or "{}")
            except (TypeError, json.JSONDecodeError):
                metadata = {}
            if str(metadata.get("modelRunId") or "") != run_id:
                continue
            try:
                return get_job(conn, user_id=user_id, job_id=row["job_id"])
            except NotFoundError:
                continue
        return None

    def _confirm_model_plan_job(self, run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not _truthy_payload(payload, "confirmed", "userConfirmed", "user_confirmed"):
            raise ValueError("User confirmation is required before starting extraction from a model plan.")

        run = self.model_runs.get(run_id)
        if run.result is None:
            raise ValueError("modelRunId does not reference a completed plan")
        model_plan = run.result
        run_config, validation = self._validated_model_plan_for_enqueue(model_plan)
        project_id, video_id = self._model_plan_project_video(model_plan, payload)

        conn = self.connection()
        try:
            user_id = self._local_user(conn)["id"]
            existing_job = self._confirmed_job_for_model_run(conn, user_id=user_id, run_id=run_id)
            if existing_job is not None:
                return _public_value(
                    {
                        "format": "motionjson.local_ui_model_plan_confirmed.v0.1",
                        "modelRun": run.to_dict(include_events=True),
                        "modelPlan": model_plan.to_dict(),
                        "validation": validation,
                        "job": self._public_job_snapshot_for_job(conn, existing_job, include_events=True),
                        "worker": {"status": "not_started", "reason": "model plan was already confirmed"},
                    }
                )
            job_payload = {
                **payload,
                "projectId": project_id,
                "videoId": video_id,
                "runConfig": run_config,
                "run": False,
                "start": False,
                "startWorker": False,
                "runWorker": False,
                "runImmediately": False,
            }
            job = self._enqueue_extract_from_ui_payload(conn, user_id=user_id, payload=job_payload)
            self._attach_model_plan_to_job(conn, user_id=user_id, job_id=job["id"], payload={"modelRunId": run_id})
            response: dict[str, Any] = {
                "format": "motionjson.local_ui_model_plan_confirmed.v0.1",
                "modelRun": run.to_dict(include_events=True),
                "modelPlan": model_plan.to_dict(),
                "validation": validation,
                "job": self._public_job_snapshot_for_job(conn, get_job(conn, user_id=user_id, job_id=job["id"]), include_events=True),
            }
            if _truthy_payload(payload, "run", "start", "startWorker", "runWorker", "runImmediately"):
                record_job_event(
                    conn,
                    job_id=job["id"],
                    event_type="worker_start_requested",
                    message="workspace worker start requested after model-plan confirmation",
                    metadata={"source": "workspace", "modelRunId": run_id},
                )
                response["worker"] = self._start_worker()
                response["job"] = self._public_job_snapshot_for_job(conn, get_job(conn, user_id=user_id, job_id=job["id"]), include_events=True)
            return _public_value(response)
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
        provider_warnings = self._run_config_warnings(config)
        conn = self.connection()
        try:
            user_id = self._local_user(conn)["id"]
            proof_warnings = self._runtime_proof_warnings_for_config(conn, user_id=user_id, config=config)
        finally:
            conn.close()
        hosted_ack_warnings = self._hosted_ack_warnings_for_config(config)
        proof_blocked_providers = {str(warning.get("provider") or "") for warning in proof_warnings}
        response["warnings"] = [
            warning
            for warning in provider_warnings
            if not (warning.get("code") == "provider_unavailable" and str(warning.get("provider") or "") in proof_blocked_providers)
        ]
        response["warnings"].extend(proof_warnings)
        response["warnings"].extend(hosted_ack_warnings)
        self._append_sam3_local_concept_blocker(response, config)
        return response

    def _run_config_warnings(self, config: ExtractionRunConfig) -> list[dict[str, Any]]:
        warnings: list[dict[str, Any]] = []
        providers = {
            (str(provider.get("kind") or ""), str(provider.get("name") or "")): provider
            for provider in self._capability_report().get("providers", [])
            if isinstance(provider, dict)
        }
        if not (config.provider.name == "sam3-local" and config.discovery.mode == "sam3_auto_masks"):
            provider_kind = "discovery_provider" if config.provider.name in {"sam3-local", "sam3-hosted"} else "mask_provider"
            self._append_provider_warning(
                warnings,
                providers,
                kind=provider_kind,
                name=config.provider.name,
                field="provider.name",
            )
        if config.discovery.mode:
            discovery_name = self._capability_name_for_discovery_mode(config.discovery.mode)
            if config.discovery.mode == "sam3_auto_masks" and config.provider.name != "sam3-hosted":
                self._append_sam3_scene_sweep_warning(warnings, providers, field="discovery.mode")
            else:
                self._append_provider_warning(
                    warnings,
                    providers,
                    kind="discovery_provider",
                    name=discovery_name,
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
                    "severity": "error",
                    "action": "Choose a compatible SAM2 or SAM3 engine, or use mock, motion, threshold, or external masks for the workspace worker.",
                    "message": str(exc),
                }
            )
        return warnings

    @staticmethod
    def _runtime_proof_requirements_for_config(config: ExtractionRunConfig) -> list[dict[str, str]]:
        requirements: list[dict[str, str]] = []
        discovery_config = dict(config.discovery.config or {})
        if discovery_config.get("mock"):
            return requirements

        def add(provider_id: str, field: str, *, capability_name: str | None = None) -> None:
            if not provider_id:
                return
            if any(item["providerId"] == provider_id and item["field"] == field for item in requirements):
                return
            requirements.append({"providerId": provider_id, "field": field, "capabilityName": capability_name or provider_id})

        provider_name = str(config.provider.name or "")
        discovery_mode = str(config.discovery.mode or "")
        provider_preference = str(discovery_config.get("providerPreference") or discovery_config.get("provider_preference") or "")
        hosted_requested = bool(discovery_config.get("hosted") or discovery_config.get("useHosted") or provider_preference == "sam3-hosted")

        if provider_name in {"sam2-hosted", "sam3-hosted"}:
            add(provider_name, "provider.name")
        if discovery_mode == "sam2_hf_auto_masks" or provider_name == "sam2-hf-auto-masks" or provider_preference == "sam2-hf-auto-masks":
            add("sam2-hf-auto-masks", "discovery.mode" if discovery_mode == "sam2_hf_auto_masks" else "provider.name")
        if discovery_mode == "sam3_auto_masks":
            if hosted_requested or provider_name == "sam3-hosted":
                add("sam3-hosted", "discovery.mode")
            else:
                add("sam3-local", "discovery.mode", capability_name="sam3-auto-masks")
        if discovery_mode in {"sam3_concept", "sam3_exemplar"} and (hosted_requested or provider_name == "sam3-hosted"):
            add("sam3-hosted", "discovery.mode")
        if discovery_mode in {"sam3_concept", "sam3_exemplar"} and not hosted_requested and provider_name == "sam3-local":
            add(
                "sam3-local",
                "discovery.mode",
                capability_name="sam3-concept" if discovery_mode == "sam3_concept" else "sam3-exemplar",
            )
        return requirements

    @staticmethod
    def _runtime_proof_warning_code(proof: dict[str, Any]) -> str:
        status = str(proof.get("proofStatus") or proof.get("runtimeProofStatus") or "")
        return {
            "expired": "runtime_proof_expired",
            "failed": "runtime_proof_failed",
            "gpu_device_mismatch": "gpu_device_mismatch",
            "hosted_opt_in_required": "runtime_proof_hosted_opt_in_required",
            "missing": "runtime_proof_missing",
            "missing_cache": "runtime_proof_missing",
            "network_smoke_failed": "hosted_network_smoke_failed",
            "settings_not_ready": "runtime_proof_settings_not_ready",
            "stale": "runtime_proof_stale",
        }.get(status, "runtime_proof_blocked")

    def _runtime_proof_warnings_for_config(
        self,
        conn: sqlite3.Connection,
        *,
        user_id: str,
        config: ExtractionRunConfig,
    ) -> list[dict[str, Any]]:
        warnings: list[dict[str, Any]] = []
        providers = {
            (str(provider.get("kind") or ""), str(provider.get("name") or "")): provider
            for provider in self._capability_report().get("providers", [])
            if isinstance(provider, dict)
        }
        for requirement in self._runtime_proof_requirements_for_config(config):
            provider_id = requirement["providerId"]
            capability_name = requirement.get("capabilityName") or provider_id
            capability = providers.get(("discovery_provider", capability_name)) or providers.get(("mask_provider", capability_name))
            if capability and capability.get("available") is False:
                continue
            proof = provider_runtime_proof(conn, user_id=user_id, provider_id=provider_id)
            if proof.get("allowsRun") is True:
                continue
            warnings.append(
                {
                    "code": self._runtime_proof_warning_code(proof),
                    "field": requirement["field"],
                    "provider": capability_name,
                    "kind": "runtime_proof",
                    "status": proof.get("proofStatus") or proof.get("runtimeProofStatus") or "blocked",
                    "severity": "error",
                    "action": proof.get("remediation") or "Open Model setup, fix provider setup, then rerun smoke proof.",
                    "message": proof.get("message") or f"{provider_id} runtime proof is required before extraction.",
                    "runtimeProof": _public_value(proof),
                }
            )
        return warnings

    @staticmethod
    def _hosted_ack_warnings_for_config(config: ExtractionRunConfig) -> list[dict[str, Any]]:
        warnings: list[dict[str, Any]] = []
        discovery_config = dict(config.discovery.config or {})

        def discovery_truthy(*keys: str) -> bool:
            return _truthy_payload(discovery_config, *keys)

        def add(provider_id: str, field: str, message: str) -> None:
            if any(item.get("provider") == provider_id and item.get("field") == field for item in warnings):
                return
            warnings.append(
                {
                    "code": "sam3_hosted_requires_opt_in" if provider_id == "sam3-hosted" else "hosted_network_ack_required",
                    "field": field,
                    "provider": provider_id,
                    "kind": "hosted_network_ack",
                    "status": "per_run_ack_required",
                    "severity": "error",
                    "action": "Confirm hosted network use and cost/privacy acknowledgement for this run.",
                    "message": message,
                }
            )

        provider_name = str(config.provider.name or "")
        provider_preference = str(discovery_config.get("providerPreference") or discovery_config.get("provider_preference") or "")
        sam3_hosted_discovery = bool(
            provider_name == "sam3-hosted"
            or provider_preference == "sam3-hosted"
            or discovery_config.get("hosted")
            or discovery_config.get("useHosted")
        )

        if provider_name == "sam2-hosted" and not bool(config.provider.sam2.hosted_allow_network):
            add(
                "sam2-hosted",
                "provider.sam2.hosted_allow_network",
                "sam2-hosted requires per-run hosted network and cost/privacy acknowledgement before extraction can send video frames.",
            )

        sam3_allow_network = bool(config.provider.sam3.hosted_allow_network or discovery_truthy("allowNetwork", "allow_network"))
        sam3_acknowledged = bool(
            config.provider.sam3.hosted_allow_network
            or discovery_truthy("acknowledgeCostPrivacy", "acknowledge_cost_privacy", "acknowledge_cost_and_privacy")
        )
        if sam3_hosted_discovery and not sam3_allow_network:
            add(
                "sam3-hosted",
                "discovery.config.allowNetwork",
                "sam3-hosted requires allowNetwork=true before discovery can send sampled frames.",
            )
        if sam3_hosted_discovery and not sam3_acknowledged:
            add(
                "sam3-hosted",
                "discovery.config.acknowledgeCostPrivacy",
                "sam3-hosted requires cost/privacy acknowledgement before discovery can send sampled frames.",
            )
        return warnings

    @staticmethod
    def _capability_name_for_discovery_mode(mode: str | None) -> str:
        return {
            "sam2_hf_auto_masks": "sam2-hf-auto-masks",
            "sam3_auto_masks": "sam3-auto-masks",
            "sam3_concept": "sam3-concept",
            "sam3_exemplar": "sam3-exemplar",
        }.get(str(mode or ""), str(mode or ""))

    def _append_sam3_local_concept_blocker(self, response: dict[str, Any], config: ExtractionRunConfig) -> None:
        if config.discovery.mode not in {"sam3_concept", "sam3_exemplar"}:
            return
        discovery_config = dict(config.discovery.config or {})
        if discovery_config.get("mock") or discovery_config.get("hosted"):
            return
        preference = str(discovery_config.get("providerPreference") or discovery_config.get("provider_preference") or config.provider.name or "")
        if config.provider.name != "sam3-local" and preference != "sam3-local":
            return
        provider_name = self._capability_name_for_discovery_mode(config.discovery.mode)
        providers = {
            (str(provider.get("kind") or ""), str(provider.get("name") or "")): provider
            for provider in self._capability_report().get("providers", [])
            if isinstance(provider, dict)
        }
        provider = providers.get(("discovery_provider", provider_name)) or providers.get(("discovery_provider", "sam3-local"))
        if not provider or (provider.get("available") is not False and provider.get("runnable") is not False):
            return
        mode_label = "Find by description" if config.discovery.mode == "sam3_concept" else "SAM3 box/example tracing"
        code = self._sam3_advanced_local_blocker_code(provider)
        action = (
            "Use a hosted SAM3 concept provider, switch to Trace all objects / SAM3 Scene Sweep, "
            "or configure the advanced official SAM3 package plus a local sam3.pt checkpoint path."
        )
        response["valid"] = False
        response.setdefault("errors", []).append(
            {
                "code": code,
                "legacyCode": "sam3_local_concept_unavailable",
                "field": "discovery.mode",
                "provider": "advanced_local_sam3_concept_exemplar",
                "discoveryProvider": provider_name,
                "severity": "error",
                "action": action,
                "message": (
                    f"{mode_label} cannot use the normal SAM3 Scene Sweep runtime as a local text/concept adapter. "
                    "Scene Sweep can propose visible objects, but local text/concept SAM3 requires the advanced official SAM3 adapter."
                ),
                "reasons": _public_value(provider.get("reasons") or []),
            }
        )

    @staticmethod
    def _sam3_advanced_local_blocker_code(provider: Mapping[str, Any]) -> str:
        text = " ".join(
            [
                str(provider.get("status") or ""),
                str(provider.get("installHint") or ""),
                *[str(reason) for reason in provider.get("reasons") or []],
            ]
        ).lower()
        if "sam3_local_model" in text or "sam3.pt" in text or "checkpoint" in text or "model path" in text:
            return "sam3_advanced_local_missing_checkpoint"
        return "sam3_advanced_local_unavailable"

    @staticmethod
    def _sam3_scene_sweep_warning_code(provider: Mapping[str, Any]) -> str:
        text = " ".join(
            [
                str(provider.get("status") or ""),
                str(provider.get("installHint") or ""),
                *[str(reason) for reason in provider.get("reasons") or []],
            ]
        ).lower()
        if "sam3tracker" in text or "tracker automatic-mask" in text or "tracker classes" in text or "does not expose sam3 tracker" in text:
            return "sam3_scene_sweep_missing_tracker_classes"
        if "transformers" in text:
            return "sam3_scene_sweep_missing_transformers"
        return "sam3_scene_sweep_unavailable"

    @classmethod
    def _append_sam3_scene_sweep_warning(
        cls,
        warnings: list[dict[str, Any]],
        providers: dict[tuple[str, str], dict[str, Any]],
        *,
        field: str,
    ) -> None:
        provider = providers.get(("discovery_provider", "sam3-auto-masks"))
        if not provider or (provider.get("available") is not False and provider.get("runnable") is not False):
            return
        status = provider.get("status")
        if provider.get("available") is not False and status == "runtime_proof_required":
            return
        message = "SAM3 Scene Sweep is not available on this machine."
        if provider.get("available") is not False and provider.get("runnable") is False:
            status = "not_runnable"
            message = "SAM3 Scene Sweep is configured but cannot run from this local workflow yet."
        warnings.append(
            {
                "code": cls._sam3_scene_sweep_warning_code(provider),
                "field": field,
                "provider": "sam3_tracker_scene_sweep",
                "capabilityProvider": "sam3-auto-masks",
                "kind": "discovery_provider",
                "status": status,
                "severity": "error",
                "action": provider.get("installHint") or "Install the sam3-transformers runtime, cache facebook/sam3, then run scene-sweep proof.",
                "message": message,
                "reasons": _public_value(provider.get("reasons") or []),
                "installHint": provider.get("installHint"),
            }
        )

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
        if not provider or (provider.get("available") is not False and provider.get("runnable") is not False):
            return
        status = provider.get("status")
        message = f"{name} is not available on this machine."
        if provider.get("available") is not False and provider.get("runnable") is False:
            status = "not_runnable"
            message = f"{name} is configured but cannot run from this local workflow yet."
        code = "provider_unavailable"
        if name == "sam3-hosted":
            text = " ".join([str(provider.get("status") or ""), *[str(reason) for reason in provider.get("reasons") or []]]).lower()
            if "api_key" in text or "api key" in text or "token" in text or "credential" in text or "env" in text:
                code = "sam3_hosted_missing_credentials"
        warnings.append(
            {
                "code": code,
                "field": field,
                "provider": name,
                "kind": kind,
                "status": status,
                "severity": "error",
                "action": provider.get("installHint") or "Choose a ready no-model provider or configure this optional provider before starting a run.",
                "message": message,
                "reasons": _public_value(provider.get("reasons") or []),
                "installHint": provider.get("installHint"),
            }
        )

    def _upload_video_form(
        self,
        conn: sqlite3.Connection,
        *,
        user_id: str,
        fields: dict[str, str],
        files: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        upload = files.get("video") or files.get("file")
        if not upload:
            raise ValueError("video file is required")
        data = upload.get("bytes")
        if not isinstance(data, bytes) or not data:
            raise ValueError("video file is empty")

        filename = _safe_upload_filename(str(upload.get("filename") or "uploaded-video"))
        project_id = str(fields.get("projectId") or fields.get("project_id") or "").strip()
        project: dict[str, Any] | None = None
        if not project_id:
            project_name = str(fields.get("projectName") or fields.get("project_name") or Path(filename).stem or "MotionJSON local project").strip()
            project = create_project(conn, user_id=user_id, name=project_name or "MotionJSON local project")
            project_id = project["id"]

        with tempfile.TemporaryDirectory(prefix="motionjson_ui_upload_") as tmpdir:
            temp_path = Path(tmpdir) / filename
            temp_path.write_bytes(data)
            asset = register_upload(
                conn,
                storage=self.storage(),
                user_id=user_id,
                project_id=project_id,
                path=temp_path,
                kind="source_video",
                content_type=str(upload.get("contentType") or mimetypes.guess_type(filename)[0] or "application/octet-stream"),
                metadata={
                    "rights_context": {
                        "source_uri": f"upload://{filename}",
                        "source_type": "user_upload",
                        "display_text": filename,
                    }
                },
            )

        if project is None:
            project = next((item for item in list_projects(conn, user_id=user_id) if item["id"] == project_id), {"id": project_id})
        return {
            "project": project,
            "video": self._public_video_payload(conn, user_id=user_id, asset=asset, prepare_preview=True, force_preview=True),
        }

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
            blocking_warnings = [
                *self._runtime_proof_warnings_for_config(conn, user_id=user_id, config=config),
                *self._hosted_ack_warnings_for_config(config),
            ]
            if blocking_warnings:
                messages = "; ".join(str(item.get("message") or item.get("code") or "runtime proof blocked") for item in blocking_warnings)
                raise ValueError(f"Runtime proof gate blocked extraction: {messages}")
            project_id = str(payload.get("projectId") or payload.get("project_id") or "")
            asset_id = self._asset_id_for_run_config(config, payload)
            rights_context = config.rights.to_dict()

            if not asset_id:
                if not project_id:
                    raise ValueError("projectId is required when runConfig.input.path is not a workspace asset")
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
                run_config=config.to_dict(),
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

    def _capability_report(
        self,
        *,
        video_path: str | Path | None = None,
        output_dir: str | Path | None = None,
    ) -> dict[str, Any]:
        conn = self.connection()
        try:
            user = self._local_user(conn)
            settings = provider_settings_for_capabilities(conn, user_id=user["id"])
        finally:
            conn.close()
        try:
            return build_capability_report(
                video_path=video_path,
                output_dir=output_dir,
                provider_settings=settings,
            )
        except TypeError as exc:
            if "unexpected keyword argument" not in str(exc):
                raise
            return build_capability_report()

    def _provider_settings_response(self) -> dict[str, Any]:
        conn = self.connection()
        try:
            user = self._local_user(conn)
            return _public_value(provider_settings_response(conn, user_id=user["id"]))
        finally:
            conn.close()

    def _save_provider_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        conn = self.connection()
        try:
            user = self._local_user(conn)
            return _public_value(save_provider_settings(conn, user_id=user["id"], payload=payload))
        finally:
            conn.close()

    def _reset_provider_settings(self, provider_id: str) -> dict[str, Any]:
        conn = self.connection()
        try:
            user = self._local_user(conn)
            result = reset_provider_settings(conn, user_id=user["id"], provider_id=provider_id)
            return _public_value({**result, "providerSettings": provider_settings_response(conn, user_id=user["id"])})
        finally:
            conn.close()

    def _test_provider_settings(self, provider_id: str) -> dict[str, Any]:
        conn = self.connection()
        try:
            user = self._local_user(conn)
            return _public_value(test_provider_settings(conn, user_id=user["id"], provider_id=provider_id))
        finally:
            conn.close()

    def _diagnose_provider_settings(self, provider_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        conn = self.connection()
        try:
            user = self._local_user(conn)
            return _public_value(
                diagnose_provider_settings(
                    conn,
                    user_id=user["id"],
                    provider_id=provider_id,
                    payload=payload,
                )
            )
        finally:
            conn.close()

    def _smoke_test_provider_settings(self, provider_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        conn = self.connection()
        try:
            user = self._local_user(conn)
            if provider_id in {"sam2-local", "sam2-hf-auto-masks", "sam3-local"}:
                return _public_value(
                    local_sam_smoke_test(
                        conn,
                        user_id=user["id"],
                        provider_id=provider_id,
                        payload=payload,
                    )
                )
            return _public_value(
                hosted_sam3_smoke_test(
                    conn,
                    user_id=user["id"],
                    payload={**payload, "providerId": provider_id},
                )
                )
        finally:
            conn.close()

    def _advanced_local_paths(self, provider_id: str) -> dict[str, Any]:
        conn = self.connection()
        try:
            user = self._local_user(conn)
            return provider_advanced_local_paths(conn, user_id=user["id"], provider_id=provider_id)
        finally:
            conn.close()

    def _start_provider_setup_job(self, provider_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        conn = self.connection()
        try:
            user = self._local_user(conn)
            job = create_provider_setup_job(conn, user_id=user["id"], provider_id=provider_id, payload=payload)
            job_id = str(job["id"])
            if payload.get("runInline") is True or payload.get("run_inline") is True:
                job = run_provider_setup_job(conn, user_id=user["id"], job_id=job_id, payload=payload)
                return _public_value(
                    {
                        "format": "motionjson.provider_setup_job.v0.1.start",
                        "setupJob": job,
                        "actions": provider_setup_actions(provider_id),
                        "providerSettings": provider_settings_response(conn, user_id=user["id"]),
                    }
                )
            self._start_provider_setup_thread(job_id, payload)
            return _public_value(
                {
                    "format": "motionjson.provider_setup_job.v0.1.start",
                    "setupJob": job,
                    "actions": provider_setup_actions(provider_id),
                    "providerSettings": provider_settings_response(conn, user_id=user["id"]),
                }
            )
        finally:
            conn.close()

    def _start_provider_setup_thread(self, job_id: str, payload: dict[str, Any]) -> None:
        def run() -> None:
            conn = self.connection()
            try:
                user = self._local_user(conn)
                run_provider_setup_job(conn, user_id=user["id"], job_id=job_id, payload=payload)
            finally:
                conn.close()
                with self._provider_setup_lock:
                    self._provider_setup_threads.pop(job_id, None)

        with self._provider_setup_lock:
            existing = self._provider_setup_threads.get(job_id)
            if existing is not None and existing.is_alive():
                return
            thread = threading.Thread(target=run, name=f"motionjson-provider-setup-{job_id[:8]}", daemon=True)
            self._provider_setup_threads[job_id] = thread
            thread.start()

    def _provider_setup_job_response(self, job_id: str) -> dict[str, Any]:
        conn = self.connection()
        try:
            user = self._local_user(conn)
            return _public_value(
                {
                    "format": "motionjson.provider_setup_job.v0.1",
                    "setupJob": public_provider_setup_job(conn, user_id=user["id"], job_id=job_id, include_events=True),
                    "providerSettings": provider_settings_response(conn, user_id=user["id"]),
                }
            )
        finally:
            conn.close()

    def _cancel_provider_setup_job(self, job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        conn = self.connection()
        try:
            user = self._local_user(conn)
            return _public_value(
                {
                    "format": "motionjson.provider_setup_job.v0.1",
                    "setupJob": cancel_provider_setup_job(
                        conn,
                        user_id=user["id"],
                        job_id=job_id,
                        reason=str(payload.get("reason") or "user_canceled"),
                    ),
                }
            )
        finally:
            conn.close()

    def _job_review_for_lifecycle(self, conn: sqlite3.Connection, job: dict[str, Any]) -> dict[str, Any]:
        assets = list_assets_for_job(conn, project_id=job["project_id"], source_job_id=job["id"])
        corrections = list_track_corrections(conn, user_id=job["created_by_user_id"], job_id=job["id"])
        return self._review_metadata(assets, corrections=corrections, job_id=job["id"])

    def _job_readiness_for_assets(
        self,
        job: dict[str, Any],
        *,
        assets: list[dict[str, Any]],
        events: list[dict[str, Any]],
        review: dict[str, Any],
    ) -> dict[str, Any]:
        event_types = _event_type_set(events)
        if "result_json" in job:
            try:
                result = json.loads(job.get("result_json") or "{}")
            except (TypeError, json.JSONDecodeError):
                result = {}
        else:
            result = job.get("result", {})
        result_readiness = result.get("readiness") if isinstance(result, dict) and isinstance(result.get("readiness"), dict) else {}
        raw_status = str(job.get("status") or "").lower()
        active = raw_status in {"pending", "queued", "running", "cancel_requested"}
        worker_complete = bool(
            result_readiness.get("workerComplete")
            or raw_status in TERMINAL_JOB_STATUSES
            or event_types.intersection({"worker_complete", "job_succeeded", "succeeded"})
        )
        artifacts_registered = bool(
            result_readiness.get("artifactsRegistered")
            or event_types.intersection({"artifacts_registered"})
            or (not active and len(assets) > 0)
        )
        return job_readiness(
            rel_paths=[_asset_rel_path(asset) for asset in assets],
            worker_complete=worker_complete,
            artifacts_registered=artifacts_registered,
            job_active=active,
            review_summary=review_lifecycle_summary(review),
        )

    def _public_job_snapshot_for_job(
        self,
        conn: sqlite3.Connection,
        job: dict[str, Any],
        *,
        include_events: bool = False,
        include_review: bool = True,
    ) -> dict[str, Any]:
        events = list_job_events(conn, job_id=job["id"])
        if include_review:
            assets = list_assets_for_job(conn, project_id=job["project_id"], source_job_id=job["id"])
            corrections = list_track_corrections(conn, user_id=job["created_by_user_id"], job_id=job["id"])
            review = self._review_metadata(assets, corrections=corrections, job_id=job["id"])
            readiness = self._job_readiness_for_assets(job, assets=assets, events=events, review=review)
        else:
            review = {}
            readiness = None
        return _public_job_snapshot(job, events=events, include_events=include_events, review=review, readiness=readiness)

    def _job_center_payload(
        self,
        conn: sqlite3.Connection,
        *,
        user_id: str,
        project_id: str | None = None,
        limit: int = 8,
    ) -> dict[str, Any]:
        params: list[Any] = [user_id]
        project_clause = ""
        if project_id:
            project_clause = " AND jobs.project_id = ?"
            params.append(project_id)
        params.append(limit)
        rows = conn.execute(
            f"""
            SELECT jobs.*
            FROM jobs
            JOIN projects ON projects.id = jobs.project_id
            WHERE projects.owner_user_id = ? AND projects.archived_at IS NULL{project_clause}
            ORDER BY jobs.updated_at DESC, jobs.created_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        recent_jobs = [
            self._public_job_snapshot_for_job(conn, dict(row), include_events=False, include_review=True)
            for row in rows
        ]
        active_statuses = {"queued", "running"}
        active_jobs = [
            job for job in recent_jobs
            if job.get("lifecycle", {}).get("status") in active_statuses
        ]
        selected = active_jobs[0] if active_jobs else recent_jobs[0] if recent_jobs else None
        return {
            "format": "motionjson.local_ui_job_center.v0.1",
            "activeJobsCount": len(active_jobs),
            "selectedJobId": selected.get("id") if selected else None,
            "activeJobs": active_jobs,
            "recentJobs": recent_jobs,
        }

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
        if content_type == "image/svg+xml":
            return str(asset.get("kind") or "") in PUBLIC_DOWNLOAD_ARTIFACT_KINDS
        return content_type.startswith(PUBLIC_ARTIFACT_CONTENT_TYPES) or str(asset.get("kind") or "") in PUBLIC_DOWNLOAD_ARTIFACT_KINDS

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
            "selection": {},
        }
        storage = self.storage()
        seen_fallback: set[str] = set()
        artifact_ids_by_rel_path = _artifact_ids_by_rel_path(assets)
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
            elif kind == "object_manifest":
                self._apply_object_manifest_review(review, document)
            elif kind == "failure_diagnostics":
                review["failure"] = _public_review_value(document)
            elif kind == "provider_diagnostics":
                review["providerDiagnostics"] = _public_review_value(document.get("diagnostics", document))
            elif kind == "partial_review":
                review["partialReview"] = _public_review_value(document)
                review["partialSuccess"] = bool(document.get("partialSuccess", True))
                if isinstance(document.get("reviewableObjectIds"), list):
                    review["reviewableObjectCount"] = len(document["reviewableObjectIds"])
            elif kind == "job_metrics":
                review["metrics"] = _public_review_value(document)
            elif kind == "candidate_summary":
                self._apply_candidate_review(review, document, artifact_ids_by_rel_path=artifact_ids_by_rel_path)
            elif kind == "review_state_manifest":
                manifest_review = document.get("review") if isinstance(document.get("review"), dict) else {}
                review["reviewStateManifest"] = _public_review_value(
                    {
                        "format": document.get("format"),
                        "generatedAt": document.get("generatedAt"),
                        "correctionEventCount": document.get("correctionEventCount"),
                        "export": manifest_review.get("export") if isinstance(manifest_review.get("export"), dict) else {},
                    }
                )
            elif kind == "selected_candidate_tracking":
                review["selection"] = _public_review_value(document)

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
        selection = review.get("selection") if isinstance(review.get("selection"), dict) else {}
        selected_ids = {str(item) for item in selection.get("selectedCandidateIds", []) if item}
        if selected_ids and selection.get("trackMode") == "selected_only":
            review["tracks"] = [
                track
                for track in review.get("tracks", [])
                if str(track.get("objectId") or "") in selected_ids
            ]
            review["objects"] = [
                item
                for item in review.get("objects", [])
                if str(item.get("objectId") or "") in selected_ids
            ]
            if selection.get("exportReviewRequired") is True:
                track_edits = correction_state.get("trackEdits") if isinstance(correction_state.get("trackEdits"), dict) else {}
                for track in review["tracks"]:
                    track_id = str(track.get("objectId") or "")
                    edit = track_edits.get(track_id) if isinstance(track_edits.get(track_id), dict) else {}
                    if edit.get("exportIncluded") is True:
                        continue
                    track["exportStatus"] = "review_pending"
                    track["exportIncluded"] = False
                    discovery = track.get("discovery") if isinstance(track.get("discovery"), dict) else {}
                    track["discovery"] = {
                        **discovery,
                        "reviewStatus": "selected",
                        "selectedForTracking": True,
                        "reviewRequired": True,
                        "exportStatus": "review_pending",
                    }
                for item in review["objects"]:
                    item["exportStatus"] = "review_pending"
            candidate_summary = review.get("candidateSummary") if isinstance(review.get("candidateSummary"), dict) else {}
            if candidate_summary:
                candidate_summary["acceptedCandidateCount"] = len(selected_ids)
                candidate_summary["selectedCandidateCount"] = len(selected_ids)
                candidate_summary["trackMode"] = selection.get("trackMode")
                review["candidateSummary"] = candidate_summary
            for candidate in review.get("candidates", []):
                candidate_id = str(candidate.get("candidateId") or candidate.get("id") or "")
                candidate["selectedForTracking"] = candidate_id in selected_ids
                if candidate_id in selected_ids:
                    candidate["reviewStatus"] = "selected"
                elif candidate.get("reviewStatus") == "accepted":
                    candidate["reviewStatus"] = "ignored"
        review["timeline"] = review_timeline_payload(
            candidates=review.get("candidates") if isinstance(review.get("candidates"), list) else [],
            tracks=review.get("tracks") if isinstance(review.get("tracks"), list) else [],
            source=review.get("source") if isinstance(review.get("source"), dict) else {},
            candidate_summary=review.get("candidateSummary") if isinstance(review.get("candidateSummary"), dict) else {},
        )
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
                "message": "artifact is too large to inline for workspace review",
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
    def _apply_candidate_review(
        review: dict[str, Any],
        document: dict[str, Any],
        *,
        artifact_ids_by_rel_path: dict[str, str],
    ) -> None:
        candidate_review = candidate_review_payload(document, artifact_ids_by_rel_path=artifact_ids_by_rel_path)
        legacy_summary = _public_review_value(document)
        shaped_summary = _public_review_value(candidate_review["candidateSummary"])
        review["candidates"] = _public_review_value(candidate_review["candidates"])
        review["candidateSummary"] = {
            **shaped_summary,
            "provider": legacy_summary.get("provider"),
            "config": legacy_summary.get("config", {}),
            "video": legacy_summary.get("video", {}),
            "candidates": legacy_summary.get("candidates", []),
        }

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
                "sampleFps": source.get("sampleFps") or canvas.get("fps"),
                "sourceFps": source.get("fps"),
                "frameCount": source.get("sampledFrameCount") or canvas.get("frame_count"),
                "frameMap": source.get("frameMap") if isinstance(source.get("frameMap"), list) else [],
            }
        )
        objects = document.get("objects") if isinstance(document.get("objects"), list) else []
        review["objects"] = [
            _public_review_value(_scene_object_review_summary(item))
            for item in objects
            if isinstance(item, dict)
        ]
        source_asset_id = None
        for item in objects:
            if not isinstance(item, dict):
                continue
            rights = item.get("rights") if isinstance(item.get("rights"), dict) else {}
            source_attribution = rights.get("sourceAttribution") if isinstance(rights.get("sourceAttribution"), dict) else {}
            source_asset_id = source_attribution.get("sourceAssetId")
            if source_asset_id:
                break
        review["rightsSummary"] = _public_review_value(build_rights_review_report(scene=document, source_asset_id=source_asset_id))

    @staticmethod
    def _apply_object_manifest_review(review: dict[str, Any], document: dict[str, Any]) -> None:
        object_summary = _public_review_value(_object_manifest_review_summary(document))
        track_summary = _public_review_value(_object_manifest_track_summary(document))
        _append_unique_by_object_id(review["objects"], object_summary)
        _append_unique_by_object_id(review["tracks"], track_summary)

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
                raise NotFoundError("artifact content is not public through the Runtime API")
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

    def _preview_file_content(self, job_id: str, rel_path: str, *, head: bool = False) -> tuple[int, dict[str, str], bytes]:
        safe_rel_path = _normalize_preview_rel_path(rel_path)
        if not _is_allowed_preview_rel_path(safe_rel_path):
            raise NotFoundError("preview file not found")
        conn = self.connection()
        try:
            user = self._local_user(conn)
            job = get_job(conn, user_id=user["id"], job_id=job_id)
            assets = list_assets_for_job(conn, project_id=job["project_id"], source_job_id=job_id)
            asset = next((item for item in assets if _asset_rel_path(item) == safe_rel_path), None)
            if asset is None:
                raise NotFoundError("preview file not found")
            try:
                data = self.storage().load_bytes(asset["storage_key"])
            except FileNotFoundError as exc:
                raise NotFoundError("preview file not found") from exc

            content_type = asset.get("content_type") or mimetypes.guess_type(safe_rel_path)[0] or "application/octet-stream"
            if safe_rel_path.endswith(".js") and content_type == "application/octet-stream":
                content_type = "text/javascript"
            if safe_rel_path.endswith(".json"):
                try:
                    document = json.loads(data.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise NotFoundError("preview file not found") from exc
                data = (json.dumps(_public_review_value(document), indent=2, sort_keys=True) + "\n").encode("utf-8")
                content_type = "application/json; charset=utf-8"
            elif content_type.startswith(("text/", "application/javascript")) or content_type in {"text/javascript", "application/x-javascript"}:
                if "charset=" not in content_type:
                    content_type = f"{content_type}; charset=utf-8"

            return (
                HTTPStatus.OK,
                {
                    "content-type": content_type,
                    "cache-control": "no-store",
                    "content-length": str(len(data)),
                },
                b"" if head else data,
            )
        finally:
            conn.close()

    def _asset_content(self, asset_id: str, *, head: bool = False) -> tuple[int, dict[str, str], bytes]:
        conn = self.connection()
        try:
            user = self._local_user(conn)
            asset = get_asset(conn, user_id=user["id"], asset_id=asset_id)
            if asset["kind"] == "source_video":
                raise NotFoundError("use the source video route for source_video assets")
            content_type = str(asset.get("content_type") or "application/octet-stream")
            if not (content_type.startswith(("image/", "video/")) or asset["kind"] in PUBLIC_DOWNLOAD_ARTIFACT_KINDS):
                raise NotFoundError("asset content is not public through the Runtime API")
            try:
                data = self.storage().load_bytes(asset["storage_key"])
            except FileNotFoundError as exc:
                raise NotFoundError("asset content not found in local storage") from exc
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
        return HTTPStatus.OK, {"content-type": f"{content_type}; charset=utf-8", "cache-control": "no-store"}, data

    def _error(self, status: HTTPStatus, message: str) -> tuple[int, dict[str, str], bytes]:
        return _json_response({"error": _redact_public_text(message)}, status=status)

    @staticmethod
    def _query_one(query: dict[str, list[str]], key: str) -> str | None:
        values = query.get(key) or []
        return values[0] if values else None

    @staticmethod
    def _library_filters(query: dict[str, list[str]]) -> dict[str, str]:
        allowed = {
            "collectionId",
            "commercialUse",
            "commercialUseStatus",
            "creatorApproved",
            "license",
            "licenseScope",
            "packId",
            "q",
            "tag",
            "type",
        }
        return {key: values[0] for key, values in query.items() if key in allowed and values and values[0] != ""}


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
