from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import cv2
import numpy as np
from PIL import Image

from ..masks import ExternalMaskProvider
from ..tracks import Box, ObjectCandidate, Point, RunContext, VideoSource
from .base import ProviderConfigError


DISCOVERY_MODES = {
    "manual_prompt",
    "auto_object_proposals",
    "sam_auto_masks",
    "text_detector",
    "class_detector",
    "motion_foreground",
    "external_masks",
}


CLASS_DETECTOR_PRESETS: dict[str, tuple[str, ...]] = {
    "common_objects": ("person", "sports ball", "car", "dog", "cat"),
    "people": ("person",),
    "vehicles": ("car", "truck", "bus", "motorcycle", "bicycle"),
    "animals": ("dog", "cat", "bird", "horse"),
    "sports": ("sports ball", "frisbee", "skateboard"),
    "custom": (),
}

MOCK_OBJECT_DISCOVERY_PRESETS: dict[str, dict[str, int]] = {
    "clean": {"accepted": 4, "rejected": 2},
    "balanced": {"accepted": 7, "rejected": 3},
    "maximum_recall": {"accepted": 14, "rejected": 6},
    "trace_everything": {"accepted": 18, "rejected": 10},
}


DISCOVERY_PROVIDER_SCHEMAS: dict[str, dict[str, Any]] = {
    "manual_prompt": {
        "mode": "manual_prompt",
        "title": "Manual prompt",
        "description": "Use user-created points, boxes, or mask references as object candidates.",
        "whenToUse": "Choose when the user knows the object and can mark it directly.",
        "inputs": ["points", "boxes", "mask_refs"],
        "configSchema": {
            "prompts": "array of {kind, frame_index, object_id, label, data}",
        },
        "noModelSafe": True,
        "mockAvailable": True,
    },
    "auto_object_proposals": {
        "mode": "auto_object_proposals",
        "title": "Discover objects",
        "description": "API-first automatic object proposals with low-cost default presets and review gates.",
        "whenToUse": "Use as the default discovery workflow when users should choose from API-returned candidates before tracking.",
        "inputs": ["quality preset", "keyframe policy", "candidate caps", "filter controls", "optional mock"],
        "configSchema": {
            "qualityPreset": "one of clean, balanced, maximum_recall, trace_everything",
            "intent": "discover_objects_clean, discover_objects_balanced, discover_objects_maximum_recall, or trace_everything",
            "providerPreference": "auto, mock, sam2-local, sam2-hosted, sam3-local, or sam3-hosted",
            "keyframePolicy": "scene_changes, uniform_interval, or manual",
            "maxKeyframes": "integer >= 1",
            "frameInterval": "integer >= 1 or null",
            "maxCandidatesPerKeyframe": "integer >= 1",
            "maxObjects": "integer >= 1",
            "minMaskArea": "integer >= 1",
            "maxMaskAreaRatio": "number 0..1",
            "dedupeIou": "number 0..1",
            "stabilityThreshold": "number 0..1",
            "trackSelectedOnly": "boolean",
            "requireReview": "boolean",
            "writeRejectedCandidates": "boolean",
            "costWarningAcknowledged": "required true for trace_everything",
        },
        "qualityPresets": ["clean", "balanced", "maximum_recall", "trace_everything"],
        "defaultQualityPreset": "clean",
        "noModelSafe": False,
        "mockAvailable": True,
        "requiresReview": True,
    },
    "sam_auto_masks": {
        "mode": "sam_auto_masks",
        "title": "Automatic masks",
        "description": "Scaffold for automatic keyframe mask proposals with area, stability, and overlap filters.",
        "whenToUse": "Use for proposing visible segments after a SAM2 automatic-mask backend is configured.",
        "inputs": ["keyframes", "filter controls", "optional mock"],
        "configSchema": {
            "keyframes": "array of frame indexes",
            "min_area": "number",
            "max_area_ratio": "number 0..1",
            "stability_threshold": "number 0..1",
            "overlap_threshold": "number 0..1",
            "max_candidates": "integer",
            "mock": "boolean",
        },
        "noModelSafe": False,
        "mockAvailable": True,
    },
    "text_detector": {
        "mode": "text_detector",
        "title": "Text detector",
        "description": "Open-vocabulary detector scaffold that turns text prompts into candidate boxes or masks.",
        "whenToUse": "Choose when the user can describe target objects by text labels.",
        "inputs": ["text prompt", "optional detector backend", "optional mock"],
        "configSchema": {
            "text": "string such as 'red ball . hand . cup'",
            "mock": "boolean",
            "max_candidates": "integer",
        },
        "noModelSafe": False,
        "mockAvailable": True,
    },
    "class_detector": {
        "mode": "class_detector",
        "title": "Class detector",
        "description": "Known-class detector scaffold that turns requested classes into candidates.",
        "whenToUse": "Choose when target classes come from a fixed detector label set.",
        "inputs": ["class preset", "classes", "optional detector backend", "optional mock"],
        "configSchema": {
            "class_preset": "one of common_objects, people, vehicles, animals, sports, custom",
            "classes": "array of class names",
            "confidence_threshold": "number 0..1",
            "mock": "boolean",
            "max_candidates": "integer",
        },
        "presets": {name: list(labels) for name, labels in CLASS_DETECTOR_PRESETS.items()},
        "noModelSafe": False,
        "mockAvailable": True,
    },
    "motion_foreground": {
        "mode": "motion_foreground",
        "title": "Motion foreground",
        "description": "CPU frame-difference provider that proposes moving foreground regions.",
        "whenToUse": "Choose for simple videos where target objects move against a mostly stable background.",
        "inputs": ["sampled frames", "threshold", "area filters"],
        "configSchema": {
            "threshold": "integer 0..255",
            "min_area": "number",
            "max_candidates": "integer",
            "morph_open": "integer",
            "morph_close": "integer",
        },
        "noModelSafe": True,
        "mockAvailable": True,
    },
    "external_masks": {
        "mode": "external_masks",
        "title": "External masks",
        "description": "Import object candidates from user-provided mask directories or a manifest.",
        "whenToUse": "Choose when masks or boxes were created in another tool.",
        "inputs": ["mask directories", "optional manifest"],
        "configSchema": {
            "objects": "array of {object_id, label, mask_dir, z_index}",
            "manifest": "path to JSON manifest with an objects array",
        },
        "noModelSafe": True,
        "mockAvailable": True,
    },
}


SAFE_OBJECT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


def discovery_provider_schemas() -> list[dict[str, Any]]:
    return [dict(DISCOVERY_PROVIDER_SCHEMAS[mode]) for mode in sorted(DISCOVERY_PROVIDER_SCHEMAS)]


def class_detector_presets() -> dict[str, list[str]]:
    return {name: list(labels) for name, labels in CLASS_DETECTOR_PRESETS.items()}


def _int_config(config: Mapping[str, Any], name: str, default: int) -> int:
    value = config.get(name, config.get("maxCandidatesPerKeyframe", default) if name == "max_candidates" else default)
    if isinstance(value, bool):
        raise ProviderConfigError(f"discovery.{name}: expected integer")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ProviderConfigError(f"discovery.{name}: expected integer") from exc


def _int_config_any(config: Mapping[str, Any], names: Sequence[str], default: int) -> int:
    for name in names:
        if name in config and config[name] is not None:
            return _int_config(config, name, default)
    return int(default)


def _bool_config_any(config: Mapping[str, Any], names: Sequence[str], default: bool) -> bool:
    for name in names:
        if name not in config or config[name] is None:
            continue
        value = config[name]
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
        raise ProviderConfigError(f"discovery.{name}: expected boolean")
    return bool(default)


def _float_config(config: Mapping[str, Any], name: str, default: float) -> float:
    value = config.get(name, default)
    if isinstance(value, bool):
        raise ProviderConfigError(f"discovery.{name}: expected number")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ProviderConfigError(f"discovery.{name}: expected number") from exc


def _ratio_config(config: Mapping[str, Any], name: str, default: float) -> float:
    value = _float_config(config, name, default)
    if value < 0.0 or value > 1.0:
        raise ProviderConfigError(f"discovery.{name}: expected number between 0 and 1")
    return value


def _mask_files(mask_dir: Path) -> list[Path]:
    files: list[Path] = []
    for pattern in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
        files.extend(sorted(mask_dir.glob(pattern)))
    return sorted(files)


def _safe_id(raw: str, fallback: str) -> str:
    candidate = re.sub(r"[^A-Za-z0-9_-]+", "_", raw.strip()).strip("_")
    if not candidate or not SAFE_OBJECT_ID_PATTERN.match(candidate):
        return fallback
    return candidate


def _prompt_payload(prompt: Any) -> tuple[str, int, str | None, str | None, Mapping[str, Any]]:
    if isinstance(prompt, Mapping):
        data = prompt.get("data", {})
        return (
            str(prompt.get("kind", "point")),
            int(prompt.get("frame_index", prompt.get("frameIndex", 0)) or 0),
            prompt.get("object_id") or prompt.get("objectId"),
            prompt.get("label"),
            data if isinstance(data, Mapping) else {},
        )
    kind = str(getattr(prompt, "kind", "point"))
    frame_index = int(getattr(prompt, "frame_index", 0) or 0)
    object_id = getattr(prompt, "object_id", None)
    label = getattr(prompt, "label", None)
    data = getattr(prompt, "data", {})
    return kind, frame_index, object_id, label, data if isinstance(data, Mapping) else {}


def _candidate_metadata(mode: str, description: str, extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
    metadata = {
        "providerMode": mode,
        "providerDescription": DISCOVERY_PROVIDER_SCHEMAS[mode]["description"],
        "whenToUse": DISCOVERY_PROVIDER_SCHEMAS[mode]["whenToUse"],
        "description": description,
    }
    if extra:
        metadata.update(dict(extra))
    return metadata


def _write_mask_sequence(video: VideoSource, mask_dir: Path, masks: Sequence[np.ndarray]) -> None:
    mask_dir.mkdir(parents=True, exist_ok=True)
    for stale in mask_dir.glob("mask_*.png"):
        stale.unlink()
    for frame, mask in zip(video.frames, masks):
        frame_number = int(getattr(frame, "out_index", frame.index)) + 1
        Image.fromarray(np.where(mask > 127, 255, 0).astype(np.uint8)).save(mask_dir / f"mask_{frame_number:06d}.png")


def _write_box_mask_sequence(video: VideoSource, candidate: ObjectCandidate, mask_dir: Path) -> None:
    height = int(getattr(video.info, "height", 0))
    width = int(getattr(video.info, "width", 0))
    if height <= 0 or width <= 0:
        raise ProviderConfigError("discovery: video dimensions are unavailable for box mask generation")
    box = candidate.box or Box(width // 4, height // 4, max(1, width // 2), max(1, height // 2))
    x0 = max(0, min(width, int(box.x)))
    y0 = max(0, min(height, int(box.y)))
    x1 = max(x0, min(width, int(box.x + box.w)))
    y1 = max(y0, min(height, int(box.y + box.h)))
    mask = np.zeros((height, width), dtype=np.uint8)
    mask[y0:y1, x0:x1] = 255
    _write_mask_sequence(video, mask_dir, [mask.copy() for _frame in video.frames])


def _box_mask(video: VideoSource, candidate: ObjectCandidate) -> np.ndarray:
    height = int(getattr(video.info, "height", 0))
    width = int(getattr(video.info, "width", 0))
    box = candidate.box or Box(width // 4, height // 4, max(1, width // 2), max(1, height // 2))
    x0 = max(0, min(width, int(box.x)))
    y0 = max(0, min(height, int(box.y)))
    x1 = max(x0, min(width, int(box.x + box.w)))
    y1 = max(y0, min(height, int(box.y + box.h)))
    mask = np.zeros((height, width), dtype=np.uint8)
    mask[y0:y1, x0:x1] = 255
    return mask


def _write_mock_candidate_previews(video: VideoSource, candidate: ObjectCandidate, mask_dir: Path) -> dict[str, str]:
    if not video.frames:
        return {}
    frame_index = max(0, min(len(video.frames) - 1, int(candidate.frame_index or 0)))
    frame = video.frames[frame_index].rgb
    frame_image = Image.fromarray(frame)
    box = candidate.box
    thumb = frame_image.copy()
    if box is not None:
        width, height = frame_image.size
        x0 = max(0, min(width, int(box.x)))
        y0 = max(0, min(height, int(box.y)))
        x1 = max(x0 + 1, min(width, int(box.x + box.w)))
        y1 = max(y0 + 1, min(height, int(box.y + box.h)))
        thumb = frame_image.crop((x0, y0, x1, y1))
    thumb.thumbnail((160, 160))
    thumbnail_path = mask_dir / "thumbnail.png"
    thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
    thumb.save(thumbnail_path)

    mask = _box_mask(video, candidate)
    overlay = frame_image.convert("RGBA")
    red = Image.new("RGBA", overlay.size, (235, 72, 72, 0))
    alpha = Image.fromarray(np.where(mask > 0, 112, 0).astype(np.uint8))
    red.putalpha(alpha)
    preview = Image.alpha_composite(overlay, red)
    preview.thumbnail((240, 240))
    mask_preview_path = mask_dir / "mask_preview.png"
    preview.save(mask_preview_path)
    if mask_dir.parts:
        rel_base = "/".join(mask_dir.parts[-3:])
    else:
        rel_base = str(mask_dir)
    return {
        "thumbnailArtifactPath": f"{rel_base}/thumbnail.png",
        "maskPreviewArtifactPath": f"{rel_base}/mask_preview.png",
    }


def _mock_object_filter_metadata(config: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "maxKeyframes": config.get("maxKeyframes", config.get("max_keyframes")),
        "maxCandidatesPerKeyframe": config.get("maxCandidatesPerKeyframe", config.get("max_candidates")),
        "maxObjects": config.get("maxObjects", config.get("max_objects")),
        "minMaskArea": config.get("minMaskArea", config.get("min_area")),
        "maxMaskAreaRatio": config.get("maxMaskAreaRatio", config.get("max_area_ratio")),
        "dedupeIou": config.get("dedupeIou", config.get("dedupe_iou")),
        "stabilityThreshold": config.get("stabilityThreshold", config.get("stability_threshold")),
        "trackSelectedOnly": config.get("trackSelectedOnly", config.get("track_selected_only", True)),
        "writeRejectedCandidates": config.get("writeRejectedCandidates", config.get("write_rejected_candidates", True)),
    }


def _relative_mask_dir(ctx: RunContext, provider_name: str, object_id: str) -> tuple[Path, str]:
    if ctx.out_dir is None:
        raise ProviderConfigError(f"{provider_name} discovery needs RunContext.out_dir to write candidate masks")
    rel = f"discovery/{provider_name}/{object_id}"
    return Path(ctx.out_dir) / rel, rel


def _mock_box(index: int, width: int, height: int) -> Box:
    w = max(4, width // 4)
    h = max(4, height // 4)
    x = min(max(0, width - w), 4 + index * max(2, width // 8))
    y = min(max(0, height - h), 4 + index * max(2, height // 10))
    return Box(x, y, w, h)


def _mock_object_box(index: int, width: int, height: int) -> Box:
    w = max(6, min(width - 1, width // 5 + (index % 3) * max(1, width // 18)))
    h = max(6, min(height - 1, height // 5 + (index % 2) * max(1, height // 16)))
    x_stride = max(2, width // 7)
    y_stride = max(2, height // 6)
    x = min(max(0, width - w), 3 + (index * x_stride) % max(1, width - w))
    y = min(max(0, height - h), 3 + (index * y_stride) % max(1, height - h))
    return Box(x, y, w, h)


def _mock_rejected_box(index: int, width: int, height: int) -> tuple[str, Box]:
    reason = ("too_small", "duplicate_mask", "whole_frame", "background_like")[index % 4]
    if reason == "too_small":
        return reason, Box(1 + index, 1 + index, max(1, width // 18), max(1, height // 18))
    if reason == "duplicate_mask":
        return reason, _mock_object_box(0, width, height)
    if reason == "whole_frame":
        return reason, Box(0, 0, max(1, width), max(1, height))
    return reason, Box(0, max(0, height - max(2, height // 3)), max(1, width), max(2, height // 3))


@dataclass
class ManualPromptDiscoveryProvider:
    prompts: Sequence[Any] | None = None
    name: str = "manual_prompt"

    def propose(self, video: VideoSource, config: Mapping[str, Any], ctx: RunContext) -> Sequence[ObjectCandidate]:
        prompts = list(self.prompts if self.prompts is not None else config.get("prompts", []) or [])
        candidates: list[ObjectCandidate] = []
        for index, prompt in enumerate(prompts):
            kind, frame_index, object_id, label, data = _prompt_payload(prompt)
            object_id = _safe_id(str(object_id or f"manual_{index}"), f"manual_{index}")
            point = None
            box = None
            mask_ref = None
            if kind in {"point", "positive_point", "negative_point"}:
                point = Point(int(data.get("x", 0)), int(data.get("y", 0)))
            elif kind == "box":
                box = Box(int(data.get("x", 0)), int(data.get("y", 0)), int(data.get("w", 1)), int(data.get("h", 1)))
            elif kind == "mask":
                mask_ref = str(data.get("mask_ref") or data.get("maskRef") or data.get("path") or "")
                if not mask_ref:
                    raise ProviderConfigError("manual_prompt mask prompts require data.mask_ref or data.path")
            else:
                raise ProviderConfigError(f"manual_prompt unsupported prompt kind: {kind}")
            candidates.append(
                ObjectCandidate(
                    id=object_id,
                    label=str(label or object_id),
                    source=self.name,
                    frame_index=frame_index,
                    box=box,
                    point=point,
                    mask_ref=mask_ref or None,
                    score=1.0,
                    z_index=10 + index * 10,
                    metadata=_candidate_metadata(self.name, "user-created prompt", {"promptKind": kind}),
                )
            )
        return candidates


@dataclass
class ExternalMasksDiscoveryProvider:
    name: str = "external_masks"

    def propose(self, video: VideoSource, config: Mapping[str, Any], ctx: RunContext) -> Sequence[ObjectCandidate]:
        records = _external_mask_records(config)
        candidates: list[ObjectCandidate] = []
        for index, record in enumerate(records):
            raw_mask_dir = record.get("mask_dir") or record.get("maskDir")
            if not raw_mask_dir:
                raise ProviderConfigError("external_masks objects require mask_dir")
            mask_dir = Path(str(raw_mask_dir))
            files = _mask_files(mask_dir)
            if not files:
                raise ProviderConfigError(f"external_masks found no mask images in {mask_dir}")
            object_id = _safe_id(str(record.get("object_id") or record.get("objectId") or record.get("id") or f"external_{index}"), f"external_{index}")
            candidates.append(
                ObjectCandidate(
                    id=object_id,
                    label=str(record.get("label") or object_id),
                    source=self.name,
                    frame_index=int(record.get("frame_index", record.get("frameIndex", 0)) or 0),
                    score=1.0,
                    z_index=int(record.get("z_index", record.get("zIndex", 10 + index * 10)) or 10),
                    metadata=_candidate_metadata(
                        self.name,
                        "imported external mask sequence",
                        {"maskDir": str(mask_dir), "maskFiles": len(files), "filters": {"validatedFiles": len(files)}},
                    ),
                )
            )
        return candidates


def _external_mask_records(config: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    if config.get("manifest"):
        manifest_path = Path(str(config["manifest"]))
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ProviderConfigError(f"external_masks manifest is invalid JSON: {manifest_path}") from exc
        if not isinstance(payload, Mapping):
            raise ProviderConfigError("external_masks manifest must be a JSON object")
        objects = payload.get("objects", [])
        if not isinstance(objects, list):
            raise ProviderConfigError("external_masks manifest objects must be an array")
        records: list[Mapping[str, Any]] = []
        for item in objects:
            if not isinstance(item, Mapping):
                raise ProviderConfigError("external_masks manifest objects[] must be objects")
            record = dict(item)
            raw_dir = record.get("mask_dir") or record.get("maskDir")
            if raw_dir:
                path = Path(str(raw_dir))
                record["mask_dir"] = str(path if path.is_absolute() else manifest_path.parent / path)
            records.append(record)
        return records
    objects = config.get("objects", [])
    if isinstance(objects, Mapping):
        return [
            {"object_id": object_id, "mask_dir": mask_dir, "label": object_id}
            for object_id, mask_dir in objects.items()
        ]
    if isinstance(objects, list):
        if not all(isinstance(item, Mapping) for item in objects):
            raise ProviderConfigError("external_masks objects must contain objects")
        return list(objects)
    mask_dirs = config.get("mask_dirs") or config.get("maskDirs")
    if isinstance(mask_dirs, Mapping):
        return [
            {"object_id": object_id, "mask_dir": mask_dir, "label": object_id}
            for object_id, mask_dir in mask_dirs.items()
        ]
    raise ProviderConfigError("external_masks requires config.objects, config.mask_dirs, or config.manifest")


@dataclass
class MotionForegroundDiscoveryProvider:
    name: str = "motion_foreground"

    def propose(self, video: VideoSource, config: Mapping[str, Any], ctx: RunContext) -> Sequence[ObjectCandidate]:
        if len(video.frames) < 2:
            return []
        threshold = _int_config(config, "threshold", 25)
        min_area = _float_config(config, "min_area", 25.0)
        max_candidates = max(1, _int_config(config, "max_candidates", 4))
        open_size = max(1, _int_config(config, "morph_open", 3))
        close_size = max(1, _int_config(config, "morph_close", 5))
        diff_masks: list[np.ndarray] = []
        previous_gray: np.ndarray | None = None
        for frame in video.frames:
            gray = cv2.cvtColor(frame.rgb, cv2.COLOR_RGB2GRAY)
            if previous_gray is None:
                diff = np.zeros_like(gray, dtype=np.uint8)
            else:
                delta = cv2.absdiff(gray, previous_gray)
                _, diff = cv2.threshold(delta, threshold, 255, cv2.THRESH_BINARY)
                if open_size > 1:
                    diff = cv2.morphologyEx(diff, cv2.MORPH_OPEN, np.ones((open_size, open_size), np.uint8))
                if close_size > 1:
                    diff = cv2.morphologyEx(diff, cv2.MORPH_CLOSE, np.ones((close_size, close_size), np.uint8))
            previous_gray = gray
            diff_masks.append(diff)

        union = np.maximum.reduce(diff_masks)
        components, labels, stats, _centroids = cv2.connectedComponentsWithStats(np.where(union > 0, 255, 0).astype(np.uint8), 8)
        sortable: list[tuple[int, int]] = []
        for component_id in range(1, components):
            area = int(stats[component_id, cv2.CC_STAT_AREA])
            if area >= min_area:
                sortable.append((area, component_id))
        sortable.sort(reverse=True)

        candidates: list[ObjectCandidate] = []
        frame_area = max(1, int(getattr(video.info, "width", 1)) * int(getattr(video.info, "height", 1)))
        for index, (area, component_id) in enumerate(sortable[:max_candidates]):
            x = int(stats[component_id, cv2.CC_STAT_LEFT])
            y = int(stats[component_id, cv2.CC_STAT_TOP])
            w = int(stats[component_id, cv2.CC_STAT_WIDTH])
            h = int(stats[component_id, cv2.CC_STAT_HEIGHT])
            object_id = f"motion_{index}"
            component_mask = labels == component_id
            masks = [np.where((mask > 0) & component_mask, 255, 0).astype(np.uint8) for mask in diff_masks]
            mask_dir, mask_dir_rel = _relative_mask_dir(ctx, self.name, object_id)
            _write_mask_sequence(video, mask_dir, masks)
            candidates.append(
                ObjectCandidate(
                    id=object_id,
                    label=f"Moving foreground {index + 1}",
                    source=self.name,
                    frame_index=0,
                    box=Box(x, y, w, h),
                    score=round(min(1.0, area / frame_area), 4),
                    z_index=10 + index * 10,
                    metadata=_candidate_metadata(
                        self.name,
                        "CPU frame-difference moving region",
                        {
                            "maskDir": mask_dir_rel,
                            "maskFiles": len(masks),
                            "filters": {
                                "threshold": threshold,
                                "minArea": min_area,
                                "maxCandidates": max_candidates,
                                "morphOpen": open_size,
                                "morphClose": close_size,
                            },
                        },
                    ),
                )
            )
            ctx.emit("candidate_discovery", "running", f"motion candidate {object_id} discovered", metadata={"objectId": object_id, "area": area})
        return candidates


@dataclass
class SamAutoMasksDiscoveryProvider:
    backend: Any | None = None
    name: str = "sam_auto_masks"

    def propose(self, video: VideoSource, config: Mapping[str, Any], ctx: RunContext) -> Sequence[ObjectCandidate]:
        if self.backend is not None:
            result = self.backend.propose(video, config, ctx)
            return list(result)
        if config.get("mock"):
            max_candidates = max(1, _int_config(config, "max_candidates", 3))
            labels = [f"Visible segment {index + 1}" for index in range(max_candidates)]
            return _mock_box_candidates(video, {**dict(config), "labels": labels}, ctx, self.name, "Mock automatic mask proposal")
        raise ProviderConfigError(
            "sam_auto_masks discovery requires a configured automatic-mask backend. "
            "Install/configure SAM2 automatic masks or set discovery mock mode for tests."
        )


@dataclass
class MockObjectDiscoveryProvider:
    name: str = "auto_object_proposals"
    provider_name: str = "mock"

    def propose(self, video: VideoSource, config: Mapping[str, Any], ctx: RunContext) -> Sequence[ObjectCandidate]:
        if not config.get("mock"):
            raise ProviderConfigError(
                "auto_object_proposals mock discovery requires discovery.config.mock=true until real proposal adapters are configured."
            )
        quality_preset = str(config.get("qualityPreset") or config.get("quality_preset") or "clean").strip() or "clean"
        if quality_preset not in MOCK_OBJECT_DISCOVERY_PRESETS:
            allowed = ", ".join(sorted(MOCK_OBJECT_DISCOVERY_PRESETS))
            raise ProviderConfigError(f"auto_object_proposals unknown qualityPreset {quality_preset!r}; expected one of: {allowed}")
        preset = MOCK_OBJECT_DISCOVERY_PRESETS[quality_preset]
        candidate_cap = max(1, _int_config_any(config, ("maxCandidatesPerKeyframe", "max_candidates", "maxCandidates"), preset["accepted"] + preset["rejected"]))
        object_cap = max(1, _int_config_any(config, ("maxObjects", "max_objects"), preset["accepted"]))
        write_rejected = _bool_config_any(config, ("writeRejectedCandidates", "write_rejected_candidates"), True)
        accepted_count = min(preset["accepted"], object_cap, candidate_cap)
        rejected_count = min(preset["rejected"], max(0, candidate_cap - accepted_count)) if write_rejected else 0
        candidates: list[ObjectCandidate] = []
        for index in range(accepted_count):
            candidates.append(self._candidate(video, config, ctx, index=index, accepted=True, quality_preset=quality_preset))
        for index in range(rejected_count):
            candidates.append(self._candidate(video, config, ctx, index=index, accepted=False, quality_preset=quality_preset))
        return candidates

    def _candidate(
        self,
        video: VideoSource,
        config: Mapping[str, Any],
        ctx: RunContext,
        *,
        index: int,
        accepted: bool,
        quality_preset: str,
    ) -> ObjectCandidate:
        width = int(getattr(video.info, "width", 64))
        height = int(getattr(video.info, "height", 64))
        if accepted:
            object_id = f"{self.name}_cand_{index + 1:03d}"
            label = f"Mock object {index + 1}"
            box = _mock_object_box(index, width, height)
            rejection_reason = None
            warnings: list[str] = []
            stability = round(max(0.5, 0.94 - index * 0.021), 4)
            motion = round(max(0.2, 0.72 - index * 0.017), 4)
        else:
            reason, box = _mock_rejected_box(index, width, height)
            object_id = f"{self.name}_rejected_{index + 1:03d}"
            label = f"Rejected {reason.replace('_', ' ')}"
            rejection_reason = reason
            warnings = [f"mock filter rejected candidate: {reason}"]
            stability = round(max(0.1, 0.62 - index * 0.035), 4)
            motion = round(max(0.05, 0.32 - index * 0.02), 4)
        confidence = round((stability * 0.65) + (motion * 0.35), 4)
        frame_count = max(1, len(video.frames))
        mask_dir, mask_dir_rel = _relative_mask_dir(ctx, self.name, object_id)
        candidate = ObjectCandidate(
            id=object_id,
            label=label,
            source=self.name,
            frame_index=0,
            box=box,
            score=confidence,
            z_index=10 + (index * 10 if accepted else 1000 + index),
            metadata=_candidate_metadata(
                self.name,
                "Deterministic no-model automatic object proposal",
                {
                    "providerName": self.provider_name,
                    "qualityPreset": quality_preset,
                    "mock": True,
                    "aiUsage": "none",
                    "filters": _mock_object_filter_metadata(config),
                    "stabilityScore": stability,
                    "motionScore": motion,
                    "confidence": confidence,
                    "frameCoverageEstimate": 1.0 if accepted else round(max(0.15, 0.35 - index * 0.03), 4),
                    "defaultSelected": accepted,
                    "reviewStatus": "pending" if accepted else "rejected",
                    "warnings": warnings,
                    "rejectionReason": rejection_reason,
                    "maskDir": mask_dir_rel,
                    "maskFiles": frame_count,
                },
            ),
        )
        _write_box_mask_sequence(video, candidate, mask_dir)
        artifact_paths = _write_mock_candidate_previews(video, candidate, mask_dir)
        metadata = {
            **candidate.metadata,
            **artifact_paths,
        }
        ctx.emit(
            "candidate_discovery",
            "running",
            f"mock object candidate {object_id} generated",
            metadata={"objectId": object_id, "qualityPreset": quality_preset, "rejectionReason": rejection_reason},
        )
        return ObjectCandidate(
            id=candidate.id,
            label=candidate.label,
            source=candidate.source,
            frame_index=candidate.frame_index,
            box=candidate.box,
            score=candidate.score,
            z_index=candidate.z_index,
            metadata=metadata,
        )


@dataclass
class TextDetectorDiscoveryProvider:
    detector: Any | None = None
    name: str = "text_detector"

    def propose(self, video: VideoSource, config: Mapping[str, Any], ctx: RunContext) -> Sequence[ObjectCandidate]:
        if self.detector is not None:
            return [_candidate_from_detection(item, index, self.name) for index, item in enumerate(self.detector.detect(video, config))]
        if config.get("mock"):
            text = str(config.get("text") or config.get("prompt") or "object")
            return _mock_box_candidates(video, {**dict(config), "labels": _split_labels(text)}, ctx, self.name, "Mock text detector box")
        raise ProviderConfigError(
            "text_detector discovery requires a configured detector or mock mode; text prompts are not routed directly to SAM2."
        )


@dataclass
class ClassDetectorDiscoveryProvider:
    detector: Any | None = None
    name: str = "class_detector"

    def propose(self, video: VideoSource, config: Mapping[str, Any], ctx: RunContext) -> Sequence[ObjectCandidate]:
        labels, preset = _class_detector_labels(config)
        confidence_threshold = _ratio_config(config, "confidence_threshold", 0.35)
        config_with_classes = {**dict(config), "classes": labels, "class_preset": preset}
        if self.detector is not None:
            return [_candidate_from_detection(item, index, self.name) for index, item in enumerate(self.detector.detect(video, config_with_classes))]
        if config.get("mock"):
            return _mock_box_candidates(
                video,
                {
                    **config_with_classes,
                    "labels": labels,
                    "filters": {
                        "classPreset": preset,
                        "requestedClasses": labels,
                        "confidenceThreshold": confidence_threshold,
                    },
                    "metadata": {
                        "classPreset": preset,
                        "requestedClasses": labels,
                    },
                },
                ctx,
                self.name,
                "Mock class detector box",
            )
        raise ProviderConfigError("class_detector discovery requires a configured detector or mock mode.")


def _split_labels(text: str) -> list[str]:
    labels = [part.strip() for part in re.split(r"[,.]", text) if part.strip()]
    return labels or ["object"]


def _label_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return _split_labels(value)
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [str(item).strip() for item in value if str(item).strip()]
    raise ProviderConfigError("class_detector classes must be a string or array")


def _class_detector_labels(config: Mapping[str, Any]) -> tuple[list[str], str]:
    preset = str(config.get("class_preset") or config.get("preset") or "custom").strip() or "custom"
    if preset not in CLASS_DETECTOR_PRESETS:
        allowed = ", ".join(sorted(CLASS_DETECTOR_PRESETS))
        raise ProviderConfigError(f"class_detector unknown class preset {preset!r}; expected one of: {allowed}")
    labels = [*CLASS_DETECTOR_PRESETS[preset], *_label_list(config.get("classes") or config.get("labels"))]
    unique = list(dict.fromkeys(label for label in labels if label))
    return (unique or ["object"], preset)


def _candidate_from_detection(item: Mapping[str, Any], index: int, source: str) -> ObjectCandidate:
    raw_box = item.get("box") or item.get("bbox")
    box = None
    if isinstance(raw_box, Mapping):
        box = Box(int(raw_box.get("x", 0)), int(raw_box.get("y", 0)), int(raw_box.get("w", raw_box.get("width", 1))), int(raw_box.get("h", raw_box.get("height", 1))))
    elif isinstance(raw_box, (list, tuple)) and len(raw_box) == 4:
        box = Box(int(raw_box[0]), int(raw_box[1]), int(raw_box[2]), int(raw_box[3]))
    object_id = _safe_id(str(item.get("object_id") or item.get("id") or f"{source}_{index}"), f"{source}_{index}")
    return ObjectCandidate(
        id=object_id,
        label=str(item.get("label") or object_id),
        source=source,
        frame_index=int(item.get("frame_index", item.get("frameIndex", 0)) or 0),
        box=box,
        mask_ref=str(item.get("mask_ref") or item.get("maskRef")) if item.get("mask_ref") or item.get("maskRef") else None,
        score=float(item.get("score", 1.0)),
        z_index=int(item.get("z_index", item.get("zIndex", 10 + index * 10)) or 10),
        metadata=_candidate_metadata(source, "detector output", item.get("metadata") if isinstance(item.get("metadata"), Mapping) else None),
    )


def _mock_box_candidates(
    video: VideoSource,
    config: Mapping[str, Any],
    ctx: RunContext,
    source: str,
    description: str,
) -> Sequence[ObjectCandidate]:
    labels = config.get("labels") or ["object"]
    if isinstance(labels, str):
        labels = [labels]
    max_candidates = max(1, _int_config(config, "max_candidates", len(labels)))
    width = int(getattr(video.info, "width", 64))
    height = int(getattr(video.info, "height", 64))
    candidates: list[ObjectCandidate] = []
    for index, label_value in enumerate(list(labels)[:max_candidates]):
        label = str(label_value)
        object_id = _safe_id(f"{source}_{label}", f"{source}_{index}")
        box = _mock_box(index, width, height)
        extra_filters = config.get("filters") if isinstance(config.get("filters"), Mapping) else {}
        extra_metadata = config.get("metadata") if isinstance(config.get("metadata"), Mapping) else {}
        metadata = _candidate_metadata(
            source,
            description,
            {**dict(extra_metadata), "filters": {"maxCandidates": max_candidates, **dict(extra_filters)}, "mock": True},
        )
        candidate = ObjectCandidate(
            id=object_id,
            label=label,
            source=source,
            frame_index=0,
            box=box,
            score=1.0,
            z_index=10 + index * 10,
            metadata=metadata,
        )
        if config.get("write_box_masks", True):
            mask_dir, mask_dir_rel = _relative_mask_dir(ctx, source, object_id)
            _write_box_mask_sequence(video, candidate, mask_dir)
            candidate = ObjectCandidate(
                id=candidate.id,
                label=candidate.label,
                source=candidate.source,
                frame_index=candidate.frame_index,
                box=candidate.box,
                score=candidate.score,
                z_index=candidate.z_index,
                metadata={**candidate.metadata, "maskDir": mask_dir_rel, "maskFiles": len(video.frames)},
            )
        candidates.append(candidate)
    return candidates


def object_specs_from_candidates(
    candidates: Sequence[ObjectCandidate],
    *,
    base_dir: str | Path | None = None,
    mask_provider_factory: Callable[[ObjectCandidate], Any] | None = None,
) -> list[Any]:
    from ..pipeline import ObjectExtractionSpec

    specs: list[Any] = []
    for index, candidate in enumerate(candidates):
        review_status = str(candidate.metadata.get("reviewStatus") or "").strip().lower()
        if candidate.metadata.get("rejectionReason") or review_status in {"rejected", "ignored", "excluded"}:
            continue
        mask_dir = candidate.metadata.get("maskDir") or candidate.metadata.get("mask_dir")
        if mask_dir:
            path = Path(str(mask_dir))
            if not path.is_absolute() and base_dir is not None:
                path = Path(base_dir) / path
            provider = ExternalMaskProvider(path)
        elif mask_provider_factory is not None:
            provider = mask_provider_factory(candidate)
        else:
            raise ProviderConfigError(
                f"Discovery candidate {candidate.id!r} has no maskDir and no mask_provider_factory was supplied."
            )
        specs.append(
            ObjectExtractionSpec(
                object_id=candidate.id,
                label=candidate.label or candidate.id,
                mask_provider=provider,
                z_index=candidate.z_index if candidate.z_index is not None else 10 + index * 10,
            )
        )
    return specs
