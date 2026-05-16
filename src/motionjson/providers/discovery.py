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
    "sam_auto_masks",
    "text_detector",
    "class_detector",
    "motion_foreground",
    "external_masks",
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
        "inputs": ["classes", "optional detector backend", "optional mock"],
        "configSchema": {
            "classes": "array of class names",
            "mock": "boolean",
            "max_candidates": "integer",
        },
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


def _int_config(config: Mapping[str, Any], name: str, default: int) -> int:
    value = config.get(name, default)
    if isinstance(value, bool):
        raise ProviderConfigError(f"discovery.{name}: expected integer")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ProviderConfigError(f"discovery.{name}: expected integer") from exc


def _float_config(config: Mapping[str, Any], name: str, default: float) -> float:
    value = config.get(name, default)
    if isinstance(value, bool):
        raise ProviderConfigError(f"discovery.{name}: expected number")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ProviderConfigError(f"discovery.{name}: expected number") from exc


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
            return _mock_box_candidates(video, config, ctx, self.name, "Mock automatic mask proposal")
        raise ProviderConfigError(
            "sam_auto_masks discovery requires a configured automatic-mask backend. "
            "Install/configure SAM2 automatic masks or set discovery mock mode for tests."
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
        if self.detector is not None:
            return [_candidate_from_detection(item, index, self.name) for index, item in enumerate(self.detector.detect(video, config))]
        if config.get("mock"):
            labels = config.get("classes") or config.get("labels") or ["object"]
            if isinstance(labels, str):
                labels = _split_labels(labels)
            return _mock_box_candidates(video, {**dict(config), "labels": list(labels)}, ctx, self.name, "Mock class detector box")
        raise ProviderConfigError("class_detector discovery requires a configured detector or mock mode.")


def _split_labels(text: str) -> list[str]:
    labels = [part.strip() for part in re.split(r"[,.]", text) if part.strip()]
    return labels or ["object"]


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
        metadata = _candidate_metadata(source, description, {"filters": {"maxCandidates": max_candidates}, "mock": True})
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
