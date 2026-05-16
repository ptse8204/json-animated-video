from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np


@dataclass(frozen=True)
class Point:
    x: int
    y: int

    def to_dict(self) -> dict[str, int]:
        return {"x": int(self.x), "y": int(self.y)}


@dataclass(frozen=True)
class Box:
    x: int
    y: int
    w: int
    h: int

    def to_dict(self) -> dict[str, int]:
        return {"x": int(self.x), "y": int(self.y), "w": int(self.w), "h": int(self.h)}


@dataclass(frozen=True)
class VideoSource:
    path: Path
    info: Any
    frames: Sequence[Any]

    def to_summary(self) -> dict[str, Any]:
        return {
            "path": self.path.name,
            "width": int(getattr(self.info, "width", 0)),
            "height": int(getattr(self.info, "height", 0)),
            "sourceFps": float(getattr(self.info, "source_fps", 0.0)),
            "sampleFps": float(getattr(self.info, "sample_fps", 0.0)),
            "totalSourceFrames": int(getattr(self.info, "total_source_frames", 0)),
            "sampledFrameCount": len(self.frames),
        }


@dataclass
class RunContext:
    out_dir: Path | None = None
    job_context: Any | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def emit(
        self,
        stage: str,
        status: str,
        message: str,
        *,
        progress: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        emit = getattr(self.job_context, "emit", None)
        if callable(emit):
            emit(stage, status, message, progress=progress, metadata=metadata)

    def check_cancel(self, stage: str) -> None:
        check = getattr(self.job_context, "check_cancel", None)
        if callable(check):
            check(stage)


@dataclass(frozen=True)
class ObjectCandidate:
    id: str
    label: str | None = None
    source: str = "manual"
    frame_index: int = 0
    box: Box | None = None
    point: Point | None = None
    mask_ref: str | None = None
    score: float | None = None
    z_index: int = 10
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "label": self.label,
            "source": self.source,
            "frameIndex": int(self.frame_index),
            "zIndex": int(self.z_index),
            "metadata": dict(self.metadata),
        }
        if self.box is not None:
            data["box"] = self.box.to_dict()
        if self.point is not None:
            data["point"] = self.point.to_dict()
        if self.mask_ref is not None:
            data["maskRef"] = self.mask_ref
        if self.score is not None:
            data["score"] = float(self.score)
        return data


@dataclass
class InitialMask:
    object_id: str
    label: str | None
    frame_index: int
    provider_name: str
    mask: np.ndarray | None = field(default=None, repr=False)
    candidate: ObjectCandidate | None = None
    score: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_summary(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "objectId": self.object_id,
            "label": self.label,
            "frameIndex": int(self.frame_index),
            "providerName": self.provider_name,
            "metadata": dict(self.metadata),
        }
        if self.candidate is not None:
            data["candidateId"] = self.candidate.id
        if self.score is not None:
            data["score"] = float(self.score)
        if self.mask is not None:
            data["maskShape"] = list(self.mask.shape[:2])
            data["maskArea"] = int(np.count_nonzero(self.mask))
        return data


@dataclass
class TrackFrame:
    source_frame_index: int
    frame: int
    out_index: int
    t: float
    rgb: np.ndarray | None = field(default=None, repr=False)
    mask: np.ndarray | None = field(default=None, repr=False)
    visible: bool = False
    area: float = 0.0
    bbox: list[int] | None = None
    centroid: list[float] | None = None
    polygon: list[list[float]] = field(default_factory=list)
    contour_points: int = 0
    mask_ref: str | None = None
    asset_ref: str | None = None
    anchor: list[float] = field(default_factory=lambda: [0.0, 0.0])
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_summary(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "sourceFrameIndex": int(self.source_frame_index),
            "frame": int(self.frame),
            "outIndex": int(self.out_index),
            "t": round(float(self.t), 6),
            "visible": bool(self.visible),
            "area": float(self.area),
            "bbox": self.bbox,
            "centroid": self.centroid,
            "contourPoints": int(self.contour_points),
        }
        if self.mask is not None:
            data["maskShape"] = list(self.mask.shape[:2])
            data["maskArea"] = int(np.count_nonzero(self.mask))
        if self.mask_ref is not None:
            data["mask"] = self.mask_ref
        if self.asset_ref is not None:
            data["asset"] = self.asset_ref
        if self.polygon:
            data["polygon"] = self.polygon
        if self.metadata:
            data["metadata"] = dict(self.metadata)
        return data


@dataclass
class ObjectTrack:
    object_id: str
    label: str | None
    source: str
    frames: list[TrackFrame]
    z_index: int = 10
    confidence: float | None = None
    provider_name: str | None = None
    warnings: list[str] = field(default_factory=list)
    export_status: str = "accepted"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_summary(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "objectId": self.object_id,
            "label": self.label,
            "source": self.source,
            "zIndex": int(self.z_index),
            "providerName": self.provider_name,
            "frameCount": len(self.frames),
            "visibleFrameCount": sum(1 for frame in self.frames if frame.visible),
            "warnings": list(self.warnings),
            "exportStatus": self.export_status,
            "frames": [frame.to_summary() for frame in self.frames],
            "metadata": _json_safe(self.metadata),
        }
        if self.confidence is not None:
            data["confidence"] = float(self.confidence)
        return data


def _json_safe(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return {"arrayShape": list(value.shape), "nonZero": int(np.count_nonzero(value))}
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value
