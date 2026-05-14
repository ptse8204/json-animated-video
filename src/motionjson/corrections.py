from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

from .exporters.scene_graph import write_json
from .masks import ExternalMaskProvider
from .pipeline import run_pipeline


@dataclass(frozen=True)
class CorrectedMaskSet:
    mask_dir: Path
    frame_count: int
    changed_frames: list[int]


def _binary(mask: np.ndarray) -> np.ndarray:
    if mask.ndim == 3:
        mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
    return np.where(mask > 127, 255, 0).astype(np.uint8)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _first_object(scene: dict[str, Any], object_id: str) -> dict[str, Any]:
    for obj in scene.get("objects", []):
        if obj.get("id") == object_id:
            return obj
    raise ValueError(f"Object {object_id!r} not found in scene_graph.json")


def _source_video_path(source_dir: Path, scene: dict[str, Any]) -> Path:
    raw = scene.get("source", {}).get("video")
    if not raw:
        raise ValueError("scene_graph.json is missing source.video; cannot rerun correction output")
    path = Path(raw)
    if path.exists():
        return path
    candidate = source_dir / path
    if candidate.exists():
        return candidate
    raise FileNotFoundError(f"Source video {raw!r} does not exist")


def _mask_files(source_dir: Path, object_id: str) -> list[Path]:
    mask_dir = source_dir / "masks" / object_id
    files = sorted(mask_dir.glob("mask_*.png"))
    if not files:
        raise FileNotFoundError(f"No source masks found under {mask_dir}")
    return files


def _clamped_frame_range(value: Any, frame_count: int) -> tuple[int, int] | None:
    if not isinstance(value, list | tuple) or len(value) != 2:
        return None
    start = max(1, min(frame_count, int(value[0])))
    end = max(1, min(frame_count, int(value[1])))
    if start > end:
        start, end = end, start
    return start, end


def _frame_targets(operation: dict[str, Any], frame_count: int, propagation: dict[str, Any]) -> list[int]:
    propagate = bool(operation.get("propagate", propagation.get("enabled", False)))
    mode = str(propagation.get("mode", "same_coordinates"))
    if propagate and mode != "none":
        frame_range = _clamped_frame_range(operation.get("frameRange"), frame_count) or _clamped_frame_range(
            propagation.get("frameRange"),
            frame_count,
        )
        if frame_range:
            return list(range(frame_range[0], frame_range[1] + 1))
        return list(range(1, frame_count + 1))
    frame = int(operation.get("frame") or operation.get("frameNumber") or 1)
    return [max(1, min(frame_count, frame))]


def _mask_centroids(masks: list[np.ndarray]) -> list[tuple[float, float] | None]:
    centroids: list[tuple[float, float] | None] = []
    for mask in masks:
        moments = cv2.moments((mask > 127).astype(np.uint8))
        if moments["m00"] == 0:
            centroids.append(None)
            continue
        centroids.append((float(moments["m10"] / moments["m00"]), float(moments["m01"] / moments["m00"])))
    return centroids


def _shift_point(point: Any, dx: float, dy: float) -> list[int]:
    return [int(round(float(point[0]) + dx)), int(round(float(point[1]) + dy))]


def _operation_for_frame(
    operation: dict[str, Any],
    *,
    frame_number: int,
    source_frame_number: int,
    propagation_mode: str,
    centroids: list[tuple[float, float] | None],
) -> dict[str, Any]:
    shifted = dict(operation)
    shifted["frame"] = frame_number
    if propagation_mode != "centroid_delta" or frame_number == source_frame_number:
        return shifted

    source_centroid = centroids[source_frame_number - 1] if 0 <= source_frame_number - 1 < len(centroids) else None
    target_centroid = centroids[frame_number - 1] if 0 <= frame_number - 1 < len(centroids) else None
    if source_centroid is None or target_centroid is None:
        return shifted

    dx = target_centroid[0] - source_centroid[0]
    dy = target_centroid[1] - source_centroid[1]
    if "x" in shifted:
        shifted["x"] = int(round(float(shifted["x"]) + dx))
    if "y" in shifted:
        shifted["y"] = int(round(float(shifted["y"]) + dy))
    if isinstance(shifted.get("points"), list):
        shifted["points"] = [_shift_point(point, dx, dy) for point in shifted["points"]]
    return shifted


def _draw_point(mask: np.ndarray, *, x: int, y: int, radius: int, value: int) -> None:
    cv2.circle(mask, (int(x), int(y)), max(1, int(radius)), int(value), -1)


def _draw_box(mask: np.ndarray, *, x: int, y: int, w: int, h: int, mode: str) -> None:
    raw_x0 = int(x)
    raw_y0 = int(y)
    raw_x1 = raw_x0 + max(0, int(w))
    raw_y1 = raw_y0 + max(0, int(h))
    x0 = max(0, raw_x0)
    y0 = max(0, raw_y0)
    x1 = min(mask.shape[1], raw_x1)
    y1 = min(mask.shape[0], raw_y1)
    if x1 <= x0 or y1 <= y0:
        return
    if mode == "remove":
        mask[y0:y1, x0:x1] = 0
    elif mode == "add":
        mask[y0:y1, x0:x1] = 255
    elif mode == "constrain":
        constrained = np.zeros_like(mask)
        constrained[y0:y1, x0:x1] = mask[y0:y1, x0:x1]
        mask[:, :] = constrained
    elif mode == "replace":
        mask[:, :] = 0
        mask[y0:y1, x0:x1] = 255
    else:
        raise ValueError(f"Unsupported box correction mode: {mode!r}")


def _draw_brush(mask: np.ndarray, *, points: list[list[int]], radius: int, value: int) -> None:
    if not points:
        return
    previous: tuple[int, int] | None = None
    for point in points:
        current = (int(point[0]), int(point[1]))
        _draw_point(mask, x=current[0], y=current[1], radius=radius, value=value)
        if previous is not None:
            cv2.line(mask, previous, current, int(value), max(1, int(radius) * 2))
        previous = current


def _apply_operation(mask: np.ndarray, operation: dict[str, Any]) -> np.ndarray:
    corrected = mask.copy()
    op_type = str(operation.get("type", "")).replace("-", "_")
    if op_type == "box":
        default_mode = "constrain"
    elif op_type == "brush":
        default_mode = "add"
    else:
        default_mode = ""
    mode = str(operation.get("mode", default_mode)).lower()
    radius = int(operation.get("radius") or 10)

    if op_type == "add_point":
        _draw_point(corrected, x=int(operation["x"]), y=int(operation["y"]), radius=radius, value=255)
    elif op_type == "remove_point":
        _draw_point(corrected, x=int(operation["x"]), y=int(operation["y"]), radius=radius, value=0)
    elif op_type == "box":
        _draw_box(corrected, x=int(operation["x"]), y=int(operation["y"]), w=int(operation["w"]), h=int(operation["h"]), mode=mode)
    elif op_type == "brush":
        points = operation.get("points") or []
        if not isinstance(points, list):
            raise ValueError("brush operation requires points array")
        if mode not in {"add", "remove"}:
            raise ValueError(f"Unsupported brush correction mode: {mode!r}")
        value = 0 if mode == "remove" else 255
        _draw_brush(corrected, points=points, radius=radius, value=value)
    else:
        raise ValueError(f"Unsupported correction operation type: {operation.get('type')!r}")

    return _binary(corrected)


def _smooth_masks(masks: list[np.ndarray], *, radius: int, threshold: float) -> list[np.ndarray]:
    radius = max(0, int(radius))
    if radius == 0 or len(masks) < 2:
        return masks
    threshold = min(1.0, max(0.0, float(threshold)))
    smoothed: list[np.ndarray] = []
    for index in range(len(masks)):
        start = max(0, index - radius)
        end = min(len(masks), index + radius + 1)
        stack = np.stack([(mask > 127).astype(np.uint8) for mask in masks[start:end]], axis=0)
        votes = np.sum(stack, axis=0)
        required = max(1, int(np.ceil(stack.shape[0] * threshold)))
        smoothed.append(np.where(votes >= required, 255, 0).astype(np.uint8))
    return smoothed


def build_correction_request(
    *,
    object_id: str,
    operations: list[dict[str, Any]],
    propagate: bool = False,
    propagation_mode: str = "same_coordinates",
    frame_range: list[int] | None = None,
    smooth: bool = False,
    smooth_radius: int = 1,
) -> dict[str, Any]:
    propagation = {"enabled": bool(propagate), "mode": propagation_mode}
    if frame_range is not None:
        propagation["frameRange"] = frame_range
    return {
        "schema": "motionjson.correction_request.v0.1",
        "objectId": object_id,
        "operations": operations,
        "propagation": propagation,
        "temporalSmoothing": {"enabled": bool(smooth), "radius": int(smooth_radius), "threshold": 0.5},
        "aiUsage": "none",
    }


def apply_correction_request(source_dir: str | Path, request: dict[str, Any], *, work_dir: str | Path) -> CorrectedMaskSet:
    source_dir = Path(source_dir)
    work_dir = Path(work_dir)
    object_id = str(request.get("objectId") or "object_0")
    files = _mask_files(source_dir, object_id)
    masks = [_binary(np.array(Image.open(path).convert("L"))) for path in files]
    changed: set[int] = set()
    applied_operations: list[tuple[int, dict[str, Any]]] = []
    propagation = request.get("propagation", {})
    if not isinstance(propagation, dict):
        propagation = {}
    propagation_mode = str(propagation.get("mode", "same_coordinates"))
    centroids = _mask_centroids(masks) if propagation_mode == "centroid_delta" else []

    for operation in request.get("operations", []):
        if not isinstance(operation, dict):
            raise ValueError("Correction operation must be an object")
        source_frame_number = max(1, min(len(masks), int(operation.get("frame") or operation.get("frameNumber") or 1)))
        for frame_number in _frame_targets(operation, len(masks), propagation):
            frame_operation = _operation_for_frame(
                operation,
                frame_number=frame_number,
                source_frame_number=source_frame_number,
                propagation_mode=propagation_mode,
                centroids=centroids,
            )
            index = frame_number - 1
            before = masks[index]
            after = _apply_operation(before, frame_operation)
            if not np.array_equal(before, after):
                changed.add(frame_number)
            masks[index] = after
            applied_operations.append((frame_number, frame_operation))

    smoothing = request.get("temporalSmoothing", {})
    if smoothing.get("enabled"):
        before = [mask.copy() for mask in masks]
        masks = _smooth_masks(
            masks,
            radius=int(smoothing.get("radius", 1)),
            threshold=float(smoothing.get("threshold", 0.5)),
        )
        changed.update(index + 1 for index, (old, new) in enumerate(zip(before, masks)) if not np.array_equal(old, new))
        for frame_number, operation in applied_operations:
            index = frame_number - 1
            before_explicit = masks[index]
            after_explicit = _apply_operation(before_explicit, operation)
            if not np.array_equal(before_explicit, after_explicit):
                changed.add(frame_number)
            masks[index] = after_explicit

    mask_dir = work_dir / "corrected_masks" / object_id
    mask_dir.mkdir(parents=True, exist_ok=True)
    for index, mask in enumerate(masks, start=1):
        Image.fromarray(mask).save(mask_dir / f"mask_{index:06d}.png")

    return CorrectedMaskSet(mask_dir=mask_dir, frame_count=len(masks), changed_frames=sorted(changed))


def write_correction_manifest(
    *,
    source_dir: Path,
    output_dir: Path,
    request: dict[str, Any],
    changed_frames: list[int],
    scene: dict[str, Any],
) -> dict[str, Any]:
    object_id = str(request.get("objectId") or "object_0")
    quality = _first_object(scene, object_id).get("quality", {})
    manifest = {
        "schema": "motionjson.correction_manifest.v0.1",
        "objectId": object_id,
        "sourceOutputDir": str(source_dir),
        "correctedOutputDir": str(output_dir),
        "request": request,
        "changedFrames": changed_frames,
        "regeneratedArtifacts": [
            "masks",
            "cutouts",
            "spritesheet",
            "scene_graph.json",
            "object_motion.json",
            f"objects/{object_id}/object_manifest.json",
            "web_asset_manifest.json",
            "resource_profile.json",
        ],
        "quality": quality,
        "recommendedOutput": _first_object(scene, object_id).get("recommendedOutput", "raster_alpha_sequence"),
        "aiUsage": "none",
        "providerPolicy": "deterministic_local_correction_only",
    }
    write_json(output_dir / "correction_manifest.json", manifest)
    write_json(output_dir / "correction_request.json", request)
    return manifest


def correct_output_dir(
    *,
    source_dir: str | Path,
    output_dir: str | Path,
    request: dict[str, Any],
    in_place: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_dir = Path(source_dir)
    output_dir = Path(output_dir)
    if not in_place and output_dir.resolve() == source_dir.resolve():
        raise ValueError("Refusing in-place correction without explicit --in-place")

    scene = _load_json(source_dir / "scene_graph.json")
    object_id = str(request.get("objectId") or "object_0")
    obj = _first_object(scene, object_id)
    video_path = _source_video_path(source_dir, scene)
    source = scene.get("source", {})
    output_mode = scene.get("rendering", {}).get("outputMode", "authoring")
    production = obj.get("assets", {}).get("production")
    production_avif = bool(isinstance(production, dict) and "avifSpriteAtlas" in production.get("assets", {}))

    target_dir = source_dir if in_place else output_dir
    if target_dir.exists() and not in_place:
        shutil.rmtree(target_dir)

    with tempfile.TemporaryDirectory(prefix="motionjson-correction-") as tmp:
        corrected = apply_correction_request(source_dir, request, work_dir=tmp)
        corrected_scene = run_pipeline(
            video_path=video_path,
            out_dir=target_dir,
            mask_provider=ExternalMaskProvider(corrected.mask_dir),
            object_id=object_id,
            object_label=obj.get("label", "selected_object"),
            sample_fps=float(source.get("sampleFps") or scene.get("canvas", {}).get("fps") or 12),
            max_frames=int(source.get("sampledFrameCount") or scene.get("canvas", {}).get("frame_count") or corrected.frame_count),
            output_mode=output_mode,
            production_avif=production_avif,
        )
    manifest = write_correction_manifest(
        source_dir=source_dir,
        output_dir=target_dir,
        request=request,
        changed_frames=corrected.changed_frames,
        scene=corrected_scene,
    )
    return corrected_scene, manifest
