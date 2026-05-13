from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _safe_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except FileNotFoundError:
        return 0


def _dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            total += _safe_size(Path(root) / name)
    return total


def _count(path: Path, pattern: str) -> int:
    return len(list(path.glob(pattern))) if path.exists() else 0


def _object(scene: dict[str, Any], object_id: str) -> dict[str, Any]:
    for obj in scene.get("objects", []):
        if obj.get("id") == object_id:
            return obj
    return {}


def build_resource_profile(*, video_path: str | Path, out_dir: str | Path, object_id: str, scene: dict[str, Any]) -> dict[str, Any]:
    """Build an honest profile of package size and preview/edit strategy."""
    video_path = Path(video_path)
    out_dir = Path(out_dir)
    object_dir = out_dir / "objects" / object_id
    cutout_dir = object_dir / "cutouts"
    mask_dir = out_dir / "masks" / object_id
    frames_dir = out_dir / "frames"
    source_bytes = _safe_size(video_path)
    scene_graph_bytes = _safe_size(out_dir / "scene_graph.json")
    web_manifest_bytes = _safe_size(out_dir / "web_asset_manifest.json")
    lottie_bytes = _safe_size(out_dir / "silhouette_lottie.json")
    object_motion_bytes = _safe_size(out_dir / "object_motion.json")
    object_manifest_bytes = _safe_size(object_dir / "object_manifest.json")
    preview_bytes = _dir_size(out_dir / "preview")
    sprite_bytes = _safe_size(object_dir / "spritesheet.webp") or _safe_size(object_dir / "spritesheet.png")
    cutout_bytes = _dir_size(cutout_dir)
    mask_bytes = _dir_size(mask_dir)
    sampled_frame_bytes = _dir_size(frames_dir)
    benchmark_bytes = _safe_size(out_dir / "benchmark_report.json")

    payloads = {
        "scene_graph_json_bytes": scene_graph_bytes,
        "object_motion_json_bytes": object_motion_bytes,
        "object_manifest_json_bytes": object_manifest_bytes,
        "web_asset_manifest_json_bytes": web_manifest_bytes,
        "silhouette_lottie_json_bytes": lottie_bytes,
        "sampled_frame_debug_png_bytes": sampled_frame_bytes,
        "mask_sequence_bytes": mask_bytes,
        "cutout_sequence_png_bytes": cutout_bytes,
        "spritesheet_bytes": sprite_bytes,
        "preview_html_bytes": preview_bytes,
        "benchmark_report_json_bytes": benchmark_bytes,
    }
    extracted_package_bytes = sum(payloads.values())
    website_package_bytes = web_manifest_bytes + sprite_bytes
    authoring_package_bytes = scene_graph_bytes + cutout_bytes + mask_bytes + object_manifest_bytes

    canvas = scene.get("canvas", {})
    frame_count = int(canvas.get("frame_count", 0) or scene.get("source", {}).get("sampledFrameCount", 0) or 0)
    canvas_pixels = int(canvas.get("width", 0) or 0) * int(canvas.get("height", 0) or 0) * frame_count
    layer_pixels = 0
    obj = _object(scene, object_id)
    for entry in obj.get("motion", []):
        if entry.get("visible"):
            layer_pixels += int(entry.get("w") or 0) * int(entry.get("h") or 0)

    pixel_ratio = round(layer_pixels / canvas_pixels, 4) if canvas_pixels else None
    pixel_reduction = round(1 - pixel_ratio, 4) if pixel_ratio is not None else None
    package_ratio = round(extracted_package_bytes / source_bytes, 4) if source_bytes else None
    website_ratio = round(website_package_bytes / source_bytes, 4) if source_bytes else None
    png_warning = bool(source_bytes and cutout_bytes > source_bytes)
    package_warning = bool(source_bytes and extracted_package_bytes > source_bytes)

    example_edit = {
        "objectId": object_id,
        "edit": {"translate": [40, -20], "scale": 1.12, "rotation": 0.08, "opacity": 0.92},
    }
    json_edit_bytes = len(json.dumps(example_edit, separators=(",", ":")).encode("utf-8"))

    warnings: list[str] = []
    if png_warning:
        warnings.append("PNG cutout sequence is larger than the source video. This is normal for a debug/authoring format; use WebP/AVIF sprites, transparent WebM, or a GPU texture atlas for production.")
    if package_warning:
        warnings.append("Full extracted package is larger than source video because it includes debug frames, masks, cutouts, manifests, and previews.")

    return {
        "schema": "motionjson.resource_profile.v0.1",
        "goal": "honest_resource_profile_for_cached_object_layer_workflow",
        "sourceVideo": {
            "path": str(video_path),
            "bytes": source_bytes,
        },
        "counts": {
            "frameCount": frame_count,
            "sampledFramePngCount": _count(frames_dir, "frame_*.png"),
            "maskCount": _count(mask_dir, "mask_*.png"),
            "cutoutCount": _count(cutout_dir, "cutout_*.png"),
        },
        "sizes": {
            "extractedPackageBytes": extracted_package_bytes,
            "extractedPackageToSourceRatio": package_ratio,
            "websitePackageBytes": website_package_bytes,
            "websitePackageToSourceRatio": website_ratio,
            "authoringPackageBytes": authoring_package_bytes,
            "payloads": payloads,
        },
        "previewStrategy": {
            "runtime": "Canvas2D MVP; WebGL/PixiJS texture atlas recommended for production",
            "aiUsage": "Run AI at ingest/correction time, not during normal playback or transform edits.",
            "editRepresentation": "Transform edits are small JSON deltas over cached raster/alpha assets.",
            "partialInvalidation": "Only changed object layers need preview recomposition.",
            "jsonTransformEditBytes": json_edit_bytes,
        },
        "pixelWork": {
            "fullFramePixelsPerSampledClip": canvas_pixels,
            "objectLayerPixelsPerSampledClip": layer_pixels,
            "objectLayerPixelRatio": pixel_ratio,
            "estimatedPixelWorkReduction": pixel_reduction,
        },
        "warnings": warnings,
        "recommendations": [
            "Keep photorealistic objects as raster/alpha assets; do not force them into SVG/Lottie.",
            "Use transparent WebM, WebP sprite atlas, AVIF sequence, or GPU texture atlas for production payloads.",
            "Keep Lottie/SVG for silhouettes, outlines, labels, annotations, and flat vector-like graphics.",
            "Measure browser preview FPS separately before claiming production performance.",
        ],
    }
