from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


def validate_mask_fitness(out_dir: str | Path, *, object_id: str | None = None) -> dict[str, Any]:
    root = Path(out_dir)
    scene_path = root / "scene_graph.json"
    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    source = scene.get("source", {}) if isinstance(scene.get("source"), dict) else {}
    canvas = scene.get("canvas", {}) if isinstance(scene.get("canvas"), dict) else {}
    width = int(source.get("width") or canvas.get("width") or 0)
    height = int(source.get("height") or canvas.get("height") or 0)
    issues: list[str] = []
    checked_frames = 0
    checked_visible_frames = 0

    for obj in scene.get("objects", []):
        if object_id and obj.get("id") != object_id:
            continue
        for index, frame in enumerate(obj.get("motion", [])):
            checked_frames += 1
            label = f"{obj.get('id', '<object>')} motion[{index}]"
            mask_rel = frame.get("mask")
            if not mask_rel:
                issues.append(f"{label}: missing mask path")
                continue
            mask_path = root / str(mask_rel)
            if not mask_path.exists():
                issues.append(f"{label}: mask file does not exist: {mask_rel}")
                continue
            mask = np.array(Image.open(mask_path).convert("L"))
            if mask.shape != (height, width):
                issues.append(f"{label}: mask shape {list(mask.shape)} != canvas {[height, width]}")
            if not np.isin(mask, [0, 255]).all():
                issues.append(f"{label}: mask is not binary 0/255")
            mask_area = int(np.count_nonzero(mask))
            if frame.get("maskArea") is not None and int(frame["maskArea"]) != mask_area:
                issues.append(f"{label}: maskArea {frame['maskArea']} != file nonzero count {mask_area}")
            _check_source_bbox(issues, label, frame, mask)
            if frame.get("visible"):
                checked_visible_frames += 1
                _check_cutout(issues, label, root, frame, mask, width, height)

    return {
        "schema": "motionjson.mask_fitness_report.v0.1",
        "outDir": str(root),
        "objectId": object_id,
        "checkedFrames": checked_frames,
        "checkedVisibleFrames": checked_visible_frames,
        "issues": issues,
        "ok": not issues,
    }


def _check_source_bbox(issues: list[str], label: str, frame: dict[str, Any], mask: np.ndarray) -> None:
    source_bbox = frame.get("sourceBbox") or frame.get("bbox")
    if not source_bbox or int(np.count_nonzero(mask)) == 0:
        return
    ys, xs = np.nonzero(mask)
    min_x, max_x = int(xs.min()), int(xs.max())
    min_y, max_y = int(ys.min()), int(ys.max())
    x, y, w, h = [int(round(float(value))) for value in source_bbox]
    if min_x < x or min_y < y or max_x >= x + w or max_y >= y + h:
        issues.append(f"{label}: sourceBbox {source_bbox} does not enclose mask bounds {[min_x, min_y, max_x - min_x + 1, max_y - min_y + 1]}")


def _check_cutout(
    issues: list[str],
    label: str,
    root: Path,
    frame: dict[str, Any],
    mask: np.ndarray,
    canvas_width: int,
    canvas_height: int,
) -> None:
    asset_rel = frame.get("asset")
    if not asset_rel:
        issues.append(f"{label}: visible frame has no cutout asset")
        return
    asset_path = root / str(asset_rel)
    if not asset_path.exists():
        issues.append(f"{label}: cutout file does not exist: {asset_rel}")
        return
    x = int(round(float(frame.get("x") or 0)))
    y = int(round(float(frame.get("y") or 0)))
    w = int(round(float(frame.get("w") or 0)))
    h = int(round(float(frame.get("h") or 0)))
    if w <= 0 or h <= 0:
        issues.append(f"{label}: visible frame has non-positive render size {[w, h]}")
        return
    if x < 0 or y < 0 or x + w > canvas_width or y + h > canvas_height:
        issues.append(f"{label}: render bbox {[x, y, w, h]} is outside canvas {[canvas_width, canvas_height]}")
        return
    cutout = Image.open(asset_path).convert("RGBA")
    if cutout.size != (w, h):
        issues.append(f"{label}: cutout size {list(cutout.size)} != render size {[w, h]}")
        return
    alpha = np.array(cutout)[:, :, 3]
    mask_crop = mask[y : y + h, x : x + w] > 0
    if not np.any(alpha > 0):
        issues.append(f"{label}: cutout alpha is empty")
    if mask_crop.shape != alpha.shape:
        issues.append(f"{label}: mask crop shape {list(mask_crop.shape)} != cutout alpha shape {list(alpha.shape)}")
        return
    if np.any(mask_crop) and not np.all(alpha[mask_crop] > 0):
        issues.append(f"{label}: cutout alpha misses foreground mask pixels")
