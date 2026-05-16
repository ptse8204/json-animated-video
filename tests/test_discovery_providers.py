from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

from motionjson import cli
from motionjson.pipeline import run_multi_object_pipeline
from motionjson.providers import (
    DISCOVERY_PROVIDER_SCHEMAS,
    ClassDetectorDiscoveryProvider,
    ExternalMasksDiscoveryProvider,
    ManualPromptDiscoveryProvider,
    MotionForegroundDiscoveryProvider,
    SamAutoMasksDiscoveryProvider,
    TextDetectorDiscoveryProvider,
    discovery_provider_schemas,
    object_specs_from_candidates,
)
from motionjson.providers.base import ProviderConfigError
from motionjson.providers.pipeline_adapters import ContourVectorizer, IdentityTrackLinker, ObjectSpecInitialMaskProvider, PerFrameMaskVideoTracker
from motionjson.tracks import RunContext, VideoSource
from motionjson.validation import validate_output_dir
from motionjson.video import Frame, VideoInfo


def frames(count: int = 3) -> list[Frame]:
    output: list[Frame] = []
    for index in range(count):
        rgb = np.full((32, 40, 3), 245, dtype=np.uint8)
        rgb[10:18, 6 + index * 3 : 14 + index * 3] = (230, 20, 20)
        rgb[4:10, 26:34] = (20, 90, 220)
        output.append(Frame(index=index, out_index=index, time_sec=index / 12, rgb=rgb))
    return output


def video_source(count: int = 3) -> VideoSource:
    return VideoSource(
        path=Path("tiny.mp4"),
        info=VideoInfo(width=40, height=32, source_fps=12, sample_fps=12, total_source_frames=count),
        frames=frames(count),
    )


def make_tiny_video(path: Path, frame_count: int = 3) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 12, (40, 32))
    if not writer.isOpened():
        raise RuntimeError("Could not open test video writer")
    for frame in frames(frame_count):
        writer.write(cv2.cvtColor(frame.rgb, cv2.COLOR_RGB2BGR))
    writer.release()


def write_mask_dir(path: Path, *, x: int, y: int, w: int, h: int, count: int = 3) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for index in range(count):
        mask = np.zeros((32, 40), dtype=np.uint8)
        mask[y : y + h, x : x + w] = 255
        Image.fromarray(mask).save(path / f"mask_{index + 1:06d}.png")


def test_discovery_provider_schemas_cover_phase5_modes():
    modes = {schema["mode"] for schema in discovery_provider_schemas()}

    assert modes == {
        "manual_prompt",
        "sam_auto_masks",
        "text_detector",
        "class_detector",
        "motion_foreground",
        "external_masks",
    }
    assert DISCOVERY_PROVIDER_SCHEMAS["text_detector"]["configSchema"]["text"]
    assert DISCOVERY_PROVIDER_SCHEMAS["motion_foreground"]["noModelSafe"] is True


def test_manual_prompt_discovery_accepts_multiple_points_and_boxes_without_ml():
    provider = ManualPromptDiscoveryProvider()
    candidates = provider.propose(
        video_source(),
        {
            "prompts": [
                {"kind": "point", "object_id": "ball", "label": "Ball", "data": {"x": 8, "y": 12}},
                {"kind": "box", "object_id": "hand", "label": "Hand", "data": {"x": 20, "y": 4, "w": 8, "h": 6}},
            ]
        },
        RunContext(),
    )

    assert [candidate.id for candidate in candidates] == ["ball", "hand"]
    assert candidates[0].point.to_dict() == {"x": 8, "y": 12}
    assert candidates[1].box.to_dict() == {"x": 20, "y": 4, "w": 8, "h": 6}
    assert candidates[0].metadata["providerDescription"]


def test_motion_foreground_discovery_proposes_cpu_candidates_without_gpu(tmp_path):
    source = video_source()
    ctx = RunContext(out_dir=tmp_path)

    candidates = MotionForegroundDiscoveryProvider().propose(
        source,
        {"threshold": 10, "min_area": 4, "max_candidates": 2},
        ctx,
    )

    assert candidates
    assert candidates[0].source == "motion_foreground"
    assert candidates[0].metadata["maskDir"].startswith("discovery/motion_foreground/")
    assert (tmp_path / candidates[0].metadata["maskDir"]).is_dir()


def test_external_masks_discovery_imports_multiple_objects_without_gpu(tmp_path):
    mask_a = tmp_path / "masks" / "ball"
    mask_b = tmp_path / "masks" / "hand"
    write_mask_dir(mask_a, x=6, y=10, w=8, h=8)
    write_mask_dir(mask_b, x=26, y=4, w=8, h=6)

    candidates = ExternalMasksDiscoveryProvider().propose(
        video_source(),
        {
            "objects": [
                {"object_id": "ball", "label": "Ball", "mask_dir": str(mask_a)},
                {"object_id": "hand", "label": "Hand", "mask_dir": str(mask_b)},
            ]
        },
        RunContext(),
    )
    specs = object_specs_from_candidates(candidates)

    assert [candidate.id for candidate in candidates] == ["ball", "hand"]
    assert [spec.object_id for spec in specs] == ["ball", "hand"]
    assert candidates[0].metadata["maskFiles"] == 3


def test_mock_text_detector_discovery_maps_text_prompt_to_candidates_without_network(tmp_path):
    candidates = TextDetectorDiscoveryProvider().propose(
        video_source(),
        {"mock": True, "text": "red ball . hand", "max_candidates": 2},
        RunContext(out_dir=tmp_path),
    )
    specs = object_specs_from_candidates(candidates, base_dir=tmp_path)

    assert [candidate.label for candidate in candidates] == ["red ball", "hand"]
    assert all(candidate.metadata["mock"] is True for candidate in candidates)
    assert [spec.object_id for spec in specs] == ["text_detector_red_ball", "text_detector_hand"]


def test_mock_class_detector_discovery_filters_requested_classes_without_network(tmp_path):
    candidates = ClassDetectorDiscoveryProvider().propose(
        video_source(),
        {"mock": True, "classes": ["person", "cup"], "max_candidates": 1},
        RunContext(out_dir=tmp_path),
    )

    assert len(candidates) == 1
    assert candidates[0].label == "person"
    assert candidates[0].metadata["maskDir"].startswith("discovery/class_detector/")


def test_sam_auto_masks_discovery_missing_deps_returns_capability_warning_not_crash():
    provider = SamAutoMasksDiscoveryProvider()

    with pytest.raises(ProviderConfigError, match="sam_auto_masks discovery requires"):
        provider.propose(video_source(), {}, RunContext())


def test_heavy_detector_missing_deps_are_capability_warnings_not_import_errors():
    with pytest.raises(ProviderConfigError, match="text prompts are not routed directly to SAM2"):
        TextDetectorDiscoveryProvider().propose(video_source(), {"text": "red ball"}, RunContext())
    with pytest.raises(ProviderConfigError, match="class_detector discovery requires"):
        ClassDetectorDiscoveryProvider().propose(video_source(), {"classes": ["person"]}, RunContext())


def test_discovery_candidates_feed_shared_mask_tracking_vectorization_pipeline(tmp_path):
    source = video_source()
    mask_dir = tmp_path / "masks" / "ball"
    write_mask_dir(mask_dir, x=6, y=10, w=8, h=8)
    candidates = ExternalMasksDiscoveryProvider().propose(
        source,
        {"objects": [{"object_id": "ball", "label": "Ball", "mask_dir": str(mask_dir)}]},
        RunContext(),
    )
    specs = object_specs_from_candidates(candidates)
    initial = list(ObjectSpecInitialMaskProvider(specs).initialize_masks(source, candidates, RunContext()))
    tracks = list(PerFrameMaskVideoTracker(specs).track(source, initial, {}, RunContext()))
    linked = list(IdentityTrackLinker().link(tracks, {}, RunContext()))
    vectorized = list(ContourVectorizer(min_area=1).vectorize(linked, {"min_area": 1}, RunContext()))

    assert vectorized[0].object_id == "ball"
    assert vectorized[0].frames[0].visible is True
    assert vectorized[0].frames[0].bbox == [6, 10, 8, 8]


def test_discovery_provider_feeds_run_multi_object_pipeline(tmp_path):
    video = tmp_path / "tiny.mp4"
    out = tmp_path / "out"
    mask_dir = tmp_path / "external" / "ball"
    make_tiny_video(video)
    write_mask_dir(mask_dir, x=6, y=10, w=8, h=8)

    scene = run_multi_object_pipeline(
        video_path=video,
        out_dir=out,
        object_specs=[],
        candidate_provider=ExternalMasksDiscoveryProvider(),
        candidate_config={"objects": [{"object_id": "ball", "label": "Ball", "mask_dir": str(mask_dir)}]},
        candidate_to_specs=lambda candidates: object_specs_from_candidates(candidates, base_dir=out),
        sample_fps=12,
        max_frames=2,
        min_area=1,
    )

    candidates_payload = json.loads((out / "candidates.json").read_text())
    assert scene["objects"][0]["id"] == "ball"
    assert candidates_payload["provider"] == "external_masks"
    assert candidates_payload["candidates"][0]["source"] == "external_masks"
    assert validate_output_dir(out, object_id="ball").ok


def test_manual_prompt_discovery_cli_feeds_shared_pipeline_with_prompt_factory(tmp_path):
    video = tmp_path / "tiny.mp4"
    out = tmp_path / "out"
    make_tiny_video(video)

    cli.main(
        [
            "extract",
            str(video),
            "--out",
            str(out),
            "--discovery-provider",
            "manual_prompt",
            "--mask-provider",
            "mock",
            "--prompt-box",
            "6,10,8,8",
            "--max-frames",
            "2",
            "--min-area",
            "1",
        ]
    )

    candidates_payload = json.loads((out / "candidates.json").read_text())
    assert candidates_payload["provider"] == "manual_prompt"
    assert candidates_payload["candidates"][0]["box"] == {"x": 6, "y": 10, "w": 8, "h": 8}
    assert validate_output_dir(out).ok


def test_discovery_candidate_summaries_include_ui_description_source_score_and_filters(tmp_path):
    candidates = MotionForegroundDiscoveryProvider().propose(
        video_source(),
        {"threshold": 10, "min_area": 4, "max_candidates": 1},
        RunContext(out_dir=tmp_path),
    )
    summary = candidates[0].to_dict()

    assert summary["source"] == "motion_foreground"
    assert summary["score"] > 0
    assert summary["metadata"]["providerDescription"]
    assert summary["metadata"]["whenToUse"]
    assert "filters" in summary["metadata"]
