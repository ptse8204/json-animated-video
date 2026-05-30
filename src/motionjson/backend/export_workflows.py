from __future__ import annotations

import copy
import json
import mimetypes
import re
import shutil
import sqlite3
import subprocess
import uuid
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from xml.sax.saxutils import escape as xml_escape

from jsonschema.exceptions import ValidationError

from motionjson import __version__
from motionjson.backend.assets import list_assets_for_job, register_generated_asset
from motionjson.backend.corrections import build_track_correction_state, list_track_corrections
from motionjson.backend.jobs import create_completed_job, get_job, record_job_event
from motionjson.backend.rights import record_asset_lineage, record_audit_event, record_rights_metadata
from motionjson.exporters.final_render import build_final_export_manifest, final_export_entry, render_frames
from motionjson.exporters.object_layer_pack import OBJECT_LAYER_PACK_FORMAT, write_object_layer_pack
from motionjson.exporters.remotion import write_remotion_plan
from motionjson.exporters.website_package import export_website_package
from motionjson.providers.base import StorageProvider
from motionjson.rights import build_rights_review_report
from motionjson.validation import validate_document, validate_file, validate_output_dir


QUALITY_ROUTING_FORMAT = "motionjson.export_quality_routing.v0.1"


EXPORT_PRESETS: dict[str, dict[str, Any]] = {
    "compact": {
        "label": "Compact MotionJSON",
        "description": "Validated edited scene graph plus manifest and lightweight overlay preview.",
        "includeMasks": False,
        "includeContours": False,
        "includePreview": True,
    },
    "debug": {
        "label": "Debug package",
        "description": "Validated MotionJSON with contours, boxes, masks, overlay preview, and validation details.",
        "includeMasks": True,
        "includeContours": True,
        "includePreview": True,
    },
    "vector-heavy": {
        "label": "Vector-heavy handoff",
        "description": "Validated MotionJSON with contour and box JSON for downstream vector tooling.",
        "includeMasks": False,
        "includeContours": True,
        "includePreview": True,
    },
    "raster-fallback": {
        "label": "Raster fallback handoff",
        "description": "Validated MotionJSON plus fallback diagnostics for raster-only or weak vector runs.",
        "includeMasks": True,
        "includeContours": False,
        "includePreview": True,
    },
}

LOCAL_PATH_RE = re.compile(r"(?i)\bfile://[^\r\n]+|(?<![\w:])/(?:Users|private|var|tmp|Volumes|home)/[^\r\n]+")
WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"(?i)(?<![\w:])(?:[A-Z]:[\\/]|\\\\)[^\r\n\"'<>|]+")
STORAGE_KEY_RE = re.compile(r"\bprojects/[A-Za-z0-9._~!$&'()*+,;=:@%/-]+")
SCENE_CORRECTION_ONLY_KEYS = {
    "corrections",
    "deleted",
    "exportIncluded",
    "exportStatus",
    "hidden",
    "mergedInto",
    "repairRequested",
    "visible",
}


def export_presets() -> list[dict[str, Any]]:
    return [{"id": key, **value} for key, value in EXPORT_PRESETS.items()]


def _json_bytes(document: dict[str, Any]) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return parsed


def _safe_rel_path(value: str) -> Path:
    rel = Path(value.replace("\\", "/"))
    if rel.is_absolute() or ".." in rel.parts or not rel.parts:
        raise ValueError(f"unsafe artifact rel_path: {value}")
    return rel


def _artifact_rel_path(asset: dict[str, Any]) -> str:
    metadata = json.loads(asset.get("metadata_json") or "{}")
    rel_path = metadata.get("rel_path")
    return rel_path if isinstance(rel_path, str) and rel_path else str(asset.get("kind") or "artifact")


def materialize_job_assets(
    conn: sqlite3.Connection,
    *,
    storage: StorageProvider,
    project_id: str,
    source_job_id: str,
    out_dir: Path,
) -> list[dict[str, Any]]:
    assets = list_assets_for_job(conn, project_id=project_id, source_job_id=source_job_id)
    for asset in assets:
        rel_path = _safe_rel_path(_artifact_rel_path(asset))
        dest = out_dir / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(storage.load_bytes(asset["storage_key"]))
    return assets


def _sanitize_text(value: str) -> str:
    redacted = WINDOWS_ABSOLUTE_PATH_RE.sub("[LOCAL_PATH_REDACTED]", value)
    redacted = LOCAL_PATH_RE.sub("[LOCAL_PATH_REDACTED]", redacted)
    return STORAGE_KEY_RE.sub("[STORAGE_KEY_REDACTED]", redacted)


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _sanitize_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, str):
        return _sanitize_text(value)
    return value


def _object_id(item: dict[str, Any]) -> str:
    return str(item.get("id") or item.get("objectId") or item.get("object_id") or "")


def _edit_for_object(track_edits: dict[str, Any], object_id: str) -> dict[str, Any]:
    edit = track_edits.get(object_id)
    return edit if isinstance(edit, dict) else {}


def _status_excludes(value: Any) -> bool:
    return bool(re.search(r"deleted|excluded|rejected|failed|fallback_raster|merged|review_pending", str(value or "")))


def _status_hard_excludes(value: Any) -> bool:
    return bool(re.search(r"deleted|excluded|rejected|failed|fallback_raster|merged", str(value or "")))


def _status_requires_review(value: Any) -> bool:
    return bool(re.search(r"pending|review_pending|needs_review|awaiting_review", str(value or "")))


def _explicit_review_include(edit: dict[str, Any]) -> bool:
    return edit.get("exportIncluded") is True


def _track_id(item: dict[str, Any]) -> str:
    return str(item.get("objectId") or item.get("object_id") or item.get("id") or "")


def _track_export_ready(item: dict[str, Any]) -> bool:
    if item.get("deleted") or item.get("exportIncluded") is False:
        return False
    return not _status_excludes(item.get("exportStatus") or item.get("export_status") or "accepted")


def _export_ready_track_ids(track_summary: dict[str, Any] | None) -> set[str]:
    if not isinstance(track_summary, dict):
        return set()
    tracks = track_summary.get("tracks") if isinstance(track_summary.get("tracks"), list) else []
    return {
        track_id
        for track in tracks
        if isinstance(track, dict) and (track_id := _track_id(track)) and _track_export_ready(track)
    }


def _object_requires_review(item: dict[str, Any]) -> bool:
    quality = item.get("quality") if isinstance(item.get("quality"), dict) else {}
    discovery = item.get("discovery") if isinstance(item.get("discovery"), dict) else {}
    return (
        quality.get("reviewRequired") is True
        or discovery.get("reviewRequired") is True
        or _status_requires_review(item.get("exportStatus"))
        or _status_requires_review(discovery.get("exportStatus"))
    )


def _mark_reviewed_for_export(item: dict[str, Any]) -> None:
    item["exportIncluded"] = True
    item["exportStatus"] = "accepted"
    quality = item.get("quality") if isinstance(item.get("quality"), dict) else {}
    if quality:
        item["quality"] = {**quality, "reviewRequired": False}
    discovery = item.get("discovery") if isinstance(item.get("discovery"), dict) else {}
    if discovery:
        item["discovery"] = {
            **discovery,
            "reviewRequired": False,
            "reviewStatus": "accepted",
            "exportStatus": "accepted",
            "selectedForTracking": True,
        }


def _static_keyframe_fallback(obj: dict[str, Any]) -> bool:
    discovery = obj.get("discovery") if isinstance(obj.get("discovery"), dict) else {}
    if str(discovery.get("trackingProvider") or "") != "keyframe_seed_sequence":
        return False
    centers: list[tuple[float, float]] = []
    for entry in obj.get("motion", []):
        if not isinstance(entry, dict) or not entry.get("visible"):
            continue
        try:
            x = float(entry.get("x") or 0.0)
            y = float(entry.get("y") or 0.0)
            w = float(entry.get("w") or 0.0)
            h = float(entry.get("h") or 0.0)
        except (TypeError, ValueError):
            continue
        centers.append((x + w / 2.0, y + h / 2.0))
    if len(centers) <= 1:
        return False
    first_x, first_y = centers[0]
    max_shift = max(((x - first_x) ** 2 + (y - first_y) ** 2) ** 0.5 for x, y in centers)
    return max_shift < 2.0


def _included_object_ids(
    scene: dict[str, Any],
    correction_state: dict[str, Any],
    *,
    export_ready_track_ids: set[str] | None = None,
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    track_edits = correction_state.get("trackEdits") if isinstance(correction_state.get("trackEdits"), dict) else {}
    history = correction_state.get("history") if isinstance(correction_state.get("history"), list) else []
    scene_ids = {_object_id(obj) for obj in scene.get("objects", []) if isinstance(obj, dict)}
    export_ready_track_ids = export_ready_track_ids or set()
    included: list[str] = []
    excluded: list[str] = []
    diagnostics: list[dict[str, Any]] = []
    for obj in scene.get("objects", []):
        if not isinstance(obj, dict):
            continue
        object_id = _object_id(obj)
        edit = _edit_for_object(track_edits, object_id)
        include = True
        exclusion_reason: str | None = None
        if edit.get("deleted") or edit.get("mergedInto"):
            include = False
            exclusion_reason = "correction_state"
        if edit.get("exportIncluded") is False:
            include = False
            exclusion_reason = "export_excluded"
        quality = obj.get("quality") if isinstance(obj.get("quality"), dict) else {}
        discovery = obj.get("discovery") if isinstance(obj.get("discovery"), dict) else {}
        explicit_include = _explicit_review_include(edit)
        track_review_include = object_id in export_ready_track_ids
        hard_excluded = (
            obj.get("exportIncluded") is False
            or _status_hard_excludes(obj.get("exportStatus"))
            or _status_hard_excludes(discovery.get("exportStatus"))
        )
        review_required = _object_requires_review(obj)
        if not explicit_include and hard_excluded:
            include = False
            if obj.get("exportIncluded") is False:
                exclusion_reason = "export_excluded"
            elif _status_hard_excludes(obj.get("exportStatus")):
                exclusion_reason = str(obj.get("exportStatus") or "correction_state")
            elif _status_hard_excludes(discovery.get("exportStatus")):
                exclusion_reason = str(discovery.get("exportStatus") or "correction_state")
        elif not explicit_include and review_required and not track_review_include:
            include = False
            exclusion_reason = "review_required"
        elif not explicit_include and not track_review_include and (
            obj.get("exportIncluded") is False
            or _status_excludes(obj.get("exportStatus"))
            or quality.get("reviewRequired") is True
            or discovery.get("reviewRequired") is True
            or _status_excludes(discovery.get("exportStatus"))
        ):
            include = False
            if quality.get("reviewRequired") is True or discovery.get("reviewRequired") is True:
                exclusion_reason = "review_required"
            elif obj.get("exportIncluded") is False:
                exclusion_reason = "export_excluded"
            elif _status_excludes(obj.get("exportStatus")):
                exclusion_reason = str(obj.get("exportStatus") or "correction_state")
            elif _status_excludes(discovery.get("exportStatus")):
                exclusion_reason = str(discovery.get("exportStatus") or "correction_state")
        if include and _static_keyframe_fallback(obj):
            include = False
            exclusion_reason = "static_keyframe_mask_sequence"
            diagnostics.append(
                {
                    "code": "static_keyframe_mask_sequence",
                    "objectId": object_id,
                    "reason": "static_keyframe_mask_sequence",
                    "message": "This object uses a static keyframe mask sequence, so the exported trace would not follow the moving object.",
                }
            )
        if include:
            included.append(object_id)
        else:
            reason = exclusion_reason or edit.get("exportStatus") or obj.get("exportStatus")
            if not reason:
                reason = "review_required" if review_required else "correction_state"
            excluded.append(object_id)
            if reason != "static_keyframe_mask_sequence":
                diagnostics.append(
                    {
                        "code": "track_excluded_from_export",
                        "objectId": object_id,
                        "reason": reason,
                    }
                )
    for entry in history:
        if not isinstance(entry, dict):
            continue
        candidate_id = (
            entry.get("objectId")
            if entry.get("type") == "add_object"
            else entry.get("newTrackId") or entry.get("newObjectId")
            if entry.get("type") == "split_track"
            else None
        )
        if not candidate_id:
            continue
        candidate_id = str(candidate_id)
        if candidate_id in scene_ids or candidate_id in excluded:
            continue
        excluded.append(candidate_id)
        diagnostics.append(
            {
                "code": "correction_track_not_materialized",
                "objectId": candidate_id,
                "reason": "Correction hook is saved but no scene assets have been materialized for export.",
            }
        )
    return included, excluded, diagnostics


def _sanitized_scene(
    scene: dict[str, Any],
    correction_state: dict[str, Any],
    *,
    export_ready_track_ids: set[str] | None = None,
) -> tuple[dict[str, Any], list[str], list[str], list[dict[str, Any]]]:
    edited = copy.deepcopy(scene)
    track_edits = correction_state.get("trackEdits") if isinstance(correction_state.get("trackEdits"), dict) else {}
    export_ready_track_ids = export_ready_track_ids or set()
    track_reviewed_gate_ids = {
        _object_id(obj)
        for obj in edited.get("objects", [])
        if isinstance(obj, dict) and _object_id(obj) in export_ready_track_ids and _object_requires_review(obj)
    }
    included_ids, excluded_ids, diagnostics = _included_object_ids(
        edited,
        correction_state,
        export_ready_track_ids=export_ready_track_ids,
    )
    included_set = set(included_ids)

    objects: list[dict[str, Any]] = []
    for obj in edited.get("objects", []):
        if not isinstance(obj, dict):
            continue
        object_id = _object_id(obj)
        if object_id not in included_set:
            continue
        edit = _edit_for_object(track_edits, object_id)
        clean = {key: copy.deepcopy(value) for key, value in obj.items() if key not in SCENE_CORRECTION_ONLY_KEYS}
        if edit.get("label"):
            clean["label"] = str(edit["label"])
        if _explicit_review_include(edit) or object_id in track_reviewed_gate_ids:
            _mark_reviewed_for_export(clean)
        objects.append(clean)
    edited["objects"] = objects

    layers: list[dict[str, Any]] = []
    for layer in edited.get("layers", []):
        if not isinstance(layer, dict):
            continue
        object_id = str(layer.get("object_id") or layer.get("objectId") or "")
        if object_id not in included_set:
            continue
        edit = _edit_for_object(track_edits, object_id)
        clean = {key: copy.deepcopy(value) for key, value in layer.items() if key not in SCENE_CORRECTION_ONLY_KEYS}
        if _explicit_review_include(edit) or object_id in track_reviewed_gate_ids:
            clean["exportIncluded"] = True
            clean["exportStatus"] = "accepted"
        layers.append(clean)
    edited["layers"] = layers
    return _sanitize_value(edited), included_ids, excluded_ids, diagnostics


def _validation_issue(path: str, error: ValidationError) -> dict[str, Any]:
    parts = [str(part) for part in error.absolute_path]
    return {"path": path, "jsonPath": "$" if not parts else "$/" + "/".join(parts), "message": error.message}


def _validate_export_documents(documents: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    for path, document in documents:
        issues.extend(_validation_issue(path, error) for error in validate_document(document))
    return {
        "ok": not issues,
        "checked": len(documents),
        "issueCount": len(issues),
        "issues": issues,
        "aiUsage": "none",
    }


def _export_validation_messages(
    diagnostics: list[dict[str, Any]],
    export_warnings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for diagnostic in diagnostics:
        if not isinstance(diagnostic, dict):
            continue
        reason = str(diagnostic.get("reason") or "")
        object_id = str(diagnostic.get("objectId") or "")
        review_required = reason in {"review_required", "review_pending"}
        static_keyframe = reason == "static_keyframe_mask_sequence"
        messages.append(
            {
                "code": "auto_discovered_object_review_required"
                if review_required
                else "static_keyframe_mask_sequence"
                if static_keyframe
                else str(diagnostic.get("code") or "export_diagnostic"),
                "severity": "error" if static_keyframe else "warn",
                "objectId": object_id,
                "message": (
                    f"{object_id} was not included because auto-discovered objects require review before export."
                    if review_required and object_id
                    else f"{object_id} was not included because its mask sequence is static and would not follow the moving object."
                    if static_keyframe and object_id
                    else str(diagnostic.get("reason") or diagnostic.get("message") or "object was not included in export")
                ),
                "suggestedAction": (
                    "Review and accept the object track, then validate export again."
                    if review_required
                    else "Track the selected candidate again with moving masks, use template-match/SAM video propagation, or provide external masks before export."
                    if static_keyframe
                    else "Review track corrections and export inclusion before publishing."
                ),
                "source": "export_validation",
            }
        )
    for warning in export_warnings:
        if not isinstance(warning, dict):
            continue
        messages.append(
            {
                "code": str(warning.get("code") or "export_warning"),
                "severity": str(warning.get("severity") or "warn"),
                "objectId": warning.get("objectId"),
                "message": str(warning.get("message") or warning.get("suggestedAction") or "export warning"),
                "suggestedAction": warning.get("suggestedAction"),
                "source": "rights_and_lineage",
            }
        )
    return _sanitize_value(messages)


def _canvas(scene: dict[str, Any]) -> dict[str, Any]:
    source = scene.get("source", {}) if isinstance(scene.get("source"), dict) else {}
    canvas = scene.get("canvas", {}) if isinstance(scene.get("canvas"), dict) else {}
    return {
        "width": int(source.get("width") or canvas.get("width") or 1),
        "height": int(source.get("height") or canvas.get("height") or 1),
        "fps": float(source.get("sampleFps") or canvas.get("fps") or 12),
        "frameCount": int(source.get("sampledFrameCount") or canvas.get("frame_count") or 0),
    }


def _ready_status(value: Any) -> bool:
    return isinstance(value, dict) and value.get("status") == "ready" and bool(value.get("path"))


def _candidate_delivery_from_optimizer(selected: dict[str, Any] | None) -> dict[str, Any] | None:
    if not _ready_status(selected):
        return None
    name = str(selected.get("name") or "")
    route_by_name = {
        "webpSpriteAtlas": "sprite_atlas_webp",
        "transparentWebm": "transparent_webm",
        "avifSpriteAtlas": "sprite_atlas_avif",
    }
    if name not in route_by_name:
        return None
    return {
        "route": route_by_name[name],
        "status": "ready",
        "path": selected.get("path"),
        "bytes": int(selected.get("bytes") or 0),
        "source": "compression_optimizer",
        "reason": selected.get("reason"),
    }


def _candidate_delivery_from_assets(production: dict[str, Any]) -> dict[str, Any] | None:
    assets = production.get("assets") if isinstance(production.get("assets"), dict) else {}
    candidates: list[dict[str, Any]] = []
    for key, route in (
        ("webpSpriteAtlas", "sprite_atlas_webp"),
        ("transparentWebm", "transparent_webm"),
        ("avifSpriteAtlas", "sprite_atlas_avif"),
    ):
        asset = assets.get(key)
        if _ready_status(asset):
            candidates.append(
                {
                    "route": route,
                    "status": "ready",
                    "path": asset.get("path"),
                    "bytes": int(asset.get("bytes") or 0),
                    "source": "ready_production_asset",
                    "reason": asset.get("reason"),
                }
            )
    if not candidates:
        return None
    return min(candidates, key=lambda candidate: int(candidate.get("bytes") or 0))


def _object_delivery_route(obj: dict[str, Any]) -> dict[str, Any]:
    assets = obj.get("assets") if isinstance(obj.get("assets"), dict) else {}
    production = assets.get("production")
    if isinstance(production, dict):
        optimizer = production.get("compressionOptimizer") if isinstance(production.get("compressionOptimizer"), dict) else {}
        selected = optimizer.get("selected") if isinstance(optimizer.get("selected"), dict) else None
        delivery = _candidate_delivery_from_optimizer(selected) or _candidate_delivery_from_assets(production)
        if delivery is not None:
            return delivery

    spritesheet = assets.get("spritesheet")
    if isinstance(spritesheet, dict) and spritesheet.get("path"):
        return {
            "route": "sprite_atlas_webp" if str(spritesheet.get("path", "")).endswith(".webp") else "sprite_atlas",
            "status": "ready",
            "path": spritesheet.get("path"),
            "bytes": int(spritesheet.get("bytes") or 0),
            "source": "authoring_spritesheet",
            "reason": None,
        }

    return {
        "route": "raster_alpha_sequence",
        "status": "ready",
        "path": obj.get("asset") or assets.get("cutoutPattern", ""),
        "bytes": 0,
        "source": "cached_rgba_cutout_sequence",
        "reason": "no ready sprite atlas or transparent WebM production asset",
    }


def _object_quality_route(obj: dict[str, Any], *, include_contours: bool) -> dict[str, Any]:
    quality = obj.get("quality") if isinstance(obj.get("quality"), dict) else {}
    recommended = str(obj.get("recommendedOutput") or "raster_alpha_sequence")
    routing_reasons = [str(item) for item in quality.get("routingReasons", []) if str(item)]
    vector_ready = recommended == "hybrid_vector_silhouette_plus_raster" and include_contours
    if recommended == "hybrid_vector_silhouette_plus_raster" and not include_contours:
        routing_reasons = [*routing_reasons, "export_preset_excludes_contours"]
    selected = "hybrid_vector_silhouette_plus_raster" if vector_ready else "raster_alpha_sequence"
    return {
        "selectedOutput": selected,
        "recommendedOutput": recommended,
        "productionReadiness": quality.get("productionReadiness", "review"),
        "productionReadinessScore": quality.get("productionReadinessScore"),
        "vectorSuitability": quality.get("vectorSuitability"),
        "routingReasons": routing_reasons,
        "rasterAlpha": {
            "status": "ready",
            "path": obj.get("asset") or (obj.get("assets") if isinstance(obj.get("assets"), dict) else {}).get("cutoutPattern", ""),
            "source": "cached_rgba_cutout_sequence",
        },
        "vectorSilhouette": {
            "status": "ready" if vector_ready else "skipped",
            "path": "objects/contours_boxes.json" if include_contours else None,
            "reason": None if vector_ready else "quality route or export preset did not enable vector silhouette",
            "source": "cached_contours_and_boxes",
        },
    }


def _load_track_summary_from_assets(source_dir: Path, assets: list[dict[str, Any]]) -> dict[str, Any] | None:
    for asset in reversed(assets):
        if asset.get("kind") != "track_summary":
            continue
        rel_path = _safe_rel_path(_artifact_rel_path(asset))
        path = source_dir / rel_path
        if path.exists():
            return _load_json(path)
    return None


def _build_quality_routing(
    *,
    scene: dict[str, Any],
    preset: str,
    include_masks: bool,
    include_contours: bool,
    include_preview: bool,
    preview: dict[str, Any] | None,
    mp4_preview: dict[str, Any],
) -> dict[str, Any]:
    resource_profile = scene.get("resource_profile") if isinstance(scene.get("resource_profile"), dict) else {}
    comparison = resource_profile.get("resourceComparison") if isinstance(resource_profile.get("resourceComparison"), dict) else {}
    objects: list[dict[str, Any]] = []
    for obj in scene.get("objects", []):
        if not isinstance(obj, dict):
            continue
        quality_route = _object_quality_route(obj, include_contours=include_contours)
        delivery_route = _object_delivery_route(obj)
        objects.append(
            {
                "objectId": obj.get("id") or obj.get("objectId"),
                "label": obj.get("label"),
                **quality_route,
                "selectedDelivery": delivery_route,
                "resourceSignals": {
                    "productionPackageToSourceRatio": comparison.get("productionPackageToSourceRatio"),
                    "webpSpriteAtlasToCutoutRatio": comparison.get("webpSpriteAtlasToCutoutRatio"),
                    "transparentWebmToCutoutRatio": comparison.get("transparentWebmToCutoutRatio"),
                    "avifSpriteAtlasToCutoutRatio": comparison.get("avifSpriteAtlasToCutoutRatio"),
                },
            }
        )
    return {
        "format": QUALITY_ROUTING_FORMAT,
        "preset": preset,
        "aiUsage": "none",
        "source": "cached_quality_scores_and_resource_profile",
        "includeMasks": include_masks,
        "includeContours": include_contours,
        "includePreview": include_preview,
        "objects": objects,
        "preview": {
            "overlayPreview": {
                "status": "ready" if preview else "skipped",
                "path": preview.get("path") if isinstance(preview, dict) else None,
                "source": "cached_scene_boxes",
            },
            "mp4Preview": mp4_preview,
        },
        "notes": [
            "Raster alpha remains the default photoreal object representation.",
            "Vector silhouette routing is only selected when quality and export preset both allow contours.",
            "Sprite atlas and transparent WebM delivery are selected from local production assets when available.",
            "MP4 preview is optional and depends on local FFmpeg availability.",
        ],
    }


def _remove_partial_file(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return


def _write_mp4_preview(
    *,
    source_dir: Path,
    export_dir: Path,
    scene: dict[str, Any],
    include_preview: bool,
    render: bool = True,
) -> dict[str, Any]:
    rel_path = "preview/preview.mp4"
    output_path = export_dir / rel_path
    canvas = _canvas(scene)
    base = {
        "type": "mp4_preview",
        "format": "mp4",
        "status": "skipped",
        "mimeType": "video/mp4",
        "path": rel_path,
        "bytes": 0,
        "aiUsage": "none",
        "source": "cached_assets_and_json_transforms",
        "width": canvas["width"],
        "height": canvas["height"],
        "fps": canvas["fps"],
        "frameCount": canvas["frameCount"],
    }
    if not include_preview:
        return {**base, "reason": "preview export disabled"}
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return {**base, "status": "unavailable", "reason": "ffmpeg executable was not found"}
    if not render:
        return {**base, "status": "plan_ready", "reason": "preview MP4 will be encoded during export"}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="motionjson_export_preview_") as tmp:
        frame_dir = Path(tmp)
        try:
            render_frames(out_dir=source_dir, scene=scene, frame_dir=frame_dir)
            command = [
                ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-framerate",
                str(canvas["fps"]),
                "-i",
                str(frame_dir / "frame_%06d.png"),
                "-vf",
                "pad=ceil(iw/2)*2:ceil(ih/2)*2",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                "-an",
                str(output_path),
            ]
            result = subprocess.run(command, capture_output=True, text=True, check=False)
        except Exception as exc:
            _remove_partial_file(output_path)
            return {**base, "status": "error", "reason": _sanitize_text(str(exc))}
    if result.returncode != 0:
        _remove_partial_file(output_path)
        return {**base, "status": "error", "reason": _sanitize_text((result.stderr or result.stdout or "ffmpeg failed").strip())}
    if not output_path.exists() or output_path.stat().st_size == 0:
        _remove_partial_file(output_path)
        return {**base, "status": "error", "reason": "ffmpeg completed but produced no output bytes"}
    return final_export_entry(
        export_type="mp4_preview",
        format_name="mp4",
        output_path=output_path,
        out_dir=export_dir,
        status="ready",
        mime_type="video/mp4",
        width=canvas["width"],
        height=canvas["height"],
        fps=canvas["fps"],
        frame_count=canvas["frameCount"],
        extra={"preset": "preview", "cachedSources": ["scene_graph.json", "objects/*/cutouts/*.png"]},
    )


def _first_visible_frame(obj: dict[str, Any]) -> dict[str, Any] | None:
    for frame in obj.get("frames", []):
        if isinstance(frame, dict) and frame.get("visible"):
            return frame
    for frame in obj.get("motion", []):
        if isinstance(frame, dict) and frame.get("visible"):
            return frame
    return None


def _write_preview_svg(scene: dict[str, Any], path: Path) -> dict[str, Any]:
    canvas = _canvas(scene)
    path.parent.mkdir(parents=True, exist_ok=True)
    width = canvas["width"]
    height = canvas["height"]
    colors = ["#10a37f", "#2f80ed", "#9a6a12", "#6046a5", "#b42318", "#0f766e"]
    rows = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f7f9f8"/>',
    ]
    overlay_count = 0
    for index, obj in enumerate(scene.get("objects", [])):
        if not isinstance(obj, dict):
            continue
        frame = _first_visible_frame(obj)
        if not frame:
            continue
        bbox = frame.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            bbox = [frame.get("x", 0), frame.get("y", 0), frame.get("w", 0), frame.get("h", 0)]
        x, y, w, h = [int(float(part or 0)) for part in bbox]
        color = colors[index % len(colors)]
        label = xml_escape(_sanitize_text(str(obj.get("label") or obj.get("id") or f"object_{index}")))
        rows.append(f'<rect x="{x}" y="{y}" width="{max(w, 0)}" height="{max(h, 0)}" fill="none" stroke="{color}" stroke-width="3"/>')
        rows.append(f'<text x="{max(x, 4)}" y="{max(y - 6, 14)}" font-family="Arial, sans-serif" font-size="13" fill="{color}">{label}</text>')
        overlay_count += 1
    rows.append("</svg>")
    path.write_text("\n".join(rows), encoding="utf-8")
    return {
        "format": "motionjson.preview_overlay.v0.1",
        "path": "preview/overlay_preview.svg",
        "objectCount": overlay_count,
        "width": width,
        "height": height,
        "aiUsage": "none",
    }


def _frame_contour_record(frame: dict[str, Any]) -> dict[str, Any]:
    return {
        "frame": frame.get("frame"),
        "visible": bool(frame.get("visible")),
        "bbox": frame.get("bbox") or [frame.get("x"), frame.get("y"), frame.get("w"), frame.get("h")],
        "centroid": frame.get("centroid"),
        "polygon": frame.get("polygon", []),
        "mask": frame.get("mask"),
        "asset": frame.get("asset"),
    }


def _write_contours(scene: dict[str, Any], path: Path) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    objects = []
    for obj in scene.get("objects", []):
        if not isinstance(obj, dict):
            continue
        frames = obj.get("frames") if isinstance(obj.get("frames"), list) else obj.get("motion", [])
        objects.append(
            {
                "objectId": obj.get("id"),
                "label": obj.get("label"),
                "frames": [_frame_contour_record(frame) for frame in frames if isinstance(frame, dict)],
            }
        )
    document = {"format": "motionjson.export_contours.v0.1", "objects": objects, "aiUsage": "none"}
    path.write_bytes(_json_bytes(document))
    return document


def _copy_masks(source_dir: Path, export_dir: Path, included_ids: list[str]) -> list[str]:
    copied: list[str] = []
    for object_id in included_ids:
        source = source_dir / "masks" / object_id
        if not source.exists() or not source.is_dir():
            continue
        dest = export_dir / "masks" / object_id
        dest.mkdir(parents=True, exist_ok=True)
        for mask in sorted(source.glob("*.png")):
            target = dest / mask.name
            shutil.copy2(mask, target)
            copied.append(str(target.relative_to(export_dir)).replace("\\", "/"))
    return copied


def _source_asset_id(conn: sqlite3.Connection, source_job_id: str) -> str | None:
    row = conn.execute(
        """
        SELECT source_asset_id
        FROM asset_lineage
        WHERE job_id = ? AND source_asset_id IS NOT NULL
        ORDER BY created_at, id
        LIMIT 1
        """,
        (source_job_id,),
    ).fetchone()
    return row["source_asset_id"] if row else None


def _rights_by_object(scene: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rights: dict[str, dict[str, Any]] = {}
    for index, obj in enumerate(scene.get("objects", [])):
        if not isinstance(obj, dict):
            continue
        object_id = str(obj.get("id") or obj.get("objectId") or f"object_{index}")
        value = obj.get("rights") if isinstance(obj.get("rights"), dict) else {}
        rights[object_id] = copy.deepcopy(value)
    return rights


def _object_id_for_export_rel_path(rel_path: Path) -> str | None:
    parts = rel_path.parts
    if len(parts) >= 2 and parts[0] == "masks":
        return parts[1]
    if len(parts) >= 3 and parts[0] == "objects":
        return parts[1]
    return None


def _record_export_asset_rights_and_lineage(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    job_id: str,
    asset: dict[str, Any],
    source_asset_id: str | None,
    rel_path: Path,
    export_id: str,
    preset: str,
    rights_by_object: dict[str, dict[str, Any]],
) -> None:
    object_id = _object_id_for_export_rel_path(rel_path)
    record_asset_lineage(
        conn,
        project_id=project_id,
        source_asset_id=source_asset_id,
        derived_asset_id=asset["id"],
        job_id=job_id,
        operation="validated_motionjson_export",
        object_id=object_id,
        metadata={
            "exportId": export_id,
            "preset": preset,
            "rel_path": rel_path.as_posix(),
            "kind": asset.get("kind"),
            "aiUsage": "none",
        },
    )
    if object_id and object_id in rights_by_object:
        record_rights_metadata(conn, project_id=project_id, asset_id=asset["id"], object_id=object_id, job_id=job_id, rights=rights_by_object[object_id])
        return
    for rights_object_id, rights in rights_by_object.items():
        record_rights_metadata(conn, project_id=project_id, asset_id=asset["id"], object_id=rights_object_id, job_id=job_id, rights=rights)


def _build_export_tree(
    conn: sqlite3.Connection,
    *,
    storage: StorageProvider,
    user_id: str,
    job_id: str,
    export_dir: Path,
    preset: str,
    include_masks: bool | None = None,
    include_contours: bool | None = None,
    include_preview: bool | None = None,
    render_mp4_preview: bool = True,
) -> dict[str, Any]:
    if preset not in EXPORT_PRESETS:
        raise ValueError(f"export preset must be one of: {', '.join(EXPORT_PRESETS)}")
    job = get_job(conn, user_id=user_id, job_id=job_id)
    source_dir = export_dir.parent / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    materialized_assets = materialize_job_assets(conn, storage=storage, project_id=job["project_id"], source_job_id=job_id, out_dir=source_dir)
    scene_path = source_dir / "scene_graph.json"
    if not scene_path.exists():
        raise ValueError("selected job has no scene_graph.json artifact to export")
    scene = _load_json(scene_path)
    track_summary = _load_track_summary_from_assets(source_dir, materialized_assets)
    export_ready_track_ids = _export_ready_track_ids(track_summary)
    corrections = list_track_corrections(conn, user_id=user_id, job_id=job_id)
    correction_state = build_track_correction_state(corrections, job_id=job_id)
    exported_scene, included_ids, excluded_ids, diagnostics = _sanitized_scene(
        scene,
        correction_state,
        export_ready_track_ids=export_ready_track_ids,
    )
    if not exported_scene.get("objects"):
        raise ValueError("No exportable object tracks are included; enable at least one accepted track before export")

    preset_config = EXPORT_PRESETS[preset]
    include_masks = preset_config["includeMasks"] if include_masks is None else bool(include_masks)
    include_contours = preset_config["includeContours"] if include_contours is None else bool(include_contours)
    include_preview = preset_config["includePreview"] if include_preview is None else bool(include_preview)

    export_dir.mkdir(parents=True, exist_ok=True)
    exported_scene_path = export_dir / "scene_graph.json"
    exported_scene_path.write_bytes(_json_bytes(exported_scene))
    exports = [
        final_export_entry(
            export_type="validated_motionjson_scene",
            format_name="motionjson-json",
            output_path=exported_scene_path,
            out_dir=export_dir,
            status="ready",
            mime_type="application/json",
            width=_canvas(exported_scene)["width"],
            height=_canvas(exported_scene)["height"],
            fps=_canvas(exported_scene)["fps"],
            frame_count=_canvas(exported_scene)["frameCount"],
            extra={"includedObjectIds": included_ids, "excludedObjectIds": excluded_ids, "preset": preset},
        )
    ]

    contour_document = None
    if include_contours:
        contour_path = export_dir / "objects" / "contours_boxes.json"
        contour_document = _write_contours(exported_scene, contour_path)
        exports.append(
            final_export_entry(
                export_type="contours_boxes",
                format_name="json",
                output_path=contour_path,
                out_dir=export_dir,
                status="ready",
                mime_type="application/json",
                extra={"preset": preset, "objectCount": len(contour_document["objects"])},
            )
        )

    mask_paths = _copy_masks(source_dir, export_dir, included_ids) if include_masks else []
    if mask_paths:
        exports.append(
            {
                "type": "mask_sequence",
                "format": "png-sequence",
                "status": "ready",
                "mimeType": "image/png",
                "path": "masks/",
                "bytes": sum((export_dir / rel).stat().st_size for rel in mask_paths),
                "aiUsage": "none",
                "source": "cached_mask_artifacts",
                "fileCount": len(mask_paths),
                "includedObjectIds": included_ids,
            }
        )

    preview = None
    if include_preview:
        preview_path = export_dir / "preview" / "overlay_preview.svg"
        preview = _write_preview_svg(exported_scene, preview_path)
        exports.append(
            final_export_entry(
                export_type="preview_overlay",
                format_name="svg",
                output_path=preview_path,
                out_dir=export_dir,
                status="ready",
                mime_type="image/svg+xml",
                width=preview["width"],
                height=preview["height"],
                extra={"preset": preset, "objectCount": preview["objectCount"]},
            )
        )
    mp4_preview = _write_mp4_preview(
        source_dir=source_dir,
        export_dir=export_dir,
        scene=exported_scene,
        include_preview=include_preview,
        render=render_mp4_preview,
    )
    exports.append(mp4_preview)

    quality_routing = _build_quality_routing(
        scene=exported_scene,
        preset=preset,
        include_masks=include_masks,
        include_contours=include_contours,
        include_preview=include_preview,
        preview=preview,
        mp4_preview=mp4_preview,
    )
    routing_path = export_dir / "quality_routing.json"
    routing_path.write_bytes(_json_bytes(quality_routing))
    exports.append(
        final_export_entry(
            export_type="export_quality_routing",
            format_name="json",
            output_path=routing_path,
            out_dir=export_dir,
            status="ready",
            mime_type="application/json",
            extra={"preset": preset, "objectCount": len(quality_routing["objects"])},
        )
    )

    payload = json.loads(job.get("payload_json") or "{}")
    export_id = export_dir.name
    source_asset_id = _source_asset_id(conn, job_id)
    rights_report = _sanitize_value(build_rights_review_report(scene=exported_scene, source_asset_id=source_asset_id))
    export_warnings = rights_report["warnings"]
    export_validation_messages = _export_validation_messages(diagnostics, export_warnings)
    provenance = {
        "app": "motionjson",
        "version": __version__,
        "sourceJobId": job_id,
        "sourceAssetId": source_asset_id,
        "exportId": export_id,
        "exportPreset": preset,
        "correctionEventCount": len(corrections),
        "includedObjectIds": included_ids,
        "excludedObjectIds": excluded_ids,
        "diagnostics": diagnostics,
        "rightsSummary": rights_report["summary"],
        "rightsWarningCount": len(export_warnings),
        "aiUsage": "none",
    }
    config = {
        "preset": preset,
        "includeMasks": include_masks,
        "includeContours": include_contours,
        "includePreview": include_preview,
        "sourceJob": _sanitize_value({"type": job.get("type"), "payload": payload}),
        "correctionState": _sanitize_value(correction_state),
    }
    remotion_plan_path = export_dir / "remotion_export_plan.json"
    remotion_plan_entry = write_remotion_plan(out_dir=export_dir, output_path=remotion_plan_path)
    exports.append(remotion_plan_entry)
    object_layer_pack_path = export_dir / "object_layer_pack.json"
    object_layer_pack = write_object_layer_pack(
        object_layer_pack_path,
        exported_scene,
        selected_object_ids=included_ids,
        excluded_object_ids=excluded_ids,
        quality_routing=quality_routing,
        validation_messages=export_validation_messages,
        source_scene_graph="scene_graph.json",
        website_package_path="website_package.zip",
        remotion_plan_path="remotion_export_plan.json",
    )
    exports.append(
        final_export_entry(
            export_type="object_layer_pack",
            format_name="json",
            output_path=object_layer_pack_path,
            out_dir=export_dir,
            status="ready",
            mime_type="application/json",
            extra={
                "preset": preset,
                "packFormat": OBJECT_LAYER_PACK_FORMAT,
                "selectedObjectIds": included_ids,
                "excludedObjectIds": excluded_ids,
                "objectCount": object_layer_pack["objectCount"],
            },
        )
    )
    website_package_path = export_dir / "website_package.zip"
    website_package_entry = export_website_package(
        out_dir=source_dir,
        output_path=website_package_path,
        object_ids=included_ids,
        excluded_object_ids=excluded_ids,
        scene_override=exported_scene,
        quality_routing=quality_routing,
        validation_messages=export_validation_messages,
    )
    website_package_entry["path"] = "website_package.zip"
    website_package_entry["bytes"] = website_package_path.stat().st_size if website_package_path.exists() else 0
    website_package_entry["includedObjectIds"] = included_ids
    website_package_entry["excludedObjectIds"] = excluded_ids
    website_package_entry["preset"] = preset
    exports.append(website_package_entry)
    validation = _validate_export_documents([("scene_graph.json", exported_scene)])
    manifest = build_final_export_manifest(
        out_dir=export_dir,
        scene=exported_scene,
        exports=exports,
        provenance=provenance,
        config=config,
        quality_routing=quality_routing,
        object_layer_pack={
            "format": object_layer_pack["format"],
            "path": "object_layer_pack.json",
            "selectedObjectIds": included_ids,
            "excludedObjectIds": excluded_ids,
            "objectCount": object_layer_pack["objectCount"],
        },
        export_validation_messages=export_validation_messages,
        export_warnings=export_warnings,
        validation={key: value for key, value in validation.items() if key != "issues"},
    )
    validation = _validate_export_documents([("scene_graph.json", exported_scene), ("final_export_manifest.json", manifest)])
    manifest["validation"] = {key: value for key, value in validation.items() if key != "issues"}
    manifest_path = export_dir / "final_export_manifest.json"
    manifest_path.write_bytes(_json_bytes(manifest))

    validation_report = {
        "format": "motionjson.export_validation_report.v0.1",
        "exportId": export_id,
        "preset": preset,
        "validation": validation,
        "includedObjectIds": included_ids,
        "excludedObjectIds": excluded_ids,
        "diagnostics": diagnostics,
        "exportValidationMessages": export_validation_messages,
        "qualityRouting": quality_routing,
        "objectLayerPack": {
            "format": object_layer_pack["format"],
            "path": "object_layer_pack.json",
            "selectedObjectIds": included_ids,
            "excludedObjectIds": excluded_ids,
            "objectCount": object_layer_pack["objectCount"],
        },
        "rightsSummary": rights_report,
        "exportWarnings": export_warnings,
        "aiUsage": "none",
    }
    validation_path = export_dir / "validation_report.json"
    validation_path.write_bytes(_json_bytes(validation_report))

    bundle_path = export_dir / "motionjson_export.zip"
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(export_dir.rglob("*")):
            if not path.is_file() or path == bundle_path:
                continue
            rel = path.relative_to(export_dir)
            if rel.is_absolute() or ".." in rel.parts:
                continue
            archive.write(path, rel.as_posix())

    return {
        "format": "motionjson.local_ui_validated_export.v0.1",
        "exportId": export_id,
        "preset": preset,
        "exportDir": export_dir,
        "scene": exported_scene,
        "manifest": manifest,
        "validation": validation,
        "validationReport": validation_report,
        "preview": preview,
        "contours": contour_document,
        "qualityRouting": quality_routing,
        "objectLayerPack": object_layer_pack,
        "exportValidationMessages": export_validation_messages,
        "rightsSummary": rights_report,
        "exportWarnings": export_warnings,
        "maskPaths": mask_paths,
        "includedObjectIds": included_ids,
        "excludedObjectIds": excluded_ids,
        "diagnostics": diagnostics,
        "provenance": provenance,
        "config": config,
    }


def validate_motionjson_export_job(
    conn: sqlite3.Connection,
    *,
    storage: StorageProvider,
    user_id: str,
    job_id: str,
    preset: str = "compact",
    include_masks: bool | None = None,
    include_contours: bool | None = None,
    include_preview: bool | None = None,
) -> dict[str, Any]:
    with TemporaryDirectory(prefix="motionjson_validate_export_") as tmp:
        result = _build_export_tree(
            conn,
            storage=storage,
            user_id=user_id,
            job_id=job_id,
            export_dir=Path(tmp) / f"export_{uuid.uuid4().hex[:10]}",
            preset=preset,
            include_masks=include_masks,
            include_contours=include_contours,
            include_preview=include_preview,
            render_mp4_preview=False,
        )
        return {
            "format": "motionjson.local_ui_export_validation.v0.1",
            "exportId": result["exportId"],
            "preset": preset,
            "validation": result["validation"],
            "includedObjectIds": result["includedObjectIds"],
            "excludedObjectIds": result["excludedObjectIds"],
            "diagnostics": result["diagnostics"],
            "exportValidationMessages": result["exportValidationMessages"],
            "qualityRouting": result["qualityRouting"],
            "objectLayerPack": {
                "format": result["objectLayerPack"]["format"],
                "selectedObjectIds": result["objectLayerPack"]["selectedObjectIds"],
                "excludedObjectIds": result["objectLayerPack"]["excludedObjectIds"],
                "objectCount": result["objectLayerPack"]["objectCount"],
            },
            "rightsSummary": result["rightsSummary"],
            "exportWarnings": result["exportWarnings"],
            "provenance": result["provenance"],
            "config": result["config"],
        }


def export_motionjson_job(
    conn: sqlite3.Connection,
    *,
    storage: StorageProvider,
    user_id: str,
    job_id: str,
    preset: str = "compact",
    include_masks: bool | None = None,
    include_contours: bool | None = None,
    include_preview: bool | None = None,
) -> dict[str, Any]:
    job = get_job(conn, user_id=user_id, job_id=job_id)
    export_id = f"export_{uuid.uuid4().hex[:10]}"
    with TemporaryDirectory(prefix="motionjson_export_") as tmp:
        result = _build_export_tree(
            conn,
            storage=storage,
            user_id=user_id,
            job_id=job_id,
            export_dir=Path(tmp) / export_id,
            preset=preset,
            include_masks=include_masks,
            include_contours=include_contours,
            include_preview=include_preview,
        )
        if not result["validation"]["ok"]:
            first_issue = result["validation"]["issues"][0]["message"] if result["validation"].get("issues") else "validation failed"
            raise ValueError(f"MotionJSON export validation failed: {first_issue}")
        assets = []
        rights_by_object = _rights_by_object(result["scene"])
        source_asset_id = result["provenance"].get("sourceAssetId")
        for rel_path, kind, content_type in _export_asset_specs(result["exportDir"]):
            path = result["exportDir"] / rel_path
            metadata: dict[str, Any] = {
                "aiUsage": "none",
                "exportId": export_id,
                "preset": preset,
                "validation": {key: value for key, value in result["validation"].items() if key != "issues"},
                "rightsWarningCount": len(result["exportWarnings"]),
            }
            if kind in {"export_quality_routing", "export_validation_report"}:
                metadata["qualityRouting"] = result["qualityRouting"]
                metadata["rightsSummary"] = result["rightsSummary"]
            asset = register_generated_asset(
                conn,
                storage=storage,
                project_id=job["project_id"],
                source_job_id=job_id,
                kind=kind,
                path=path,
                rel_path=f"exports/{export_id}/{rel_path.as_posix()}",
                content_type=content_type,
                metadata=metadata,
            )
            assets.append(asset)
            _record_export_asset_rights_and_lineage(
                conn,
                project_id=job["project_id"],
                job_id=job_id,
                asset=asset,
                source_asset_id=source_asset_id,
                rel_path=rel_path,
                export_id=export_id,
                preset=preset,
                rights_by_object=rights_by_object,
            )
    record_job_event(
        conn,
        job_id=job_id,
        event_type="export_validated",
        message=f"{preset} MotionJSON export generated",
        metadata={
            "exportId": export_id,
            "preset": preset,
            "validation": {key: value for key, value in result["validation"].items() if key != "issues"},
            "includedObjectIds": result["includedObjectIds"],
            "excludedObjectIds": result["excludedObjectIds"],
            "rightsWarningCount": len(result["exportWarnings"]),
        },
    )
    record_audit_event(
        conn,
        user_id=user_id,
        project_id=job["project_id"],
        job_id=job_id,
        event_type="validated_motionjson_export",
        metadata={"exportId": export_id, "preset": preset, "aiUsage": "none", "rightsWarningCount": len(result["exportWarnings"])},
    )
    return {**{key: value for key, value in result.items() if key != "exportDir"}, "assets": assets}


def _export_asset_specs(export_dir: Path) -> list[tuple[Path, str, str]]:
    specs: list[tuple[Path, str, str]] = []
    for path in sorted(export_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(export_dir)
        name = rel.as_posix()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if name == "scene_graph.json":
            kind = "validated_motionjson_scene"
        elif name == "final_export_manifest.json":
            kind = "final_export_manifest"
        elif name == "validation_report.json":
            kind = "export_validation_report"
        elif name == "quality_routing.json":
            kind = "export_quality_routing"
        elif name == "object_layer_pack.json":
            kind = "object_layer_pack"
        elif name == "remotion_export_plan.json":
            kind = "remotion_plan"
        elif name == "website_package.zip":
            kind = "website_package"
            content_type = "application/zip"
        elif name == "preview/overlay_preview.svg":
            kind = "preview_overlay"
        elif name == "preview/preview.mp4":
            kind = "mp4_preview"
        elif name == "objects/contours_boxes.json":
            kind = "contours_boxes"
        elif name == "motionjson_export.zip":
            kind = "motionjson_export_zip"
            content_type = "application/zip"
        elif name.startswith("masks/"):
            kind = "export_mask"
        else:
            kind = "motionjson_export_file"
        specs.append((rel, kind, content_type))
    return specs


def _import_kind_for_rel_path(rel_path: str) -> str:
    path = Path(rel_path.replace("\\", "/"))
    name = path.name
    if rel_path == "scene_graph.json":
        return "scene_graph"
    if rel_path == "object_motion.json":
        return "object_motion"
    if rel_path == "rights_manifest.json":
        return "rights_manifest"
    if rel_path == "resource_profile.json":
        return "resource_profile"
    if name == "object_manifest.json":
        return "object_manifest"
    if name == "web_asset_manifest.json":
        return "web_manifest"
    if name.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".svg")):
        return "imported_preview"
    return "imported_motionjson_file"


def import_motionjson_result(
    conn: sqlite3.Connection,
    *,
    storage: StorageProvider,
    user_id: str,
    project_id: str,
    path: str | Path,
) -> dict[str, Any]:
    source = Path(path).expanduser()
    if not source.exists():
        raise FileNotFoundError(f"MotionJSON import path does not exist: {source}")
    if source.is_symlink():
        raise ValueError("MotionJSON import paths cannot be symlinks")
    if source.is_dir():
        source_root = source.resolve()
        files = []
        for item in sorted(source.rglob("*")):
            if item.is_symlink():
                raise ValueError("MotionJSON import directories cannot contain symlinks")
            if not item.is_file():
                continue
            resolved = item.resolve()
            if source_root not in (resolved, *resolved.parents):
                raise ValueError("MotionJSON import file escapes the selected directory")
            files.append(item)
        validation_result = validate_output_dir(source)
        rel_paths = [item.relative_to(source).as_posix() for item in files]
    else:
        validation_result = validate_file(source)
        files = [source]
        try:
            imported_document = _load_json(source)
        except Exception:
            imported_document = {}
        rel_paths = ["scene_graph.json" if imported_document.get("schema") == "motionjson.scene_graph.v0.1" else source.name]
    validation = {
        "ok": validation_result.ok,
        "checked": len(validation_result.checked),
        "skipped": len(validation_result.skipped),
        "issueCount": len(validation_result.issues),
        "issues": [
            {"path": Path(issue.path).name, "message": issue.message, "json_path": issue.json_path}
            for issue in validation_result.issues
        ],
        "aiUsage": "none",
    }
    job = create_completed_job(
        conn,
        user_id=user_id,
        project_id=project_id,
        job_type="motionjson_import",
        payload={"sourceName": source.name, "sourceKind": "directory" if source.is_dir() else "file"},
        result={"validation": validation, "sourceName": source.name, "aiUsage": "none"},
    )
    assets = []
    for file_path, rel_path in zip(files, rel_paths):
        _safe_rel_path(rel_path)
        assets.append(
            register_generated_asset(
                conn,
                storage=storage,
                project_id=project_id,
                source_job_id=job["id"],
                kind=_import_kind_for_rel_path(rel_path),
                path=file_path,
                rel_path=rel_path,
                content_type=mimetypes.guess_type(file_path.name)[0] or "application/octet-stream",
                metadata={"aiUsage": "none", "imported": True, "sourceName": source.name},
            )
        )
    record_job_event(
        conn,
        job_id=job["id"],
        event_type="motionjson_imported",
        message="previous MotionJSON result imported for review",
        metadata={"validation": validation, "assetCount": len(assets), "aiUsage": "none"},
    )
    return {
        "format": "motionjson.local_ui_import.v0.1",
        "job": job,
        "assets": assets,
        "validation": validation,
    }
