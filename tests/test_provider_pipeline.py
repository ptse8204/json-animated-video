from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from motionjson.masks import ThresholdMaskProvider
from motionjson.pipeline import ObjectExtractionSpec, run_pipeline
from motionjson.providers import (
    Exporter,
    MaskProvider,
    MockMaskProvider,
    MockObjectCandidateProvider,
    MockPipelineExporter,
    MockTrackLinker,
    MockVectorizer,
    MockVideoTracker,
    ObjectCandidateProvider,
    ObjectSpecCandidateProvider,
    ObjectSpecInitialMaskProvider,
    SegmentationMaskProvider,
    TrackLinker,
    Vectorizer,
    VideoTracker,
)
from motionjson.providers.base import ProviderExecutionError
from motionjson.providers.mocks import MockSegmentationProvider
from motionjson.providers.pipeline_adapters import ContourVectorizer, MotionJSONArtifactExporter, PerFrameMaskVideoTracker
from motionjson.tracks import RunContext, VideoSource
from motionjson.validation import validate_output_dir
from motionjson.video import Frame, VideoInfo


def frames(count: int = 3) -> list[Frame]:
    output: list[Frame] = []
    for index in range(count):
        rgb = np.full((24, 32, 3), 245, dtype=np.uint8)
        rgb[6:14, 8 + index : 16 + index] = (230, 20, 20)
        output.append(Frame(index=index, out_index=index, time_sec=index / 12, rgb=rgb))
    return output


def video_source(count: int = 3) -> VideoSource:
    return VideoSource(
        path=Path("mock.mp4"),
        info=VideoInfo(width=32, height=24, source_fps=12, sample_fps=12, total_source_frames=count),
        frames=frames(count),
    )


def make_tiny_video(path: Path, frame_count: int = 3) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 12, (32, 24))
    if not writer.isOpened():
        raise RuntimeError("Could not open test video writer")
    for frame in frames(frame_count):
        writer.write(cv2.cvtColor(frame.rgb, cv2.COLOR_RGB2BGR))
    writer.release()


def test_phase4_provider_interfaces_are_exported_and_runtime_checkable():
    assert isinstance(MockObjectCandidateProvider(), ObjectCandidateProvider)
    assert isinstance(MockMaskProvider(), MaskProvider)
    assert isinstance(MockVideoTracker(), VideoTracker)
    assert isinstance(MockTrackLinker(), TrackLinker)
    assert isinstance(MockVectorizer(), Vectorizer)
    assert isinstance(MockPipelineExporter(), Exporter)
    assert isinstance(MotionJSONArtifactExporter(), Exporter)


def test_mock_pipeline_produces_deterministic_object_tracks_without_ml():
    source = video_source()
    ctx = RunContext()
    config = {"object_id": "mock_box", "label": "Mock Box", "min_area": 1}

    def run_once():
        candidates = MockObjectCandidateProvider().propose(source, config, ctx)
        masks = MockMaskProvider().initialize_masks(source, candidates, ctx)
        tracks = MockVideoTracker().track(source, masks, config, ctx)
        linked = MockTrackLinker().link(tracks, config, ctx)
        vectorized = MockVectorizer().vectorize(linked, config, ctx)
        exported = MockPipelineExporter().export({"tracks": vectorized}, config, ctx)
        return [track.to_summary() for track in vectorized], list(exported)

    tracks_a, exported_a = run_once()
    tracks_b, exported_b = run_once()

    assert tracks_a == tracks_b
    assert exported_a == exported_b
    assert tracks_a[0]["objectId"] == "mock_box"
    assert tracks_a[0]["visibleFrameCount"] == 3
    assert tracks_a[0]["frames"][0]["bbox"] == [8, 6, 16, 12]
    assert exported_a == [{"kind": "mock_tracks", "objects": 1, "format": "json", "aiUsage": "none"}]


def test_pipeline_stages_run_independently_with_debug_summaries():
    source = video_source()
    spec = ObjectExtractionSpec("red_square", "Red square", ThresholdMaskProvider((0, 80, 80), (12, 255, 255)))
    ctx = RunContext()

    candidates = list(ObjectSpecCandidateProvider([spec]).propose(source, {}, ctx))
    initial = list(ObjectSpecInitialMaskProvider([spec]).initialize_masks(source, candidates, ctx))
    tracks = list(PerFrameMaskVideoTracker([spec]).track(source, initial, {}, ctx))
    vectorized = list(ContourVectorizer(min_area=1).vectorize(tracks, {"min_area": 1}, ctx))

    assert candidates[0].to_dict()["metadata"]["providerName"] == "ThresholdMaskProvider"
    assert initial[0].to_summary()["providerName"] == "ThresholdMaskProvider"
    assert vectorized[0].object_id == "red_square"
    assert vectorized[0].frames[0].visible is True
    assert vectorized[0].frames[0].bbox == [8, 6, 8, 8]
    assert MotionJSONArtifactExporter().export({"objects": [{"id": "red_square"}]}, {}, ctx)[0]["path"] == "scene_graph.json"


@pytest.mark.parametrize(
    "provider",
    [
        SegmentationMaskProvider(MockSegmentationProvider(), prompt_point=(12, 10)),
        SegmentationMaskProvider(MockSegmentationProvider(), prompt_box=(4, 5, 8, 9)),
    ],
)
def test_single_prompt_pipeline_preserves_legacy_outputs(tmp_path, provider):
    video = tmp_path / "tiny.mp4"
    out = tmp_path / "out"
    make_tiny_video(video)

    scene = run_pipeline(
        video_path=video,
        out_dir=out,
        mask_provider=provider,
        sample_fps=12,
        max_frames=2,
        min_area=1,
    )

    assert scene["objects"][0]["id"] == "object_0"
    assert (out / "scene_graph.json").exists()
    assert (out / "object_motion.json").exists()
    assert (out / "web_asset_manifest.json").exists()
    assert (out / "objects" / "object_0" / "object_manifest.json").exists()
    assert (out / "candidates.json").exists()
    assert (out / "tracks.json").exists()
    candidates = json.loads((out / "candidates.json").read_text())
    assert candidates["video"]["path"] == "tiny.mp4"
    assert validate_output_dir(out).ok


class FailingMaskProvider:
    def prepare(self, video_metadata):
        return None

    def get_mask(self, frame_index, frame_bgr):
        raise ProviderExecutionError("stage provider failed")

    def close(self):
        return None


def test_stage_provider_failure_is_not_swallowed():
    source = video_source(1)
    spec = ObjectExtractionSpec("failing", "Failing", FailingMaskProvider())
    ctx = RunContext()
    candidates = list(ObjectSpecCandidateProvider([spec]).propose(source, {}, ctx))
    initial = list(ObjectSpecInitialMaskProvider([spec]).initialize_masks(source, candidates, ctx))

    with pytest.raises(ProviderExecutionError, match="stage provider failed"):
        PerFrameMaskVideoTracker([spec]).track(source, initial, {}, ctx)
