from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from motionjson.exporters.scene_graph import write_json
from motionjson.exporters.web_manifest import write_web_asset_manifest
from motionjson.pipeline import _preview_copy
from motionjson.rights import build_rights_manifest


PARTIAL_REVIEW_FORMAT = "motionjson.partial_review_payload.v0.1"


def synthesize_partial_review_payload(
    out_dir: str | Path,
    *,
    video_path: str | Path | None = None,
    job_id: str | None = None,
    diagnostic: Mapping[str, Any] | None = None,
    runtime_proof: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build root review artifacts from completed per-object manifests.

    Multi-object extraction checkpoints object manifests before global export.
    If a later object fails, these completed objects should remain reviewable.
    This helper writes the minimal global artifacts the existing review tools
    need: scene graph, root/object web manifests, tracks, rights, preview tools,
    and a partial diagnostic.
    """

    root = Path(out_dir)
    diagnostic_payload = dict(diagnostic or {})
    if _root_review_payload_exists(root):
        return {
            "format": PARTIAL_REVIEW_FORMAT,
            "status": "skipped",
            "reasonCode": "root_review_payload_exists",
            "reviewableObjectCount": 0,
            "reviewableObjectIds": [],
            "writtenRelPaths": [],
        }
    failed_object_id = str(diagnostic_payload.get("objectId") or "").strip()
    manifests = _completed_object_manifests(root, failed_object_id=failed_object_id)
    if not manifests:
        return {
            "format": PARTIAL_REVIEW_FORMAT,
            "status": "skipped",
            "reasonCode": "no_completed_object_manifests",
            "reviewableObjectCount": 0,
            "reviewableObjectIds": [],
            "writtenRelPaths": [],
        }

    scene = _partial_scene(
        manifests,
        video_path=video_path,
        job_id=job_id,
        diagnostic=diagnostic_payload,
        runtime_proof=dict(runtime_proof or {}),
    )
    first_object_id = str(scene["objects"][0]["id"])
    rights_manifest = build_rights_manifest(source=scene["source"], objects=scene["objects"])
    tracks = _partial_tracks(manifests, diagnostic_payload)
    fallback = _partial_fallback_diagnostics(diagnostic_payload)

    write_json(root / "scene_graph.json", scene)
    write_json(root / "tracks.json", tracks)
    write_json(root / "fallback_diagnostics.json", fallback)
    write_json(root / "rights_manifest.json", rights_manifest)
    for obj in scene["objects"]:
        object_id = str(obj["id"])
        write_web_asset_manifest(
            root / "objects" / object_id / "web_asset_manifest.json",
            scene,
            object_id=object_id,
            path_prefix="../../",
            source_scene_graph="../../scene_graph.json",
        )
    write_web_asset_manifest(root / "web_asset_manifest.json", scene, object_id=first_object_id)
    _preview_copy(root)

    written_rel_paths = [
        "scene_graph.json",
        "tracks.json",
        "fallback_diagnostics.json",
        "rights_manifest.json",
        "web_asset_manifest.json",
        *[f"objects/{obj['id']}/web_asset_manifest.json" for obj in scene["objects"]],
        "preview/canvas_player.html",
        "preview/object_selection_workflow.html",
        "preview/object_selection_workflow.js",
        "preview/timeline_editor.html",
        "preview/timeline_editor.js",
    ]
    result = {
        "format": PARTIAL_REVIEW_FORMAT,
        "status": "ready",
        "partialSuccess": True,
        "jobId": job_id or "",
        "reviewableObjectCount": len(scene["objects"]),
        "reviewableObjectIds": [str(obj["id"]) for obj in scene["objects"]],
        "failedObjectId": failed_object_id or None,
        "diagnostic": diagnostic_payload,
        "runtimeProof": dict(runtime_proof or {}),
        "writtenRelPaths": written_rel_paths,
    }
    write_json(root / "partial_review.json", result)
    return result


def _root_review_payload_exists(root: Path) -> bool:
    required = ("scene_graph.json", "web_asset_manifest.json", "tracks.json")
    return all((root / rel_path).is_file() for rel_path in required)


def _completed_object_manifests(root: Path, *, failed_object_id: str = "") -> list[dict[str, Any]]:
    manifests: list[dict[str, Any]] = []
    for path in sorted((root / "objects").glob("*/object_manifest.json")):
        object_id = path.parent.name
        if failed_object_id and object_id == failed_object_id:
            continue
        if (path.parent / "failure.json").exists():
            continue
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(document, dict):
            continue
        document.setdefault("objectId", object_id)
        motion = document.get("motion")
        frames = document.get("frames")
        if not isinstance(motion, list) and not isinstance(frames, list):
            continue
        manifests.append(document)
    return manifests


def _partial_scene(
    manifests: Sequence[Mapping[str, Any]],
    *,
    video_path: str | Path | None,
    job_id: str | None,
    diagnostic: Mapping[str, Any],
    runtime_proof: Mapping[str, Any],
) -> dict[str, Any]:
    objects = [_scene_object_from_manifest(manifest, index=index) for index, manifest in enumerate(manifests)]
    source = _source_from_manifests(manifests, video_path=video_path)
    return {
        "schema": "motionjson.scene_graph.v0.1",
        "format": "motionjson.scene_graph.v0.1",
        "version": "0.1.0",
        "partialSuccess": True,
        "jobId": job_id or "",
        "partialReview": {
            "format": PARTIAL_REVIEW_FORMAT,
            "status": "ready",
            "reasonCode": diagnostic.get("reasonCode") or diagnostic.get("compatibilityReasonCode") or "partial_object_recovery",
            "message": diagnostic.get("message") or "Partial review artifacts were synthesized from completed object checkpoints.",
            "failedObjectId": diagnostic.get("objectId"),
            "frame": diagnostic.get("frame"),
            "position": diagnostic.get("position"),
            "totalFrames": diagnostic.get("totalFrames"),
            "runtimeProof": dict(runtime_proof or {}),
        },
        "source": source,
        "canvas": {
            "width": source["width"],
            "height": source["height"],
            "fps": source["sampleFps"],
            "frame_count": source["sampledFrameCount"],
        },
        "objects": objects,
        "layers": [_layer_from_object(obj) for obj in objects],
        "rendering": {
            "recommendedRuntime": "Canvas/WebGL/PixiJS",
            "defaultRenderMode": "raster_alpha_sequence",
            "outputMode": "authoring",
            "vectorPolicy": "Partial review preserves completed raster/mask tracks; rerun failed objects before production export if needed.",
        },
        "providerPerformance": [],
        "latencyMetrics": {},
        "rightsManifest": "rights_manifest.json",
        "costDashboard": {
            "schema": "motionjson.cost_dashboard.v0.1",
            "aiUsage": "none_for_preview_edits",
            "policy": "Partial review synthesis uses completed artifacts only and makes no hosted calls.",
            "providers": [],
            "totals": {"providerAttempts": 0, "estimatedCostUnits": 0.0, "unknownProviderCostCount": 0},
            "cache": {},
            "latency": {},
        },
    }


def _scene_object_from_manifest(manifest: Mapping[str, Any], *, index: int) -> dict[str, Any]:
    object_id = str(manifest.get("objectId") or manifest.get("id") or f"partial_object_{index + 1:03d}")
    motion = [dict(frame) for frame in manifest.get("motion", []) if isinstance(frame, Mapping)]
    frames = [dict(frame) for frame in manifest.get("frames", []) if isinstance(frame, Mapping)]
    discovery = dict(manifest.get("discovery") or {}) if isinstance(manifest.get("discovery"), Mapping) else {}
    export_status = str(discovery.get("exportStatus") or manifest.get("exportStatus") or "review_pending")
    discovery = {
        **discovery,
        "partialReview": True,
        "reviewRequired": True,
        "exportStatus": export_status,
    }
    return {
        "id": object_id,
        "label": manifest.get("label") or object_id,
        "renderMode": manifest.get("renderMode") or "raster_alpha_sequence",
        "asset": f"objects/{object_id}/cutouts/cutout_%06d.png",
        "mask": f"masks/{object_id}/mask_%06d.png",
        "assets": {
            "cutoutPattern": f"objects/{object_id}/cutouts/cutout_%06d.png",
            "spritesheet": manifest.get("spritesheet"),
        },
        "zIndex": int(manifest.get("zIndex") or 10 + index),
        "motion": motion,
        "frames": frames,
        "frameMap": manifest.get("frameMap") if isinstance(manifest.get("frameMap"), list) else _frame_map_from_motion(motion),
        "quality": manifest.get("quality") if isinstance(manifest.get("quality"), Mapping) else {},
        "recommendedOutput": manifest.get("recommendedOutput"),
        "rights": manifest.get("rights") if isinstance(manifest.get("rights"), Mapping) else {},
        "discovery": discovery,
        "exportStatus": export_status,
        "exportIncluded": False,
    }


def _layer_from_object(obj: Mapping[str, Any]) -> dict[str, Any]:
    object_id = str(obj.get("id") or obj.get("objectId") or "")
    motion = [frame for frame in obj.get("motion", []) if isinstance(frame, Mapping)]
    fps = _sample_fps_from_frames(motion)
    return {
        "id": f"{object_id}_raster_layer",
        "object_id": object_id,
        "type": "raster_alpha_sequence",
        "asset_type": "cropped_rgba_png_sequence",
        "fps": fps,
        "z_index": obj.get("zIndex", 10),
        "blend_mode": "source-over",
        "frames": [_layer_frame(frame) for frame in motion],
        "discovery": obj.get("discovery") if isinstance(obj.get("discovery"), Mapping) else {},
        "controls": {
            "editable": ["x", "y", "scale", "rotation", "opacity", "visible", "z_index"],
            "exportStatus": obj.get("exportStatus") or "review_pending",
            "exportIncluded": False,
            "partialReview": True,
        },
    }


def _layer_frame(frame: Mapping[str, Any]) -> dict[str, Any]:
    bbox = frame.get("bbox") if isinstance(frame.get("bbox"), list) else None
    return {
        "frame": frame.get("frame"),
        "t": frame.get("t"),
        "visible": bool(frame.get("visible")),
        "asset": frame.get("asset"),
        "mask": frame.get("mask"),
        "x": frame.get("x", bbox[0] if bbox and len(bbox) > 0 else 0),
        "y": frame.get("y", bbox[1] if bbox and len(bbox) > 1 else 0),
        "width": frame.get("w", bbox[2] if bbox and len(bbox) > 2 else 0),
        "height": frame.get("h", bbox[3] if bbox and len(bbox) > 3 else 0),
        "anchor": frame.get("anchor") or [0.0, 0.0],
        "opacity": frame.get("opacity", 1.0 if frame.get("visible") else 0.0),
        "scale": frame.get("scale", 1.0),
        "rotation": frame.get("rotation", 0.0),
    }


def _partial_tracks(manifests: Sequence[Mapping[str, Any]], diagnostic: Mapping[str, Any]) -> dict[str, Any]:
    tracks = []
    for index, manifest in enumerate(manifests):
        object_id = str(manifest.get("objectId") or f"partial_object_{index + 1:03d}")
        motion = manifest.get("frames") if isinstance(manifest.get("frames"), list) else manifest.get("motion", [])
        visible = [frame for frame in motion if isinstance(frame, Mapping) and frame.get("visible")]
        discovery = dict(manifest.get("discovery") or {}) if isinstance(manifest.get("discovery"), Mapping) else {}
        export_status = str(discovery.get("exportStatus") or manifest.get("exportStatus") or "review_pending")
        tracks.append(
            {
                "objectId": object_id,
                "label": manifest.get("label") or object_id,
                "source": "partial_object_manifest",
                "providerName": discovery.get("trackingProvider") or discovery.get("candidateProvider") or "partial_review_synthesis",
                "frameCount": len(motion) if isinstance(motion, list) else 0,
                "visibleFrameCount": len(visible),
                "exportStatus": export_status,
                "exportIncluded": False,
                "metadata": {
                    "partialObjectManifest": True,
                    "partialReview": True,
                    "frameMap": manifest.get("frameMap") if isinstance(manifest.get("frameMap"), list) else [],
                    "discovery": discovery,
                },
                "frames": [dict(frame) for frame in motion if isinstance(frame, Mapping)],
                "discovery": {**discovery, "partialReview": True, "reviewRequired": True, "exportStatus": export_status},
            }
        )
    return {
        "schema": "motionjson.track_summary.v0.1",
        "partialSuccess": True,
        "tracks": tracks,
        "filterReport": {
            "summary": {
                "trackCount": len(tracks),
                "acceptedCount": 0,
                "reviewPendingCount": len(tracks),
                "rejectedCount": 0,
                "partialReview": True,
            },
            "decisions": [
                {
                    "objectId": track["objectId"],
                    "status": "needs_review",
                    "reasonCodes": ["partial_review_requires_confirmation"],
                }
                for track in tracks
            ],
        },
        "fallbackDiagnostics": _partial_fallback_diagnostics(diagnostic)["diagnostics"],
    }


def _partial_fallback_diagnostics(diagnostic: Mapping[str, Any]) -> dict[str, Any]:
    if not diagnostic:
        diagnostics: list[dict[str, Any]] = []
    else:
        diagnostics = [
            {
                "reasonCode": diagnostic.get("reasonCode") or diagnostic.get("compatibilityReasonCode") or "partial_object_recovery",
                "compatibilityReasonCode": diagnostic.get("compatibilityReasonCode"),
                "objectId": diagnostic.get("objectId"),
                "frame": diagnostic.get("frame"),
                "position": diagnostic.get("position"),
                "totalFrames": diagnostic.get("totalFrames"),
                "message": diagnostic.get("message") or "A later object failed after completed object artifacts were checkpointed.",
                "reviewRequired": True,
                "partialSuccess": True,
            }
        ]
    return {
        "schema": "motionjson.fallback_diagnostics.v0.1",
        "summary": {"partialSuccess": True, "diagnosticCount": len(diagnostics)},
        "diagnostics": diagnostics,
    }


def _source_from_manifests(manifests: Sequence[Mapping[str, Any]], *, video_path: str | Path | None) -> dict[str, Any]:
    frames = [
        frame
        for manifest in manifests
        for frame in (manifest.get("frames") if isinstance(manifest.get("frames"), list) else manifest.get("motion", []))
        if isinstance(frame, Mapping)
    ]
    width, height = _source_dimensions(frames)
    sample_fps = _sample_fps_from_frames(frames)
    sampled_count = _sampled_frame_count(frames)
    return {
        "video": str(video_path or ""),
        "width": width,
        "height": height,
        "fps": sample_fps,
        "sampleFps": sample_fps,
        "sampledFrameCount": sampled_count,
        "frameMap": _frame_map_from_motion(frames),
        "partialReview": True,
    }


def _source_dimensions(frames: Sequence[Mapping[str, Any]]) -> tuple[int, int]:
    for frame in frames:
        shape = frame.get("maskShape")
        if isinstance(shape, list) and len(shape) >= 2:
            return int(shape[1] or 0), int(shape[0] or 0)
    max_x = max_y = 0
    for frame in frames:
        bbox = frame.get("sourceBbox") or frame.get("bbox")
        if isinstance(bbox, list) and len(bbox) >= 4:
            max_x = max(max_x, int((bbox[0] or 0) + (bbox[2] or 0)))
            max_y = max(max_y, int((bbox[1] or 0) + (bbox[3] or 0)))
    return max(max_x, 1), max(max_y, 1)


def _sample_fps_from_frames(frames: Sequence[Mapping[str, Any]]) -> float:
    for frame in frames:
        value = frame.get("sampleFps")
        if isinstance(value, (int, float)) and value > 0:
            return float(value)
    return 12.0


def _sampled_frame_count(frames: Sequence[Mapping[str, Any]]) -> int:
    indices = []
    for frame in frames:
        value = frame.get("outIndex", frame.get("sampleIndex", frame.get("frame")))
        if isinstance(value, (int, float)):
            indices.append(int(value))
    return max(indices) + 1 if indices else len(frames)


def _frame_map_from_motion(frames: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[int, int]] = set()
    frame_map: list[dict[str, Any]] = []
    for index, frame in enumerate(frames):
        sample_index = _int_value(frame.get("sampleIndex", frame.get("outIndex")), index)
        source_frame_index = _int_value(frame.get("sourceFrameIndex"), _int_value(frame.get("frame"), sample_index))
        key = (sample_index, source_frame_index)
        if key in seen:
            continue
        seen.add(key)
        frame_map.append(
            {
                "sampleIndex": sample_index,
                "sourceFrameIndex": source_frame_index,
                "t": frame.get("t", 0),
                "frame": frame.get("frame", source_frame_index),
                "outIndex": _int_value(frame.get("outIndex"), sample_index),
                "sampleFps": frame.get("sampleFps") or _sample_fps_from_frames([frame]),
            }
        )
    return sorted(frame_map, key=lambda item: (item["sampleIndex"], item["sourceFrameIndex"]))


def _int_value(value: Any, default: int) -> int:
    if isinstance(value, bool):
        return int(default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)
