from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
from PIL import Image
from tqdm import tqdm

from .exporters.lottie import write_silhouette_lottie
from .exporters.production_assets import export_production_assets
from .exporters.scene_graph import write_json
from .exporters.web_manifest import write_web_asset_manifest
from .layers import crop_rgba_layer, write_spritesheet
from .masks import MaskProvider
from .metrics import build_resource_profile
from .rights import build_object_rights, build_rights_manifest, normalize_rights_context, write_rights_manifest
from .vectorize import build_quality_scores, mask_to_largest_polygon, recommended_output
from .video import iter_sampled_frames


SAFE_OBJECT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


@dataclass(frozen=True)
class ObjectExtractionSpec:
    object_id: str
    label: str
    mask_provider: MaskProvider
    z_index: int = 10


def _validate_object_id(object_id: str) -> None:
    if not SAFE_OBJECT_ID_PATTERN.match(object_id):
        raise ValueError("Object IDs must be safe path segments using letters, numbers, underscores, or hyphens")


def _clear_generated_frames(*directories: Path) -> None:
    for directory in directories:
        if not directory.exists():
            continue
        for pattern in ("frame_*.png", "mask_*.png", "cutout_*.png", "layer_*.webp", "layer_*.png"):
            for file in directory.glob(pattern):
                file.unlink()


def _preview_copy(out_dir: Path) -> None:
    preview_dir = out_dir / "preview"
    preview_dir.mkdir(parents=True, exist_ok=True)
    repo_root = Path(__file__).resolve().parents[2]
    for name in (
        "canvas_player.html",
        "pixi_player.html",
        "plain_js_embed.html",
        "website_graphics_hero.html",
        "object_selection_workflow.html",
        "object_selection_workflow.js",
        "timeline_editor.html",
        "timeline_editor.js",
    ):
        src = repo_root / "examples" / name
        if src.exists():
            shutil.copyfile(src, preview_dir / name)
    for directory_name in ("website_templates", "website_snippets"):
        src_dir = repo_root / "examples" / directory_name
        dest_dir = preview_dir / directory_name
        if src_dir.exists():
            if dest_dir.exists():
                shutil.rmtree(dest_dir)
            shutil.copytree(src_dir, dest_dir)
    runtime_src = repo_root / "packages" / "motionjson-runtime" / "src"
    runtime_dest = preview_dir / "runtime"
    if runtime_src.exists():
        if runtime_dest.exists():
            shutil.rmtree(runtime_dest)
        shutil.copytree(runtime_src, runtime_dest)


def _rel(path: Path, root: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def _object_dir(out_dir: Path, object_id: str) -> Path:
    return out_dir / "objects" / object_id


def _write_object_motion(out_dir: Path, object_id: str, object_motion: dict[str, Any], *, legacy: bool = False) -> None:
    write_json(_object_dir(out_dir, object_id) / "object_motion.json", object_motion)
    if legacy:
        write_json(out_dir / "object_motion.json", object_motion)


def _write_object_web_manifest(out_dir: Path, scene: dict[str, Any], object_id: str, *, legacy: bool = False) -> None:
    write_web_asset_manifest(
        _object_dir(out_dir, object_id) / "web_asset_manifest.json",
        scene,
        object_id=object_id,
        path_prefix="../../",
        source_scene_graph="../../scene_graph.json",
    )
    if legacy:
        write_web_asset_manifest(out_dir / "web_asset_manifest.json", scene, object_id=object_id)


def write_profiled_outputs(
    *,
    out_dir: Path,
    video_path: Path,
    object_id: str,
    scene: dict[str, Any],
    profile_updates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write profile-dependent outputs until self-reported JSON sizes stabilize."""
    profile: dict[str, Any] = {}
    seen_payloads: set[tuple[tuple[str, Any], ...]] = set()
    for _ in range(20):
        profile = build_resource_profile(video_path=video_path, out_dir=out_dir, object_id=object_id, scene=scene)
        if profile_updates:
            profile.update(profile_updates)
        scene["resource_profile"] = profile
        write_json(out_dir / "resource_profile.json", profile)
        write_json(out_dir / "scene_graph.json", scene)
        for index, obj in enumerate(scene.get("objects", [])):
            current_id = obj.get("id")
            if current_id:
                _write_object_web_manifest(out_dir, scene, current_id, legacy=index == 0 and current_id == object_id)
        payloads = profile.get("sizes", {}).get("payloads", {})
        actual_profile = build_resource_profile(video_path=video_path, out_dir=out_dir, object_id=object_id, scene=scene)
        if profile_updates:
            actual_profile.update(profile_updates)
        actual_payloads = actual_profile.get("sizes", {}).get("payloads", {})
        if actual_payloads == payloads:
            break
        payload_key = tuple(sorted(payloads.items()))
        if payload_key in seen_payloads:
            break
        seen_payloads.add(payload_key)
    return profile


def _build_layer_frames(object_id: str, fps: float, motion: list[dict[str, Any]], *, z_index: int = 10) -> dict[str, Any]:
    return {
        "id": f"{object_id}_raster_layer",
        "object_id": object_id,
        "type": "raster_alpha_sequence",
        "asset_type": "cropped_rgba_png_sequence",
        "fps": fps,
        "z_index": z_index,
        "blend_mode": "source-over",
        "frames": [
            {
                "frame": entry["frame"],
                "t": entry["t"],
                "visible": entry["visible"],
                "asset": entry["asset"],
                "mask": entry["mask"],
                "x": entry["x"],
                "y": entry["y"],
                "width": entry["w"],
                "height": entry["h"],
                "anchor": entry["anchor"],
                "opacity": entry["opacity"],
                "scale": entry["scale"],
                "rotation": entry["rotation"],
            }
            for entry in motion
        ],
        "controls": {
            "editable": ["x", "y", "scale", "rotation", "opacity", "visible", "z_index"],
            "json_edit_example": {
                "translate": [40, -20],
                "scale": 1.12,
                "rotation": 0.08,
                "opacity": 0.92,
            },
        },
    }


def _extract_object(
    *,
    out_dir: Path,
    frames_dir: Path,
    info: Any,
    frames: list[Any],
    spec: ObjectExtractionSpec,
    min_area: float,
    simplify_ratio: float,
    feather: int,
    layer_padding: int,
    sprite_format: str,
    output_mode: str,
    production_avif: bool,
    rights_context: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    object_id = spec.object_id
    mask_dir = out_dir / "masks" / object_id
    object_dir = _object_dir(out_dir, object_id)
    cutout_dir = object_dir / "cutouts"
    for directory in (mask_dir, cutout_dir, object_dir):
        directory.mkdir(parents=True, exist_ok=True)
    _clear_generated_frames(mask_dir, cutout_dir)
    for stale_dir in (object_dir / "masks", object_dir / "layers", object_dir / "production"):
        if stale_dir.exists():
            shutil.rmtree(stale_dir)
    for stale in (object_dir / "spritesheet.webp", object_dir / "spritesheet.png"):
        if stale.exists():
            stale.unlink()

    spec.mask_provider.prepare(info)
    detailed_frames: list[dict[str, Any]] = []
    motion: list[dict[str, Any]] = []
    cutout_paths: list[Path] = []

    try:
        for frame in tqdm(frames, desc=f"processing {object_id}"):
            frame_number = frame.out_index + 1
            frame_name = f"frame_{frame_number:06d}.png"
            mask_name = f"mask_{frame_number:06d}.png"
            cutout_name = f"cutout_{frame_number:06d}.png"

            frame_path = frames_dir / frame_name
            mask_path = mask_dir / mask_name
            cutout_path = cutout_dir / cutout_name

            if not frame_path.exists():
                Image.fromarray(frame.rgb).save(frame_path)
            frame_bgr = cv2.cvtColor(frame.rgb, cv2.COLOR_RGB2BGR)
            mask = spec.mask_provider.get_mask(frame.index, frame_bgr)
            contour = mask_to_largest_polygon(mask, min_area=min_area, simplify_ratio=simplify_ratio)
            Image.fromarray(mask).save(mask_path)

            visible = bool(contour.visible and contour.bbox)
            x = y = w = h = 0
            anchor = [0.0, 0.0]
            cutout_rel: str | None = None
            if visible:
                layer_crop = crop_rgba_layer(
                    frame.rgb,
                    mask,
                    contour.bbox or [0, 0, 1, 1],
                    centroid=contour.centroid,
                    feather=feather,
                    padding=layer_padding,
                )
                Image.fromarray(layer_crop.rgba, mode="RGBA").save(cutout_path)
                cutout_paths.append(cutout_path)
                x, y, w, h = layer_crop.bbox
                anchor = layer_crop.anchor
                cutout_rel = _rel(cutout_path, out_dir)

            frame_record = {
                "source_frame_index": frame.index,
                "frame": frame_number,
                "out_index": frame.out_index,
                "t": round(frame.time_sec, 6),
                "visible": visible,
                "area": contour.area,
                "bbox": [x, y, w, h] if visible else None,
                "centroid": contour.centroid,
                "polygon": contour.polygon,
                "contour_points": contour.contour_points,
                "framePath": _rel(frame_path, out_dir),
                "mask": _rel(mask_path, out_dir),
                "asset": cutout_rel,
                "anchor": anchor,
            }
            detailed_frames.append(frame_record)
            motion.append(
                {
                    "frame": frame_number,
                    "sourceFrameIndex": frame.index,
                    "t": round(frame.time_sec, 6),
                    "visible": visible,
                    "x": x,
                    "y": y,
                    "w": w,
                    "h": h,
                    "scale": 1.0,
                    "rotation": 0.0,
                    "opacity": 1.0 if visible else 0.0,
                    "anchor": anchor,
                    "asset": cutout_rel,
                    "mask": _rel(mask_path, out_dir),
                    "centroid": contour.centroid,
                }
            )
    finally:
        spec.mask_provider.close()

    quality = build_quality_scores(detailed_frames)
    route = recommended_output(quality)
    sprite_path = object_dir / f"spritesheet.{sprite_format}"
    sprite_meta = write_spritesheet(
        cutout_paths=cutout_paths,
        output_path=sprite_path,
        format="WEBP" if sprite_format == "webp" else "PNG",
    )
    if sprite_meta:
        sprite_meta["path"] = _rel(sprite_path, out_dir)
        for entry, sprite_frame in zip((m for m in motion if m["asset"]), sprite_meta["frames"]):
            entry["sprite"] = sprite_frame

    rights = build_object_rights(object_id=object_id, context=rights_context, fallback_source_uri=rights_context.get("source_uri") if rights_context else None)
    obj = {
        "id": object_id,
        "label": spec.label,
        "renderMode": "raster_alpha_sequence",
        "asset": f"objects/{object_id}/cutouts/cutout_%06d.png",
        "mask": f"masks/{object_id}/mask_%06d.png",
        "assets": {
            "cutoutPattern": f"objects/{object_id}/cutouts/cutout_%06d.png",
            "spritesheet": sprite_meta,
        },
        "zIndex": spec.z_index,
        "motion": motion,
        "frames": detailed_frames,
        "interactions": {
            "idle": {"loop": True, "scale": 1.0, "opacity": 1.0},
            "hover": {"scale": 1.06, "outline": True},
            "click": {"action": "reuse_or_open_detail"},
        },
        "quality": quality,
        "recommendedOutput": route,
        "rights": rights,
    }
    if output_mode in {"production", "both"}:
        production_assets = export_production_assets(
            out_dir=out_dir,
            object_id=object_id,
            motion=motion,
            canvas_width=info.width,
            canvas_height=info.height,
            fps=info.sample_fps,
            include_avif=production_avif,
        )
        obj["assets"]["production"] = production_assets

    object_manifest = {
        "schema": "motionjson.object_manifest.v0.1",
        "objectId": object_id,
        "label": spec.label,
        "renderMode": obj["renderMode"],
        "cutouts": [entry["asset"] for entry in motion if entry["asset"]],
        "masks": [entry["mask"] for entry in motion],
        "spritesheet": sprite_meta,
        "motion": motion,
        "quality": quality,
        "recommendedOutput": route,
        "rights": rights,
    }
    if "production" in obj["assets"]:
        object_manifest["production"] = obj["assets"]["production"]
    object_motion = {
        "schema": "motionjson.object_motion.v0.1",
        "objectId": object_id,
        "fps": info.sample_fps,
        "motion": motion,
        "quality": quality,
        "recommendedOutput": route,
    }

    write_json(object_dir / "object_manifest.json", object_manifest)
    _write_object_motion(out_dir, object_id, object_motion)
    layer = _build_layer_frames(object_id, info.sample_fps, motion, z_index=spec.z_index)
    return obj, layer, object_motion, detailed_frames


def run_multi_object_pipeline(
    *,
    video_path: str | Path,
    out_dir: str | Path,
    object_specs: list[ObjectExtractionSpec],
    sample_fps: float | None = None,
    max_frames: int | None = None,
    min_area: float = 100.0,
    simplify_ratio: float = 0.006,
    feather: int = 0,
    layer_padding: int = 4,
    sprite_format: str = "webp",
    output_mode: str = "authoring",
    production_avif: bool = False,
    rights_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if sprite_format not in {"webp", "png"}:
        raise ValueError("sprite_format must be 'webp' or 'png'")
    if output_mode not in {"authoring", "production", "both"}:
        raise ValueError("output_mode must be 'authoring', 'production', or 'both'")
    if not object_specs:
        raise ValueError("At least one object extraction spec is required")
    object_ids = [spec.object_id for spec in object_specs]
    for object_id in object_ids:
        _validate_object_id(object_id)
    if len(set(object_ids)) != len(object_ids):
        raise ValueError("Object extraction specs must use unique object IDs")

    video_path = Path(video_path)
    out_dir = Path(out_dir)
    normalized_rights = normalize_rights_context(rights_context, fallback_source_uri=video_path)
    rights_payload = {
        "source_type": normalized_rights.source_type,
        "source_asset_id": normalized_rights.source_asset_id,
        "source_uri": normalized_rights.source_uri,
        "display_text": normalized_rights.display_text,
        "attribution_required": normalized_rights.attribution_required,
        "license": normalized_rights.license,
        "license_name": normalized_rights.license_name,
        "license_url": normalized_rights.license_url,
        "license_scope": normalized_rights.license_scope,
        "creator_approved": normalized_rights.creator_approved,
        "creator_approval_status": normalized_rights.creator_approval_status,
        "creator_approval_evidence": list(normalized_rights.creator_approval_evidence),
        "commercial_use": normalized_rights.commercial_use,
        "commercial_use_status": normalized_rights.commercial_use_status,
        "audit_log": list(normalized_rights.audit_log),
    }
    frames_dir = out_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    _clear_generated_frames(frames_dir)
    for stale in (out_dir / "benchmark_report.json", out_dir / "silhouette_lottie.json"):
        if stale.exists():
            stale.unlink()

    info, frame_iter = iter_sampled_frames(video_path, sample_fps=sample_fps, max_frames=max_frames)
    frames = list(frame_iter)
    for frame in frames:
        frame_number = frame.out_index + 1
        Image.fromarray(frame.rgb).save(frames_dir / f"frame_{frame_number:06d}.png")

    source = {
        "video": str(video_path),
        "width": info.width,
        "height": info.height,
        "fps": info.source_fps,
        "sampleFps": info.sample_fps,
        "totalSourceFrames": info.total_source_frames,
        "sampledFrameCount": len(frames),
    }
    objects: list[dict[str, Any]] = []
    layers: list[dict[str, Any]] = []
    object_motions: dict[str, dict[str, Any]] = {}
    first_detailed_frames: list[dict[str, Any]] = []
    for index, spec in enumerate(object_specs):
        obj, layer, object_motion, detailed_frames = _extract_object(
            out_dir=out_dir,
            frames_dir=frames_dir,
            info=info,
            frames=frames,
            spec=spec,
            min_area=min_area,
            simplify_ratio=simplify_ratio,
            feather=feather,
            layer_padding=layer_padding,
            sprite_format=sprite_format,
            output_mode=output_mode,
            production_avif=production_avif,
            rights_context=rights_payload,
        )
        objects.append(obj)
        layers.append(layer)
        object_motions[spec.object_id] = object_motion
        if index == 0:
            first_detailed_frames = detailed_frames

    scene = {
        "schema": "motionjson.scene_graph.v0.1",
        "version": "0.1.0",
        "source": source,
        "objects": objects,
        "canvas": {
            "width": info.width,
            "height": info.height,
            "source_fps": info.source_fps,
            "fps": info.sample_fps,
            "frame_count": len(frames),
        },
        "layers": layers,
        "rendering": {
            "recommendedRuntime": "Canvas/WebGL/PixiJS",
            "defaultRenderMode": "raster_alpha_sequence",
            "outputMode": output_mode,
            "vectorPolicy": "Use SVG/Lottie only for simple silhouettes, outlines, labels, annotations, or clean flat graphics.",
        },
        "rightsManifest": "rights_manifest.json",
    }
    rights_manifest = build_rights_manifest(source=source, objects=objects, context=rights_payload)

    default_object_id = object_specs[0].object_id
    _write_object_motion(out_dir, default_object_id, object_motions[default_object_id], legacy=True)
    write_silhouette_lottie(
        out_dir / "silhouette_lottie.json",
        width=info.width,
        height=info.height,
        fps=info.sample_fps,
        frames=first_detailed_frames,
    )
    write_json(out_dir / "scene_graph.json", scene)
    write_rights_manifest(out_dir / "rights_manifest.json", rights_manifest)
    for index, spec in enumerate(object_specs):
        _write_object_web_manifest(out_dir, scene, spec.object_id, legacy=index == 0)
    _preview_copy(out_dir)
    write_profiled_outputs(out_dir=out_dir, video_path=video_path, object_id=default_object_id, scene=scene)

    return scene


def run_pipeline(
    *,
    video_path: str | Path,
    out_dir: str | Path,
    mask_provider: MaskProvider,
    object_id: str = "object_0",
    object_label: str = "selected_object",
    sample_fps: float | None = None,
    max_frames: int | None = None,
    min_area: float = 100.0,
    simplify_ratio: float = 0.006,
    feather: int = 0,
    layer_padding: int = 4,
    sprite_format: str = "webp",
    output_mode: str = "authoring",
    production_avif: bool = False,
    rights_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return run_multi_object_pipeline(
        video_path=video_path,
        out_dir=out_dir,
        object_specs=[ObjectExtractionSpec(object_id=object_id, label=object_label, mask_provider=mask_provider)],
        sample_fps=sample_fps,
        max_frames=max_frames,
        min_area=min_area,
        simplify_ratio=simplify_ratio,
        feather=feather,
        layer_padding=layer_padding,
        sprite_format=sprite_format,
        output_mode=output_mode,
        production_avif=production_avif,
        rights_context=rights_context,
    )
