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
from .mask_cache import normalize_binary_mask
from .sam2 import LocalSAM2AutomaticMaskProposalBackend, LocalSAM2HFAutomaticMaskProposalBackend
from .sam3 import LocalSAM3DiscoveryBackend


DISCOVERY_MODES = {
    "manual_prompt",
    "auto_object_proposals",
    "sam2_hf_auto_masks",
    "sam_auto_masks",
    "sam3_concept",
    "sam3_exemplar",
    "sam3_auto_masks",
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
        "description": "API-first automatic object proposals with low-cost default presets, review gates, mock mode, and optional SAM2 local proposals.",
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
        "description": "Automatic keyframe mask proposals with area, stability, overlap filters, and optional SAM2 local execution.",
        "whenToUse": "Use for proposing visible segments after SAM2 automatic masks are configured, or in mock mode for smoke tests.",
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
    "sam2_hf_auto_masks": {
        "mode": "sam2_hf_auto_masks",
        "title": "SAM2 HF automatic masks",
        "description": "Hugging Face Transformers SAM2 automatic keyframe masks, separate from official SAM2 checkpoint/config prompt tracking.",
        "whenToUse": "Use as a fallback for finding everything in the scene when SAM3 Scene Sweep is blocked.",
        "inputs": ["quality preset", "keyframes", "filter controls", "optional mock"],
        "configSchema": {
            "sam2HfModel": "Hugging Face repo id or local HF model directory, default facebook/sam2.1-hiera-large",
            "providerPreference": "sam2-hf-auto-masks",
            "mock": "boolean",
            "maxCandidatesPerKeyframe": "integer",
            "maxObjects": "integer",
        },
        "noModelSafe": False,
        "mockAvailable": True,
    },
    "sam3_concept": {
        "mode": "sam3_concept",
        "title": "SAM3 concept",
        "description": "Optional SAM3-style concept discovery from text phrases, with mock mode for local review flows.",
        "whenToUse": "Use when users want to find all instances of a described concept and SAM3 is configured, or in mock mode for smoke tests.",
        "inputs": ["concept", "text prompt", "candidate caps", "optional mock"],
        "configSchema": {
            "concept": "text phrase such as 'red ball'",
            "mock": "boolean",
            "max_candidates": "integer",
        },
        "noModelSafe": False,
        "mockAvailable": True,
    },
    "sam3_exemplar": {
        "mode": "sam3_exemplar",
        "title": "SAM3 exemplar",
        "description": "Optional SAM3-style exemplar discovery from a crop or reference, with mock mode for local review flows.",
        "whenToUse": "Use when users want to find objects like a selected exemplar and SAM3 is configured, or in mock mode for smoke tests.",
        "inputs": ["exemplar references", "candidate caps", "optional mock"],
        "configSchema": {
            "exemplars": "array of crop, artifact, or reference ids",
            "mock": "boolean",
            "max_candidates": "integer",
        },
        "noModelSafe": False,
        "mockAvailable": True,
    },
    "sam3_auto_masks": {
        "mode": "sam3_auto_masks",
        "title": "SAM3 auto masks",
        "description": "Optional SAM3-style high-recall automatic proposals, with mock mode for local review flows.",
        "whenToUse": "Use for semantic/high-recall proposal review when SAM3 is configured, or in mock mode for tests.",
        "inputs": ["quality preset", "candidate caps", "optional mock"],
        "configSchema": {
            "qualityPreset": "clean, balanced, maximum_recall, or trace_everything",
            "mock": "boolean",
            "maxCandidatesPerKeyframe": "integer",
            "maxObjects": "integer",
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


def _value_config_any(config: Mapping[str, Any], names: Sequence[str], default: Any = None) -> Any:
    for name in names:
        if name in config and config[name] is not None:
            return config[name]
    return default


def _float_config_any(config: Mapping[str, Any], names: Sequence[str], default: float) -> float:
    value = _value_config_any(config, names, default)
    if isinstance(value, bool):
        raise ProviderConfigError(f"discovery.{names[0]}: expected number")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ProviderConfigError(f"discovery.{names[0]}: expected number") from exc


def _ratio_config_any(config: Mapping[str, Any], names: Sequence[str], default: float) -> float:
    value = _float_config_any(config, names, default)
    if value < 0.0 or value > 1.0:
        raise ProviderConfigError(f"discovery.{names[0]}: expected number between 0 and 1")
    return value


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


def _write_candidate_previews(
    video: VideoSource,
    candidate: ObjectCandidate,
    mask_dir: Path,
    *,
    mask: np.ndarray | None = None,
) -> dict[str, str]:
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

    if mask is None:
        mask = _box_mask(video, candidate)
    else:
        mask = normalize_binary_mask(mask)
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


def _write_mock_candidate_previews(video: VideoSource, candidate: ObjectCandidate, mask_dir: Path) -> dict[str, str]:
    return _write_candidate_previews(video, candidate, mask_dir)


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
            record_metadata = record.get("metadata") if isinstance(record.get("metadata"), Mapping) else {}
            source = str(record.get("source") or record_metadata.get("source") or self.name)
            score = record.get("score", record_metadata.get("confidence", record_metadata.get("score", 1.0)))
            try:
                score_value = float(score)
            except (TypeError, ValueError):
                score_value = 1.0
            candidates.append(
                ObjectCandidate(
                    id=object_id,
                    label=str(record.get("label") or object_id),
                    source=source,
                    frame_index=int(record.get("frame_index", record.get("frameIndex", 0)) or 0),
                    score=score_value,
                    z_index=int(record.get("z_index", record.get("zIndex", 10 + index * 10)) or 10),
                    metadata=_candidate_metadata(
                        self.name,
                        "imported external mask sequence",
                        {
                            **dict(record_metadata),
                            "source": source,
                            "maskDir": str(mask_dir),
                            "maskFiles": len(files),
                            "filters": {"validatedFiles": len(files), **dict(record_metadata.get("filters") if isinstance(record_metadata.get("filters"), Mapping) else {})},
                        },
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


def _proposal_keyframe_indexes(video: VideoSource, config: Mapping[str, Any]) -> list[int]:
    frame_count = len(video.frames)
    if frame_count <= 0:
        return []
    max_keyframes = max(1, _int_config_any(config, ("maxKeyframes", "max_keyframes", "max_keyframes_per_video"), 3))
    raw_keyframes = config.get("keyframes")
    if isinstance(raw_keyframes, Sequence) and not isinstance(raw_keyframes, (str, bytes, bytearray)):
        indexes: list[int] = []
        for raw_index in raw_keyframes:
            try:
                index = int(raw_index)
            except (TypeError, ValueError) as exc:
                raise ProviderConfigError("discovery.keyframes: expected integer frame indexes") from exc
            if 0 <= index < frame_count and index not in indexes:
                indexes.append(index)
        return indexes[:max_keyframes] or [0]

    frame_interval = _value_config_any(config, ("frameInterval", "frame_interval"), None)
    if frame_interval is not None:
        interval = max(1, _int_config_any(config, ("frameInterval", "frame_interval"), 1))
        return list(range(0, frame_count, interval))[:max_keyframes] or [0]

    if max_keyframes >= frame_count:
        return list(range(frame_count))
    if max_keyframes == 1:
        return [0]
    step = (frame_count - 1) / float(max_keyframes - 1)
    indexes = [round(index * step) for index in range(max_keyframes)]
    return list(dict.fromkeys(max(0, min(frame_count - 1, int(index))) for index in indexes))


def _box_from_mask(mask: np.ndarray) -> Box:
    normalized = normalize_binary_mask(mask)
    ys, xs = np.where(normalized > 0)
    if not len(xs) or not len(ys):
        height, width = normalized.shape[:2]
        return Box(0, 0, max(1, width), max(1, height))
    x0 = int(xs.min())
    y0 = int(ys.min())
    x1 = int(xs.max()) + 1
    y1 = int(ys.max()) + 1
    return Box(x0, y0, max(1, x1 - x0), max(1, y1 - y0))


def _box_iou(left: Box, right: Box) -> float:
    left_x1 = left.x + left.w
    left_y1 = left.y + left.h
    right_x1 = right.x + right.w
    right_y1 = right.y + right.h
    inter_w = max(0, min(left_x1, right_x1) - max(left.x, right.x))
    inter_h = max(0, min(left_y1, right_y1) - max(left.y, right.y))
    intersection = inter_w * inter_h
    if intersection <= 0:
        return 0.0
    union = max(1, left.w * left.h + right.w * right.h - intersection)
    return intersection / union


def _record_value(record: Mapping[str, Any], keys: Sequence[str]) -> Any:
    for key in keys:
        if key in record and record[key] is not None:
            return record[key]
    return None


def _proposal_mask(record: Mapping[str, Any], *, width: int, height: int) -> np.ndarray:
    mask_value = None
    for key in ("segmentation", "mask", "binary_mask"):
        if key in record and record[key] is not None:
            mask_value = record[key]
            break
    if mask_value is None:
        raw_box = _record_value(record, ("bbox", "box"))
        box = _proposal_box(raw_box, width=width, height=height)
        mask = np.zeros((height, width), dtype=np.uint8)
        mask[box.y : box.y + box.h, box.x : box.x + box.w] = 255
        return mask
    mask = normalize_binary_mask(np.asarray(mask_value))
    if mask.ndim > 2:
        mask = normalize_binary_mask(np.squeeze(mask))
    if mask.shape[:2] != (height, width):
        raise ProviderConfigError(
            f"SAM2 automatic proposal mask shape {mask.shape[:2]} does not match video frame {(height, width)}"
        )
    return mask


def _proposal_box(raw_box: Any, *, width: int, height: int) -> Box:
    if isinstance(raw_box, Mapping):
        x = int(raw_box.get("x", 0))
        y = int(raw_box.get("y", 0))
        w = int(raw_box.get("w", raw_box.get("width", 1)))
        h = int(raw_box.get("h", raw_box.get("height", 1)))
    elif isinstance(raw_box, (list, tuple)) and len(raw_box) >= 4:
        x, y, w, h = (int(raw_box[0]), int(raw_box[1]), int(raw_box[2]), int(raw_box[3]))
    else:
        return Box(0, 0, max(1, width), max(1, height))
    x = max(0, min(width - 1, x))
    y = max(0, min(height - 1, y))
    w = max(1, min(width - x, w))
    h = max(1, min(height - y, h))
    return Box(x, y, w, h)


def _sam2_proposal_filters(config: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "keyframePolicy": config.get("keyframePolicy", config.get("keyframe_policy")),
        "maxKeyframes": config.get("maxKeyframes", config.get("max_keyframes")),
        "frameInterval": config.get("frameInterval", config.get("frame_interval")),
        "maxCandidatesPerKeyframe": config.get("maxCandidatesPerKeyframe", config.get("max_candidates")),
        "maxObjects": config.get("maxObjects", config.get("max_objects")),
        "minMaskArea": config.get("minMaskArea", config.get("min_area")),
        "maxMaskAreaRatio": config.get("maxMaskAreaRatio", config.get("max_area_ratio")),
        "dedupeIou": config.get("dedupeIou", config.get("dedupe_iou", config.get("overlap_threshold"))),
        "stabilityThreshold": config.get("stabilityThreshold", config.get("stability_threshold")),
        "rejectWholeFrame": config.get("rejectWholeFrame", config.get("reject_whole_frame")),
        "rejectBackgroundLike": config.get("rejectBackgroundLike", config.get("reject_background_like", config.get("reject_background"))),
        "trackSelectedOnly": config.get("trackSelectedOnly", config.get("track_selected_only", True)),
        "writeRejectedCandidates": config.get("writeRejectedCandidates", config.get("write_rejected_candidates", True)),
    }


@dataclass
class SamAutoMasksDiscoveryProvider:
    backend: Any | None = None
    name: str = "sam_auto_masks"

    def propose(self, video: VideoSource, config: Mapping[str, Any], ctx: RunContext) -> Sequence[ObjectCandidate]:
        if self.backend is not None:
            if hasattr(self.backend, "propose"):
                result = self.backend.propose(video, config, ctx)
                return list(result)
            return SAM2AutomaticProposalDiscoveryProvider(backend=self.backend, name=self.name).propose(video, config, ctx)
        if config.get("mock"):
            max_candidates = max(1, _int_config(config, "max_candidates", 3))
            labels = [f"Visible segment {index + 1}" for index in range(max_candidates)]
            return _mock_box_candidates(video, {**dict(config), "labels": labels}, ctx, self.name, "Mock automatic mask proposal")
        return SAM2AutomaticProposalDiscoveryProvider(name=self.name).propose(video, config, ctx)


@dataclass
class SAM2HFAutomaticMasksDiscoveryProvider:
    backend: Any | None = None
    backend_factory: Callable[[Mapping[str, Any]], Any] | None = None
    name: str = "sam2_hf_auto_masks"
    provider_name: str = "sam2-hf-auto-masks"

    def propose(self, video: VideoSource, config: Mapping[str, Any], ctx: RunContext) -> Sequence[ObjectCandidate]:
        if config.get("mock"):
            max_candidates = max(1, _int_config_any(config, ("maxCandidatesPerKeyframe", "max_candidates"), 3))
            labels = [f"SAM2 HF proposal {index + 1}" for index in range(max_candidates)]
            return _mock_box_candidates(
                video,
                {**dict(config), "labels": labels, "metadata": {"providerName": self.provider_name, "mock": True}},
                ctx,
                self.name,
                "Mock SAM2 HF automatic-mask proposal",
            )
        backend = self.backend
        if backend is None:
            backend = self.backend_factory(config) if self.backend_factory is not None else LocalSAM2HFAutomaticMaskProposalBackend.from_config(config)
        return SAM2AutomaticProposalDiscoveryProvider(
            backend=backend,
            name=self.name,
            provider_name=getattr(backend, "provider_name", self.provider_name),
        ).propose(video, {**dict(config), "providerPreference": "sam2-hf-auto-masks"}, ctx)


@dataclass
class SAM2AutomaticProposalDiscoveryProvider:
    backend: Any | None = None
    backend_factory: Callable[[Mapping[str, Any]], Any] | None = None
    name: str = "auto_object_proposals"
    provider_name: str = "sam2-local"

    def propose(self, video: VideoSource, config: Mapping[str, Any], ctx: RunContext) -> Sequence[ObjectCandidate]:
        provider_preference = str(config.get("providerPreference") or config.get("provider_preference") or "sam2-local")
        if provider_preference not in {"auto", "sam2-local", "sam2-hf-auto-masks", "sam_auto_masks"}:
            raise ProviderConfigError(
                f"{self.name} SAM2 automatic proposals require providerPreference 'auto', 'sam2-local', or 'sam2-hf-auto-masks', got {provider_preference!r}"
            )
        backend = self._backend(config)
        if hasattr(backend, "propose") and backend is not self:
            result = backend.propose(video, config, ctx)
            return list(result)

        width = int(getattr(video.info, "width", 0))
        height = int(getattr(video.info, "height", 0))
        if width <= 0 or height <= 0:
            raise ProviderConfigError(f"{self.name} discovery needs video dimensions for SAM2 proposals")
        keyframes = _proposal_keyframe_indexes(video, config)
        max_per_keyframe = max(1, _int_config_any(config, ("maxCandidatesPerKeyframe", "max_candidates"), 32))
        max_objects = max(1, _int_config_any(config, ("maxObjects", "max_objects"), 12))
        min_area = max(1, _int_config_any(config, ("minMaskArea", "min_area"), 96))
        max_area_ratio = _ratio_config_any(config, ("maxMaskAreaRatio", "max_area_ratio"), 0.45)
        stability_threshold = _ratio_config_any(config, ("stabilityThreshold", "stability_threshold"), 0.86)
        dedupe_iou = _ratio_config_any(config, ("dedupeIou", "dedupe_iou", "overlap_threshold"), 0.78)
        reject_whole_frame = _bool_config_any(config, ("rejectWholeFrame", "reject_whole_frame"), True)
        reject_background_like = _bool_config_any(config, ("rejectBackgroundLike", "reject_background_like", "reject_background"), True)
        write_rejected = _bool_config_any(config, ("writeRejectedCandidates", "write_rejected_candidates"), True)
        quality_preset = str(config.get("qualityPreset") or config.get("quality_preset") or "custom")

        accepted_boxes: list[Box] = []
        accepted_count = 0
        rejected_count = 0
        candidates: list[ObjectCandidate] = []
        frame_area = max(1, width * height)
        for frame_index in keyframes:
            frame = video.frames[frame_index]
            records = list(backend.propose_masks(frame.rgb, frame_index=frame_index, config=config))
            sortable = sorted(records, key=lambda record: _proposal_score(record), reverse=True)[:max_per_keyframe]
            for record_index, record in enumerate(sortable):
                mask = _proposal_mask(record, width=width, height=height)
                box = _proposal_box(_record_value(record, ("bbox", "box")), width=width, height=height)
                if box.w == width and box.h == height and "bbox" not in record and "box" not in record:
                    box = _box_from_mask(mask)
                area = int(np.count_nonzero(mask))
                area_ratio = area / frame_area
                explicit_stability = _explicit_proposal_stability(record)
                stability = explicit_stability if explicit_stability is not None else _proposal_score(record)
                rejection_reason: str | None = None
                warnings: list[str] = []
                if area < min_area:
                    rejection_reason = "too_small"
                elif area_ratio > max_area_ratio:
                    rejection_reason = "whole_frame" if reject_whole_frame else "too_large"
                elif explicit_stability is not None and stability < stability_threshold:
                    rejection_reason = "unstable_mask"
                elif any(_box_iou(box, previous) >= dedupe_iou for previous in accepted_boxes):
                    rejection_reason = "duplicate_mask"
                elif reject_background_like and _background_like(box, width=width, height=height, area_ratio=area_ratio):
                    rejection_reason = "background_like"
                elif accepted_count >= max_objects:
                    rejection_reason = "max_objects"

                accepted = rejection_reason is None
                if accepted:
                    accepted_count += 1
                    accepted_boxes.append(box)
                    index_for_id = accepted_count
                else:
                    rejected_count += 1
                    index_for_id = rejected_count
                    warnings.append(f"SAM2 automatic proposal rejected: {rejection_reason}")
                    if not write_rejected:
                        continue

                object_id = f"{self.name}_{'cand' if accepted else 'rejected'}_{index_for_id:03d}"
                if accepted:
                    mask_sequence, tracking_warning = self._mask_sequence_for_candidate(
                        backend,
                        video,
                        frame_index=frame_index,
                        object_id=object_id,
                        box=box,
                        mask=mask,
                        config=config,
                    )
                else:
                    mask_sequence = [mask.copy() for _frame in video.frames]
                    tracking_warning = None
                if tracking_warning:
                    warnings.append(tracking_warning)
                mask_dir, mask_dir_rel = _relative_mask_dir(ctx, self.name, object_id)
                _write_mask_sequence(video, mask_dir, mask_sequence)
                score = _proposal_score(record)
                confidence = round((score * 0.65) + (stability * 0.35), 4)
                frame_coverage = _mask_sequence_coverage(mask_sequence)
                candidate = ObjectCandidate(
                    id=object_id,
                    label=f"SAM2 proposal {index_for_id}" if accepted else f"Rejected SAM2 proposal {index_for_id}",
                    source=self.name,
                    frame_index=frame_index,
                    box=box,
                    score=confidence,
                    z_index=10 + (accepted_count * 10 if accepted else 1000 + rejected_count),
                    metadata=_candidate_metadata(
                        self.name,
                        "SAM2 automatic keyframe mask proposal",
                        {
                            "providerName": self.provider_name,
                            "qualityPreset": quality_preset,
                            "mock": False,
                            "aiUsage": "local_optional_sam2",
                            "keyframeIndex": frame_index,
                            "proposalIndex": record_index,
                            "filters": _sam2_proposal_filters({**dict(config), "keyframes": keyframes}),
                            "areaRatio": round(area_ratio, 6),
                            "stabilityScore": round(stability, 4),
                            "motionScore": None,
                            "confidence": confidence,
                            "frameCoverageEstimate": frame_coverage,
                            "defaultSelected": accepted,
                            "reviewStatus": "pending" if accepted else "rejected",
                            "warnings": warnings,
                            "rejectionReason": rejection_reason,
                            "maskDir": mask_dir_rel,
                            "maskFiles": len(mask_sequence),
                            "trackingProvider": self.provider_name if tracking_warning is None else "keyframe_seed_sequence",
                        },
                    ),
                )
                artifact_paths = _write_candidate_previews(video, candidate, mask_dir, mask=mask)
                candidates.append(
                    ObjectCandidate(
                        id=candidate.id,
                        label=candidate.label,
                        source=candidate.source,
                        frame_index=candidate.frame_index,
                        box=candidate.box,
                        score=candidate.score,
                        z_index=candidate.z_index,
                        metadata={**candidate.metadata, **artifact_paths},
                    )
                )
                ctx.emit(
                    "candidate_discovery",
                    "running",
                    f"SAM2 object candidate {object_id} generated",
                    metadata={"objectId": object_id, "keyframeIndex": frame_index, "rejectionReason": rejection_reason},
                )
        if not candidates:
            raise ProviderConfigError("SAM2 automatic proposals produced no candidates after filtering.")
        return candidates

    def _backend(self, config: Mapping[str, Any]) -> Any:
        if self.backend is not None:
            return self.backend
        if self.backend_factory is not None:
            self.backend = self.backend_factory(config)
        elif str(config.get("providerPreference") or config.get("provider_preference") or "") == "sam2-hf-auto-masks":
            self.backend = LocalSAM2HFAutomaticMaskProposalBackend.from_config(config)
        else:
            self.backend = LocalSAM2AutomaticMaskProposalBackend.from_config(config)
        return self.backend

    def _mask_sequence_for_candidate(
        self,
        backend: Any,
        video: VideoSource,
        *,
        frame_index: int,
        object_id: str,
        box: Box,
        mask: np.ndarray,
        config: Mapping[str, Any],
    ) -> tuple[list[np.ndarray], str | None]:
        box_tuple = (box.x, box.y, box.w, box.h)
        if hasattr(backend, "track_candidate"):
            masks = list(
                backend.track_candidate(
                    video,
                    frame_index=frame_index,
                    object_id=object_id,
                    box=box_tuple,
                    mask=mask,
                    config=config,
                )
            )
            if len(masks) != len(video.frames):
                raise ProviderConfigError("SAM2 selected-candidate propagation returned the wrong number of masks.")
            return [normalize_binary_mask(candidate_mask) for candidate_mask in masks], None
        return [mask.copy() for _frame in video.frames], (
            "SAM2 propagation backend was not available; selected tracking will use the keyframe proposal mask sequence."
        )


def _proposal_score(record: Mapping[str, Any]) -> float:
    for key in ("score", "confidence", "predicted_iou", "iou"):
        if key in record and record[key] is not None:
            try:
                return max(0.0, min(1.0, float(record[key])))
            except (TypeError, ValueError):
                continue
    return 0.75


def _explicit_proposal_stability(record: Mapping[str, Any]) -> float | None:
    for key in ("stability_score", "stabilityScore", "stability"):
        if key in record and record[key] is not None:
            try:
                return max(0.0, min(1.0, float(record[key])))
            except (TypeError, ValueError):
                continue
    return None


def _proposal_stability(record: Mapping[str, Any]) -> float:
    explicit = _explicit_proposal_stability(record)
    if explicit is not None:
        return explicit
    return _proposal_score(record)


def _background_like(box: Box, *, width: int, height: int, area_ratio: float) -> bool:
    touches = sum(
        (
            box.x <= 1,
            box.y <= 1,
            box.x + box.w >= width - 1,
            box.y + box.h >= height - 1,
        )
    )
    return area_ratio >= 0.35 and touches >= 2


def _mask_sequence_coverage(masks: Sequence[np.ndarray]) -> float:
    if not masks:
        return 0.0
    visible = sum(1 for mask in masks if np.count_nonzero(mask) > 0)
    return round(visible / len(masks), 4)


def _translate_mask(mask: np.ndarray, *, dx: int, dy: int) -> np.ndarray:
    source = normalize_binary_mask(mask)
    height, width = source.shape[:2]
    output = np.zeros((height, width), dtype=np.uint8)
    src_x0 = max(0, -dx)
    src_y0 = max(0, -dy)
    src_x1 = min(width, width - dx) if dx >= 0 else width
    src_y1 = min(height, height - dy) if dy >= 0 else height
    dst_x0 = max(0, dx)
    dst_y0 = max(0, dy)
    dst_x1 = dst_x0 + max(0, src_x1 - src_x0)
    dst_y1 = dst_y0 + max(0, src_y1 - src_y0)
    if src_x1 <= src_x0 or src_y1 <= src_y0 or dst_x1 <= dst_x0 or dst_y1 <= dst_y0:
        return output
    output[dst_y0:dst_y1, dst_x0:dst_x1] = source[src_y0:src_y1, src_x0:src_x1]
    return output


def _template_match_mask_sequence(
    video: VideoSource,
    *,
    frame_index: int,
    mask: np.ndarray,
    box: Box,
    config: Mapping[str, Any],
) -> list[np.ndarray] | None:
    frames = list(video.frames)
    if not frames:
        return None
    seed_index = min(max(0, int(frame_index)), len(frames) - 1)
    seed_mask = normalize_binary_mask(mask)
    if np.count_nonzero(seed_mask) <= 0:
        return None
    seed_box = _box_from_mask(seed_mask)
    if seed_box.w <= 1 or seed_box.h <= 1:
        seed_box = box
    height, width = seed_mask.shape[:2]
    padding = _int_config_any(
        config,
        ("templateTrackPadding", "template_track_padding"),
        max(4, int(max(seed_box.w, seed_box.h) * 0.75)),
    )
    x0 = max(0, seed_box.x - padding)
    y0 = max(0, seed_box.y - padding)
    x1 = min(width, seed_box.x + seed_box.w + padding)
    y1 = min(height, seed_box.y + seed_box.h + padding)
    if x1 - x0 < 3 or y1 - y0 < 3:
        return None
    seed_rgb = np.asarray(frames[seed_index].rgb, dtype=np.uint8)
    template = cv2.cvtColor(seed_rgb[y0:y1, x0:x1], cv2.COLOR_RGB2GRAY)
    if template.size <= 0 or float(np.std(template)) < 1.0:
        return None
    minimum_score = _ratio_config_any(config, ("templateTrackMinScore", "template_track_min_score"), 0.12)
    masks: list[np.ndarray] = []
    scores: list[float] = []
    for index, frame in enumerate(frames):
        if index == seed_index:
            masks.append(seed_mask.copy())
            continue
        rgb = np.asarray(frame.rgb, dtype=np.uint8)
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        if gray.shape[0] < template.shape[0] or gray.shape[1] < template.shape[1]:
            return None
        result = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
        if result.size <= 0:
            return None
        _min_value, max_value, _min_location, max_location = cv2.minMaxLoc(result)
        if not np.isfinite(max_value):
            return None
        scores.append(float(max_value))
        masks.append(_translate_mask(seed_mask, dx=int(max_location[0] - x0), dy=int(max_location[1] - y0)))
    if scores and float(np.mean(scores)) < minimum_score:
        return None
    return masks


def _redact_local_paths_from_error(error: Exception) -> str:
    text = str(error) or type(error).__name__
    text = re.sub(r"(?<![\w:])(?:/[^\s'\"<>]+)+", "[LOCAL_PATH_REDACTED]", text)
    return re.sub(r"[A-Za-z]:\\[^\s'\"<>]+", "[LOCAL_PATH_REDACTED]", text)


def _sam3_template_fallback_result(
    video: VideoSource,
    *,
    frame_index: int,
    mask: np.ndarray,
    box: Box,
    config: Mapping[str, Any],
    reason: str,
) -> tuple[list[np.ndarray], str, str]:
    tracked = _template_match_mask_sequence(video, frame_index=frame_index, mask=mask, box=box, config=config)
    if tracked is not None:
        return tracked, f"{reason}; using local template-match propagation for review.", "template_match_fallback"
    return [mask.copy() for _frame in video.frames], f"{reason}; using the static keyframe mask sequence for review.", "keyframe_seed_sequence"


def _sam3_backend(current: Any | None, factory: Callable[[Mapping[str, Any]], Any] | None, config: Mapping[str, Any]) -> Any:
    if current is not None:
        return current
    if factory is not None:
        return factory(config)
    provider_preference = str(
        config.get("providerPreference")
        or config.get("provider_preference")
        or config.get("sam3Provider")
        or config.get("sam3_provider")
        or ""
    )
    if provider_preference == "sam3-hosted" or _bool_config_any(config, ("hosted", "useHosted", "use_hosted"), False):
        from .hosted_sam import hosted_sam3_backend_from_config

        return hosted_sam3_backend_from_config(config)
    return LocalSAM3DiscoveryBackend.from_config(config)


def _sam3_record_mask_sequence(
    record: Mapping[str, Any],
    video: VideoSource,
    *,
    width: int,
    height: int,
) -> list[np.ndarray] | None:
    raw = record.get("mask_sequence") or record.get("maskSequence") or record.get("masks")
    if raw is None:
        return None
    if isinstance(raw, np.ndarray):
        items = [raw[index] for index in range(raw.shape[0])] if raw.ndim >= 3 else [raw]
    elif isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray)):
        items = list(raw)
    else:
        return None
    if len(items) != len(video.frames):
        return None
    masks = [normalize_binary_mask(np.asarray(item)) for item in items]
    for mask in masks:
        if mask.shape[:2] != (height, width):
            raise ProviderConfigError(f"SAM3 mask sequence shape {mask.shape[:2]} does not match video frame {(height, width)}")
    return masks


def _sam3_track_or_seed_sequence(
    backend: Any,
    video: VideoSource,
    *,
    source: str,
    ctx: RunContext,
    record: Mapping[str, Any],
    frame_index: int,
    object_id: str,
    box: Box,
    mask: np.ndarray,
    config: Mapping[str, Any],
) -> tuple[list[np.ndarray], str | None, str]:
    width = int(getattr(video.info, "width", 0))
    height = int(getattr(video.info, "height", 0))
    record_sequence = _sam3_record_mask_sequence(record, video, width=width, height=height)
    if record_sequence is not None:
        return record_sequence, None, "sam3-local"
    scene_sweep_record = bool(
        source == "sam3_auto_masks"
        or record.get("sceneSweep")
        or record.get("scene_sweep")
        or _bool_config_any(config, ("sceneSweep", "scene_sweep"), False)
    )
    tracker_requested = _bool_config_any(
        config,
        ("useTransformersTracker", "use_transformers_tracker", "requireTransformersTracker", "require_transformers_tracker"),
        False,
    )
    if scene_sweep_record and not tracker_requested:
        return _sam3_template_fallback_result(
            video,
            frame_index=frame_index,
            mask=mask,
            box=box,
            config=config,
            reason="SAM3 Scene Sweep video propagation is disabled by default",
        )
    if hasattr(backend, "track_candidate"):
        try:
            masks = list(
                backend.track_candidate(
                    video,
                    frame_index=frame_index,
                    object_id=object_id,
                    box=(box.x, box.y, box.w, box.h),
                    mask=mask,
                    config=config,
                )
            )
            if len(masks) != len(video.frames):
                raise ProviderConfigError("SAM3 video tracking returned the wrong number of masks.")
            return [normalize_binary_mask(candidate_mask) for candidate_mask in masks], None, getattr(backend, "provider_name", "sam3-local")
        except Exception as exc:
            detail = _redact_local_paths_from_error(exc)
            warning = f"SAM3 video tracking failed: {detail}"
            ctx.emit(
                "candidate_discovery",
                "running",
                warning,
                metadata={
                    "objectId": object_id,
                    "keyframeIndex": frame_index,
                    "provider": getattr(backend, "provider_name", "sam3-local"),
                    "trackingProvider": "keyframe_seed_sequence",
                    "fallbackReason": "sam3_tracking_failed",
                    "errorType": type(exc).__name__,
                },
            )
            return _sam3_template_fallback_result(
                video,
                frame_index=frame_index,
                mask=mask,
                box=box,
                config=config,
                reason=warning,
            )
    return [mask.copy() for _frame in video.frames], (
        "SAM3 video tracking backend was not available; review uses the prompt-frame mask sequence."
    ), "keyframe_seed_sequence"


def _sam3_records_to_candidates(
    backend: Any,
    video: VideoSource,
    config: Mapping[str, Any],
    ctx: RunContext,
    records: Sequence[Mapping[str, Any]],
    *,
    source: str,
    prompt_type: str,
    prompt_value: str | None,
) -> Sequence[ObjectCandidate]:
    width = int(getattr(video.info, "width", 0))
    height = int(getattr(video.info, "height", 0))
    if width <= 0 or height <= 0:
        raise ProviderConfigError(f"{source} discovery needs video dimensions for SAM3 proposals")
    max_candidates = max(1, _int_config_any(config, ("maxCandidatesPerKeyframe", "max_candidates", "maxCandidates"), len(records) or 1))
    max_objects = max(1, _int_config_any(config, ("maxObjects", "max_objects"), max_candidates))
    min_area = max(1, _int_config_any(config, ("minMaskArea", "min_area"), 32))
    max_area_ratio = _ratio_config_any(config, ("maxMaskAreaRatio", "max_area_ratio"), 0.45 if source == "sam3_auto_masks" else 0.9)
    stability_threshold = _ratio_config_any(config, ("stabilityThreshold", "stability_threshold"), 0.0)
    dedupe_iou = _ratio_config_any(config, ("dedupeIou", "dedupe_iou", "overlap_threshold"), 0.78 if source == "sam3_auto_masks" else 1.0)
    write_rejected = _bool_config_any(config, ("writeRejectedCandidates", "write_rejected_candidates"), True)
    quality_preset = str(config.get("qualityPreset") or config.get("quality_preset") or "custom")
    provider_name = str(getattr(backend, "provider_name", "sam3-local") or "sam3-local")
    hosted_backend = provider_name.startswith("sam3-hosted")
    frame_area = max(1, width * height)
    accepted_count = 0
    rejected_count = 0
    accepted_boxes: list[Box] = []
    candidates: list[ObjectCandidate] = []
    sorted_records = sorted([dict(record) for record in records], key=lambda record: _proposal_score(record), reverse=True)[:max_candidates]
    for record_index, record in enumerate(sorted_records):
        frame_index = int(record.get("frame_index", record.get("frameIndex", config.get("frameIndex", 0))) or 0)
        frame_index = min(max(0, frame_index), max(0, len(video.frames) - 1))
        record_sequence = _sam3_record_mask_sequence(record, video, width=width, height=height)
        if record_sequence is not None:
            mask = record_sequence[frame_index]
        else:
            mask = _proposal_mask(record, width=width, height=height)
        box = _proposal_box(_record_value(record, ("bbox", "box")), width=width, height=height)
        if box.w == width and box.h == height and "bbox" not in record and "box" not in record:
            box = _box_from_mask(mask)
        area = int(np.count_nonzero(mask))
        area_ratio = area / frame_area
        explicit_stability = _explicit_proposal_stability(record)
        stability = explicit_stability if explicit_stability is not None else _proposal_score(record)
        rejection_reason: str | None = None
        warnings: list[str] = []
        if area < min_area:
            rejection_reason = "too_small"
        elif area_ratio > max_area_ratio:
            rejection_reason = "whole_frame"
        elif explicit_stability is not None and stability < stability_threshold:
            rejection_reason = "unstable_mask"
        elif any(_box_iou(box, previous) >= dedupe_iou for previous in accepted_boxes):
            rejection_reason = "duplicate_mask"
        elif accepted_count >= max_objects:
            rejection_reason = "max_objects"
        accepted = rejection_reason is None
        if accepted:
            accepted_count += 1
            accepted_boxes.append(box)
            index_for_id = accepted_count
        else:
            rejected_count += 1
            index_for_id = rejected_count
            warnings.append(f"SAM3 proposal rejected: {rejection_reason}")
            if not write_rejected:
                continue
        object_id = str(record.get("object_id") or record.get("objectId") or f"{source}_{'cand' if accepted else 'rejected'}_{index_for_id:03d}")
        if accepted:
            mask_sequence, tracking_warning, tracking_provider = _sam3_track_or_seed_sequence(
                backend,
                video,
                source=source,
                ctx=ctx,
                record=record,
                frame_index=frame_index,
                object_id=object_id,
                box=box,
                mask=mask,
                config=config,
            )
        else:
            mask_sequence = [mask.copy() for _frame in video.frames]
            tracking_warning = None
            tracking_provider = "not_tracked_rejected_candidate"
        if tracking_warning:
            warnings.append(tracking_warning)
        mask_dir, mask_dir_rel = _relative_mask_dir(ctx, source, object_id)
        _write_mask_sequence(video, mask_dir, mask_sequence)
        confidence = round(_proposal_score(record), 4)
        label = str(record.get("label") or record.get("phrase") or record.get("text") or f"SAM3 {prompt_type} {index_for_id}")
        if not accepted:
            label = f"Rejected {label}"
        candidate = ObjectCandidate(
            id=object_id,
            label=label,
            source=source,
            frame_index=frame_index,
            box=box,
            score=confidence,
            z_index=10 + (accepted_count * 10 if accepted else 1000 + rejected_count),
            metadata=_candidate_metadata(
                source,
                (
                    "SAM3 hosted scene sweep proposal"
                    if hosted_backend and source == "sam3_auto_masks"
                    else "SAM3 scene sweep keyframe mask proposal"
                    if source == "sam3_auto_masks"
                    else "SAM3 hosted discovery proposal"
                    if hosted_backend
                    else "SAM3 local discovery proposal"
                ),
                {
                    "providerName": provider_name,
                    "qualityPreset": quality_preset,
                    "mock": False,
                    "aiUsage": "hosted_optional_sam3" if hosted_backend else "local_optional_sam3",
                    "networkRequired": hosted_backend,
                    "promptType": prompt_type,
                    "prompt": prompt_value,
                    "keyframeIndex": frame_index,
                    "proposalIndex": record_index,
                    "filters": {
                        "maxCandidates": max_candidates,
                        "maxObjects": max_objects,
                        "minMaskArea": min_area,
                        "maxMaskAreaRatio": max_area_ratio,
                        "stabilityThreshold": stability_threshold,
                        "dedupeIou": dedupe_iou,
                        "writeRejectedCandidates": write_rejected,
                    },
                    "areaRatio": round(area_ratio, 6),
                    "stabilityScore": round(stability, 4),
                    "motionScore": None,
                    "confidence": confidence,
                    "frameCoverageEstimate": _mask_sequence_coverage(mask_sequence),
                    "defaultSelected": accepted,
                    "reviewStatus": "pending" if accepted else "rejected",
                    "warnings": warnings,
                    "rejectionReason": rejection_reason,
                    "maskDir": mask_dir_rel,
                    "maskFiles": len(mask_sequence),
                    "trackingProvider": tracking_provider,
                },
            ),
        )
        artifact_paths = _write_candidate_previews(video, candidate, mask_dir, mask=mask)
        candidates.append(
            ObjectCandidate(
                id=candidate.id,
                label=candidate.label,
                source=candidate.source,
                frame_index=candidate.frame_index,
                box=candidate.box,
                score=candidate.score,
                z_index=candidate.z_index,
                metadata={**candidate.metadata, **artifact_paths},
            )
        )
        ctx.emit(
            "candidate_discovery",
            "running",
            f"SAM3 object candidate {object_id} generated",
            metadata={"objectId": object_id, "keyframeIndex": frame_index, "rejectionReason": rejection_reason},
        )
    if not candidates:
        if source == "sam3_auto_masks":
            raise ProviderConfigError(
                "SAM3 scene sweep produced no candidate masks after filtering. Try a higher-recall quality preset, "
                "lower minMaskArea, raise maxMaskAreaRatio for large foreground objects, or verify SAM3 Tracker mask generation is ready."
            )
        raise ProviderConfigError("SAM3 discovery produced no candidates.")
    return candidates


@dataclass
class SAM3ConceptDiscoveryProvider:
    detector: Any | None = None
    backend: Any | None = None
    backend_factory: Callable[[Mapping[str, Any]], Any] | None = None
    name: str = "sam3_concept"
    provider_name: str = "sam3-mock"

    def propose(self, video: VideoSource, config: Mapping[str, Any], ctx: RunContext) -> Sequence[ObjectCandidate]:
        if self.detector is not None:
            return [_candidate_from_detection(item, index, self.name) for index, item in enumerate(self.detector.detect(video, config))]
        if not config.get("mock"):
            backend = _sam3_backend(self.backend, self.backend_factory, config)
            records = backend.discover_concept(video, config, ctx)
            return _sam3_records_to_candidates(
                backend,
                video,
                config,
                ctx,
                records,
                source=self.name,
                prompt_type="concept",
                prompt_value=str(config.get("concept") or config.get("text") or config.get("prompt") or ""),
            )
        concept = str(config.get("concept") or config.get("text") or config.get("prompt") or "object")
        labels = [f"SAM3 concept: {label}" for label in _split_labels(concept)]
        return _mock_box_candidates(
            video,
            {
                **dict(config),
                "labels": labels,
                "metadata": {
                    "providerName": self.provider_name,
                    "sam3Mode": "concept",
                    "concept": concept,
                    "aiUsage": "none",
                },
                "filters": {
                    "maxCandidates": config.get("max_candidates", config.get("maxCandidates")),
                },
            },
            ctx,
            self.name,
            "Mock SAM3 concept proposal",
        )


@dataclass
class SAM3ExemplarDiscoveryProvider:
    detector: Any | None = None
    backend: Any | None = None
    backend_factory: Callable[[Mapping[str, Any]], Any] | None = None
    name: str = "sam3_exemplar"
    provider_name: str = "sam3-mock"

    def propose(self, video: VideoSource, config: Mapping[str, Any], ctx: RunContext) -> Sequence[ObjectCandidate]:
        if self.detector is not None:
            return [_candidate_from_detection(item, index, self.name) for index, item in enumerate(self.detector.detect(video, config))]
        if not config.get("mock"):
            backend = _sam3_backend(self.backend, self.backend_factory, config)
            records = backend.discover_exemplar(video, config, ctx)
            return _sam3_records_to_candidates(
                backend,
                video,
                config,
                ctx,
                records,
                source=self.name,
                prompt_type="exemplar",
                prompt_value=str(config.get("exemplars") or config.get("exemplarRefs") or config.get("box") or ""),
            )
        exemplars = _label_list(config.get("exemplars") or config.get("exemplarRefs") or config.get("exemplar_refs") or ["selected exemplar"])
        labels = [f"SAM3 exemplar match {index + 1}" for index, _item in enumerate(exemplars)] or ["SAM3 exemplar match 1"]
        return _mock_box_candidates(
            video,
            {
                **dict(config),
                "labels": labels,
                "metadata": {
                    "providerName": self.provider_name,
                    "sam3Mode": "exemplar",
                    "exemplarCount": len(exemplars),
                    "aiUsage": "none",
                },
                "filters": {
                    "maxCandidates": config.get("max_candidates", config.get("maxCandidates")),
                    "exemplarCount": len(exemplars),
                },
            },
            ctx,
            self.name,
            "Mock SAM3 exemplar proposal",
        )


@dataclass
class SAM3AutoMasksDiscoveryProvider:
    backend: Any | None = None
    backend_factory: Callable[[Mapping[str, Any]], Any] | None = None
    name: str = "sam3_auto_masks"
    provider_name: str = "sam3-mock"

    def propose(self, video: VideoSource, config: Mapping[str, Any], ctx: RunContext) -> Sequence[ObjectCandidate]:
        if not config.get("mock"):
            backend = _sam3_backend(self.backend, self.backend_factory, config)
            records = backend.discover_auto_masks(video, config, ctx)
            return _sam3_records_to_candidates(
                backend,
                video,
                config,
                ctx,
                records,
                source=self.name,
                prompt_type="scene_sweep",
                prompt_value=str(config.get("concept") or config.get("text") or config.get("prompt") or "").strip() or None,
            )
        return MockObjectDiscoveryProvider(name=self.name, provider_name=self.provider_name).propose(video, {**dict(config), "mock": True}, ctx)


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
                metadata={
                    "candidateId": candidate.id,
                    "candidateMetadata": dict(candidate.metadata),
                    "source": candidate.source,
                },
            )
        )
    return specs
