from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image


EVALUATION_FIXTURES = (
    "red_ball",
    "multi_object",
    "occlusion",
    "small_object",
    "camera_motion",
    "whole_frame_regression",
)
DEFAULT_BENCHMARK_MODES = ("external_masks",)
BENCHMARK_SUMMARY_SCHEMA = "motionjson.evaluation_benchmark.v0.1"
BENCHMARK_SUMMARY_FORMAT = BENCHMARK_SUMMARY_SCHEMA
FIXTURE_MANIFEST_FORMAT = "motionjson.evaluation_fixture.v0.1"
LOCAL_PATH_RE = re.compile(r"(?i)\bfile://[^\r\n]+|(?<![\w:])/(?:Users|private|var|tmp|Volumes|home)/[^\r\n]+")


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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sanitize_text(value: str) -> str:
    return LOCAL_PATH_RE.sub("[LOCAL_PATH_REDACTED]", value)


def normalize_fixture_names(value: str | list[str] | tuple[str, ...] | None) -> list[str]:
    if value is None:
        return list(EVALUATION_FIXTURES)
    if isinstance(value, str) and value.strip() in {"", "all", "synthetic"}:
        return list(EVALUATION_FIXTURES)
    raw = value if isinstance(value, (list, tuple)) else str(value).split(",")
    if any(str(item).strip() in {"all", "synthetic"} for item in raw):
        return list(EVALUATION_FIXTURES)
    names = [str(item).strip() for item in raw if str(item).strip()]
    unknown = sorted(set(names) - set(EVALUATION_FIXTURES))
    if unknown:
        raise ValueError(f"unknown benchmark fixture(s): {', '.join(unknown)}")
    return names


def normalize_benchmark_modes(value: str | list[str] | tuple[str, ...] | None) -> list[str]:
    aliases = {
        "external": "external_masks",
        "external-masks": "external_masks",
        "motion": "motion_foreground",
        "motion-foreground": "motion_foreground",
        "mock": "text_detector_mock",
        "text-mock": "text_detector_mock",
        "threshold": "external_masks",
    }
    allowed = {"external_masks", "motion_foreground", "text_detector_mock"}
    raw = DEFAULT_BENCHMARK_MODES if value is None or (isinstance(value, str) and not value.strip()) else value if isinstance(value, (list, tuple)) else str(value).split(",")
    modes = [aliases.get(str(item).strip(), str(item).strip()) for item in raw if str(item).strip()]
    unknown = sorted(set(modes) - allowed)
    if unknown:
        raise ValueError(f"unknown benchmark mode(s): {', '.join(unknown)}")
    return modes


def _background(width: int, height: int, *, shift: int = 0) -> np.ndarray:
    frame = np.full((height, width, 3), 244, dtype=np.uint8)
    frame[:, :, 1] = 247
    frame[:, :, 2] = 246
    for x in range(-(shift % 16), width, 16):
        frame[:, max(0, x) : min(width, x + 1)] = (224, 231, 229)
    for y in range(-((shift // 2) % 16), height, 16):
        frame[max(0, y) : min(height, y + 1), :] = (224, 231, 229)
    return frame


def _circle_mask(width: int, height: int, center: tuple[int, int], radius: int) -> np.ndarray:
    mask = np.zeros((height, width), dtype=np.uint8)
    cv2.circle(mask, center, radius, 255, -1)
    return mask


def _rect_mask(width: int, height: int, x: int, y: int, w: int, h: int) -> np.ndarray:
    mask = np.zeros((height, width), dtype=np.uint8)
    x0 = max(0, min(width, x))
    y0 = max(0, min(height, y))
    x1 = max(x0, min(width, x + w))
    y1 = max(y0, min(height, y + h))
    mask[y0:y1, x0:x1] = 255
    return mask


def _paint_mask(frame: np.ndarray, mask: np.ndarray, color: tuple[int, int, int]) -> None:
    frame[mask > 0] = color


def _fixture_frame_data(
    fixture: str,
    *,
    width: int,
    height: int,
    frames: int,
) -> tuple[list[np.ndarray], dict[str, dict[str, Any]], dict[str, Any]]:
    objects: dict[str, dict[str, Any]] = {}

    def ensure_object(object_id: str, label: str) -> list[np.ndarray]:
        objects.setdefault(object_id, {"id": object_id, "label": label, "masks": []})
        return objects[object_id]["masks"]

    rgb_frames: list[np.ndarray] = []
    for index in range(frames):
        shift = index * 3 if fixture == "camera_motion" else 0
        frame = _background(width, height, shift=shift)
        if fixture == "red_ball":
            center = (18 + index * 5, height // 2)
            mask = _circle_mask(width, height, center, 8)
            _paint_mask(frame, mask, (225, 32, 35))
            ensure_object("red_ball", "Red ball").append(mask)
        elif fixture == "multi_object":
            red = _circle_mask(width, height, (18 + index * 4, height // 2 - 9), 7)
            blue = _rect_mask(width, height, width - 26 - index * 3, height // 2 + 5, 12, 10)
            _paint_mask(frame, red, (225, 32, 35))
            _paint_mask(frame, blue, (24, 88, 214))
            ensure_object("red_ball", "Red ball").append(red)
            ensure_object("blue_block", "Blue block").append(blue)
        elif fixture == "occlusion":
            center = (20 + index * 5, height // 2)
            mask = _circle_mask(width, height, center, 9)
            occluder = _rect_mask(width, height, width // 2 - 4, 0, 8, height)
            visible = np.where(occluder > 0, 0, mask).astype(np.uint8)
            _paint_mask(frame, mask, (225, 32, 35))
            _paint_mask(frame, occluder, (122, 128, 126))
            ensure_object("occluded_ball", "Occluded ball").append(visible)
        elif fixture == "small_object":
            mask = _circle_mask(width, height, (12 + index * 4, 14 + index), 2)
            _paint_mask(frame, mask, (225, 32, 35))
            ensure_object("small_dot", "Small dot").append(mask)
        elif fixture == "camera_motion":
            mask = _circle_mask(width, height, (width // 2 + index * 2, height // 2), 7)
            _paint_mask(frame, mask, (225, 32, 35))
            ensure_object("camera_ball", "Camera-motion ball").append(mask)
        elif fixture == "whole_frame_regression":
            mask = np.full((height, width), 255, dtype=np.uint8)
            frame[:, :] = (226, 54, 54)
            ensure_object("whole_frame", "Whole-frame mask").append(mask)
        else:
            raise ValueError(f"unknown fixture: {fixture}")
        rgb_frames.append(frame)

    expected = {
        "objectCount": len(objects),
        "objectIds": list(objects),
        "acceptedTracks": 0 if fixture == "whole_frame_regression" else len(objects),
        "rejectedTracks": 1 if fixture == "whole_frame_regression" else 0,
        "fallbackReasonCounts": {"masks_too_large_whole_frame": 1} if fixture == "whole_frame_regression" else {},
        "expectedBehavior": _fixture_expected_behavior(fixture),
    }
    return rgb_frames, objects, expected


def _fixture_expected_behavior(fixture: str) -> str:
    return {
        "red_ball": "one red object track should be accepted with stable coverage",
        "multi_object": "two visible object tracks should be accepted without duplicate rejection",
        "occlusion": "one partially occluded object should remain accepted across visible frames",
        "small_object": "one tiny object should be accepted when min-area is set for small fixtures",
        "camera_motion": "external-mask mode should keep the target object despite background motion",
        "whole_frame_regression": "the whole-frame mask must be rejected with masks_too_large_whole_frame",
    }[fixture]


def generate_synthetic_fixture(
    fixture: str,
    out_dir: str | Path,
    *,
    width: int = 96,
    height: int = 64,
    frames: int = 6,
    fps: float = 12.0,
) -> dict[str, Any]:
    """Generate a CPU-only synthetic benchmark fixture with ground-truth masks."""
    if fixture not in EVALUATION_FIXTURES:
        raise ValueError(f"unknown fixture: {fixture}")
    out_dir = Path(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    frames = max(2, int(frames))
    width = max(32, int(width))
    height = max(24, int(height))
    rgb_frames, objects, expected = _fixture_frame_data(fixture, width=width, height=height, frames=frames)

    video_path = out_dir / "video.mp4"
    writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"mp4v"), float(fps), (width, height))
    if not writer.isOpened():
        raise RuntimeError(f"Could not open video writer for {video_path}")
    try:
        for frame in rgb_frames:
            writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
    finally:
        writer.release()

    manifest_objects: list[dict[str, Any]] = []
    for object_id, payload in objects.items():
        mask_dir = out_dir / "masks" / object_id
        mask_dir.mkdir(parents=True, exist_ok=True)
        nonzero_counts: list[int] = []
        for index, mask in enumerate(payload["masks"], start=1):
            nonzero_counts.append(int(np.count_nonzero(mask)))
            Image.fromarray(mask).save(mask_dir / f"mask_{index:06d}.png")
        manifest_objects.append(
            {
                "objectId": object_id,
                "label": payload["label"],
                "maskDir": f"masks/{object_id}",
                "frames": len(payload["masks"]),
                "minMaskArea": min(nonzero_counts) if nonzero_counts else 0,
                "maxMaskArea": max(nonzero_counts) if nonzero_counts else 0,
            }
        )

    manifest = {
        "format": FIXTURE_MANIFEST_FORMAT,
        "fixture": fixture,
        "description": _fixture_expected_behavior(fixture),
        "video": "video.mp4",
        "width": width,
        "height": height,
        "fps": float(fps),
        "frames": len(rgb_frames),
        "objects": manifest_objects,
        "expected": expected,
        "aiUsage": "none",
    }
    _write_json(out_dir / "fixture_manifest.json", manifest)
    _write_json(out_dir / "expected.json", {"format": "motionjson.evaluation_expected.v0.1", **expected, "aiUsage": "none"})
    return manifest


def _mode_label(mode: str) -> str:
    return {
        "external_masks": "External masks",
        "motion_foreground": "Motion foreground",
        "text_detector_mock": "Mock text detector",
    }[mode]


def _relative_to(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def _run_pipeline_for_mode(
    *,
    fixture_manifest: dict[str, Any],
    fixture_dir: Path,
    run_dir: Path,
    mode: str,
    sample_fps: float,
    max_frames: int | None,
    min_area: float,
) -> dict[str, Any]:
    from .masks import ExternalMaskProvider
    from .pipeline import ObjectExtractionSpec, run_multi_object_pipeline
    from .providers.discovery import MotionForegroundDiscoveryProvider, TextDetectorDiscoveryProvider, object_specs_from_candidates

    video_path = fixture_dir / fixture_manifest["video"]
    if mode == "external_masks":
        specs = [
            ObjectExtractionSpec(
                object_id=item["objectId"],
                label=item["label"],
                mask_provider=ExternalMaskProvider(fixture_dir / item["maskDir"]),
                z_index=10 + index * 10,
            )
            for index, item in enumerate(fixture_manifest["objects"])
        ]
        return run_multi_object_pipeline(
            video_path=video_path,
            out_dir=run_dir,
            object_specs=specs,
            sample_fps=sample_fps,
            max_frames=max_frames,
            min_area=min_area,
        )
    if mode == "motion_foreground":
        return run_multi_object_pipeline(
            video_path=video_path,
            out_dir=run_dir,
            object_specs=[],
            candidate_provider=MotionForegroundDiscoveryProvider(),
            candidate_config={"threshold": 18, "min_area": max(3.0, min_area), "max_candidates": 4},
            candidate_to_specs=lambda candidates: object_specs_from_candidates(candidates, base_dir=run_dir),
            sample_fps=sample_fps,
            max_frames=max_frames,
            min_area=min_area,
        )
    if mode == "text_detector_mock":
        labels = [item["label"] for item in fixture_manifest["objects"]] or ["object"]
        return run_multi_object_pipeline(
            video_path=video_path,
            out_dir=run_dir,
            object_specs=[],
            candidate_provider=TextDetectorDiscoveryProvider(),
            candidate_config={"mock": True, "labels": labels, "max_candidates": len(labels), "write_box_masks": True},
            candidate_to_specs=lambda candidates: object_specs_from_candidates(candidates, base_dir=run_dir),
            sample_fps=sample_fps,
            max_frames=max_frames,
            min_area=min_area,
        )
    raise ValueError(f"unsupported benchmark mode: {mode}")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validation_summary(run_dir: Path, *, object_ids: list[str] | tuple[str, ...]) -> dict[str, Any]:
    from .validation import validate_output_dir

    normalized_ids = list(dict.fromkeys(str(object_id) for object_id in object_ids if str(object_id).strip())) or ["object_0"]
    checked: dict[str, Path] = {}
    skipped: dict[str, Path] = {}
    issues: list[dict[str, Any]] = []
    issue_keys: set[tuple[str, str, str]] = set()
    for object_id in normalized_ids:
        result = validate_output_dir(run_dir, object_id=object_id)
        for path in result.checked:
            checked[_relative_to(path, run_dir)] = path
        for path in result.skipped:
            skipped[_relative_to(path, run_dir)] = path
        for issue in result.issues:
            rel_path = _relative_to(issue.path, run_dir)
            key = (rel_path, issue.message, issue.json_path)
            if key in issue_keys:
                continue
            issue_keys.add(key)
            issues.append({"objectId": object_id, "path": rel_path, "message": issue.message, "jsonPath": issue.json_path})
    return {
        "ok": not issues,
        "objectIds": normalized_ids,
        "checked": len(checked),
        "skipped": len(skipped),
        "issueCount": len(issues),
        "issues": issues[:8],
    }


def _bbox_iou_from_lists(a: list[Any] | None, b: list[Any] | None) -> float:
    if not a or not b or len(a) < 4 or len(b) < 4:
        return 0.0
    ax0, ay0, aw, ah = (float(a[0]), float(a[1]), float(a[2]), float(a[3]))
    bx0, by0, bw, bh = (float(b[0]), float(b[1]), float(b[2]), float(b[3]))
    ax1, ay1 = ax0 + aw, ay0 + ah
    bx1, by1 = bx0 + bw, by0 + bh
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    intersection = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
    if intersection <= 0:
        return 0.0
    union = (aw * ah) + (bw * bh) - intersection
    return round(intersection / union, 4) if union else 0.0


def _track_pair_mean_iou(left: dict[str, Any], right: dict[str, Any]) -> float:
    right_frames: dict[int, list[Any]] = {}
    for frame in right.get("frames", []):
        if not isinstance(frame, dict) or not frame.get("visible") or not frame.get("bbox"):
            continue
        try:
            right_frames[int(frame.get("frame"))] = frame.get("bbox")
        except (TypeError, ValueError):
            continue
    overlaps: list[float] = []
    for frame in left.get("frames", []):
        if not isinstance(frame, dict) or not frame.get("visible") or not frame.get("bbox"):
            continue
        try:
            frame_index = int(frame.get("frame"))
        except (TypeError, ValueError):
            continue
        if frame_index in right_frames:
            overlaps.append(_bbox_iou_from_lists(frame.get("bbox"), right_frames[frame_index]))
    return round(float(np.mean(overlaps)), 4) if overlaps else 0.0


def _duplicate_overlap_summary(tracks: dict[str, Any], filter_report: dict[str, Any]) -> dict[str, Any]:
    track_items = [item for item in tracks.get("tracks", []) if isinstance(item, dict)]
    pair_overlaps: list[dict[str, Any]] = []
    for left_index, left in enumerate(track_items):
        left_id = str(left.get("objectId") or "")
        if not left_id:
            continue
        for right in track_items[left_index + 1 :]:
            right_id = str(right.get("objectId") or "")
            if not right_id:
                continue
            pair_overlaps.append(
                {
                    "leftObjectId": left_id,
                    "rightObjectId": right_id,
                    "meanIou": _track_pair_mean_iou(left, right),
                }
            )
    mean_values = [float(item["meanIou"]) for item in pair_overlaps]
    suggestions = [
        {
            "keepObjectId": str(item.get("keepObjectId") or ""),
            "mergeObjectId": str(item.get("mergeObjectId") or ""),
            "meanIou": float(item.get("meanIou") or 0.0),
            "reason": str(item.get("reason") or "duplicate_track"),
        }
        for item in filter_report.get("mergeSuggestions", [])
        if isinstance(item, dict)
    ]
    suggestion_values = [float(item["meanIou"]) for item in suggestions]
    return {
        "pairCount": len(pair_overlaps),
        "maxMeanIou": round(max(mean_values), 4) if mean_values else 0.0,
        "meanPairIou": round(float(np.mean(mean_values)), 4) if mean_values else 0.0,
        "mergeSuggestionCount": len(suggestions),
        "suggestedMaxMeanIou": round(max(suggestion_values), 4) if suggestion_values else 0.0,
        "pairs": pair_overlaps[:20],
        "suggestions": suggestions,
    }


def _quality_summary(*, fixture_manifest: dict[str, Any], run_dir: Path, scene: dict[str, Any], elapsed_ms: float) -> dict[str, Any]:
    expected = fixture_manifest["expected"]
    tracks = _load_json(run_dir / "tracks.json") if (run_dir / "tracks.json").exists() else {}
    filter_report = tracks.get("filterReport") if isinstance(tracks.get("filterReport"), dict) else {}
    filter_summary = filter_report.get("summary") if isinstance(filter_report.get("summary"), dict) else {}
    decisions = filter_report.get("decisions") if isinstance(filter_report.get("decisions"), list) else []
    fallback_counts = filter_summary.get("fallbackReasonCounts") if isinstance(filter_summary.get("fallbackReasonCounts"), dict) else {}
    scene_object_ids = [str(item.get("id")) for item in scene.get("objects", []) if isinstance(item, dict) and item.get("id")]
    expected_object_ids = [str(item) for item in expected.get("objectIds", []) if str(item)]
    validation_object_ids = list(dict.fromkeys([*expected_object_ids, *scene_object_ids])) or ["object_0"]
    validation = _validation_summary(run_dir, object_ids=validation_object_ids)
    duplicate_overlap = _duplicate_overlap_summary(tracks, filter_report)
    visible_ratios = [float(decision.get("metrics", {}).get("visibleFrameRatio", 0.0)) for decision in decisions if isinstance(decision, dict)]
    max_coverages = [
        max(
            float(decision.get("metrics", {}).get("maxMaskFrameCoverageRatio", 0.0)),
            float(decision.get("metrics", {}).get("maxBboxFrameCoverageRatio", 0.0)),
        )
        for decision in decisions
        if isinstance(decision, dict)
    ]
    expected_fallbacks = expected.get("fallbackReasonCounts", {})
    fallback_expectations_met = all(int(fallback_counts.get(code, 0)) >= int(count) for code, count in expected_fallbacks.items())
    accepted = int(filter_summary.get("acceptedTracks", 0))
    rejected = int(filter_summary.get("rejectedTracks", 0))
    object_count_matches = len(scene_object_ids) == int(expected.get("objectCount", 0))
    object_ids_match = set(scene_object_ids) == set(expected_object_ids)
    passed = (
        validation["ok"]
        and object_count_matches
        and object_ids_match
        and accepted == int(expected.get("acceptedTracks", 0))
        and rejected == int(expected.get("rejectedTracks", 0))
        and fallback_expectations_met
    )
    return {
        "passed": passed,
        "validation": validation,
        "expectedObjectCount": expected.get("objectCount", 0),
        "expectedObjectIds": expected_object_ids,
        "sceneObjectCount": len(scene.get("objects", [])),
        "sceneObjectIds": scene_object_ids,
        "objectCountMatches": object_count_matches,
        "objectIdsMatch": object_ids_match,
        "acceptedTracks": accepted,
        "rejectedTracks": rejected,
        "fallbackReasonCounts": dict(fallback_counts),
        "expectedFallbackReasonCounts": dict(expected_fallbacks),
        "fallbackExpectationsMet": fallback_expectations_met,
        "duplicateOverlap": duplicate_overlap,
        "meanTrackContinuity": round(float(np.mean(visible_ratios)), 4) if visible_ratios else 0.0,
        "maxFrameCoverageRatio": round(max(max_coverages), 4) if max_coverages else 0.0,
        "runtimeMs": _round_ms(elapsed_ms),
        "sampledFrames": scene.get("source", {}).get("sampledFrameCount"),
    }


def _run_one_benchmark(
    *,
    fixture_manifest: dict[str, Any],
    fixture_dir: Path,
    run_dir: Path,
    output_root: Path,
    mode: str,
    sample_fps: float,
    max_frames: int | None,
    min_area: float,
) -> dict[str, Any]:
    if run_dir.exists():
        shutil.rmtree(run_dir)
    start = _now_ms()
    try:
        scene = _run_pipeline_for_mode(
            fixture_manifest=fixture_manifest,
            fixture_dir=fixture_dir,
            run_dir=run_dir,
            mode=mode,
            sample_fps=sample_fps,
            max_frames=max_frames,
            min_area=min_area,
        )
        elapsed = _now_ms() - start
        quality = _quality_summary(fixture_manifest=fixture_manifest, run_dir=run_dir, scene=scene, elapsed_ms=elapsed)
        status = "passed" if quality["passed"] else "regressed"
        error = None
    except Exception as exc:
        elapsed = _now_ms() - start
        error_message = _sanitize_text(str(exc))
        status = "failed"
        quality = {
            "passed": False,
            "runtimeMs": _round_ms(elapsed),
            "validation": {"ok": False, "checked": 0, "skipped": 0, "issueCount": 1, "issues": [{"path": "benchmark", "message": error_message}]},
            "acceptedTracks": 0,
            "rejectedTracks": 0,
            "fallbackReasonCounts": {},
            "expectedFallbackReasonCounts": dict(fixture_manifest.get("expected", {}).get("fallbackReasonCounts", {})),
            "fallbackExpectationsMet": False,
            "duplicateOverlap": {
                "pairCount": 0,
                "maxMeanIou": 0.0,
                "meanPairIou": 0.0,
                "mergeSuggestionCount": 0,
                "suggestedMaxMeanIou": 0.0,
                "pairs": [],
                "suggestions": [],
            },
            "meanTrackContinuity": 0.0,
            "maxFrameCoverageRatio": 0.0,
        }
        error = {"type": type(exc).__name__, "message": error_message}
        run_dir.mkdir(parents=True, exist_ok=True)
        _write_json(run_dir / "benchmark_failure.json", {"format": "motionjson.evaluation_failure.v0.1", "error": error, "aiUsage": "none"})
    return {
        "fixture": fixture_manifest["fixture"],
        "mode": mode,
        "modeLabel": _mode_label(mode),
        "status": status,
        "runDir": _relative_to(run_dir, output_root),
        "quality": quality,
        "error": error,
        "aiUsage": "none",
    }


def _summary_payload(*, output_root: Path, fixtures: list[str], modes: list[str], runs: list[dict[str, Any]]) -> dict[str, Any]:
    passed = sum(1 for run in runs if run["status"] == "passed")
    failed = sum(1 for run in runs if run["status"] == "failed")
    regressed = sum(1 for run in runs if run["status"] == "regressed")
    fallback_reason_counts: dict[str, int] = {}
    for run in runs:
        for reason, count in run.get("quality", {}).get("fallbackReasonCounts", {}).items():
            fallback_reason_counts[reason] = fallback_reason_counts.get(reason, 0) + int(count)
    return {
        "schema": BENCHMARK_SUMMARY_SCHEMA,
        "format": BENCHMARK_SUMMARY_FORMAT,
        "fixtures": fixtures,
        "modes": modes,
        "runs": runs,
        "summary": {
            "totalRuns": len(runs),
            "passedRuns": passed,
            "regressedRuns": regressed,
            "failedRuns": failed,
            "fallbackReasonCounts": fallback_reason_counts,
            "outputDirectory": ".",
        },
        "outputs": {
            "summaryJson": "summary.json",
            "summaryMarkdown": "summary.md",
            "fixturesDir": "fixtures/",
            "runsDir": "runs/",
        },
        "notes": [
            "Benchmarks use generated local fixtures and CPU/no-model providers only.",
            "External-mask mode is the deterministic reference path.",
            "Motion foreground and mock detector modes are comparison paths and may fail individual fixtures without failing the benchmark command.",
        ],
        "aiUsage": "none",
    }


def _markdown_summary(payload: dict[str, Any]) -> str:
    rows = [
        "# MotionJSON Evaluation Benchmark",
        "",
        "| Fixture | Mode | Status | Accepted | Rejected | Duplicate max IoU | Merge suggestions | Fallback reasons | Runtime ms |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | --- | ---: |",
    ]
    for run in payload["runs"]:
        quality = run["quality"]
        fallbacks = quality.get("fallbackReasonCounts") or {}
        duplicate_overlap = quality.get("duplicateOverlap") or {}
        fallback_text = ", ".join(f"{key}={value}" for key, value in sorted(fallbacks.items())) or "none"
        rows.append(
            f"| {run['fixture']} | {run['mode']} | {run['status']} | "
            f"{quality.get('acceptedTracks', 0)} | {quality.get('rejectedTracks', 0)} | "
            f"{duplicate_overlap.get('maxMeanIou', 0)} | {duplicate_overlap.get('mergeSuggestionCount', 0)} | "
            f"{fallback_text} | {quality.get('runtimeMs', 0)} |"
        )
    summary = payload["summary"]
    rows.extend(
        [
            "",
            "## Summary",
            "",
            f"- Total runs: {summary['totalRuns']}",
            f"- Passed: {summary['passedRuns']}",
            f"- Regressed: {summary['regressedRuns']}",
            f"- Failed: {summary['failedRuns']}",
            "- AI/model usage: none",
            "",
            "## Expected Demo Behavior",
            "",
            "- `red_ball`: one accepted track.",
            "- `multi_object`: two accepted tracks.",
            "- `occlusion`: one accepted track with partial visibility.",
            "- `small_object`: one accepted tiny track when benchmark min-area is low.",
            "- `camera_motion`: external-mask mode should keep the target despite moving background.",
            "- `whole_frame_regression`: whole-frame mask is rejected with `masks_too_large_whole_frame`.",
            "",
        ]
    )
    return "\n".join(rows)


def run_evaluation_benchmark(
    *,
    out_dir: str | Path,
    fixtures: str | list[str] | tuple[str, ...] | None = None,
    modes: str | list[str] | tuple[str, ...] | None = None,
    width: int = 96,
    height: int = 64,
    frames: int = 6,
    sample_fps: float = 12.0,
    max_frames: int | None = None,
    min_area: float = 1.0,
) -> dict[str, Any]:
    """Generate synthetic fixtures and run no-GPU evaluation benchmarks."""
    fixture_names = normalize_fixture_names(fixtures)
    mode_names = normalize_benchmark_modes(modes)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fixtures_root = out_dir / "fixtures"
    runs_root = out_dir / "runs"
    fixtures_root.mkdir(parents=True, exist_ok=True)
    runs_root.mkdir(parents=True, exist_ok=True)

    runs: list[dict[str, Any]] = []
    for fixture in fixture_names:
        fixture_dir = fixtures_root / fixture
        manifest = generate_synthetic_fixture(fixture, fixture_dir, width=width, height=height, frames=frames, fps=sample_fps)
        for mode in mode_names:
            runs.append(
                _run_one_benchmark(
                    fixture_manifest=manifest,
                    fixture_dir=fixture_dir,
                    run_dir=runs_root / f"{fixture}_{mode}",
                    output_root=out_dir,
                    mode=mode,
                    sample_fps=sample_fps,
                    max_frames=max_frames,
                    min_area=min_area,
                )
            )

    payload = _summary_payload(output_root=out_dir, fixtures=fixture_names, modes=mode_names, runs=runs)
    _write_json(out_dir / "summary.json", payload)
    (out_dir / "summary.md").write_text(_markdown_summary(payload), encoding="utf-8")
    return payload
