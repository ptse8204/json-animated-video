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


def _asset_bytes(asset: dict[str, Any] | None) -> int:
    if not isinstance(asset, dict):
        return 0
    return int(asset.get("bytes") or 0)


ZERO_COST_SEGMENTATION_PROVIDERS = {
    "thresholdmaskprovider",
    "motionmaskprovider",
    "externalmaskprovider",
    "mock",
    "mocksegmentationprovider",
    "sam2-local",
    "maskprovidersegmentationadapter",
}


def _attempts_from_provider_performance(provider_performance: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(provider_performance, dict):
        return []
    attempts: list[dict[str, Any]] = []
    for item in provider_performance.get("objects", []):
        if isinstance(item, dict):
            nested = item.get("providerSummary")
            if isinstance(nested, dict):
                attempts.extend(attempt for attempt in nested.get("attempts", []) if isinstance(attempt, dict))
                nested_nested = nested.get("nested")
                if isinstance(nested_nested, dict):
                    attempts.extend(attempt for attempt in nested_nested.get("attempts", []) if isinstance(attempt, dict))
            else:
                attempts.extend(attempt for attempt in item.get("attempts", []) if isinstance(attempt, dict))
    attempts.extend(attempt for attempt in provider_performance.get("attempts", []) if isinstance(attempt, dict))
    return attempts


def _cache_totals(provider_performance: dict[str, Any] | None) -> dict[str, Any]:
    totals = {"hits": 0, "misses": 0, "readBytes": 0, "writtenBytes": 0, "storedBytes": 0}
    if not isinstance(provider_performance, dict):
        return {**totals, "hitRate": None}
    caches: list[dict[str, Any]] = []
    for item in provider_performance.get("objects", []):
        if not isinstance(item, dict):
            continue
        for candidate in (item.get("cache"), item.get("providerSummary", {}).get("cache") if isinstance(item.get("providerSummary"), dict) else None):
            if isinstance(candidate, dict):
                caches.append(candidate)
    for cache in caches:
        for key in totals:
            totals[key] += int(cache.get(key) or 0)
    requests = totals["hits"] + totals["misses"]
    return {**totals, "hitRate": round(totals["hits"] / requests, 4) if requests else None}


def build_cost_dashboard(
    *,
    provider_performance: dict[str, Any] | None = None,
    latency_metrics: dict[str, Any] | None = None,
    production_assets: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Summarize provider, cache, latency, and compression cost signals without paid calls."""
    attempts = _attempts_from_provider_performance(provider_performance)
    provider_names = sorted({str(attempt.get("provider") or "unknown") for attempt in attempts})
    providers: list[dict[str, Any]] = []
    total_units = 0.0
    unknown_costs = 0
    for name in provider_names:
        name_key = name.lower()
        provider_attempts = [attempt for attempt in attempts if str(attempt.get("provider") or "unknown") == name]
        estimated_units = sum(float(attempt.get("estimated_cost_units") or 0.0) for attempt in provider_attempts)
        total_units += estimated_units
        if name_key in ZERO_COST_SEGMENTATION_PROVIDERS or name_key.startswith("threshold") or name_key.startswith("external"):
            cost_status = "zero_local_provider_cost"
            unit_cost = 0.0
        elif "hosted" in name_key:
            cost_status = "unknown_external_provider_cost"
            unit_cost = None
            unknown_costs += 1
        else:
            cost_status = "unknown_local_or_custom_provider_cost"
            unit_cost = None
            unknown_costs += 1
        providers.append(
            {
                "provider": name,
                "attempts": len(provider_attempts),
                "successes": sum(1 for attempt in provider_attempts if attempt.get("status") == "success"),
                "failures": sum(1 for attempt in provider_attempts if attempt.get("status") == "error"),
                "estimatedCostUnits": round(estimated_units, 4),
                "unitCostUsd": unit_cost,
                "costStatus": cost_status,
            }
        )
    compression = None
    if isinstance(production_assets, dict):
        compression = production_assets.get("compressionOptimizer")
    return {
        "schema": "motionjson.cost_dashboard.v0.1",
        "aiUsage": "none_for_preview_edits",
        "policy": "Segmentation providers are separate from LLM routing; OpenRouter is never used as a pixel segmentation engine.",
        "providers": providers,
        "totals": {
            "providerAttempts": len(attempts),
            "estimatedCostUnits": round(total_units, 4),
            "unknownProviderCostCount": unknown_costs,
        },
        "cache": _cache_totals(provider_performance),
        "latency": latency_metrics or {},
        "compression": compression,
    }


def build_resource_profile(*, video_path: str | Path, out_dir: str | Path, object_id: str, scene: dict[str, Any]) -> dict[str, Any]:
    """Build an honest profile of package size and preview/edit strategy."""
    video_path = Path(video_path)
    out_dir = Path(out_dir)
    object_dir = out_dir / "objects" / object_id
    production_dir = object_dir / "production"
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
    production_webp_bytes = _safe_size(production_dir / "sprite_atlas.webp")
    production_avif_bytes = _safe_size(production_dir / "sprite_atlas.avif")
    production_webm_bytes = _safe_size(production_dir / "transparent_layer.webm")
    production_asset_bytes = _dir_size(production_dir)
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
        "production_webp_sprite_atlas_bytes": production_webp_bytes,
        "production_avif_sprite_atlas_bytes": production_avif_bytes,
        "production_transparent_webm_bytes": production_webm_bytes,
        "production_asset_bytes": production_asset_bytes,
        "preview_html_bytes": preview_bytes,
        "benchmark_report_json_bytes": benchmark_bytes,
    }
    extracted_package_bytes = (
        scene_graph_bytes
        + object_motion_bytes
        + object_manifest_bytes
        + web_manifest_bytes
        + lottie_bytes
        + sampled_frame_bytes
        + mask_bytes
        + cutout_bytes
        + sprite_bytes
        + production_asset_bytes
        + preview_bytes
        + benchmark_bytes
    )
    website_package_bytes = web_manifest_bytes + sprite_bytes
    authoring_package_bytes = scene_graph_bytes + cutout_bytes + mask_bytes + object_manifest_bytes
    production_package_bytes = web_manifest_bytes + production_asset_bytes

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
    production_ratio = round(production_package_bytes / source_bytes, 4) if source_bytes and production_asset_bytes else None
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

    production_assets = obj.get("assets", {}).get("production", {})
    provider_performance = scene.get("providerPerformance") if isinstance(scene.get("providerPerformance"), dict) else {}
    latency_metrics = scene.get("latencyMetrics") if isinstance(scene.get("latencyMetrics"), dict) else {}
    cost_dashboard = scene.get("costDashboard")
    if not isinstance(cost_dashboard, dict):
        cost_dashboard = build_cost_dashboard(
            provider_performance=provider_performance,
            latency_metrics=latency_metrics,
            production_assets=production_assets if isinstance(production_assets, dict) else None,
        )
    production_asset_status = production_assets.get("assets", {}) if isinstance(production_assets, dict) else {}
    webp_asset = production_asset_status.get("webpSpriteAtlas")
    avif_asset = production_asset_status.get("avifSpriteAtlas")
    webm_asset = production_asset_status.get("transparentWebm")
    resource_comparison = {
        "sourceVideoBytes": source_bytes,
        "authoringPackageBytes": authoring_package_bytes,
        "productionPackageBytes": production_package_bytes,
        "productionPackageToSourceRatio": production_ratio,
        "cutoutSequencePngBytes": cutout_bytes,
        "webpSpriteAtlasBytes": _asset_bytes(webp_asset),
        "transparentWebmBytes": _asset_bytes(webm_asset),
        "avifSpriteAtlasBytes": _asset_bytes(avif_asset),
        "webpSpriteAtlasToCutoutRatio": round(_asset_bytes(webp_asset) / cutout_bytes, 4) if cutout_bytes and _asset_bytes(webp_asset) else None,
        "transparentWebmToCutoutRatio": round(_asset_bytes(webm_asset) / cutout_bytes, 4) if cutout_bytes and _asset_bytes(webm_asset) else None,
        "avifSpriteAtlasToCutoutRatio": round(_asset_bytes(avif_asset) / cutout_bytes, 4) if cutout_bytes and _asset_bytes(avif_asset) else None,
    }

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
            "productionPackageBytes": production_package_bytes,
            "productionPackageToSourceRatio": production_ratio,
            "payloads": payloads,
        },
        "productionAssets": production_assets or None,
        "compressionOptimizer": production_assets.get("compressionOptimizer") if isinstance(production_assets, dict) else None,
        "resourceComparison": resource_comparison,
        "providerPerformance": provider_performance,
        "latencyMetrics": latency_metrics,
        "costDashboard": cost_dashboard,
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
