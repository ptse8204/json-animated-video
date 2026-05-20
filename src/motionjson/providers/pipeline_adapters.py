from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import cv2

from ..providers.base import BatchSegmentationRequest, ProviderAttempt
from ..tracks import Box, InitialMask, ObjectCandidate, ObjectTrack, RunContext, TrackFrame, VideoSource
from ..vectorize import mask_to_largest_polygon


def _elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 3)


def _provider_name(provider: Any) -> str:
    explicit = getattr(provider, "provider_name", None)
    if isinstance(explicit, str) and explicit:
        return explicit
    return provider.__class__.__name__


@dataclass
class ObjectSpecCandidateProvider:
    """Expose existing ObjectExtractionSpec values as discovery candidates."""

    object_specs: Sequence[Any]
    name: str = "object-spec-candidates"

    def propose(self, video: VideoSource, config: Mapping[str, Any], ctx: RunContext) -> Sequence[ObjectCandidate]:
        candidates: list[ObjectCandidate] = []
        for spec in self.object_specs:
            metadata = {
                "providerName": _provider_name(spec.mask_provider),
                "source": "ObjectExtractionSpec",
            }
            candidates.append(
                ObjectCandidate(
                    id=str(spec.object_id),
                    label=str(spec.label),
                    source="manual_object_spec",
                    frame_index=int(config.get("frame_index", 0) or 0),
                    z_index=int(getattr(spec, "z_index", 10)),
                    metadata=metadata,
                )
            )
        return candidates


@dataclass
class ManualPromptCandidateProvider:
    """Turn one UI/CLI prompt into a candidate for a promptable segmenter."""

    object_id: str
    label: str
    prompt_point: tuple[int, int] | None = None
    prompt_box: tuple[int, int, int, int] | None = None
    frame_index: int = 0
    name: str = "manual-prompt-candidates"

    def propose(self, video: VideoSource, config: Mapping[str, Any], ctx: RunContext) -> Sequence[ObjectCandidate]:
        box = Box(*self.prompt_box) if self.prompt_box is not None else None
        point = None
        if self.prompt_point is not None:
            from ..tracks import Point

            point = Point(self.prompt_point[0], self.prompt_point[1])
        return [
            ObjectCandidate(
                id=self.object_id,
                label=self.label,
                source="manual_prompt",
                frame_index=self.frame_index,
                box=box,
                point=point,
                z_index=int(config.get("z_index", 10) or 10),
            )
        ]


@dataclass
class ObjectSpecInitialMaskProvider:
    """Create initial-mask records for existing per-frame mask providers.

    The legacy providers are cursor/order sensitive, so this adapter records the
    seed/provider plan without consuming a frame mask. The tracker owns actual
    per-frame mask generation.
    """

    object_specs: Sequence[Any]
    name: str = "object-spec-initial-masks"

    def initialize_masks(
        self,
        video: VideoSource,
        candidates: Sequence[ObjectCandidate],
        ctx: RunContext,
    ) -> Sequence[InitialMask]:
        specs_by_id = {str(spec.object_id): spec for spec in self.object_specs}
        initial: list[InitialMask] = []
        for candidate in candidates:
            spec = specs_by_id.get(candidate.id)
            if spec is None:
                metadata = candidate.metadata if isinstance(candidate.metadata, dict) else {}
                review_status = str(metadata.get("reviewStatus") or "").strip().lower()
                if metadata.get("rejectionReason") or review_status in {"rejected", "ignored", "excluded"}:
                    continue
                raise KeyError(candidate.id)
            initial.append(
                InitialMask(
                    object_id=candidate.id,
                    label=candidate.label,
                    frame_index=candidate.frame_index,
                    provider_name=_provider_name(spec.mask_provider),
                    candidate=candidate,
                    score=candidate.score,
                    metadata={"mode": "legacy_per_frame_mask_provider"},
                )
            )
        return initial


@dataclass
class PerFrameMaskVideoTracker:
    """Track objects by asking the existing mask provider for each sampled frame."""

    object_specs: Sequence[Any]
    name: str = "per-frame-mask-tracker"

    def track(
        self,
        video: VideoSource,
        masks: Sequence[InitialMask],
        config: Mapping[str, Any],
        ctx: RunContext,
    ) -> Sequence[ObjectTrack]:
        initial_by_id = {mask.object_id: mask for mask in masks}
        tracks: list[ObjectTrack] = []
        for spec in self.object_specs:
            object_id = str(spec.object_id)
            initial = initial_by_id.get(object_id)
            track, provider_performance = self._track_spec(video, spec, initial, ctx)
            track.metadata["providerPerformance"] = provider_performance
            tracks.append(track)
        return tracks

    def _track_spec(
        self,
        video: VideoSource,
        spec: Any,
        initial: InitialMask | None,
        ctx: RunContext,
    ) -> tuple[ObjectTrack, dict[str, Any]]:
        provider = spec.mask_provider
        provider_name = _provider_name(provider)
        mask_timings: list[float] = []
        mask_attempts: list[dict[str, Any]] = []
        batch_summary = {"supported": callable(getattr(provider, "get_masks_batch", None)), "used": False}
        prepared_frames: list[tuple[Any, Any]] = []
        batch_masks: dict[int, Any] = {}
        track_frames: list[TrackFrame] = []

        try:
            provider.prepare(video.info)
            for frame in video.frames:
                ctx.check_cancel("propagation")
                prepared_frames.append((frame, cv2.cvtColor(frame.rgb, cv2.COLOR_RGB2BGR)))
            batch_getter = getattr(provider, "get_masks_batch", None)
            if callable(batch_getter):
                batch_start = time.perf_counter()
                requests = [
                    BatchSegmentationRequest(frame_index=frame.index, frame_bgr=frame_bgr)
                    for frame, frame_bgr in prepared_frames
                ]
                masks = list(batch_getter(requests))
                batch_summary.update({"used": True, "requestCount": len(requests), "elapsedMs": _elapsed_ms(batch_start)})
                batch_masks = {frame.index: mask for (frame, _frame_bgr), mask in zip(prepared_frames, masks)}
            for position, (frame, frame_bgr) in enumerate(prepared_frames, start=1):
                ctx.check_cancel("propagation")
                mask_start = time.perf_counter()
                if frame.index in batch_masks:
                    mask = batch_masks[frame.index]
                else:
                    mask = provider.get_mask(frame.index, frame_bgr)
                elapsed_ms = _elapsed_ms(mask_start)
                mask_timings.append(elapsed_ms)
                if not callable(getattr(provider, "performance_summary", None)):
                    mask_attempts.append(
                        ProviderAttempt(
                            provider=provider_name,
                            operation="get_mask",
                            status="success",
                            elapsed_ms=elapsed_ms,
                            frame_index=frame.index,
                        ).to_dict()
                    )
                track_frames.append(
                    TrackFrame(
                        source_frame_index=frame.index,
                        frame=frame.out_index + 1,
                        out_index=frame.out_index,
                        t=round(frame.time_sec, 6),
                        rgb=frame.rgb,
                        mask=mask,
                        metadata={"initialMaskFrame": initial.frame_index if initial else None},
                    )
                )
                total = len(prepared_frames)
                ctx.emit(
                    "propagation",
                    "running",
                    f"tracked mask frame {frame.out_index + 1} for {spec.object_id}",
                    progress={
                        "current": position,
                        "total": total,
                        "stageRatio": round(position / total, 4) if total else 1.0,
                        "overallRatio": round(0.36 + ((position / total) if total else 1.0) * 0.3, 4),
                    },
                    metadata={"objectId": str(spec.object_id), "sourceFrameIndex": frame.index},
                )
        finally:
            provider.close()

        provider_summary_getter = getattr(provider, "performance_summary", None)
        provider_summary = provider_summary_getter() if callable(provider_summary_getter) else None
        total_mask_ms = round(sum(mask_timings), 3)
        provider_performance = {
            "objectId": str(spec.object_id),
            "providerName": provider_name,
            "frames": len(track_frames),
            "maskCalls": len(mask_timings),
            "maskTotalMs": total_mask_ms,
            "maskAvgMs": round(total_mask_ms / len(mask_timings), 3) if mask_timings else 0.0,
            "batching": batch_summary,
            "providerSummary": provider_summary,
            "attempts": provider_summary.get("attempts", []) if isinstance(provider_summary, dict) else mask_attempts,
            "cache": provider_summary.get("cache") if isinstance(provider_summary, dict) else None,
        }
        track = ObjectTrack(
            object_id=str(spec.object_id),
            label=str(spec.label),
            source=self.name,
            frames=track_frames,
            z_index=int(getattr(spec, "z_index", 10)),
            confidence=initial.score if initial is not None else None,
            provider_name=provider_name,
        )
        return track, provider_performance


@dataclass
class IdentityTrackLinker:
    """Phase 4 linker that preserves provider identities and order."""

    name: str = "identity-track-linker"

    def link(
        self,
        tracks: Sequence[ObjectTrack],
        config: Mapping[str, Any],
        ctx: RunContext,
    ) -> Sequence[ObjectTrack]:
        linked: list[ObjectTrack] = []
        seen: set[str] = set()
        for track in tracks:
            if track.object_id in seen:
                raise ValueError(f"duplicate object track id after linking: {track.object_id}")
            seen.add(track.object_id)
            track.metadata["linkedBy"] = self.name
            linked.append(track)
        return linked


@dataclass
class ContourVectorizer:
    """Vectorize tracked masks into largest-contour geometry."""

    min_area: float = 100.0
    simplify_ratio: float = 0.006
    name: str = "largest-contour-vectorizer"

    def vectorize(
        self,
        tracks: Sequence[ObjectTrack],
        config: Mapping[str, Any],
        ctx: RunContext,
    ) -> Sequence[ObjectTrack]:
        output: list[ObjectTrack] = []
        for track in tracks:
            total = len(track.frames)
            for position, frame in enumerate(track.frames, start=1):
                ctx.check_cancel("vectorization")
                if frame.mask is None:
                    continue
                contour = mask_to_largest_polygon(
                    frame.mask,
                    min_area=float(config.get("min_area", self.min_area)),
                    simplify_ratio=float(config.get("simplify_ratio", self.simplify_ratio)),
                )
                frame.visible = bool(contour.visible and contour.bbox)
                frame.area = contour.area
                frame.bbox = contour.bbox
                frame.centroid = contour.centroid
                frame.polygon = contour.polygon
                frame.contour_points = contour.contour_points
                ctx.emit(
                    "vectorization",
                    "running",
                    f"vectorized frame {frame.frame} for {track.object_id}",
                    progress={
                        "current": position,
                        "total": total,
                        "stageRatio": round(position / total, 4) if total else 1.0,
                        "overallRatio": round(0.66 + ((position / total) if total else 1.0) * 0.04, 4),
                    },
                    metadata={"objectId": track.object_id, "visible": frame.visible},
                )
            track.metadata["vectorizedBy"] = self.name
            output.append(track)
        return output


@dataclass
class MotionJSONArtifactExporter:
    """Small exporter descriptor for tests and UI wiring.

    The current production writer still lives in pipeline.py to preserve output
    compatibility. This class exposes the Phase 4 exporter contract without
    triggering file writes when called directly.
    """

    name: str = "motionjson-artifact-exporter"

    def export(
        self,
        project: Mapping[str, Any],
        config: Mapping[str, Any],
        ctx: RunContext,
    ) -> Sequence[Mapping[str, Any]]:
        objects = project.get("objects", [])
        return [
            {"kind": "scene_graph", "path": "scene_graph.json", "objects": len(objects) if isinstance(objects, list) else 0},
            {"kind": "tracks", "path": "tracks.json"},
            {"kind": "candidates", "path": "candidates.json"},
        ]
