from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

from motionjson.masks import ExternalMaskProvider
from motionjson.pipeline import run_multi_object_pipeline, run_pipeline
from motionjson.track_filters import (
    TrackFilterConfig,
    build_raster_fallback,
    evaluate_track,
    filter_and_dedupe_tracks,
)
from motionjson.tracks import ObjectTrack, TrackFrame, VideoSource
from motionjson.validation import validate_output_dir
from motionjson.video import Frame, VideoInfo


def track(
    object_id: str,
    *,
    label: str | None = None,
    bbox: list[int] | None = None,
    mask: np.ndarray | None = None,
    frames: int = 3,
    confidence: float | None = 1.0,
) -> ObjectTrack:
    output_frames = []
    for index in range(frames):
        output_frames.append(
            TrackFrame(
                source_frame_index=index,
                frame=index + 1,
                out_index=index,
                t=index / 12,
                mask=None if mask is None else mask.copy(),
                visible=bbox is not None or mask is not None,
                area=float(np.count_nonzero(mask)) if mask is not None else float((bbox or [0, 0, 0, 0])[2] * (bbox or [0, 0, 0, 0])[3]),
                bbox=bbox,
            )
        )
    return ObjectTrack(object_id=object_id, label=label or object_id, source="test", frames=output_frames, confidence=confidence)


def make_tiny_video(path: Path, frames: int = 3) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 12, (40, 32))
    if not writer.isOpened():
        raise RuntimeError("Could not open tiny test video writer")
    for index in range(frames):
        frame = np.full((32, 40, 3), 245, dtype=np.uint8)
        frame[10:18, 6 + index : 14 + index] = (230, 20, 20)
        writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
    writer.release()


def write_mask_dir(path: Path, mask: np.ndarray, count: int = 3) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for index in range(count):
        Image.fromarray(mask).save(path / f"mask_{index + 1:06d}.png")


def write_budget_mask_dir(path: Path) -> Path:
    mask = np.zeros((32, 40), dtype=np.uint8)
    mask[10:18, 6:14] = 255
    write_mask_dir(path, mask, count=2)
    return path


def test_whole_frame_mask_is_rejected_with_fallback_reason_and_suggestions():
    full_mask = np.full((32, 40), 255, dtype=np.uint8)
    decision = evaluate_track(
        track("whole_frame", bbox=[0, 0, 40, 32], mask=full_mask),
        width=40,
        height=32,
        config=TrackFilterConfig(max_frame_coverage_ratio=0.6),
    )

    assert decision.status == "rejected"
    assert decision.reason_codes == ["masks_too_large_whole_frame"]
    assert decision.fallback.reason_code == "masks_too_large_whole_frame"
    assert any("tighter prompt" in suggestion for suggestion in decision.fallback.suggestions)


def test_track_filter_uses_preserved_mask_area_after_arrays_are_stripped():
    stripped = track("stripped", bbox=[2, 3, 5, 4], mask=None, frames=2)
    for frame in stripped.frames:
        frame.metadata["maskArea"] = 20
        frame.metadata["maskShape"] = [32, 40]

    decision = evaluate_track(stripped, width=40, height=32, config=TrackFilterConfig(min_area=1))

    assert decision.status == "accepted"
    assert decision.metrics["visibleFrameCount"] == 2
    assert decision.metrics["meanArea"] == 20
    assert stripped.frames[0].to_summary()["maskArea"] == 20


def test_asset_materialization_budget_skips_cutouts_and_records_diagnostic(tmp_path, monkeypatch):
    video = tmp_path / "tiny.mp4"
    out = tmp_path / "out"
    make_tiny_video(video, frames=2)
    monkeypatch.setenv("MOTIONJSON_MAX_OBJECT_CUTOUT_PIXELS", "1")

    scene = run_pipeline(
        video_path=video,
        out_dir=out,
        mask_provider=ExternalMaskProvider(write_budget_mask_dir(tmp_path / "masks")),
        sample_fps=12,
        max_frames=2,
        min_area=1,
    )
    diagnostics = json.loads((out / "fallback_diagnostics.json").read_text(encoding="utf-8"))["diagnostics"]
    object_manifest = json.loads((out / "objects" / "object_0" / "object_manifest.json").read_text(encoding="utf-8"))

    assert scene["objects"][0]["exportStatus"] == "rejected"
    assert "asset_materialization_budget_exceeded" in scene["objects"][0]["discovery"]["exportValidationReasonCodes"]
    assert not list((out / "objects" / "object_0" / "cutouts").glob("*.png"))
    assert diagnostics[0]["reasonCode"] == "asset_materialization_budget_exceeded"
    assert object_manifest["discovery"]["assetMaterialization"]["status"] == "skipped"


def test_small_and_short_tracks_are_rejected_with_specific_codes():
    small_mask = np.zeros((32, 40), dtype=np.uint8)
    small_mask[5:6, 5:6] = 255

    small = evaluate_track(track("small", bbox=[5, 5, 1, 1], mask=small_mask), width=40, height=32, config=TrackFilterConfig(min_area=5))
    short = evaluate_track(track("short", bbox=[4, 4, 6, 6], frames=1), width=40, height=32, config=TrackFilterConfig(min_visible_frames=2))

    assert small.status == "rejected"
    assert "mask_area_below_minimum" in small.reason_codes
    assert short.status == "rejected"
    assert "track_too_short" in short.reason_codes


def test_no_masks_confidence_and_background_warnings_are_distinct():
    no_masks = evaluate_track(track("empty"), width=40, height=32)
    low_confidence = evaluate_track(
        track("low_confidence", bbox=[5, 5, 8, 8], confidence=0.2),
        width=40,
        height=32,
        config=TrackFilterConfig(min_confidence=0.5),
    )
    large_mask = np.zeros((32, 40), dtype=np.uint8)
    large_mask[:, :30] = 255
    background_like = evaluate_track(
        track("background_like", bbox=[0, 0, 30, 32], mask=large_mask),
        width=40,
        height=32,
        config=TrackFilterConfig(max_frame_coverage_ratio=0.9, background_likelihood_ratio=0.5),
    )

    assert no_masks.status == "rejected"
    assert no_masks.reason_codes[0] == "no_masks_accepted"
    assert low_confidence.status == "rejected"
    assert low_confidence.reason_codes == ["confidence_below_filter"]
    assert background_like.status == "accepted"
    assert background_like.warnings == ["background_likelihood_high"]


def test_static_keyframe_fallback_track_is_rejected_before_export():
    static = track("static_keyframe", bbox=[5, 5, 8, 8], frames=3)
    static.metadata["discovery"] = {"trackingProvider": "keyframe_seed_sequence"}

    decision = evaluate_track(static, width=40, height=32)

    assert decision.status == "rejected"
    assert "static_keyframe_mask_sequence" in decision.reason_codes
    assert decision.fallback.reason_code == "static_keyframe_mask_sequence"


def test_duplicate_tracks_emit_merge_suggestion_and_keep_best_track():
    tracks = [
        track("obj_0001", label="Ball", bbox=[6, 10, 8, 8], confidence=0.9),
        track("obj_0002", label="Ball copy", bbox=[6, 10, 8, 8], confidence=0.5),
    ]

    report = filter_and_dedupe_tracks(tracks, width=40, height=32, config=TrackFilterConfig(min_area=1, duplicate_iou_threshold=0.8))
    payload = report.to_dict()

    assert payload["summary"]["acceptedTracks"] == 1
    assert payload["summary"]["stableIds"] == ["obj_0001", "obj_0002"]
    assert payload["summary"]["labels"] == {"obj_0001": "Ball", "obj_0002": "Ball copy"}
    assert payload["mergeSuggestions"] == [{"keepObjectId": "obj_0001", "mergeObjectId": "obj_0002", "meanIou": 1.0, "reason": "duplicate_track"}]
    assert tracks[0].export_status == "accepted"
    assert tracks[1].export_status == "rejected"
    assert "duplicate_track" in tracks[1].warnings


def test_duplicate_filter_ignores_below_threshold_overlap_and_uses_stable_tie_break():
    below_threshold = [
        track("obj_left", bbox=[2, 4, 8, 8], confidence=0.8),
        track("obj_right", bbox=[20, 4, 8, 8], confidence=0.8),
    ]
    report = filter_and_dedupe_tracks(below_threshold, width=40, height=32, config=TrackFilterConfig(min_area=1, duplicate_iou_threshold=0.8))
    assert report.to_dict()["summary"]["acceptedTracks"] == 2
    assert report.to_dict()["mergeSuggestions"] == []

    tied = [
        track("obj_a", bbox=[6, 10, 8, 8], confidence=0.5),
        track("obj_b", bbox=[6, 10, 8, 8], confidence=0.5),
        track("obj_c", bbox=[24, 10, 8, 8], confidence=0.5),
    ]
    tied_report = filter_and_dedupe_tracks(tied, width=40, height=32, config=TrackFilterConfig(min_area=1, duplicate_iou_threshold=0.8))
    payload = tied_report.to_dict()
    assert payload["summary"]["acceptedTracks"] == 2
    assert payload["mergeSuggestions"] == [{"keepObjectId": "obj_b", "mergeObjectId": "obj_a", "meanIou": 1.0, "reason": "duplicate_track"}]


def test_raster_fallback_model_lists_reason_code_and_suggested_fixes():
    fallback = build_raster_fallback("no_candidates", metadata={"provider": "empty"})

    assert fallback.to_dict()["reasonCode"] == "no_candidates"
    assert fallback.to_dict()["suggestedFixes"]


class EmptyCandidateProvider:
    name = "empty-candidates"

    def propose(self, video: VideoSource, config, ctx):
        return []


class RecordingJobContext:
    def __init__(self) -> None:
        self.events: list[dict] = []
        self.cancel_checks: list[str] = []

    def emit(self, stage, status, message, *, progress=None, metadata=None):
        self.events.append(
            {
                "stage": stage,
                "status": status,
                "message": message,
                "progress": progress or {},
                "metadata": metadata or {},
            }
        )

    def check_cancel(self, stage):
        self.cancel_checks.append(stage)


def test_no_candidates_writes_fallback_diagnostics_before_failure(tmp_path):
    video = tmp_path / "tiny.mp4"
    out = tmp_path / "out"
    make_tiny_video(video)

    with pytest.raises(ValueError, match="produced no candidates"):
        run_multi_object_pipeline(
            video_path=video,
            out_dir=out,
            object_specs=[],
            candidate_provider=EmptyCandidateProvider(),
            candidate_config={},
            candidate_to_specs=lambda candidates: [],
            sample_fps=12,
            max_frames=2,
        )

    payload = json.loads((out / "fallback_diagnostics.json").read_text())
    assert payload["diagnostics"][0]["reasonCode"] == "no_candidates"
    assert payload["diagnostics"][0]["suggestedFixes"]


def test_pipeline_writes_track_filter_metrics_and_fallback_summary(tmp_path):
    video = tmp_path / "tiny.mp4"
    out = tmp_path / "out"
    mask_dir = tmp_path / "masks"
    full_mask = np.full((32, 40), 255, dtype=np.uint8)
    job_context = RecordingJobContext()
    make_tiny_video(video)
    write_mask_dir(mask_dir, full_mask)

    run_pipeline(
        video_path=video,
        out_dir=out,
        mask_provider=ExternalMaskProvider(mask_dir),
        sample_fps=12,
        max_frames=3,
        min_area=1,
        job_context=job_context,
    )

    tracks = json.loads((out / "tracks.json").read_text())
    fallback = json.loads((out / "fallback_diagnostics.json").read_text())

    assert tracks["filterReport"]["summary"]["rejectedTracks"] == 1
    assert tracks["tracks"][0]["exportStatus"] == "rejected"
    assert "masks_too_large_whole_frame" in tracks["tracks"][0]["warnings"]
    assert fallback["diagnostics"][0]["reasonCode"] == "masks_too_large_whole_frame"
    assert not list((out / "objects" / "object_0" / "cutouts").glob("cutout_*.png"))
    assert not (out / "objects" / "object_0" / "spritesheet.webp").exists()
    assert any(
        event["stage"] == "asset_preparation"
        and event["status"] == "skipped"
        and "masks_too_large_whole_frame" in event["metadata"].get("reasonCodes", [])
        for event in job_context.events
    )
    assert validate_output_dir(out).ok
