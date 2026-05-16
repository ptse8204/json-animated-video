from __future__ import annotations

import json
from collections.abc import Sequence as SequenceABC
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import cv2
import numpy as np

from ..video import VideoInfo
from ..tracks import Box, InitialMask, ObjectCandidate, ObjectTrack, RunContext, TrackFrame, VideoSource
from ..vectorize import mask_to_largest_polygon
from .base import BatchSegmentationRequest


@dataclass
class MockLLMProvider:
    """Deterministic no-network LLM/VLM provider for CI and local tests."""

    content: str = "mock completion"
    model: str = "mock/model"

    def complete(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        tools: Sequence[Mapping[str, Any]] | None = None,
        response_format: Mapping[str, Any] | None = None,
        **routing: Any,
    ) -> Mapping[str, Any]:
        return {
            "id": "mock-chat-completion",
            "model": model or self.model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": self.content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": len(messages), "completion_tokens": len(self.content.split()), "total_tokens": len(messages) + len(self.content.split())},
        }


@dataclass
class MockSegmentationProvider:
    """Deterministic binary mask provider with no AI or network dependency."""

    box: tuple[int, int, int, int] | None = None
    video_metadata: VideoInfo | None = field(default=None, init=False)
    provider_name: str = "mock"

    def prepare(self, video_metadata: VideoInfo) -> None:
        self.video_metadata = video_metadata

    def segment(
        self,
        frame_index: int,
        frame_bgr: np.ndarray,
        *,
        prompt_point: tuple[int, int] | None = None,
        prompt_box: tuple[int, int, int, int] | None = None,
    ) -> np.ndarray:
        height, width = frame_bgr.shape[:2]
        mask = np.zeros((height, width), dtype=np.uint8)
        x, y, w, h = prompt_box or self.box or (width // 4, height // 4, max(1, width // 2), max(1, height // 2))
        x0 = max(0, min(width, x))
        y0 = max(0, min(height, y))
        x1 = max(x0, min(width, x + w))
        y1 = max(y0, min(height, y + h))
        mask[y0:y1, x0:x1] = 255
        return mask

    def segment_batch(self, requests: Sequence[BatchSegmentationRequest]) -> Sequence[np.ndarray]:
        return [
            self.segment(
                request.frame_index,
                request.frame_bgr,
                prompt_point=request.prompt_point,
                prompt_box=request.prompt_box,
            )
            for request in requests
        ]

    def close(self) -> None:
        return None

    def performance_summary(self) -> dict[str, Any]:
        return {"providerName": self.provider_name, "cost": {"estimatedCostUnits": 0.0, "unit": "local", "costStatus": "zero_local_runtime"}}


@dataclass
class MockMattingProvider:
    """Deterministic matte refinement using optional blur over a binary mask."""

    blur: int = 0

    def refine_alpha(self, frame_rgb: np.ndarray, binary_mask: np.ndarray) -> np.ndarray:
        alpha = np.where(binary_mask > 127, 255, 0).astype(np.uint8)
        if self.blur > 1:
            kernel = self.blur if self.blur % 2 == 1 else self.blur + 1
            alpha = cv2.GaussianBlur(alpha, (kernel, kernel), 0)
        return alpha


@dataclass
class MockRenderProvider:
    """No-op renderer that reports cached-layer render intent."""

    def render_preview(self, scene_graph: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"status": "ok", "mode": "preview", "objects": len(scene_graph.get("objects", []))}

    def export_video(self, scene_graph: Mapping[str, Any], output_path: str | Path) -> Mapping[str, Any]:
        return {"status": "ok", "mode": "video", "output": str(output_path), "objects": len(scene_graph.get("objects", []))}


@dataclass
class MockStorageProvider:
    """In-memory storage provider for deterministic tests."""

    objects: dict[str, bytes] = field(default_factory=dict)
    content_types: dict[str, str | None] = field(default_factory=dict)

    def save_bytes(self, key: str, data: bytes, *, content_type: str | None = None) -> str:
        self.objects[key] = bytes(data)
        self.content_types[key] = content_type
        return f"mock://{key}"

    def load_bytes(self, key: str) -> bytes:
        if key not in self.objects:
            raise FileNotFoundError(f"Mock storage key not found: {key}")
        return self.objects[key]

    def exists(self, key: str) -> bool:
        return key in self.objects

    def put_bytes(self, key: str, data: bytes, *, content_type: str | None = None) -> str:
        """Backward-compatible alias for early Phase 2 callers."""
        return self.save_bytes(key, data, content_type=content_type)

    def get_bytes(self, key: str) -> bytes:
        """Backward-compatible alias for early Phase 2 callers."""
        return self.load_bytes(key)


@dataclass
class MockExportProvider:
    """Deterministic JSON exporter for manifests and bundle metadata."""

    def export(self, scene_graph: Mapping[str, Any], output_path: str | Path, *, format: str | None = None) -> Mapping[str, Any]:
        path = Path(output_path)
        export_format = format or path.suffix.lstrip(".") or "json"
        if export_format == "json":
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(scene_graph, indent=2, sort_keys=True), encoding="utf-8")
        return {"status": "ok", "format": export_format, "output": str(path)}


@dataclass
class MockObjectCandidateProvider:
    """Deterministic discovery provider for UI/test runs."""

    candidates: Sequence[ObjectCandidate] | None = None
    name: str = "mock-candidate-provider"

    def propose(self, video: VideoSource, config: Mapping[str, Any], ctx: RunContext) -> Sequence[ObjectCandidate]:
        if self.candidates is not None:
            return list(self.candidates)
        width = int(getattr(video.info, "width", 64))
        height = int(getattr(video.info, "height", 64))
        box = Box(width // 4, height // 4, max(1, width // 2), max(1, height // 2))
        return [
            ObjectCandidate(
                id=str(config.get("object_id", "object_0")),
                label=str(config.get("label", "mock_object")),
                source=self.name,
                frame_index=0,
                box=box,
                score=1.0,
            )
        ]


@dataclass
class MockMaskProvider:
    """Deterministic initial-mask provider that draws candidate boxes."""

    name: str = "mock-mask-provider"

    def initialize_masks(
        self,
        video: VideoSource,
        candidates: Sequence[ObjectCandidate],
        ctx: RunContext,
    ) -> Sequence[InitialMask]:
        height = int(getattr(video.info, "height", 64))
        width = int(getattr(video.info, "width", 64))
        masks: list[InitialMask] = []
        for candidate in candidates:
            mask = np.zeros((height, width), dtype=np.uint8)
            box = candidate.box or Box(width // 4, height // 4, max(1, width // 2), max(1, height // 2))
            x0 = max(0, min(width, int(box.x)))
            y0 = max(0, min(height, int(box.y)))
            x1 = max(x0, min(width, int(box.x + box.w)))
            y1 = max(y0, min(height, int(box.y + box.h)))
            mask[y0:y1, x0:x1] = 255
            masks.append(
                InitialMask(
                    object_id=candidate.id,
                    label=candidate.label,
                    frame_index=candidate.frame_index,
                    provider_name=self.name,
                    mask=mask,
                    candidate=candidate,
                    score=1.0,
                )
            )
        return masks


@dataclass
class MockVideoTracker:
    """Repeat each initial mask across sampled frames as stable object tracks."""

    name: str = "mock-video-tracker"

    def track(
        self,
        video: VideoSource,
        masks: Sequence[InitialMask],
        config: Mapping[str, Any],
        ctx: RunContext,
    ) -> Sequence[ObjectTrack]:
        tracks: list[ObjectTrack] = []
        for initial in masks:
            frames: list[TrackFrame] = []
            for frame in video.frames:
                frames.append(
                    TrackFrame(
                        source_frame_index=frame.index,
                        frame=frame.out_index + 1,
                        out_index=frame.out_index,
                        t=round(frame.time_sec, 6),
                        rgb=frame.rgb,
                        mask=None if initial.mask is None else initial.mask.copy(),
                    )
                )
            tracks.append(
                ObjectTrack(
                    object_id=initial.object_id,
                    label=initial.label,
                    source=self.name,
                    frames=frames,
                    confidence=1.0,
                    provider_name=self.name,
                )
            )
        return tracks


@dataclass
class MockTrackLinker:
    """No-op deterministic linker for mock tracks."""

    name: str = "mock-track-linker"

    def link(
        self,
        tracks: Sequence[ObjectTrack],
        config: Mapping[str, Any],
        ctx: RunContext,
    ) -> Sequence[ObjectTrack]:
        for track in tracks:
            track.metadata["linkedBy"] = self.name
        return list(tracks)


@dataclass
class MockVectorizer:
    """Deterministic contour vectorizer for mock tracks."""

    name: str = "mock-vectorizer"

    def vectorize(
        self,
        tracks: Sequence[ObjectTrack],
        config: Mapping[str, Any],
        ctx: RunContext,
    ) -> Sequence[ObjectTrack]:
        min_area = float(config.get("min_area", 1.0))
        simplify_ratio = float(config.get("simplify_ratio", 0.006))
        for track in tracks:
            for frame in track.frames:
                if frame.mask is None:
                    continue
                contour = mask_to_largest_polygon(frame.mask, min_area=min_area, simplify_ratio=simplify_ratio)
                frame.visible = bool(contour.visible and contour.bbox)
                frame.area = contour.area
                frame.bbox = contour.bbox
                frame.centroid = contour.centroid
                frame.polygon = contour.polygon
                frame.contour_points = contour.contour_points
            track.metadata["vectorizedBy"] = self.name
        return list(tracks)


@dataclass
class MockPipelineExporter:
    """Mock exporter for provider-pipeline tests without filesystem writes."""

    name: str = "mock-pipeline-exporter"

    def export(
        self,
        project: Mapping[str, Any],
        config: Mapping[str, Any],
        ctx: RunContext,
    ) -> Sequence[Mapping[str, Any]]:
        tracks = project.get("tracks", [])
        return [
            {
                "kind": "mock_tracks",
                "objects": len(tracks) if isinstance(tracks, SequenceABC) else 0,
                "format": "json",
                "aiUsage": "none",
            }
        ]
