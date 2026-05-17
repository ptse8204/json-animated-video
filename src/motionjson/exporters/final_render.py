from __future__ import annotations

import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageColor

from .scene_graph import write_json

FINAL_EXPORT_SCHEMA = "motionjson.final_export_manifest.v0.1"


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


def _safe_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except FileNotFoundError:
        return 0


def load_json(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def load_scene(out_dir: str | Path) -> dict[str, Any]:
    return load_json(Path(out_dir) / "scene_graph.json")


def _canvas(scene: dict[str, Any]) -> dict[str, Any]:
    source = scene.get("source", {})
    canvas = scene.get("canvas", {})
    return {
        "width": int(source.get("width") or canvas.get("width") or 1),
        "height": int(source.get("height") or canvas.get("height") or 1),
        "fps": float(source.get("sampleFps") or canvas.get("fps") or 12),
        "frameCount": int(source.get("sampledFrameCount") or canvas.get("frame_count") or 0),
    }


def _object_by_id(scene: dict[str, Any], object_id: str) -> dict[str, Any]:
    for obj in scene.get("objects", []):
        if obj.get("id") == object_id:
            return obj
    raise ValueError(f"Object {object_id!r} not found in scene_graph.json")


def _rights_for(scene: dict[str, Any], object_id: str | None = None) -> dict[str, Any]:
    if object_id:
        try:
            return dict(_object_by_id(scene, object_id).get("rights", {}))
        except ValueError:
            pass
    rights: dict[str, Any] = {}
    for obj in scene.get("objects", []):
        if obj.get("rights"):
            rights[obj.get("id", "object")] = obj["rights"]
    return rights


def _parse_background(background_color: str) -> tuple[int, int, int, int]:
    try:
        rgb = ImageColor.getrgb(background_color)
    except ValueError as exc:
        raise ValueError(f"Invalid background color {background_color!r}") from exc
    if len(rgb) == 4:
        return int(rgb[0]), int(rgb[1]), int(rgb[2]), int(rgb[3])
    return int(rgb[0]), int(rgb[1]), int(rgb[2]), 255


def _motion_by_frame(obj: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {int(entry.get("frame", 0)): entry for entry in obj.get("motion", [])}


def _base_layers(scene: dict[str, Any]) -> list[dict[str, Any]]:
    layers = []
    raw_layers = scene.get("layers") or []
    if raw_layers:
        for index, layer in enumerate(raw_layers):
            object_id = layer.get("object_id") or layer.get("objectId")
            if not object_id:
                continue
            layers.append(
                {
                    "id": layer.get("id") or f"{object_id}_layer",
                    "objectId": object_id,
                    "sourceAssetId": object_id,
                    "visible": layer.get("visible", True),
                    "opacity": float(layer.get("opacity", 1)),
                    "zIndex": int(layer.get("z_index", layer.get("zIndex", 10 + index))),
                    "clip": {"startFrame": 1, "endFrame": 10**9},
                    "transform": {"translate": [0, 0], "scale": 1, "rotation": 0},
                }
            )
        return layers

    for index, obj in enumerate(scene.get("objects", [])):
        layers.append(
            {
                "id": f"{obj.get('id', f'object_{index}')}_layer",
                "objectId": obj.get("id"),
                "sourceAssetId": obj.get("id"),
                "visible": True,
                "opacity": 1.0,
                "zIndex": int(obj.get("zIndex", 10 + index)),
                "clip": {"startFrame": 1, "endFrame": 10**9},
                "transform": {"translate": [0, 0], "scale": 1, "rotation": 0},
            }
        )
    return layers


def _editor_layers(editor_state: dict[str, Any] | None, scene: dict[str, Any]) -> list[dict[str, Any]]:
    if not editor_state:
        return _base_layers(scene)
    if editor_state.get("schema") != "motionjson.timeline_editor_state.v0.1":
        raise ValueError("editor state must use schema motionjson.timeline_editor_state.v0.1")
    layers = editor_state.get("layers")
    if not isinstance(layers, list):
        raise ValueError("editor state must contain a layers array")
    normalized = []
    for index, layer in enumerate(layers):
        object_id = layer.get("objectId") or layer.get("sourceAssetId")
        if not object_id:
            continue
        clip = layer.get("clip") or {}
        transform = layer.get("transform") or {}
        translate = transform.get("translate") if isinstance(transform.get("translate"), list) else [0, 0]
        normalized.append(
            {
                "id": layer.get("id") or f"{object_id}_editor_layer_{index}",
                "objectId": object_id,
                "sourceAssetId": layer.get("sourceAssetId") or object_id,
                "visible": layer.get("visible", True),
                "opacity": float(layer.get("opacity", 1)),
                "zIndex": int(layer.get("zIndex", 10 + index)),
                "clip": {
                    "startFrame": int(clip.get("startFrame", 1)),
                    "endFrame": int(clip.get("endFrame", 10**9)),
                },
                "transform": {
                    "translate": [float(translate[0] if len(translate) > 0 else 0), float(translate[1] if len(translate) > 1 else 0)],
                    "scale": float(transform.get("scale", 1)),
                    "rotation": float(transform.get("rotation", 0)),
                },
            }
        )
    return normalized


def _background_from_editor(editor_state: dict[str, Any] | None, fallback: str) -> str:
    if not editor_state:
        return fallback
    background = editor_state.get("background") or {}
    if background.get("type") == "solid" and background.get("color"):
        return str(background["color"])
    return fallback


def _apply_opacity(image: Image.Image, opacity: float) -> Image.Image:
    opacity = max(0.0, min(1.0, float(opacity)))
    if opacity >= 0.999:
        return image
    adjusted = image.copy()
    alpha = adjusted.getchannel("A").point(lambda value: int(value * opacity))
    adjusted.putalpha(alpha)
    return adjusted


def _transform_cutout(image: Image.Image, *, scale: float, rotation: float, opacity: float) -> Image.Image:
    scale = max(0.001, float(scale))
    if abs(scale - 1.0) > 0.0001:
        width = max(1, int(round(image.width * scale)))
        height = max(1, int(round(image.height * scale)))
        image = image.resize((width, height), Image.Resampling.LANCZOS)
    if abs(rotation) > 0.0001:
        image = image.rotate(-math.degrees(rotation), resample=Image.Resampling.BICUBIC, expand=True)
    return _apply_opacity(image, opacity)


def render_frames(
    *,
    out_dir: str | Path,
    scene: dict[str, Any],
    frame_dir: str | Path,
    background_color: str = "#fbfaf6",
    editor_state: dict[str, Any] | None = None,
) -> int:
    """Composite final render frames from cached object cutouts and JSON transforms."""
    out_dir = Path(out_dir)
    frame_dir = Path(frame_dir)
    frame_dir.mkdir(parents=True, exist_ok=True)
    canvas = _canvas(scene)
    width = canvas["width"]
    height = canvas["height"]
    frame_count = canvas["frameCount"]
    if frame_count <= 0:
        raise ValueError("scene_graph.json does not contain any sampled frames")

    background = _parse_background(_background_from_editor(editor_state, background_color))
    objects = {obj.get("id"): obj for obj in scene.get("objects", [])}
    motion_maps = {object_id: _motion_by_frame(obj) for object_id, obj in objects.items()}
    layers = sorted(_editor_layers(editor_state, scene), key=lambda layer: (layer["zIndex"], layer["id"]))

    written = 0
    for frame_number in range(1, frame_count + 1):
        canvas_image = Image.new("RGBA", (width, height), background)
        for layer in layers:
            if not layer["visible"] or layer["opacity"] <= 0:
                continue
            clip = layer["clip"]
            if frame_number < clip["startFrame"] or frame_number > clip["endFrame"]:
                continue
            object_id = layer["objectId"]
            motion = motion_maps.get(object_id, {}).get(frame_number)
            if not motion or not motion.get("visible") or not motion.get("asset"):
                continue
            cutout_path = out_dir / str(motion["asset"])
            if not cutout_path.exists():
                continue
            cutout = Image.open(cutout_path).convert("RGBA")
            transform = layer["transform"]
            scale = float(motion.get("scale", 1)) * float(transform.get("scale", 1))
            rotation = float(motion.get("rotation", 0)) + float(transform.get("rotation", 0))
            opacity = float(motion.get("opacity", 1)) * float(layer.get("opacity", 1))
            rendered = _transform_cutout(cutout, scale=scale, rotation=rotation, opacity=opacity)

            translate = transform.get("translate", [0, 0])
            base_w = float(motion.get("w") or cutout.width)
            base_h = float(motion.get("h") or cutout.height)
            center_x = float(motion.get("x", 0)) + base_w / 2 + float(translate[0])
            center_y = float(motion.get("y", 0)) + base_h / 2 + float(translate[1])
            paste_x = int(round(center_x - rendered.width / 2))
            paste_y = int(round(center_y - rendered.height / 2))
            canvas_image.alpha_composite(rendered, (paste_x, paste_y))
        canvas_image.convert("RGB").save(frame_dir / f"frame_{frame_number:06d}.png")
        written += 1
    return written


def final_export_entry(
    *,
    export_type: str,
    format_name: str,
    output_path: str | Path,
    out_dir: str | Path,
    status: str,
    mime_type: str,
    width: int | None = None,
    height: int | None = None,
    fps: float | None = None,
    frame_count: int | None = None,
    reason: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    output_path = Path(output_path)
    out_dir = Path(out_dir)
    path_value = _rel(output_path, out_dir) if output_path.exists() else str(output_path)
    entry: dict[str, Any] = {
        "type": export_type,
        "format": format_name,
        "status": status,
        "mimeType": mime_type,
        "path": path_value,
        "bytes": _safe_size(output_path),
        "aiUsage": "none",
        "source": "cached_assets_and_json_transforms",
    }
    if width is not None:
        entry["width"] = width
    if height is not None:
        entry["height"] = height
    if fps is not None:
        entry["fps"] = fps
    if frame_count is not None:
        entry["frameCount"] = frame_count
    if reason:
        entry["reason"] = reason
    if extra:
        entry.update(extra)
    return entry


def build_final_export_manifest(
    *,
    out_dir: str | Path,
    scene: dict[str, Any],
    exports: list[dict[str, Any]],
    object_id: str | None = None,
    provenance: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
    quality_routing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    canvas = _canvas(scene)
    manifest: dict[str, Any] = {
        "schema": FINAL_EXPORT_SCHEMA,
        "version": "0.1.0",
        "aiUsage": "none",
        "source": {
            "sceneGraph": "scene_graph.json",
            "directory": ".",
            "objectId": object_id,
            "width": canvas["width"],
            "height": canvas["height"],
            "fps": canvas["fps"],
            "frameCount": canvas["frameCount"],
        },
        "exports": exports,
        "rights": _rights_for(scene, object_id),
        "rightsManifest": scene.get("rightsManifest", "rights_manifest.json"),
        "notes": [
            "Final exports are rendered from cached raster/alpha assets and JSON transforms.",
            "No segmentation, matting, LLM, VLM, or external AI provider is invoked during export.",
        ],
    }
    if provenance is not None:
        manifest["provenance"] = provenance
    if config is not None:
        manifest["config"] = config
    if quality_routing is not None:
        manifest["qualityRouting"] = quality_routing
    if validation is not None:
        manifest["validation"] = validation
    return manifest


def write_final_export_manifest(
    *,
    manifest_path: str | Path,
    out_dir: str | Path,
    scene: dict[str, Any],
    exports: list[dict[str, Any]],
    object_id: str | None = None,
    provenance: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
    quality_routing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifest = build_final_export_manifest(
        out_dir=out_dir,
        scene=scene,
        exports=exports,
        object_id=object_id,
        provenance=provenance,
        config=config,
        validation=validation,
        quality_routing=quality_routing,
    )
    write_json(manifest_path, manifest)
    return manifest


def export_mp4(
    *,
    out_dir: str | Path,
    output_path: str | Path,
    background_color: str = "#fbfaf6",
    editor_state_path: str | Path | None = None,
) -> dict[str, Any]:
    out_dir = Path(out_dir)
    output_path = Path(output_path)
    scene = load_scene(out_dir)
    canvas = _canvas(scene)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    editor_state = load_json(editor_state_path) if editor_state_path else None
    base_extra = {
        "encoder": "ffmpeg libx264",
        "pixelFormat": "yuv420p",
        "movflags": "+faststart",
        "cachedSources": ["scene_graph.json", "objects/*/cutouts/*.png"],
    }
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return final_export_entry(
            export_type="mp4_final_render",
            format_name="mp4",
            output_path=output_path,
            out_dir=out_dir,
            status="unavailable",
            mime_type="video/mp4",
            width=canvas["width"],
            height=canvas["height"],
            fps=canvas["fps"],
            frame_count=canvas["frameCount"],
            reason="ffmpeg executable was not found",
            extra=base_extra,
        )

    with tempfile.TemporaryDirectory(prefix="motionjson_mp4_") as tmp:
        frame_dir = Path(tmp)
        render_frames(
            out_dir=out_dir,
            scene=scene,
            frame_dir=frame_dir,
            background_color=background_color,
            editor_state=editor_state,
        )
        cmd = [
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
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            return final_export_entry(
                export_type="mp4_final_render",
                format_name="mp4",
                output_path=output_path,
                out_dir=out_dir,
                status="error",
                mime_type="video/mp4",
                width=canvas["width"],
                height=canvas["height"],
                fps=canvas["fps"],
                frame_count=canvas["frameCount"],
                reason=(result.stderr or result.stdout or "ffmpeg failed").strip(),
                extra=base_extra,
            )

    if not output_path.exists() or output_path.stat().st_size == 0:
        return final_export_entry(
            export_type="mp4_final_render",
            format_name="mp4",
            output_path=output_path,
            out_dir=out_dir,
            status="error",
            mime_type="video/mp4",
            width=canvas["width"],
            height=canvas["height"],
            fps=canvas["fps"],
            frame_count=canvas["frameCount"],
            reason="ffmpeg completed but produced no output bytes",
            extra=base_extra,
        )

    return final_export_entry(
        export_type="mp4_final_render",
        format_name="mp4",
        output_path=output_path,
        out_dir=out_dir,
        status="ready",
        mime_type="video/mp4",
        width=canvas["width"],
        height=canvas["height"],
        fps=canvas["fps"],
        frame_count=canvas["frameCount"],
        extra=base_extra,
    )
