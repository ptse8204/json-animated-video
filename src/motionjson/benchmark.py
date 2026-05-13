from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import cv2
from PIL import Image


def _now_ms() -> float:
    return time.perf_counter() * 1000


def _round_ms(value: float) -> float:
    return round(value, 3)


def _source_indices(scene: dict[str, Any]) -> list[int]:
    objects = scene.get("objects", [])
    if not objects:
        return []
    return [int(f["source_frame_index"]) for f in objects[0].get("frames", [])]


def _layer_frames(scene: dict[str, Any]) -> list[dict[str, Any]]:
    layers = scene.get("layers", [])
    if layers:
        return [f for f in layers[0].get("frames", []) if f.get("visible") and f.get("asset")]
    objects = scene.get("objects", [])
    if not objects:
        return []
    return [
        {
            "asset": f.get("asset"),
            "x": 0,
            "y": 0,
            "width": scene["canvas"]["width"],
            "height": scene["canvas"]["height"],
            "visible": f.get("visible"),
        }
        for f in objects[0].get("frames", [])
        if f.get("visible") and f.get("asset")
    ]


def _benchmark_naive_video_decode(video_path: Path, wanted_indices: list[int], iterations: int) -> tuple[float, int]:
    wanted = set(wanted_indices)
    if not wanted:
        return 0.0, 0

    decoded = 0
    start = _now_ms()
    for _ in range(iterations):
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise FileNotFoundError(f"Could not open video: {video_path}")
        source_index = 0
        while True:
            ok, bgr = cap.read()
            if not ok:
                break
            if source_index in wanted:
                rgba = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGBA)
                decoded += int(rgba.shape[0] * rgba.shape[1])
                if len(wanted) and source_index >= max(wanted):
                    break
            source_index += 1
        cap.release()
    return _now_ms() - start, decoded


def _benchmark_layer_composite(out_dir: Path, scene: dict[str, Any], frames: list[dict[str, Any]], iterations: int) -> tuple[float, float, int]:
    canvas_w = int(scene["canvas"]["width"])
    canvas_h = int(scene["canvas"]["height"])

    load_start = _now_ms()
    loaded: list[tuple[Image.Image, int, int]] = []
    for frame in frames:
        asset = frame.get("asset")
        if not asset:
            continue
        img = Image.open(out_dir / asset).convert("RGBA")
        loaded.append((img, int(frame.get("x") or 0), int(frame.get("y") or 0)))
    load_ms = _now_ms() - load_start

    pixels = 0
    composite_start = _now_ms()
    for _ in range(iterations):
        for img, x, y in loaded:
            canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
            canvas.alpha_composite(img, (x, y))
            pixels += img.width * img.height
    composite_ms = _now_ms() - composite_start
    return load_ms, composite_ms, pixels


def benchmark_scene(
    *,
    video_path: str | Path,
    out_dir: str | Path,
    scene: dict[str, Any],
    iterations: int = 3,
) -> dict[str, Any]:
    """Measure naive full-video frame processing against cached layer compositing."""
    video_path = Path(video_path)
    out_dir = Path(out_dir)
    iterations = max(1, int(iterations))
    wanted_indices = _source_indices(scene)
    layer_frames = _layer_frames(scene)

    naive_ms, naive_pixels = _benchmark_naive_video_decode(video_path, wanted_indices, iterations)
    layer_load_ms, layer_composite_ms, layer_pixels = _benchmark_layer_composite(out_dir, scene, layer_frames, iterations)

    sampled_frames = max(1, len(wanted_indices))
    layer_frame_count = max(1, len(layer_frames))
    naive_per_frame = naive_ms / (sampled_frames * iterations)
    layer_hot_per_frame = layer_composite_ms / (layer_frame_count * iterations)
    speedup = naive_per_frame / layer_hot_per_frame if layer_hot_per_frame else None
    pixel_ratio = layer_pixels / naive_pixels if naive_pixels else None

    return {
        "version": scene.get("version", "0.1.0"),
        "benchmark": "naive_video_decode_vs_cached_layer_composite",
        "iterations": iterations,
        "sampled_frames": len(wanted_indices),
        "layer_frames": len(layer_frames),
        "naive_video_decode": {
            "total_ms": _round_ms(naive_ms),
            "ms_per_frame": _round_ms(naive_per_frame),
            "decoded_pixels": naive_pixels,
        },
        "cached_layer_preview": {
            "asset_load_ms": _round_ms(layer_load_ms),
            "hot_composite_ms": _round_ms(layer_composite_ms),
            "hot_composite_ms_per_frame": _round_ms(layer_hot_per_frame),
            "composited_layer_pixels": layer_pixels,
        },
        "comparison": {
            "hot_preview_speedup_vs_naive_decode": round(speedup, 3) if speedup is not None else None,
            "layer_pixel_ratio_vs_full_frame": round(pixel_ratio, 4) if pixel_ratio is not None else None,
            "layer_pixel_reduction_vs_full_frame": round(1 - pixel_ratio, 4) if pixel_ratio is not None else None,
        },
        "notes": [
            "This benchmark isolates playback/edit preview after extraction; it does not include neural segmentation time.",
            "Naive mode decodes sampled full video frames. Layer mode composites already-cached cropped RGBA assets.",
            "Browser performance should be validated separately with Canvas/WebGL frame timing for production.",
        ],
    }
