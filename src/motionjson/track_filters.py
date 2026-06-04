from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

import numpy as np

from .tracks import ObjectTrack, TrackFrame


FALLBACK_REASON_CODES = {
    "no_candidates",
    "no_masks_accepted",
    "masks_too_large_whole_frame",
    "vectorization_failed",
    "provider_unavailable",
    "tracking_failed",
    "static_keyframe_mask_sequence",
    "user_chose_raster_mode",
    "duplicate_track",
    "mask_area_below_minimum",
    "track_too_short",
    "confidence_below_filter",
    "asset_materialization_budget_exceeded",
}

FALLBACK_MESSAGES = {
    "no_candidates": "No object candidates were available for tracking.",
    "no_masks_accepted": "No masks passed the track filters.",
    "masks_too_large_whole_frame": "The mask covers too much of the frame and is likely background or the whole video.",
    "vectorization_failed": "The mask could not be converted into useful vector geometry.",
    "provider_unavailable": "The selected provider was unavailable.",
    "tracking_failed": "Object tracking failed before a usable track was produced.",
    "static_keyframe_mask_sequence": "The exported mask sequence is static keyframe fallback output and does not prove object motion was tracked.",
    "user_chose_raster_mode": "The run was configured to keep raster output.",
    "duplicate_track": "This track overlaps another accepted track and should be merged or ignored.",
    "mask_area_below_minimum": "The accepted mask area is below the configured minimum.",
    "track_too_short": "The track is visible in too few frames to export confidently.",
    "confidence_below_filter": "The track confidence is below the configured threshold.",
    "asset_materialization_budget_exceeded": "Raster cutout materialization would exceed the configured local memory/pixel budget.",
}

FALLBACK_SUGGESTIONS = {
    "no_candidates": ["Try manual point/box prompts.", "Use external masks or motion foreground discovery."],
    "no_masks_accepted": ["Lower the minimum visible frame count.", "Review provider diagnostics and mask previews."],
    "masks_too_large_whole_frame": ["Use a tighter prompt box.", "Raise the minimum area filter only after rejecting background masks.", "Try a detector or external mask for the object."],
    "vectorization_failed": ["Use raster alpha output for this object.", "Try a cleaner mask or lower min-area for small objects."],
    "provider_unavailable": ["Open provider diagnostics.", "Choose a no-model provider such as mock, motion foreground, or external masks."],
    "tracking_failed": ["Retry with fewer frames.", "Use external masks for deterministic tracking input."],
    "static_keyframe_mask_sequence": ["Track the selected candidate before export.", "Use template-match, SAM3 Tracker Video, SAM2, or external masks for moving objects."],
    "user_chose_raster_mode": ["Switch output mode only if vector diagnostics are acceptable."],
    "duplicate_track": ["Keep the higher-confidence track.", "Merge labels or delete the duplicate in review."],
    "mask_area_below_minimum": ["Lower the minimum area only for genuinely small objects.", "Use a tighter prompt or external masks."],
    "track_too_short": ["Add prompt keyframes or use external masks for more frames.", "Lower the minimum track length only after review."],
    "confidence_below_filter": ["Review the provider confidence and try another discovery mode."],
    "asset_materialization_budget_exceeded": ["Reduce max frames or candidate count.", "Review masks first, then track only selected objects."],
}


@dataclass(frozen=True)
class TrackFilterConfig:
    min_visible_frames: int = 1
    min_area: float = 1.0
    max_frame_coverage_ratio: float = 0.92
    background_likelihood_ratio: float = 0.72
    min_confidence: float = 0.0
    duplicate_iou_threshold: float = 0.9


@dataclass(frozen=True)
class RasterFallbackDiagnostic:
    reason_code: str
    message: str
    suggestions: list[str]
    severity: str = "warning"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "reasonCode": self.reason_code,
            "message": self.message,
            "suggestedFixes": list(self.suggestions),
            "severity": self.severity,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class TrackDecision:
    object_id: str
    label: str | None
    status: str
    reason_codes: list[str]
    warnings: list[str]
    metrics: dict[str, Any]
    fallback: RasterFallbackDiagnostic | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "objectId": self.object_id,
            "label": self.label,
            "status": self.status,
            "reasonCodes": list(self.reason_codes),
            "warnings": list(self.warnings),
            "metrics": dict(self.metrics),
            "fallback": self.fallback.to_dict() if self.fallback else None,
        }


@dataclass(frozen=True)
class TrackFilterReport:
    format: str
    config: dict[str, Any]
    decisions: list[TrackDecision]
    merge_suggestions: list[dict[str, Any]]
    summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": self.format,
            "config": dict(self.config),
            "decisions": [decision.to_dict() for decision in self.decisions],
            "mergeSuggestions": [dict(suggestion) for suggestion in self.merge_suggestions],
            "summary": dict(self.summary),
        }


def build_raster_fallback(reason_code: str, *, metadata: dict[str, Any] | None = None, severity: str = "warning") -> RasterFallbackDiagnostic:
    if reason_code not in FALLBACK_REASON_CODES:
        raise ValueError(f"Unsupported raster fallback reason code: {reason_code}")
    return RasterFallbackDiagnostic(
        reason_code=reason_code,
        message=FALLBACK_MESSAGES[reason_code],
        suggestions=list(FALLBACK_SUGGESTIONS[reason_code]),
        severity=severity,
        metadata=dict(metadata or {}),
    )


def _mask_area(frame: TrackFrame) -> int:
    if frame.mask is not None:
        return int(np.count_nonzero(frame.mask))
    if frame.metadata.get("maskArea") is not None:
        try:
            return int(frame.metadata["maskArea"])
        except (TypeError, ValueError):
            return 0
    if frame.bbox:
        return int(frame.bbox[2] * frame.bbox[3])
    return 0


def _bbox_area(frame: TrackFrame) -> int:
    if not frame.bbox:
        return 0
    return int(frame.bbox[2] * frame.bbox[3])


def _visible_frames(track: ObjectTrack) -> list[TrackFrame]:
    return [frame for frame in track.frames if frame.visible and (frame.bbox or frame.mask is not None or frame.metadata.get("maskArea") is not None)]


def track_metrics(track: ObjectTrack, *, width: int, height: int) -> dict[str, Any]:
    frame_area = max(1, int(width) * int(height))
    visible = _visible_frames(track)
    mask_ratios = [round(_mask_area(frame) / frame_area, 4) for frame in visible]
    bbox_ratios = [round(_bbox_area(frame) / frame_area, 4) for frame in visible]
    mean_mask_ratio = round(float(np.mean(mask_ratios)), 4) if mask_ratios else 0.0
    mean_bbox_ratio = round(float(np.mean(bbox_ratios)), 4) if bbox_ratios else 0.0
    centers = [
        (float(frame.bbox[0]) + float(frame.bbox[2]) / 2.0, float(frame.bbox[1]) + float(frame.bbox[3]) / 2.0)
        for frame in visible
        if frame.bbox
    ]
    if centers:
        first_x, first_y = centers[0]
        max_center_shift = max(((x - first_x) ** 2 + (y - first_y) ** 2) ** 0.5 for x, y in centers)
        path_length = sum(
            ((right[0] - left[0]) ** 2 + (right[1] - left[1]) ** 2) ** 0.5
            for left, right in zip(centers, centers[1:])
        )
    else:
        max_center_shift = 0.0
        path_length = 0.0
    return {
        "frameCount": len(track.frames),
        "visibleFrameCount": len(visible),
        "visibleFrameRatio": round(len(visible) / len(track.frames), 4) if track.frames else 0.0,
        "meanArea": round(float(np.mean([frame.area for frame in visible])), 3) if visible else 0.0,
        "maxMaskFrameCoverageRatio": max(mask_ratios) if mask_ratios else 0.0,
        "maxBboxFrameCoverageRatio": max(bbox_ratios) if bbox_ratios else 0.0,
        "meanMaskFrameCoverageRatio": mean_mask_ratio,
        "meanBboxFrameCoverageRatio": mean_bbox_ratio,
        "maxCenterShiftPx": round(float(max_center_shift), 3),
        "centerPathLengthPx": round(float(path_length), 3),
        "confidence": track.confidence,
    }


def evaluate_track(track: ObjectTrack, *, width: int, height: int, config: TrackFilterConfig | None = None) -> TrackDecision:
    config = config or TrackFilterConfig()
    metrics = track_metrics(track, width=width, height=height)
    reason_codes: list[str] = []
    warnings: list[str] = []
    if metrics["visibleFrameCount"] == 0:
        reason_codes.append("no_masks_accepted")
    elif metrics["visibleFrameCount"] < config.min_visible_frames:
        reason_codes.append("track_too_short")
    if metrics["meanArea"] < config.min_area:
        reason_codes.append("mask_area_below_minimum")
    if max(metrics["maxMaskFrameCoverageRatio"], metrics["maxBboxFrameCoverageRatio"]) >= config.max_frame_coverage_ratio:
        reason_codes.append("masks_too_large_whole_frame")
    elif max(metrics["meanMaskFrameCoverageRatio"], metrics["meanBboxFrameCoverageRatio"]) >= config.background_likelihood_ratio:
        warnings.append("background_likelihood_high")
    if track.confidence is not None and track.confidence < config.min_confidence:
        reason_codes.append("confidence_below_filter")
    materialization = track.metadata.get("assetMaterialization") if isinstance(track.metadata.get("assetMaterialization"), dict) else {}
    if str(materialization.get("status") or "") in {"skipped", "failed"}:
        for reason in materialization.get("reasonCodes", []):
            if reason in FALLBACK_REASON_CODES and reason not in reason_codes:
                reason_codes.append(reason)
    discovery = track.metadata.get("discovery") if isinstance(track.metadata.get("discovery"), dict) else {}
    if (
        str(discovery.get("trackingProvider") or "") == "keyframe_seed_sequence"
        and metrics["visibleFrameCount"] > 1
        and metrics["maxCenterShiftPx"] < max(2.0, min(width, height) * 0.01)
    ):
        reason_codes.append("static_keyframe_mask_sequence")
    status = "rejected" if reason_codes else "accepted"
    fallback = build_raster_fallback(reason_codes[0], metadata={"objectId": track.object_id, **metrics}) if reason_codes else None
    return TrackDecision(track.object_id, track.label, status, reason_codes, warnings, metrics, fallback)


def _bbox_iou(a: list[int] | None, b: list[int] | None) -> float:
    if not a or not b:
        return 0.0
    ax0, ay0, aw, ah = a
    bx0, by0, bw, bh = b
    ax1, ay1 = ax0 + aw, ay0 + ah
    bx1, by1 = bx0 + bw, by0 + bh
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    iw, ih = max(0, ix1 - ix0), max(0, iy1 - iy0)
    intersection = iw * ih
    if intersection <= 0:
        return 0.0
    union = (aw * ah) + (bw * bh) - intersection
    return round(intersection / union, 4) if union else 0.0


def track_iou(a: ObjectTrack, b: ObjectTrack) -> float:
    frames_by_index = {frame.frame: frame for frame in b.frames}
    overlaps = [
        _bbox_iou(frame.bbox, frames_by_index[frame.frame].bbox)
        for frame in a.frames
        if frame.frame in frames_by_index
    ]
    return round(float(np.mean(overlaps)), 4) if overlaps else 0.0


def _track_rank(track: ObjectTrack, decision: TrackDecision) -> tuple[float, int, str]:
    confidence = track.confidence if track.confidence is not None else 0.0
    return (float(confidence), int(decision.metrics["visibleFrameCount"]), track.object_id)


def filter_and_dedupe_tracks(
    tracks: Sequence[ObjectTrack],
    *,
    width: int,
    height: int,
    config: TrackFilterConfig | None = None,
) -> TrackFilterReport:
    config = config or TrackFilterConfig()
    decisions_by_id = {track.object_id: evaluate_track(track, width=width, height=height, config=config) for track in tracks}
    merge_suggestions: list[dict[str, Any]] = []
    accepted_ids = [track.object_id for track in tracks if decisions_by_id[track.object_id].status == "accepted"]
    rejected_as_duplicates: set[str] = set()

    for index, left in enumerate(tracks):
        if left.object_id not in accepted_ids or left.object_id in rejected_as_duplicates:
            continue
        for right in tracks[index + 1 :]:
            if right.object_id not in accepted_ids or right.object_id in rejected_as_duplicates:
                continue
            overlap = track_iou(left, right)
            if overlap < config.duplicate_iou_threshold:
                continue
            left_rank = _track_rank(left, decisions_by_id[left.object_id])
            right_rank = _track_rank(right, decisions_by_id[right.object_id])
            keep, merge = (left, right) if left_rank >= right_rank else (right, left)
            fallback = build_raster_fallback("duplicate_track", metadata={"keepObjectId": keep.object_id, "mergeObjectId": merge.object_id, "meanIou": overlap})
            decisions_by_id[merge.object_id] = TrackDecision(
                merge.object_id,
                merge.label,
                "rejected",
                ["duplicate_track"],
                ["duplicate_track_overlap"],
                {**decisions_by_id[merge.object_id].metrics, "duplicateOf": keep.object_id, "meanIou": overlap},
                fallback,
            )
            rejected_as_duplicates.add(merge.object_id)
            merge_suggestions.append({"keepObjectId": keep.object_id, "mergeObjectId": merge.object_id, "meanIou": overlap, "reason": "duplicate_track"})

    decisions = [decisions_by_id[track.object_id] for track in tracks]
    for track in tracks:
        decision = decisions_by_id[track.object_id]
        track.export_status = decision.status
        track.warnings = list(dict.fromkeys([*track.warnings, *decision.warnings, *decision.reason_codes]))
        track.metadata["trackFilter"] = decision.to_dict()

    accepted = sum(1 for decision in decisions if decision.status == "accepted")
    rejected = len(decisions) - accepted
    fallback_reason_counts: dict[str, int] = {}
    for decision in decisions:
        for reason in decision.reason_codes:
            fallback_reason_counts[reason] = fallback_reason_counts.get(reason, 0) + 1
    return TrackFilterReport(
        format="motionjson.track_filter_report.v0.1",
        config={
            "minVisibleFrames": config.min_visible_frames,
            "minArea": config.min_area,
            "maxFrameCoverageRatio": config.max_frame_coverage_ratio,
            "backgroundLikelihoodRatio": config.background_likelihood_ratio,
            "minConfidence": config.min_confidence,
            "duplicateIouThreshold": config.duplicate_iou_threshold,
        },
        decisions=decisions,
        merge_suggestions=merge_suggestions,
        summary={
            "tracks": len(decisions),
            "acceptedTracks": accepted,
            "rejectedTracks": rejected,
            "fallbackReasonCounts": fallback_reason_counts,
            "stableIds": [track.object_id for track in tracks],
            "labels": {track.object_id: track.label for track in tracks},
        },
    )
