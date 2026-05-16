from __future__ import annotations

import copy
import json
import mimetypes
import re
import shutil
import sqlite3
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
from motionjson.backend.rights import record_audit_event
from motionjson.exporters.final_render import build_final_export_manifest, final_export_entry
from motionjson.providers.base import StorageProvider
from motionjson.validation import validate_document, validate_file, validate_output_dir


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
    return STORAGE_KEY_RE.sub("[STORAGE_KEY_REDACTED]", LOCAL_PATH_RE.sub("[LOCAL_PATH_REDACTED]", value))


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
    return bool(re.search(r"deleted|excluded|rejected|failed|fallback_raster|merged", str(value or "")))


def _included_object_ids(scene: dict[str, Any], correction_state: dict[str, Any]) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    track_edits = correction_state.get("trackEdits") if isinstance(correction_state.get("trackEdits"), dict) else {}
    history = correction_state.get("history") if isinstance(correction_state.get("history"), list) else []
    scene_ids = {_object_id(obj) for obj in scene.get("objects", []) if isinstance(obj, dict)}
    included: list[str] = []
    excluded: list[str] = []
    diagnostics: list[dict[str, Any]] = []
    for obj in scene.get("objects", []):
        if not isinstance(obj, dict):
            continue
        object_id = _object_id(obj)
        edit = _edit_for_object(track_edits, object_id)
        include = True
        if edit.get("deleted") or edit.get("mergedInto"):
            include = False
        if edit.get("exportIncluded") is False:
            include = False
        if obj.get("exportIncluded") is False or _status_excludes(obj.get("exportStatus")):
            include = False
        if include:
            included.append(object_id)
        else:
            excluded.append(object_id)
            diagnostics.append(
                {
                    "code": "track_excluded_from_export",
                    "objectId": object_id,
                    "reason": edit.get("exportStatus") or obj.get("exportStatus") or "correction_state",
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


def _sanitized_scene(scene: dict[str, Any], correction_state: dict[str, Any]) -> tuple[dict[str, Any], list[str], list[str], list[dict[str, Any]]]:
    edited = copy.deepcopy(scene)
    track_edits = correction_state.get("trackEdits") if isinstance(correction_state.get("trackEdits"), dict) else {}
    included_ids, excluded_ids, diagnostics = _included_object_ids(edited, correction_state)
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
        objects.append(clean)
    edited["objects"] = objects

    layers: list[dict[str, Any]] = []
    for layer in edited.get("layers", []):
        if not isinstance(layer, dict):
            continue
        object_id = str(layer.get("object_id") or layer.get("objectId") or "")
        if object_id not in included_set:
            continue
        clean = {key: copy.deepcopy(value) for key, value in layer.items() if key not in SCENE_CORRECTION_ONLY_KEYS}
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


def _canvas(scene: dict[str, Any]) -> dict[str, Any]:
    source = scene.get("source", {}) if isinstance(scene.get("source"), dict) else {}
    canvas = scene.get("canvas", {}) if isinstance(scene.get("canvas"), dict) else {}
    return {
        "width": int(source.get("width") or canvas.get("width") or 1),
        "height": int(source.get("height") or canvas.get("height") or 1),
        "fps": float(source.get("sampleFps") or canvas.get("fps") or 12),
        "frameCount": int(source.get("sampledFrameCount") or canvas.get("frame_count") or 0),
    }


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
) -> dict[str, Any]:
    if preset not in EXPORT_PRESETS:
        raise ValueError(f"export preset must be one of: {', '.join(EXPORT_PRESETS)}")
    job = get_job(conn, user_id=user_id, job_id=job_id)
    source_dir = export_dir.parent / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    materialize_job_assets(conn, storage=storage, project_id=job["project_id"], source_job_id=job_id, out_dir=source_dir)
    scene_path = source_dir / "scene_graph.json"
    if not scene_path.exists():
        raise ValueError("selected job has no scene_graph.json artifact to export")
    scene = _load_json(scene_path)
    corrections = list_track_corrections(conn, user_id=user_id, job_id=job_id)
    correction_state = build_track_correction_state(corrections, job_id=job_id)
    exported_scene, included_ids, excluded_ids, diagnostics = _sanitized_scene(scene, correction_state)
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

    payload = json.loads(job.get("payload_json") or "{}")
    export_id = export_dir.name
    provenance = {
        "app": "motionjson",
        "version": __version__,
        "sourceJobId": job_id,
        "sourceAssetId": _source_asset_id(conn, job_id),
        "exportId": export_id,
        "exportPreset": preset,
        "correctionEventCount": len(corrections),
        "includedObjectIds": included_ids,
        "excludedObjectIds": excluded_ids,
        "diagnostics": diagnostics,
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
    validation = _validate_export_documents([("scene_graph.json", exported_scene)])
    manifest = build_final_export_manifest(
        out_dir=export_dir,
        scene=exported_scene,
        exports=exports,
        provenance=provenance,
        config=config,
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
        )
        return {
            "format": "motionjson.local_ui_export_validation.v0.1",
            "exportId": result["exportId"],
            "preset": preset,
            "validation": result["validation"],
            "includedObjectIds": result["includedObjectIds"],
            "excludedObjectIds": result["excludedObjectIds"],
            "diagnostics": result["diagnostics"],
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
        for rel_path, kind, content_type in _export_asset_specs(result["exportDir"]):
            path = result["exportDir"] / rel_path
            asset = register_generated_asset(
                conn,
                storage=storage,
                project_id=job["project_id"],
                source_job_id=job_id,
                kind=kind,
                path=path,
                rel_path=f"exports/{export_id}/{rel_path.as_posix()}",
                content_type=content_type,
                metadata={
                    "aiUsage": "none",
                    "exportId": export_id,
                    "preset": preset,
                    "validation": {key: value for key, value in result["validation"].items() if key != "issues"},
                },
            )
            assets.append(asset)
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
        },
    )
    record_audit_event(
        conn,
        user_id=user_id,
        project_id=job["project_id"],
        job_id=job_id,
        event_type="validated_motionjson_export",
        metadata={"exportId": export_id, "preset": preset, "aiUsage": "none"},
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
        elif name == "preview/overlay_preview.svg":
            kind = "preview_overlay"
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
