from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import cv2
from PIL import Image
from tqdm import tqdm

from .exporters.lottie import write_silhouette_lottie
from .exporters.scene_graph import write_json
from .exporters.web_manifest import write_web_asset_manifest
from .layers import crop_rgba_layer, write_spritesheet
from .masks import MaskProvider
from .metrics import build_resource_profile
from .vectorize import build_quality_scores, mask_to_largest_polygon, recommended_output
from .video import iter_sampled_frames


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
        "website_graphics_hero.html",
        "object_selection_workflow.html",
        "object_selection_workflow.js",
    ):
        src = repo_root / "examples" / name
        if src.exists():
            shutil.copyfile(src, preview_dir / name)


def _rel(path: Path, root: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def _build_layer_frames(object_id: str, fps: float, motion: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": f"{object_id}_raster_layer",
        "object_id": object_id,
        "type": "raster_alpha_sequence",
        "asset_type": "cropped_rgba_png_sequence",
        "fps": fps,
        "z_index": 10,
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
) -> dict[str, Any]:
    if sprite_format not in {"webp", "png"}:
        raise ValueError("sprite_format must be 'webp' or 'png'")

    video_path = Path(video_path)
    out_dir = Path(out_dir)
    frames_dir = out_dir / "frames"
    mask_dir = out_dir / "masks" / object_id
    object_dir = out_dir / "objects" / object_id
    cutout_dir = object_dir / "cutouts"
    for directory in (frames_dir, mask_dir, cutout_dir, object_dir):
        directory.mkdir(parents=True, exist_ok=True)
    _clear_generated_frames(frames_dir, mask_dir, cutout_dir)
    for stale_dir in (object_dir / "masks", object_dir / "layers"):
        if stale_dir.exists():
            shutil.rmtree(stale_dir)
    for stale in (out_dir / "benchmark_report.json", object_dir / "spritesheet.webp", object_dir / "spritesheet.png"):
        if stale.exists():
            stale.unlink()

    info, frame_iter = iter_sampled_frames(video_path, sample_fps=sample_fps, max_frames=max_frames)
    frames = list(frame_iter)
    mask_provider.prepare(info)

    detailed_frames: list[dict[str, Any]] = []
    motion: list[dict[str, Any]] = []
    cutout_paths: list[Path] = []

    try:
        for frame in tqdm(frames, desc="processing frames"):
            frame_number = frame.out_index + 1
            frame_name = f"frame_{frame_number:06d}.png"
            mask_name = f"mask_{frame_number:06d}.png"
            cutout_name = f"cutout_{frame_number:06d}.png"

            frame_path = frames_dir / frame_name
            mask_path = mask_dir / mask_name
            cutout_path = cutout_dir / cutout_name

            Image.fromarray(frame.rgb).save(frame_path)
            frame_bgr = cv2.cvtColor(frame.rgb, cv2.COLOR_RGB2BGR)
            mask = mask_provider.get_mask(frame.index, frame_bgr)
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
        mask_provider.close()

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

    source = {
        "video": str(video_path),
        "width": info.width,
        "height": info.height,
        "fps": info.source_fps,
        "sampleFps": info.sample_fps,
        "totalSourceFrames": info.total_source_frames,
        "sampledFrameCount": len(frames),
    }
    obj = {
        "id": object_id,
        "label": object_label,
        "renderMode": "raster_alpha_sequence",
        "asset": f"objects/{object_id}/cutouts/cutout_%06d.png",
        "mask": f"masks/{object_id}/mask_%06d.png",
        "assets": {
            "cutoutPattern": f"objects/{object_id}/cutouts/cutout_%06d.png",
            "spritesheet": sprite_meta,
        },
        "zIndex": 10,
        "motion": motion,
        "frames": detailed_frames,
        "interactions": {
            "idle": {"loop": True, "scale": 1.0, "opacity": 1.0},
            "hover": {"scale": 1.06, "outline": True},
            "click": {"action": "reuse_or_open_detail"},
        },
        "quality": quality,
        "recommendedOutput": route,
        "rights": {
            "sourceAttribution": True,
            "license": "user_uploaded_placeholder",
            "notes": "Rights and likeness review required before remixing third-party footage.",
        },
    }
    scene = {
        "schema": "motionjson.scene_graph.v0.1",
        "version": "0.1.0",
        "source": source,
        "objects": [obj],
        "canvas": {
            "width": info.width,
            "height": info.height,
            "source_fps": info.source_fps,
            "fps": info.sample_fps,
            "frame_count": len(frames),
        },
        "layers": [_build_layer_frames(object_id, info.sample_fps, motion)],
        "rendering": {
            "recommendedRuntime": "Canvas/WebGL/PixiJS",
            "defaultRenderMode": "raster_alpha_sequence",
            "vectorPolicy": "Use SVG/Lottie only for simple silhouettes, outlines, labels, annotations, or clean flat graphics.",
        },
    }
    object_manifest = {
        "schema": "motionjson.object_manifest.v0.1",
        "objectId": object_id,
        "label": object_label,
        "renderMode": obj["renderMode"],
        "cutouts": [entry["asset"] for entry in motion if entry["asset"]],
        "masks": [entry["mask"] for entry in motion],
        "spritesheet": sprite_meta,
        "motion": motion,
        "quality": quality,
        "recommendedOutput": route,
    }
    object_motion = {
        "schema": "motionjson.object_motion.v0.1",
        "objectId": object_id,
        "fps": info.sample_fps,
        "motion": motion,
        "quality": quality,
        "recommendedOutput": route,
    }

    write_json(out_dir / "object_motion.json", object_motion)
    write_json(object_dir / "object_manifest.json", object_manifest)
    write_silhouette_lottie(out_dir / "silhouette_lottie.json", width=info.width, height=info.height, fps=info.sample_fps, frames=detailed_frames)
    write_json(out_dir / "scene_graph.json", scene)
    write_web_asset_manifest(out_dir / "web_asset_manifest.json", scene, object_id=object_id)
    _preview_copy(out_dir)
    profile = build_resource_profile(video_path=video_path, out_dir=out_dir, object_id=object_id, scene=scene)
    scene["resource_profile"] = profile
    write_json(out_dir / "resource_profile.json", profile)
    write_json(out_dir / "scene_graph.json", scene)
    write_web_asset_manifest(out_dir / "web_asset_manifest.json", scene, object_id=object_id)
    profile = build_resource_profile(video_path=video_path, out_dir=out_dir, object_id=object_id, scene=scene)
    scene["resource_profile"] = profile
    write_json(out_dir / "resource_profile.json", profile)
    write_json(out_dir / "scene_graph.json", scene)
    write_web_asset_manifest(out_dir / "web_asset_manifest.json", scene, object_id=object_id)

    return scene
