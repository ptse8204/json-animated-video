from __future__ import annotations

from pathlib import Path
from typing import Any

from .scene_graph import write_json


def _prefix_rel(path: str | None, path_prefix: str) -> str | None:
    if not path:
        return path
    value = str(path).replace("\\", "/")
    if "://" in value or value.startswith(("/", "data:", "blob:")):
        return value
    return f"{path_prefix}{value}"


def _prefix_sprite(sprite: dict[str, Any] | None, path_prefix: str) -> dict[str, Any] | None:
    if not isinstance(sprite, dict):
        return sprite
    prefixed = dict(sprite)
    prefixed["path"] = _prefix_rel(prefixed.get("path"), path_prefix)
    return prefixed


def _prefix_production(production: dict[str, Any] | None, path_prefix: str) -> dict[str, Any] | None:
    if not isinstance(production, dict):
        return production
    prefixed = dict(production)
    assets: dict[str, Any] = {}
    for key, asset in (production.get("assets") or {}).items():
        if isinstance(asset, dict):
            asset_copy = dict(asset)
            asset_copy["path"] = _prefix_rel(asset_copy.get("path"), path_prefix)
            assets[key] = asset_copy
        else:
            assets[key] = asset
    if assets:
        prefixed["assets"] = assets
    return prefixed


def _first_object(scene: dict[str, Any], object_id: str) -> dict[str, Any]:
    for obj in scene.get("objects", []):
        if obj.get("id") == object_id:
            return obj
    raise ValueError(f"Object {object_id!r} not found in scene")


def build_web_asset_manifest(
    scene: dict[str, Any],
    *,
    object_id: str,
    path_prefix: str = "",
    source_scene_graph: str = "scene_graph.json",
) -> dict[str, Any]:
    """Build a website-optimized manifest from the authoring scene graph."""
    obj = _first_object(scene, object_id)
    profile = scene.get("resource_profile", {})
    sizes = profile.get("sizes", {})
    pixel_work = profile.get("pixelWork", {})
    source = scene.get("source", {})
    sprite = _prefix_sprite(obj.get("assets", {}).get("spritesheet"), path_prefix)
    raw_production = obj.get("assets", {}).get("production")
    production = _prefix_production(raw_production, path_prefix)
    transparent_webm = (
        raw_production.get("assets", {}).get("transparentWebm", {})
        if isinstance(raw_production, dict)
        else {}
    )
    fallback_video = transparent_webm.get("path") if transparent_webm.get("status") == "ready" else None
    motion = obj.get("motion", [])
    first_asset = next((entry.get("asset") for entry in motion if entry.get("asset")), None)

    frames: list[dict[str, Any]] = []
    for entry in motion:
        if not entry.get("visible"):
            continue
        frame = {
            "frame": entry.get("frame"),
            "t": entry.get("t"),
            "asset": _prefix_rel(entry.get("asset"), path_prefix),
            "x": entry.get("x"),
            "y": entry.get("y"),
            "width": entry.get("w"),
            "height": entry.get("h"),
            "anchor": entry.get("anchor"),
            "opacity": entry.get("opacity", 1),
            "scale": entry.get("scale", 1),
            "rotation": entry.get("rotation", 0),
            "visible": entry.get("visible", True),
        }
        if entry.get("sprite"):
            frame["sprite"] = entry["sprite"]
        frames.append(frame)

    assets = {
        "poster": _prefix_rel(first_asset, path_prefix),
        "spritesheet": sprite,
        "sequence": frames,
        "fallbackStaticPoster": _prefix_rel(first_asset, path_prefix),
        "fallbackVideo": _prefix_rel(fallback_video, path_prefix),
        "fallbackVideoPlaceholder": "Add an exported MP4/WebM loop here for browsers that should not run canvas animation.",
    }
    if production:
        assets["production"] = production

    return {
        "schema": "motionjson.web_asset_manifest.v0.1",
        "type": "web_motion_asset",
        "assetId": object_id,
        "label": obj.get("label", "selected_object"),
        "sourceSceneGraph": source_scene_graph,
        "renderMode": obj.get("renderMode", "raster_alpha_sequence"),
        "recommendedEmbedMode": "canvas_sprite_layer",
        "canvas": {
            "width": source.get("width") or scene.get("canvas", {}).get("width"),
            "height": source.get("height") or scene.get("canvas", {}).get("height"),
            "fps": source.get("sampleFps") or scene.get("canvas", {}).get("fps"),
            "frameCount": source.get("sampledFrameCount") or len(frames),
        },
        "assets": assets,
        "responsive": {
            "mobile": {"maxWidth": 240, "fit": "contain"},
            "tablet": {"maxWidth": 380, "fit": "contain"},
            "desktop": {"maxWidth": 560, "fit": "contain"},
        },
        "loading": {
            "lazy": True,
            "preload": "metadata",
            "decode": "async",
            "pauseWhenOffscreen": True,
        },
        "states": {
            "idle": obj.get("interactions", {}).get("idle", {"loop": True, "scale": 1.0, "opacity": 1.0}),
            "hover": obj.get("interactions", {}).get("hover", {"scale": 1.06, "outline": True}),
            "click": obj.get("interactions", {}).get("click", {"action": "reuse_or_open_detail"}),
            "scroll": {"translate": [40, -24], "rotation": 0.35},
        },
        "quality": obj.get("quality", {}),
        "discovery": obj.get("discovery", {}),
        "estimatedPackageSizes": {
            "websitePackageBytes": sizes.get("websitePackageBytes"),
            "websitePackageToSourceRatio": sizes.get("websitePackageToSourceRatio"),
            "productionPackageBytes": sizes.get("productionPackageBytes"),
            "productionPackageToSourceRatio": sizes.get("productionPackageToSourceRatio"),
            "spriteBytes": sizes.get("payloads", {}).get("spritesheet_bytes"),
            "productionSpriteBytes": sizes.get("payloads", {}).get("production_webp_sprite_atlas_bytes"),
            "transparentWebmBytes": sizes.get("payloads", {}).get("production_transparent_webm_bytes"),
            "manifestBytes": sizes.get("payloads", {}).get("web_asset_manifest_json_bytes"),
        },
        "estimatedPixelWork": {
            "objectLayerPixelRatio": pixel_work.get("objectLayerPixelRatio"),
            "estimatedPixelWorkReduction": pixel_work.get("estimatedPixelWorkReduction"),
        },
        "rights": obj.get("rights", {}),
        "rightsManifest": _prefix_rel(scene.get("rightsManifest", "rights_manifest.json"), path_prefix),
        "notes": [
            "This manifest is the website/runtime package. scene_graph.json remains the richer authoring format.",
            "Use sprite or GPU texture atlas rendering for production; sequence paths are kept for simple MVP fallback.",
        ],
    }


def write_web_asset_manifest(
    path: str | Path,
    scene: dict[str, Any],
    *,
    object_id: str,
    path_prefix: str = "",
    source_scene_graph: str = "scene_graph.json",
) -> None:
    write_json(
        path,
        build_web_asset_manifest(
            scene,
            object_id=object_id,
            path_prefix=path_prefix,
            source_scene_graph=source_scene_graph,
        ),
    )
