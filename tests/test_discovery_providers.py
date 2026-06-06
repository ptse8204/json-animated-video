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
    MockObjectDiscoveryProvider,
    MotionForegroundDiscoveryProvider,
    SAM2AutomaticProposalDiscoveryProvider,
    SAM3AutoMasksDiscoveryProvider,
    SAM3ConceptDiscoveryProvider,
    SAM3ExemplarDiscoveryProvider,
    SamAutoMasksDiscoveryProvider,
    TextDetectorDiscoveryProvider,
    discovery_provider_schemas,
    object_specs_from_candidates,
)
from motionjson.providers.base import ProviderConfigError
from motionjson.providers.pipeline_adapters import ContourVectorizer, IdentityTrackLinker, ObjectSpecInitialMaskProvider, PerFrameMaskVideoTracker
from motionjson.tracks import ObjectCandidate, RunContext, VideoSource
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


class FakeSAM2AutomaticBackend:
    provider_name = "sam2-local"

    def __init__(self, *, duplicate: bool = False) -> None:
        self.proposed: list[int] = []
        self.tracked: list[str] = []
        self.duplicate = duplicate

    def propose_masks(self, frame_rgb, *, frame_index, config):
        self.proposed.append(frame_index)
        x = 5 if self.duplicate else 5 + frame_index * 8
        accepted = np.zeros(frame_rgb.shape[:2], dtype=np.uint8)
        accepted[8:18, x : x + 10] = 255
        tiny = np.zeros(frame_rgb.shape[:2], dtype=np.uint8)
        tiny[0:1, 0:1] = 255
        return [
            {
                "segmentation": accepted,
                "bbox": [x, 8, 10, 10],
                "predicted_iou": 0.91,
                "stability_score": 0.94,
            },
            {
                "segmentation": tiny,
                "bbox": [0, 0, 1, 1],
                "predicted_iou": 0.82,
                "stability_score": 0.91,
            },
        ]

    def track_candidate(self, video, *, frame_index, object_id, box, mask, config):
        self.tracked.append(object_id)
        x, y, w, h = box
        masks = []
        for offset, _frame in enumerate(video.frames):
            tracked = np.zeros(mask.shape, dtype=np.uint8)
            tracked[y : y + h, min(mask.shape[1] - w, x + offset) : min(mask.shape[1], x + offset + w)] = 255
            masks.append(tracked)
        return masks


class FakeSAM2RecordsBackend:
    provider_name = "sam2-local"

    def __init__(self, records_by_frame, *, track_result=None) -> None:
        self.records_by_frame = records_by_frame
        self.track_result = track_result
        self.proposed: list[int] = []

    def propose_masks(self, frame_rgb, *, frame_index, config):
        self.proposed.append(frame_index)
        return self.records_by_frame.get(frame_index, [])

    def track_candidate(self, video, *, frame_index, object_id, box, mask, config):
        if self.track_result is not None:
            return self.track_result
        return [mask.copy() for _frame in video.frames]


class FakeSAM3SceneSweepBackend:
    provider_name = "sam3-local"

    def discover_auto_masks(self, video, config, ctx=None):
        return [
            {
                "object_id": "sam3_scene_001",
                "label": "scene object",
                "segmentation": proposal_mask(x=6, y=10, w=8, h=8),
                "bbox": [6, 10, 8, 8],
                "score": 0.91,
                "sceneSweep": True,
            }
        ]


class RecordingJobContext:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def emit(self, stage, status, message, *, progress=None, metadata=None):
        self.events.append({"stage": stage, "status": status, "message": message, "progress": progress or {}, "metadata": metadata or {}})


class FakeSAM2ProposalOnlyBackend:
    provider_name = "sam2-local"

    def propose_masks(self, frame_rgb, *, frame_index, config):
        mask = np.zeros(frame_rgb.shape[:2], dtype=np.uint8)
        mask[8:18, 5:15] = 255
        return [{"segmentation": mask, "bbox": [5, 8, 10, 10], "predicted_iou": 0.91, "stability_score": 0.94}]


def proposal_mask(*, x: int, y: int, w: int, h: int, width: int = 40, height: int = 32) -> np.ndarray:
    mask = np.zeros((height, width), dtype=np.uint8)
    mask[y : y + h, x : x + w] = 255
    return mask


def test_discovery_provider_schemas_cover_phase5_modes():
    modes = {schema["mode"] for schema in discovery_provider_schemas()}

    assert modes == {
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
    assert DISCOVERY_PROVIDER_SCHEMAS["auto_object_proposals"]["defaultQualityPreset"] == "clean"
    assert DISCOVERY_PROVIDER_SCHEMAS["sam3_concept"]["mockAvailable"] is True
    assert DISCOVERY_PROVIDER_SCHEMAS["sam3_exemplar"]["mockAvailable"] is True
    assert DISCOVERY_PROVIDER_SCHEMAS["sam3_auto_masks"]["mockAvailable"] is True
    assert DISCOVERY_PROVIDER_SCHEMAS["text_detector"]["configSchema"]["text"]
    assert DISCOVERY_PROVIDER_SCHEMAS["class_detector"]["presets"]["vehicles"]
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


def test_mock_sam3_concept_discovery_works_without_model(tmp_path):
    candidates = SAM3ConceptDiscoveryProvider().propose(
        video_source(),
        {"mock": True, "concept": "red ball . blue cup", "max_candidates": 2},
        RunContext(out_dir=tmp_path),
    )
    specs = object_specs_from_candidates(candidates, base_dir=tmp_path)

    assert [candidate.label for candidate in candidates] == ["SAM3 concept: red ball", "SAM3 concept: blue cup"]
    assert candidates[0].source == "sam3_concept"
    assert candidates[0].metadata["providerName"] == "sam3-mock"
    assert candidates[0].metadata["sam3Mode"] == "concept"
    assert candidates[0].metadata["maskDir"].startswith("discovery/sam3_concept/")
    assert specs[0].object_id.startswith("sam3_concept_")


def test_mock_sam3_exemplar_discovery_works_without_model(tmp_path):
    candidates = SAM3ExemplarDiscoveryProvider().propose(
        video_source(),
        {"mock": True, "exemplars": ["crop_001", "crop_002"], "max_candidates": 2},
        RunContext(out_dir=tmp_path),
    )

    assert [candidate.label for candidate in candidates] == ["SAM3 exemplar match 1", "SAM3 exemplar match 2"]
    assert candidates[0].source == "sam3_exemplar"
    assert candidates[0].metadata["providerName"] == "sam3-mock"
    assert candidates[0].metadata["sam3Mode"] == "exemplar"
    assert candidates[0].metadata["exemplarCount"] == 2
    assert candidates[0].metadata["maskDir"].startswith("discovery/sam3_exemplar/")


def test_mock_sam3_auto_masks_discovery_uses_review_artifact_shape(tmp_path):
    candidates = SAM3AutoMasksDiscoveryProvider().propose(
        video_source(),
        {"mock": True, "qualityPreset": "clean", "maxCandidatesPerKeyframe": 3, "maxObjects": 2},
        RunContext(out_dir=tmp_path),
    )

    assert len(candidates) == 3
    assert candidates[0].source == "sam3_auto_masks"
    assert candidates[0].metadata["providerName"] == "sam3-mock"
    assert candidates[0].metadata["thumbnailArtifactPath"].startswith("discovery/sam3_auto_masks/")
    assert sum(1 for candidate in candidates if not candidate.metadata.get("rejectionReason")) == 2


def test_sam3_auto_masks_reports_candidate_record_binding_and_mask_frame_io(tmp_path):
    recorder = RecordingJobContext()

    candidates = SAM3AutoMasksDiscoveryProvider(backend=FakeSAM3SceneSweepBackend()).propose(
        video_source(),
        {"minMaskArea": 1, "maxObjects": 1},
        RunContext(out_dir=tmp_path, job_context=recorder),
    )

    event_types = [event["metadata"].get("eventType") for event in recorder.events]
    assert [candidate.id for candidate in candidates] == ["sam3_scene_001"]
    assert "sam3_candidate_record_started" in event_types
    assert "sam3_candidate_object_bound" in event_types
    assert "sam3_mask_frame_encode_started" in event_types
    assert "sam3_mask_frame_write_finished" in event_types
    record_event = next(event for event in recorder.events if event["metadata"].get("eventType") == "sam3_candidate_record_started")
    assert record_event["metadata"]["recordId"] == "sam3_scene_001"
    assert record_event["metadata"]["operationKind"] == "candidate_filtering"
    write_event = next(event for event in recorder.events if event["metadata"].get("eventType") == "sam3_mask_frame_write_finished")
    assert write_event["metadata"]["objectId"] == "sam3_scene_001"
    assert write_event["metadata"]["frame"] == 1
    assert write_event["metadata"]["totalFrames"] == 3
    assert write_event["metadata"]["byteSize"] > 0
    assert write_event["metadata"]["operationKind"] == "file_write"


@pytest.mark.parametrize(
    ("provider", "message"),
        [
            (SAM3ConceptDiscoveryProvider(), "sam3_concept requires"),
            (SAM3ExemplarDiscoveryProvider(), "sam3_exemplar requires"),
            (SAM3AutoMasksDiscoveryProvider(), "sam3_auto_masks scene sweep requires"),
        ],
)
def test_sam3_mock_providers_fail_clearly_without_mock(provider, message):
    with pytest.raises(ProviderConfigError, match=message):
        provider.propose(video_source(), {}, RunContext())


def test_class_detector_presets_expand_and_merge_custom_classes_without_network(tmp_path):
    candidates = ClassDetectorDiscoveryProvider().propose(
        video_source(),
        {
            "mock": True,
            "class_preset": "vehicles",
            "classes": ["forklift", "car"],
            "max_candidates": 6,
            "confidence_threshold": 0.45,
        },
        RunContext(out_dir=tmp_path),
    )
    specs = object_specs_from_candidates(candidates, base_dir=tmp_path)

    assert [candidate.label for candidate in candidates] == ["car", "truck", "bus", "motorcycle", "bicycle", "forklift"]
    assert len({candidate.id for candidate in candidates}) == len(candidates)
    assert candidates[0].metadata["classPreset"] == "vehicles"
    assert candidates[0].metadata["filters"]["requestedClasses"][-1] == "forklift"
    assert candidates[0].metadata["filters"]["confidenceThreshold"] == 0.45
    assert candidates[0].metadata["maskDir"].startswith("discovery/class_detector/")
    assert specs[0].object_id == "class_detector_car"


@pytest.mark.parametrize(
    ("config", "message"),
    [
        ({"mock": True, "class_preset": "unknown"}, "unknown class preset"),
        ({"mock": True, "confidence_threshold": 1.2}, "between 0 and 1"),
        ({"mock": True, "classes": {"person": True}}, "classes must be"),
    ],
)
def test_class_detector_preset_config_errors_are_clear(config, message):
    with pytest.raises(ProviderConfigError, match=message):
        ClassDetectorDiscoveryProvider().propose(video_source(), config, RunContext())


def test_class_detector_injected_detector_receives_normalized_preset_config():
    class Detector:
        def __init__(self) -> None:
            self.config = None

        def detect(self, _video, config):
            self.config = dict(config)
            return [{"id": "detected_car", "label": "car", "box": {"x": 1, "y": 2, "w": 3, "h": 4}, "score": 0.8}]

    detector = Detector()
    candidates = ClassDetectorDiscoveryProvider(detector=detector).propose(
        video_source(),
        {"class_preset": "vehicles", "classes": ["forklift"], "confidence_threshold": 0.55},
        RunContext(),
    )

    assert detector.config["classes"] == ["car", "truck", "bus", "motorcycle", "bicycle", "forklift"]
    assert detector.config["class_preset"] == "vehicles"
    assert candidates[0].id == "detected_car"
    assert candidates[0].score == 0.8


def test_sam_auto_masks_discovery_missing_deps_returns_capability_warning_not_crash():
    provider = SamAutoMasksDiscoveryProvider()

    with pytest.raises(ProviderConfigError, match="sam2-local automatic proposals require"):
        provider.propose(video_source(), {}, RunContext())


def test_sam2_auto_object_proposals_fake_backend_writes_artifacts_and_tracks_masks(tmp_path):
    backend = FakeSAM2AutomaticBackend()
    provider = SAM2AutomaticProposalDiscoveryProvider(backend=backend)

    candidates = provider.propose(
        video_source(count=3),
        {
            "providerPreference": "sam2-local",
            "qualityPreset": "clean",
            "keyframePolicy": "uniform_interval",
            "frameInterval": 1,
            "maxKeyframes": 2,
            "maxCandidatesPerKeyframe": 2,
            "maxObjects": 2,
            "minMaskArea": 4,
            "maxMaskAreaRatio": 0.6,
            "stabilityThreshold": 0.7,
            "dedupeIou": 0.9,
            "writeRejectedCandidates": True,
        },
        RunContext(out_dir=tmp_path),
    )
    accepted = [candidate for candidate in candidates if not candidate.metadata.get("rejectionReason")]
    rejected = [candidate for candidate in candidates if candidate.metadata.get("rejectionReason")]
    specs = object_specs_from_candidates(candidates, base_dir=tmp_path)

    assert backend.proposed == [0, 1]
    assert backend.tracked == [candidate.id for candidate in accepted]
    assert len(accepted) == 2
    assert len(rejected) == 2
    assert rejected[0].metadata["rejectionReason"] == "too_small"
    assert accepted[0].metadata["providerName"] == "sam2-local"
    assert accepted[0].metadata["mock"] is False
    assert accepted[0].metadata["trackingProvider"] == "sam2-local"
    assert accepted[0].metadata["filters"]["maxKeyframes"] == 2
    assert (tmp_path / accepted[0].metadata["maskDir"] / "mask_000003.png").exists()
    assert (tmp_path / accepted[0].metadata["thumbnailArtifactPath"]).exists()
    assert (tmp_path / accepted[0].metadata["maskPreviewArtifactPath"]).exists()
    assert [spec.object_id for spec in specs] == [candidate.id for candidate in accepted]


def test_sam2_auto_object_proposals_filters_duplicate_masks(tmp_path):
    backend = FakeSAM2AutomaticBackend(duplicate=True)
    provider = SAM2AutomaticProposalDiscoveryProvider(backend=backend)

    candidates = provider.propose(
        video_source(count=2),
        {
            "providerPreference": "sam2-local",
            "frameInterval": 1,
            "maxKeyframes": 2,
            "maxCandidatesPerKeyframe": 1,
            "maxObjects": 4,
            "minMaskArea": 4,
            "maxMaskAreaRatio": 0.6,
            "stabilityThreshold": 0.7,
            "dedupeIou": 0.5,
            "writeRejectedCandidates": True,
        },
        RunContext(out_dir=tmp_path),
    )

    assert sum(1 for candidate in candidates if not candidate.metadata.get("rejectionReason")) == 1
    assert any(candidate.metadata.get("rejectionReason") == "duplicate_mask" for candidate in candidates)


def test_sam2_auto_object_proposals_explicit_keyframes_are_deduped_and_capped(tmp_path):
    backend = FakeSAM2AutomaticBackend()

    SAM2AutomaticProposalDiscoveryProvider(backend=backend).propose(
        video_source(count=4),
        {
            "providerPreference": "sam2-local",
            "keyframes": [0, 0, 3, 1],
            "maxKeyframes": 2,
            "maxCandidatesPerKeyframe": 1,
            "maxObjects": 4,
            "minMaskArea": 4,
            "maxMaskAreaRatio": 0.6,
            "stabilityThreshold": 0.7,
        },
        RunContext(out_dir=tmp_path),
    )

    assert backend.proposed == [0, 3]


def test_sam2_auto_object_proposals_filters_rejection_reasons_and_caps(tmp_path):
    stable = {"segmentation": proposal_mask(x=5, y=8, w=10, h=10), "bbox": [5, 8, 10, 10], "score": 0.95, "stability_score": 0.95}
    unstable = {"segmentation": proposal_mask(x=20, y=8, w=8, h=8), "bbox": [20, 8, 8, 8], "score": 0.94, "stability_score": 0.2}
    whole = {"segmentation": proposal_mask(x=0, y=0, w=40, h=32), "bbox": [0, 0, 40, 32], "score": 0.93, "stability_score": 0.95}
    background = {"segmentation": proposal_mask(x=0, y=16, w=40, h=16), "bbox": [0, 16, 40, 16], "score": 0.92, "stability_score": 0.95}
    over_cap = {"segmentation": proposal_mask(x=28, y=2, w=8, h=8), "bbox": [28, 2, 8, 8], "score": 0.91, "stability_score": 0.95}
    backend = FakeSAM2RecordsBackend({0: [stable, unstable, whole, background, over_cap]})

    candidates = SAM2AutomaticProposalDiscoveryProvider(backend=backend).propose(
        video_source(count=1),
        {
            "providerPreference": "sam2-local",
            "keyframes": [0],
            "maxCandidatesPerKeyframe": 5,
            "maxObjects": 1,
            "minMaskArea": 4,
            "maxMaskAreaRatio": 0.8,
            "stabilityThreshold": 0.7,
            "dedupeIou": 0.9,
            "rejectBackgroundLike": True,
            "writeRejectedCandidates": True,
        },
        RunContext(out_dir=tmp_path),
    )

    reasons = {candidate.metadata.get("rejectionReason") for candidate in candidates}
    assert None in reasons
    assert {"unstable_mask", "whole_frame", "background_like", "max_objects"}.issubset(reasons)


def test_sam2_auto_object_proposals_write_rejected_false_omits_rejected_records(tmp_path):
    records = [
        {"segmentation": proposal_mask(x=5, y=8, w=10, h=10), "bbox": [5, 8, 10, 10], "score": 0.9, "stability_score": 0.9},
        {"segmentation": proposal_mask(x=0, y=0, w=1, h=1), "bbox": [0, 0, 1, 1], "score": 0.8, "stability_score": 0.9},
    ]
    backend = FakeSAM2RecordsBackend({0: records})

    candidates = SAM2AutomaticProposalDiscoveryProvider(backend=backend).propose(
        video_source(count=1),
        {
            "providerPreference": "sam2-local",
            "keyframes": [0],
            "maxCandidatesPerKeyframe": 2,
            "maxObjects": 2,
            "minMaskArea": 4,
            "maxMaskAreaRatio": 0.6,
            "stabilityThreshold": 0.7,
            "writeRejectedCandidates": False,
        },
        RunContext(out_dir=tmp_path),
    )

    assert len(candidates) == 1
    assert candidates[0].metadata["rejectionReason"] is None


def test_sam2_auto_object_proposals_sorts_before_per_keyframe_cap(tmp_path):
    low = {"segmentation": proposal_mask(x=5, y=8, w=10, h=10), "bbox": [5, 8, 10, 10], "score": 0.1, "stability_score": 0.9}
    high = {"segmentation": proposal_mask(x=22, y=8, w=10, h=10), "bbox": [22, 8, 10, 10], "score": 0.95, "stability_score": 0.9}
    backend = FakeSAM2RecordsBackend({0: [low, high]})

    candidates = SAM2AutomaticProposalDiscoveryProvider(backend=backend).propose(
        video_source(count=1),
        {
            "providerPreference": "sam2-local",
            "keyframes": [0],
            "maxCandidatesPerKeyframe": 1,
            "maxObjects": 2,
            "minMaskArea": 4,
            "maxMaskAreaRatio": 0.6,
            "stabilityThreshold": 0.7,
        },
        RunContext(out_dir=tmp_path),
    )

    assert len(candidates) == 1
    assert candidates[0].box.to_dict() == {"x": 22, "y": 8, "w": 10, "h": 10}


def test_sam2_auto_object_proposals_uses_keyframe_sequence_when_propagation_absent(tmp_path):
    candidates = SAM2AutomaticProposalDiscoveryProvider(backend=FakeSAM2ProposalOnlyBackend()).propose(
        video_source(count=2),
        {
            "providerPreference": "sam2-local",
            "keyframes": [0],
            "maxCandidatesPerKeyframe": 1,
            "maxObjects": 1,
            "minMaskArea": 4,
            "maxMaskAreaRatio": 0.6,
            "stabilityThreshold": 0.7,
        },
        RunContext(out_dir=tmp_path),
    )

    assert candidates[0].metadata["trackingProvider"] == "keyframe_seed_sequence"
    assert "keyframe proposal mask sequence" in candidates[0].metadata["warnings"][0]
    assert (tmp_path / candidates[0].metadata["maskDir"] / "mask_000002.png").exists()


def test_sam2_auto_object_proposals_validates_wrong_length_propagation(tmp_path):
    mask = proposal_mask(x=5, y=8, w=10, h=10)
    backend = FakeSAM2RecordsBackend(
        {0: [{"segmentation": mask, "bbox": [5, 8, 10, 10], "score": 0.9, "stability_score": 0.9}]},
        track_result=[mask],
    )

    with pytest.raises(ProviderConfigError, match="wrong number of masks"):
        SAM2AutomaticProposalDiscoveryProvider(backend=backend).propose(
            video_source(count=2),
            {
                "providerPreference": "sam2-local",
                "keyframes": [0],
                "maxCandidatesPerKeyframe": 1,
                "maxObjects": 1,
                "minMaskArea": 4,
                "maxMaskAreaRatio": 0.6,
                "stabilityThreshold": 0.7,
            },
            RunContext(out_dir=tmp_path),
        )


def test_sam2_auto_object_proposals_missing_backend_config_is_clear(tmp_path, monkeypatch):
    monkeypatch.delenv("SAM2_LOCAL_CHECKPOINT", raising=False)
    monkeypatch.delenv("SAM2_LOCAL_CONFIG", raising=False)

    with pytest.raises(ProviderConfigError, match="SAM2_LOCAL_CHECKPOINT"):
        SAM2AutomaticProposalDiscoveryProvider().propose(
            video_source(),
            {"providerPreference": "sam2-local"},
            RunContext(out_dir=tmp_path),
        )


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


def test_sam3_scene_sweep_template_fallback_exports_moving_motion(tmp_path):
    video = tmp_path / "tiny.mp4"
    out = tmp_path / "out"
    make_tiny_video(video, frame_count=3)

    scene = run_multi_object_pipeline(
        video_path=video,
        out_dir=out,
        object_specs=[],
        candidate_provider=SAM3AutoMasksDiscoveryProvider(backend=FakeSAM3SceneSweepBackend()),
        candidate_config={"minMaskArea": 1, "maxObjects": 1},
        candidate_to_specs=lambda candidates: object_specs_from_candidates(candidates, base_dir=out),
        sample_fps=12,
        max_frames=3,
        min_area=1,
    )

    motion = scene["objects"][0]["motion"]
    assert scene["objects"][0]["discovery"]["trackingProvider"] == "template_match_fallback"
    assert motion[0]["x"] < motion[-1]["x"]
    assert scene["objects"][0].get("exportStatus") != "rejected"
    assert validate_output_dir(out, object_id="sam3_scene_001").ok


def test_multi_object_pipeline_reports_missing_discovery_provider_name(tmp_path):
    class MissingNameDiscoveryProvider:
        def propose(self, video, config, ctx):
            raise AssertionError("provider should fail contract validation before discovery runs")

    video = tmp_path / "tiny.mp4"
    out = tmp_path / "out"
    make_tiny_video(video, frame_count=1)

    with pytest.raises(ProviderConfigError, match="must define a non-empty name"):
        run_multi_object_pipeline(
            video_path=video,
            out_dir=out,
            object_specs=[],
            candidate_provider=MissingNameDiscoveryProvider(),
            candidate_config={},
            candidate_to_specs=lambda candidates: object_specs_from_candidates(candidates, base_dir=out),
            sample_fps=12,
            max_frames=1,
            min_area=1,
        )


def test_multi_object_pipeline_writes_rejected_candidates_before_no_usable_error(tmp_path):
    class RejectedCandidateProvider:
        name = "sam3_auto_masks"

        def propose(self, video, config, ctx):
            return [
                ObjectCandidate(
                    id="sam3_rejected_001",
                    label="Rejected scene object",
                    source=self.name,
                    frame_index=0,
                    box=None,
                    score=0.75,
                    metadata={
                        "rejectionReason": "unstable_mask",
                        "reviewStatus": "rejected",
                        "maskDir": "discovery/sam3_auto_masks/sam3_rejected_001",
                    },
                )
            ]

    video = tmp_path / "tiny.mp4"
    out = tmp_path / "out"
    make_tiny_video(video, frame_count=1)

    with pytest.raises(ValueError, match="unstable_mask=1"):
        run_multi_object_pipeline(
            video_path=video,
            out_dir=out,
            object_specs=[],
            candidate_provider=RejectedCandidateProvider(),
            candidate_config={},
            candidate_to_specs=lambda candidates: object_specs_from_candidates(candidates, base_dir=out),
            sample_fps=12,
            max_frames=1,
            min_area=1,
        )

    candidates_payload = json.loads((out / "candidates.json").read_text(encoding="utf-8"))
    fallback_payload = json.loads((out / "fallback_diagnostics.json").read_text(encoding="utf-8"))
    assert candidates_payload["provider"] == "sam3_auto_masks"
    assert candidates_payload["candidates"][0]["metadata"]["rejectionReason"] == "unstable_mask"
    assert fallback_payload["summary"]["candidateRejectionReasonCounts"] == {"unstable_mask": 1}


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


def test_mock_text_detector_discovery_cli_smoke_uses_detector_candidates(tmp_path):
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
            "text_detector",
            "--discovery-text",
            "red ball . hand",
            "--discovery-config",
            '{"mock": true, "max_candidates": 2}',
            "--mask-provider",
            "mock",
            "--max-frames",
            "2",
            "--min-area",
            "1",
        ]
    )

    candidates_payload = json.loads((out / "candidates.json").read_text())
    assert candidates_payload["provider"] == "text_detector"
    assert [candidate["label"] for candidate in candidates_payload["candidates"]] == ["red ball", "hand"]
    assert all(candidate["metadata"]["mock"] is True for candidate in candidates_payload["candidates"])
    assert all(candidate["source"] == "text_detector" for candidate in candidates_payload["candidates"])
    assert validate_output_dir(out, object_id="text_detector_red_ball").ok


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


def test_auto_object_proposals_mock_preset_is_deterministic_and_writes_artifacts(tmp_path):
    source = video_source()
    first = MockObjectDiscoveryProvider().propose(
        source,
        {"mock": True, "qualityPreset": "clean", "maxCandidatesPerKeyframe": 6, "maxObjects": 4},
        RunContext(out_dir=tmp_path / "first"),
    )
    second = MockObjectDiscoveryProvider().propose(
        source,
        {"mock": True, "qualityPreset": "clean", "maxCandidatesPerKeyframe": 6, "maxObjects": 4},
        RunContext(out_dir=tmp_path / "second"),
    )

    def public_shape(candidates):
        return [
            {
                "id": candidate.id,
                "label": candidate.label,
                "box": candidate.box.to_dict() if candidate.box else None,
                "score": candidate.score,
                "rejectionReason": candidate.metadata.get("rejectionReason"),
                "thumbnailArtifactPath": candidate.metadata.get("thumbnailArtifactPath"),
                "maskPreviewArtifactPath": candidate.metadata.get("maskPreviewArtifactPath"),
            }
            for candidate in candidates
        ]

    assert public_shape(first) == public_shape(second)
    assert len(first) == 6
    assert sum(1 for candidate in first if candidate.metadata.get("rejectionReason")) == 2
    assert first[0].metadata["providerName"] == "mock"
    assert first[0].metadata["qualityPreset"] == "clean"
    assert first[0].metadata["maskDir"].startswith("discovery/auto_object_proposals/")
    assert (tmp_path / "first" / first[0].metadata["maskDir"] / "mask_000001.png").exists()
    assert (tmp_path / "first" / first[0].metadata["thumbnailArtifactPath"]).exists()
    assert (tmp_path / "first" / first[0].metadata["maskPreviewArtifactPath"]).exists()
    assert [spec.object_id for spec in object_specs_from_candidates(first, base_dir=tmp_path / "first")] == [
        "auto_object_proposals_cand_001",
        "auto_object_proposals_cand_002",
        "auto_object_proposals_cand_003",
        "auto_object_proposals_cand_004",
    ]


def test_auto_object_proposals_mock_maximum_recall_is_larger_and_caps_are_honored(tmp_path):
    source = video_source()
    clean = MockObjectDiscoveryProvider().propose(
        source,
        {"mock": True, "qualityPreset": "clean"},
        RunContext(out_dir=tmp_path / "clean"),
    )
    maximum = MockObjectDiscoveryProvider().propose(
        source,
        {"mock": True, "qualityPreset": "maximum_recall"},
        RunContext(out_dir=tmp_path / "maximum"),
    )
    capped = MockObjectDiscoveryProvider().propose(
        source,
        {"mock": True, "qualityPreset": "maximum_recall", "maxCandidatesPerKeyframe": 3, "maxObjects": 2},
        RunContext(out_dir=tmp_path / "capped"),
    )

    assert len(clean) < len(maximum)
    assert len(capped) == 3
    assert sum(1 for candidate in capped if not candidate.metadata.get("rejectionReason")) == 2
    assert sum(1 for candidate in capped if candidate.metadata.get("rejectionReason")) == 1


def test_auto_object_proposals_mock_cli_writes_candidate_review_artifacts(tmp_path):
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
            "auto_object_proposals",
            "--discovery-config",
            '{"mock": true, "qualityPreset": "clean", "maxCandidatesPerKeyframe": 4, "maxObjects": 2}',
            "--mask-provider",
            "mock",
            "--max-frames",
            "2",
            "--min-area",
            "1",
        ]
    )

    candidates_payload = json.loads((out / "candidates.json").read_text())
    candidates = candidates_payload["candidates"]
    assert candidates_payload["provider"] == "auto_object_proposals"
    assert len(candidates) == 4
    assert sum(1 for candidate in candidates if candidate["metadata"].get("rejectionReason")) == 2
    assert (out / candidates[0]["metadata"]["thumbnailArtifactPath"]).exists()
    assert (out / candidates[0]["metadata"]["maskPreviewArtifactPath"]).exists()
    assert validate_output_dir(out, object_id="auto_object_proposals_cand_001").ok


def test_trace_everything_mock_cli_is_review_gated_and_writes_rejections(tmp_path):
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
            "auto_object_proposals",
            "--discovery-config",
            (
                '{"mock": true, "qualityPreset": "trace_everything", '
                '"costWarningAcknowledged": true, "maxCandidatesPerKeyframe": 5, "maxObjects": 2}'
            ),
            "--mask-provider",
            "mock",
            "--max-frames",
            "2",
            "--min-area",
            "1",
        ]
    )

    candidates_payload = json.loads((out / "candidates.json").read_text())
    scene = json.loads((out / "scene_graph.json").read_text())
    tracks = json.loads((out / "tracks.json").read_text())

    assert candidates_payload["config"]["qualityPreset"] == "trace_everything"
    assert len(candidates_payload["candidates"]) == 5
    assert sum(1 for candidate in candidates_payload["candidates"] if candidate["metadata"].get("rejectionReason")) == 3
    assert all(obj["quality"]["reviewRequired"] is True for obj in scene["objects"])
    assert tracks["filterReport"]["exportReviewGate"]["reason"] == "trace_everything_requires_review"
    assert all(track["exportStatus"] == "review_pending" for track in tracks["tracks"])
    assert validate_output_dir(out, object_id="auto_object_proposals_cand_001").ok


def test_auto_object_proposals_cli_surfaces_sam2_setup_error_without_mock(tmp_path, monkeypatch):
    video = tmp_path / "tiny.mp4"
    out = tmp_path / "out"
    make_tiny_video(video)
    monkeypatch.delenv("SAM2_LOCAL_CHECKPOINT", raising=False)
    monkeypatch.delenv("SAM2_LOCAL_CONFIG", raising=False)

    with pytest.raises(SystemExit, match="SAM2_LOCAL_CHECKPOINT"):
        cli.main(
            [
                "extract",
                str(video),
                "--out",
                str(out),
                "--discovery-provider",
                "auto_object_proposals",
                "--mask-provider",
                "mock",
                "--max-frames",
                "2",
                "--min-area",
                "1",
            ]
        )


def test_auto_object_proposals_cli_passes_sam2_flags_to_discovery_config():
    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "extract",
            "input.mp4",
            "--discovery-provider",
            "auto_object_proposals",
            "--discovery-config",
            '{"providerPreference":"sam2-local"}',
            "--sam2-checkpoint",
            "/models/sam2.pt",
            "--sam2-config",
            "/models/sam2.yaml",
            "--sam2-device",
            "mps",
        ]
    )

    _provider, config = cli.build_discovery_provider(args)

    assert isinstance(_provider, SAM2AutomaticProposalDiscoveryProvider)
    assert config["sam2Checkpoint"] == "/models/sam2.pt"
    assert config["sam2ModelConfig"] == "/models/sam2.yaml"
    assert config["sam2Device"] == "mps"


def test_initial_mask_adapter_skips_only_rejected_candidates(tmp_path):
    accepted = MockObjectDiscoveryProvider().propose(
        video_source(),
        {"mock": True, "qualityPreset": "clean", "maxCandidatesPerKeyframe": 2, "maxObjects": 1},
        RunContext(out_dir=tmp_path),
    )
    specs = object_specs_from_candidates(accepted, base_dir=tmp_path)
    initial = ObjectSpecInitialMaskProvider(specs).initialize_masks(video_source(), accepted, RunContext(out_dir=tmp_path))
    unexpected = ObjectCandidate(
        id="accepted_missing_spec",
        label="Accepted missing spec",
        source="auto_object_proposals",
        metadata={"reviewStatus": "pending"},
    )

    assert [mask.object_id for mask in initial] == ["auto_object_proposals_cand_001"]
    with pytest.raises(KeyError, match="accepted_missing_spec"):
        ObjectSpecInitialMaskProvider(specs).initialize_masks(video_source(), [unexpected], RunContext(out_dir=tmp_path))
