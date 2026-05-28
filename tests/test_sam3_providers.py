from __future__ import annotations

import builtins
import io
import os
import sys
import time
import types
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from motionjson.providers.discovery import (
    SAM3AutoMasksDiscoveryProvider,
    SAM3ConceptDiscoveryProvider,
    SAM3ExemplarDiscoveryProvider,
    object_specs_from_candidates,
)
from motionjson.providers.base import ProviderConfigError, ProviderExecutionError
from motionjson.providers.hosted_sam import FalSAM3ImageBackend, RoboflowSAM3ConceptBackend
from motionjson.providers.sam3 import (
    HostedSAM3DiscoveryBackend,
    LocalSAM3DiscoveryBackend,
    describe_sam3_model_path,
    describe_sam3_tracker_model,
    find_sam3_checkpoint_candidates,
    normalize_sam3_output,
    _run_with_progress_heartbeat,
)
from motionjson.tracks import RunContext, VideoSource
from motionjson.video import Frame, VideoInfo


def frames(count: int = 3) -> list[Frame]:
    output: list[Frame] = []
    for index in range(count):
        rgb = np.full((12, 16, 3), 245, dtype=np.uint8)
        rgb[2:7, 3 + index : 8 + index] = (220, 20, 20)
        output.append(Frame(index=index, out_index=index, time_sec=index / 12, rgb=rgb))
    return output


def video_source(count: int = 3) -> VideoSource:
    return VideoSource(
        path=Path("tiny.mp4"),
        info=VideoInfo(width=16, height=12, source_fps=12, sample_fps=12, total_source_frames=count),
        frames=frames(count),
    )


def mask_at(x: int, *, width: int = 16, height: int = 12) -> np.ndarray:
    mask = np.zeros((height, width), dtype=np.uint8)
    mask[2:7, x : x + 5] = 255
    return mask


class FakeSAM3Processor:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def set_image(self, image):
        return {"size": image.size}

    def set_text_prompt(self, *, state, prompt):
        self.prompts.append(prompt)
        return {"masks": [mask_at(3)], "boxes": [[3, 2, 5, 5]], "scores": [0.91], "labels": [prompt]}


class FakeSAM3VideoPredictor:
    def __init__(self) -> None:
        self.requests = []

    def handle_request(self, *, request):
        self.requests.append(request)
        if request["type"] == "start_session":
            return {"session_id": "session_001"}
        masks = [mask_at(3 + index) for index in range(3)]
        return {
            "outputs": [
                {
                    "object_id": "sam3_track_001",
                    "label": request.get("text") or "exemplar match",
                    "masks": masks,
                    "bbox": [3, 2, 5, 5],
                    "score": 0.92,
                }
            ]
        }


class FakeSAM3TrackingBackend:
    provider_name = "sam3-local"

    def __init__(self) -> None:
        self.tracked: list[str] = []

    def discover_concept(self, video, config, ctx=None):
        return [{"object_id": "sam3_concept_red_ball", "label": "red ball", "segmentation": mask_at(3), "bbox": [3, 2, 5, 5], "score": 0.93}]

    def discover_exemplar(self, video, config, ctx=None):
        return [{"object_id": "sam3_exemplar_001", "label": "exemplar match", "masks": [mask_at(3 + index) for index in range(3)], "bbox": [3, 2, 5, 5], "score": 0.89}]

    def discover_auto_masks(self, video, config, ctx=None):
        whole = np.full((12, 16), 255, dtype=np.uint8)
        return [
            {"object_id": "sam3_auto_001", "label": "semantic object", "segmentation": mask_at(3), "bbox": [3, 2, 5, 5], "score": 0.91},
            {"object_id": "sam3_auto_whole", "label": "whole frame", "segmentation": whole, "bbox": [0, 0, 16, 12], "score": 0.9},
        ]

    def track_candidate(self, video, *, frame_index, object_id, box, mask, config):
        self.tracked.append(object_id)
        return [mask_at(3 + index) for index, _frame in enumerate(video.frames)]


class FakeSceneMaskGenerator:
    def __init__(self, response=None):
        self.response = response
        self.calls = []

    def __call__(self, image, *, points_per_batch=64):
        self.calls.append({"size": getattr(image, "size", None), "pointsPerBatch": points_per_batch})
        if self.response is not None:
            return self.response
        return {
            "masks": [mask_at(3)],
            "boxes": [[3, 2, 5, 5]],
            "scores": [0.91],
            "labels": ["scene object"],
        }


class RecordingJobContext:
    def __init__(self) -> None:
        self.events = []
        self.cancel_checks = []

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


class FakeTrackerVideoSession:
    video_height = 12
    video_width = 16

    def __init__(self, frame_count: int):
        self.frame_count = frame_count


class FakeTrackerVideoOutput:
    def __init__(self, frame_idx: int, mask: np.ndarray):
        self.frame_idx = frame_idx
        self.pred_masks = np.asarray([mask])


class FakeTrackerVideoModel:
    device = "cpu"

    def propagate_in_video_iterator(self, session):
        for index in range(session.frame_count):
            yield FakeTrackerVideoOutput(index, mask_at(3 + index))


class FakeTrackerVideoProcessor:
    def __init__(self) -> None:
        self.added_inputs = []

    def init_video_session(self, *, video, inference_device):
        return FakeTrackerVideoSession(len(video))

    def add_inputs_to_inference_session(self, **kwargs):
        self.added_inputs.append(kwargs)

    def post_process_masks(self, masks, *, original_sizes, binarize=False):
        return masks


class FakeAutoMaskBackend:
    provider_name = "sam3-local"

    def __init__(self) -> None:
        self.configs = []
        self.tracked = []

    def discover_concept(self, video, config, ctx=None):
        raise AssertionError("sam3_auto_masks must not call concept discovery")

    def discover_auto_masks(self, video, config, ctx=None):
        self.configs.append(dict(config))
        return [{"object_id": "sam3_scene_001", "label": "scene object", "segmentation": mask_at(3), "bbox": [3, 2, 5, 5], "score": 0.91}]

    def track_candidate(self, video, *, frame_index, object_id, box, mask, config):
        self.tracked.append(object_id)
        return [mask_at(3 + index) for index, _frame in enumerate(video.frames)]


class FakeHostedSAM3Transport:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post_json(self, url, payload, *, headers=None, timeout_seconds=None):
        self.calls.append({"url": url, "payload": payload, "headers": headers or {}, "timeoutSeconds": timeout_seconds})
        if callable(self.response):
            return self.response(payload)
        return self.response


class FakeFalClient:
    def __init__(self, response):
        self.response = response
        self.uploads = []
        self.calls = []

    def upload_file(self, path):
        self.uploads.append(path)
        return "https://fal.example.test/input.png"

    def subscribe(self, model, *, arguments, with_logs=False):
        self.calls.append({"model": model, "arguments": arguments, "with_logs": with_logs})
        return self.response


def test_normalize_sam3_output_maps_official_image_shape():
    records = normalize_sam3_output({"masks": [mask_at(3)], "boxes": [[3, 2, 5, 5]], "scores": [0.91], "labels": ["red ball"]})

    assert records[0]["label"] == "red ball"
    assert records[0]["bbox"] == [3, 2, 5, 5]
    assert records[0]["score"] == 0.91


def test_roboflow_sam3_profile_rasterizes_polygon_masks_without_bearer_headers():
    transport = FakeHostedSAM3Transport(
        {
            "prompt_results": [
                {
                    "prompt_index": 0,
                    "predictions": [
                        {
                            "confidence": 0.88,
                            "masks": [[{"x": 2, "y": 2}, {"x": 8, "y": 2}, {"x": 8, "y": 8}, {"x": 2, "y": 8}]],
                        }
                    ],
                }
            ]
        }
    )
    backend = RoboflowSAM3ConceptBackend(
        api_key="roboflow-test-key-abcdef",
        allow_network=True,
        acknowledge_cost_privacy=True,
        transport=transport,
    )

    records = backend.discover_concept(video_source(), {"concept": "red ball"})

    assert records[0]["label"] == "red ball"
    assert records[0]["segmentation"].shape == (12, 16)
    assert records[0]["bbox"][2] >= 5
    assert "api_key=" in transport.calls[0]["url"]
    assert "Authorization" not in transport.calls[0]["headers"]
    assert transport.calls[0]["payload"]["prompts"][0]["text"] == "red ball"


def test_fal_sam3_profile_downloads_mask_urls():
    mask = mask_at(3)
    buffer = io.BytesIO()
    Image.fromarray(mask).save(buffer, format="PNG")
    response = {"masks": [{"url": "https://fal.example.test/mask.png"}], "scores": [0.91], "boxes": [[0.4, 0.4, 0.3, 0.3]]}
    client = FakeFalClient(response)
    backend = FalSAM3ImageBackend(
        api_key="fal-test-key-abcdef",
        allow_network=True,
        acknowledge_cost_privacy=True,
        client=client,
        downloader=lambda url: buffer.getvalue(),
    )

    records = backend.discover_concept(video_source(), {"concept": "red ball"})

    assert records[0]["segmentation"].shape == (12, 16)
    assert records[0]["score"] == 0.91
    assert client.calls[0]["model"] == "fal-ai/sam-3/image"
    assert client.calls[0]["arguments"]["image_url"] == "https://fal.example.test/input.png"


def test_hosted_sam3_smoke_requires_explicit_network_opt_in():
    transport = FakeHostedSAM3Transport({"masks": [mask_at(3)], "boxes": [[3, 2, 5, 5]], "scores": [0.9]})
    backend = HostedSAM3DiscoveryBackend(
        endpoint="https://provider.example.test/sam3",
        api_key="hosted-sam3-secret-abcdef",
        transport=transport,
    )

    with pytest.raises(ProviderConfigError, match="allowNetwork=true"):
        backend.smoke_test(prompt="object")

    assert transport.calls == []


def test_hosted_sam3_smoke_posts_one_frame_and_validates_response():
    secret = "hosted-sam3-secret-abcdef"
    transport = FakeHostedSAM3Transport({"masks": [mask_at(3)], "boxes": [[3, 2, 5, 5]], "scores": [0.9], "labels": ["object"]})
    backend = HostedSAM3DiscoveryBackend(
        endpoint="https://provider.example.test/sam3",
        api_key=secret,
        model="sam3/default",
        allow_network=True,
        acknowledge_cost_privacy=True,
        transport=transport,
        timeout_seconds=12,
    )

    result = backend.smoke_test(prompt="red ball")

    assert result["status"] == "ok"
    assert result["networkAttempted"] is True
    assert result["recordCount"] == 1
    assert secret not in str(result)
    call = transport.calls[0]
    assert call["url"] == "https://provider.example.test/sam3"
    assert call["headers"]["Authorization"] == f"Bearer {secret}"
    assert call["timeoutSeconds"] == 12
    assert call["payload"]["model"] == "sam3/default"
    assert call["payload"]["prompt"] == "red ball"
    assert call["payload"]["frame"]["format"] == "png_base64"


def test_hosted_sam3_smoke_rejects_empty_candidate_response():
    transport = FakeHostedSAM3Transport({"outputs": []})
    backend = HostedSAM3DiscoveryBackend(
        endpoint="https://provider.example.test/sam3",
        api_key="hosted-sam3-secret-abcdef",
        allow_network=True,
        acknowledge_cost_privacy=True,
        transport=transport,
    )

    with pytest.raises(ProviderExecutionError, match="did not include any candidate"):
        backend.smoke_test(prompt="object")


def test_hosted_sam3_from_config_does_not_read_api_keys_from_run_config(monkeypatch):
    monkeypatch.delenv("SAM3_HOSTED_API_KEY", raising=False)
    backend = HostedSAM3DiscoveryBackend.from_config(
        {
            "endpoint": "https://provider.example.test/sam3",
            "apiKey": "hosted-sam3-secret-should-not-be-read",
            "allowNetwork": True,
            "acknowledgeCostPrivacy": True,
        }
    )

    with pytest.raises(ProviderConfigError, match="requires auth"):
        backend.smoke_test(prompt="object")


def test_sam3_concept_can_use_hosted_backend_when_explicitly_configured(tmp_path):
    def hosted_response(payload):
        if payload["task"] == "sam3_track_candidate":
            return {
                "outputs": [
                    {
                        "object_id": "sam3_hosted_track_001",
                        "masks": [mask_at(3 + index) for index in range(3)],
                        "bbox": [3, 2, 5, 5],
                        "score": 0.9,
                    }
                ]
            }
        return {"masks": [mask_at(3)], "boxes": [[3, 2, 5, 5]], "scores": [0.9], "labels": ["red ball"]}

    transport = FakeHostedSAM3Transport(hosted_response)
    candidates = SAM3ConceptDiscoveryProvider(
        backend_factory=lambda _config: HostedSAM3DiscoveryBackend(
            endpoint="https://provider.example.test/sam3",
            api_key="hosted-sam3-secret-abcdef",
            allow_network=True,
            acknowledge_cost_privacy=True,
            transport=transport,
        )
    ).propose(
        video_source(),
        {"concept": "red ball", "minMaskArea": 1, "maxObjects": 1},
        RunContext(out_dir=tmp_path),
    )

    assert candidates[0].metadata["providerName"] == "sam3-hosted"
    assert candidates[0].metadata["aiUsage"] == "hosted_optional_sam3"
    assert candidates[0].metadata["networkRequired"] is True
    assert transport.calls[0]["payload"]["task"] == "sam3_concept"


def test_local_sam3_image_backend_uses_injected_processor_without_model():
    processor = FakeSAM3Processor()
    backend = LocalSAM3DiscoveryBackend(image_processor=processor)

    records = backend.discover_concept(video_source(), {"concept": "red ball", "useVideoSession": False}, RunContext())
    smoke = backend.smoke_test(prompt="blue cup")

    assert processor.prompts == ["red ball", "blue cup"]
    assert len(records) == 1
    assert records[0]["label"] == "red ball"
    assert smoke["recordCount"] == 1


def test_local_sam3_video_backend_returns_track_sequence():
    predictor = FakeSAM3VideoPredictor()
    backend = LocalSAM3DiscoveryBackend(video_predictor=predictor)

    records = backend.discover_concept(video_source(), {"concept": "red ball"}, RunContext())

    assert predictor.requests[0]["type"] == "start_session"
    assert predictor.requests[1]["text"] == "red ball"
    assert records[0]["object_id"] == "sam3_track_001"
    assert len(records[0]["mask_sequence"]) == 3


def test_local_sam3_auto_masks_runs_scene_sweep_generator_without_object_prompt():
    generator = FakeSceneMaskGenerator()
    backend = LocalSAM3DiscoveryBackend(tracker_mask_generator=generator)

    records = backend.discover_auto_masks(video_source(), {"keyframes": [0, 2], "maxCandidatesPerKeyframe": 1, "pointsPerBatch": 32}, RunContext())

    assert [record["frame_index"] for record in records] == [0, 2]
    assert records[0]["label"] == "scene object"
    assert records[0]["sceneSweep"] is True
    assert generator.calls == [{"size": (16, 12), "pointsPerBatch": 32}, {"size": (16, 12), "pointsPerBatch": 32}]


def test_local_sam3_auto_masks_reports_scene_sweep_progress_events():
    recorder = RecordingJobContext()
    backend = LocalSAM3DiscoveryBackend(tracker_mask_generator=FakeSceneMaskGenerator())

    backend.discover_auto_masks(
        video_source(),
        {"keyframes": [0, 2], "maxCandidatesPerKeyframe": 1, "pointsPerBatch": 32},
        RunContext(job_context=recorder),
    )

    messages = [event["message"] for event in recorder.events]
    assert "loading SAM3 Tracker scene-sweep model" in messages
    assert any("generating SAM3 scene masks for keyframe 1/2" in message for message in messages)
    assert any("SAM3 scene masks generated for keyframe 2/2" in message for message in messages)
    assert all("facebook" not in event["message"].lower() for event in recorder.events)
    assert recorder.cancel_checks == ["sam3_scene_sweep", "sam3_scene_sweep"]


def test_local_sam3_scene_sweep_empty_result_is_actionable():
    backend = LocalSAM3DiscoveryBackend(tracker_mask_generator=FakeSceneMaskGenerator({"masks": []}))

    with pytest.raises(ProviderExecutionError, match="SAM3 scene sweep did not return any masks"):
        backend.discover_auto_masks(video_source(), {"keyframes": [0]}, RunContext())


def test_local_sam3_tracker_video_tracks_scene_sweep_candidate():
    processor = FakeTrackerVideoProcessor()
    backend = LocalSAM3DiscoveryBackend(
        tracker_video_model=FakeTrackerVideoModel(),
        tracker_video_processor=processor,
    )

    masks = backend.track_candidate(
        video_source(),
        frame_index=0,
        object_id="sam3_scene_001",
        box=(3, 2, 5, 5),
        mask=mask_at(3),
        config={"useTransformersTracker": True},
    )

    assert len(masks) == 3
    assert np.array_equal(masks[1], mask_at(4))
    assert processor.added_inputs[0]["obj_ids"] == [3001]
    assert processor.added_inputs[0]["input_labels"] == [[[1]]]


def test_sam3_concept_provider_writes_api_candidates_and_tracks(tmp_path):
    backend = FakeSAM3TrackingBackend()
    candidates = SAM3ConceptDiscoveryProvider(backend=backend).propose(
        video_source(),
        {"concept": "red ball", "minMaskArea": 1},
        RunContext(out_dir=tmp_path),
    )
    specs = object_specs_from_candidates(candidates, base_dir=tmp_path)

    assert backend.tracked == ["sam3_concept_red_ball"]
    assert candidates[0].metadata["providerName"] == "sam3-local"
    assert candidates[0].metadata["aiUsage"] == "local_optional_sam3"
    assert candidates[0].metadata["trackingProvider"] == "sam3-local"
    assert candidates[0].metadata["maskDir"].startswith("discovery/sam3_concept/")
    assert (tmp_path / candidates[0].metadata["maskDir"] / "mask_000003.png").exists()
    assert (tmp_path / candidates[0].metadata["thumbnailArtifactPath"]).exists()
    assert [spec.object_id for spec in specs] == ["sam3_concept_red_ball"]


def test_sam3_exemplar_provider_accepts_backend_mask_sequences(tmp_path):
    candidates = SAM3ExemplarDiscoveryProvider(backend=FakeSAM3TrackingBackend()).propose(
        video_source(),
        {"exemplars": ["crop_001"], "minMaskArea": 1},
        RunContext(out_dir=tmp_path),
    )

    assert candidates[0].id == "sam3_exemplar_001"
    assert candidates[0].metadata["promptType"] == "exemplar"
    assert candidates[0].metadata["frameCoverageEstimate"] == 1.0


def test_sam3_auto_masks_provider_filters_and_records_rejected_candidates(tmp_path):
    candidates = SAM3AutoMasksDiscoveryProvider(backend=FakeSAM3TrackingBackend()).propose(
        video_source(),
        {"concept": "object", "minMaskArea": 1, "maxObjects": 1, "maxMaskAreaRatio": 0.75, "writeRejectedCandidates": True},
        RunContext(out_dir=tmp_path),
    )

    assert [candidate.metadata["rejectionReason"] for candidate in candidates] == [None, "whole_frame"]
    assert candidates[1].metadata["reviewStatus"] == "rejected"


def test_sam3_auto_masks_provider_does_not_route_through_concept_prompt(tmp_path):
    backend = FakeAutoMaskBackend()
    candidates = SAM3AutoMasksDiscoveryProvider(backend=backend).propose(
        video_source(),
        {"minMaskArea": 1, "maxObjects": 1},
        RunContext(out_dir=tmp_path),
    )

    assert backend.configs == [{"minMaskArea": 1, "maxObjects": 1}]
    assert backend.tracked == ["sam3_scene_001"]
    assert candidates[0].metadata["promptType"] == "scene_sweep"
    assert candidates[0].metadata["prompt"] is None


def test_sam3_scene_sweep_does_not_import_sam2(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "sam2" or name.startswith("sam2."):
            raise AssertionError("SAM3 scene sweep should not import SAM2")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    backend = LocalSAM3DiscoveryBackend(tracker_mask_generator=FakeSceneMaskGenerator())

    records = backend.discover_auto_masks(video_source(), {"keyframes": [0]}, RunContext())

    assert len(records) == 1


def test_sam3_scene_sweep_defaults_to_facebook_sam3_transformers_model(monkeypatch):
    captured = {}

    def fake_pipeline(task, *, model, device):
        captured["task"] = task
        captured["model"] = model
        captured["device"] = device
        return FakeSceneMaskGenerator()

    monkeypatch.setitem(sys.modules, "transformers", types.SimpleNamespace(pipeline=fake_pipeline))

    records = LocalSAM3DiscoveryBackend().discover_auto_masks(video_source(), {"keyframes": [0]}, RunContext())

    assert captured["task"] == "mask-generation"
    assert captured["model"] == "facebook/sam3"
    assert records[0]["object_id"] == "sam3_scene_0000_001"


def test_sam3_scene_sweep_rejects_checkpoint_path_before_transformers_pipeline(tmp_path, monkeypatch):
    checkpoint = tmp_path / "sam3.pt"
    checkpoint.write_bytes(b"placeholder")

    def fail_pipeline(*args, **kwargs):
        raise AssertionError("pipeline should not be called for a .pt scene-sweep model")

    monkeypatch.setitem(sys.modules, "transformers", types.SimpleNamespace(pipeline=fail_pipeline))

    with pytest.raises(ProviderConfigError, match="sam3TrackerModel=facebook/sam3"):
        LocalSAM3DiscoveryBackend().discover_auto_masks(
            video_source(),
            {"sam3TrackerModel": str(checkpoint), "keyframes": [0]},
            RunContext(),
        )


def test_sam3_scene_sweep_rejects_checkpoint_path_before_transformers_import(tmp_path, monkeypatch):
    checkpoint = tmp_path / "sam3.pt"
    checkpoint.write_bytes(b"placeholder")
    real_import = builtins.__import__

    def fail_transformers_import(name, *args, **kwargs):
        if name == "transformers" or name.startswith("transformers."):
            raise AssertionError("transformers should not be imported for invalid scene-sweep model input")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fail_transformers_import)

    with pytest.raises(ProviderConfigError, match="sam3TrackerModel=facebook/sam3"):
        LocalSAM3DiscoveryBackend().discover_auto_masks(
            video_source(),
            {"sam3TrackerModel": str(checkpoint), "keyframes": [0]},
            RunContext(),
        )


def test_sam3_scene_sweep_accepts_local_hf_model_directory(tmp_path, monkeypatch):
    model_dir = tmp_path / "sam3-hf"
    model_dir.mkdir()
    captured = {}

    def fake_pipeline(task, *, model, device):
        captured["model"] = model
        return FakeSceneMaskGenerator()

    monkeypatch.setitem(sys.modules, "transformers", types.SimpleNamespace(pipeline=fake_pipeline))

    LocalSAM3DiscoveryBackend().discover_auto_masks(video_source(), {"sam3TrackerModel": str(model_dir), "keyframes": [0]}, RunContext())

    assert captured["model"] == str(model_dir)
    assert describe_sam3_tracker_model(model_dir)["valueKind"] == "hf_model_directory"


def test_sam3_loader_heartbeat_reports_long_blocking_steps():
    events = []

    def progress(event_type, message, percent, _debug):
        events.append({"type": event_type, "message": message, "percent": percent})

    result = _run_with_progress_heartbeat(
        lambda: (time.sleep(0.03), "loaded")[1],
        progress=progress,
        event_type="loading_sam3_tracker_model_weights",
        message="Loading SAM3 Tracker model weights",
        percent=55,
        interval_seconds=0.01,
    )

    assert result == "loaded"
    assert events
    assert events[0]["type"] == "loading_sam3_tracker_model_weights"
    assert "still working" in events[0]["message"]


def test_local_sam3_backend_validates_missing_model_path():
    with pytest.raises(ProviderConfigError, match="SAM3 local adapter requires"):
        LocalSAM3DiscoveryBackend().discover_concept(video_source(), {"concept": "object", "useVideoSession": False}, RunContext())


def test_sam3_model_path_status_rejects_huggingface_repo_id():
    status = describe_sam3_model_path("facebook/sam3")

    assert status["valid"] is False
    assert status["valueKind"] == "huggingface_repo_id"
    assert "Hugging Face repo id" in status["reason"]
    assert "hf_hub_download" in status["reason"]

    with pytest.raises(ProviderConfigError, match="Hugging Face repo id"):
        LocalSAM3DiscoveryBackend(model_path="facebook/sam3").discover_concept(
            video_source(),
            {"concept": "object", "useVideoSession": False},
            RunContext(),
        )


def test_sam3_model_path_status_rejects_colab_source_directory():
    status = describe_sam3_model_path("/content/sam3")

    assert status["valid"] is False
    assert status["valueKind"] == "source_package_directory"
    assert "source/package directory" in status["reason"]
    assert "sam3.pt" in status["reason"]

    with pytest.raises(ProviderConfigError, match="source/package directory"):
        LocalSAM3DiscoveryBackend(model_path="/content/sam3").discover_concept(
            video_source(),
            {"concept": "object", "useVideoSession": False},
            RunContext(),
        )


def test_sam3_model_path_status_suggests_checkpoint_inside_directory(tmp_path):
    model_dir = tmp_path / "sam3-cache"
    checkpoint = model_dir / "nested" / "sam3.pt"
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_text("placeholder")

    status = describe_sam3_model_path(model_dir)
    candidates = find_sam3_checkpoint_candidates([model_dir])

    assert candidates == [checkpoint]
    assert status["valid"] is False
    assert status["exists"] is True
    assert status["valueKind"] == "directory_with_checkpoint"
    assert status["candidates"] == [str(checkpoint)]
    assert str(checkpoint) in status["reason"]

    with pytest.raises(ProviderConfigError, match="Use this file instead"):
        LocalSAM3DiscoveryBackend(model_path=model_dir).discover_concept(
            video_source(),
            {"concept": "object", "useVideoSession": False},
            RunContext(),
        )


def test_sam3_model_path_status_accepts_existing_checkpoint_file(tmp_path):
    checkpoint = tmp_path / "sam3.pt"
    checkpoint.write_text("placeholder")

    status = describe_sam3_model_path(checkpoint)

    assert status["valid"] is True
    assert status["resolvedPath"] == str(checkpoint)
    assert status["valueKind"] == "checkpoint_file"


def test_local_sam3_backend_missing_file_message_is_actionable(tmp_path):
    missing = tmp_path / "missing-sam3.pt"

    with pytest.raises(ProviderConfigError, match="Resolve or download facebook/sam3 sam3.pt"):
        LocalSAM3DiscoveryBackend(model_path=missing).discover_concept(
            video_source(),
            {"concept": "object", "useVideoSession": False},
            RunContext(),
        )


def test_local_sam3_backend_lazy_import_failure_after_valid_model_path(tmp_path, monkeypatch):
    model_path = tmp_path / "sam3-model"
    model_path.write_text("placeholder")
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("sam3"):
            raise ImportError("test missing sam3")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(ProviderConfigError, match="optional sam3 package"):
        LocalSAM3DiscoveryBackend(model_path=model_path).discover_concept(
            video_source(),
            {"concept": "object", "useVideoSession": False},
            RunContext(),
        )


@pytest.mark.skipif(
    not os.environ.get("MOTIONJSON_RUN_REAL_SAM3_TESTS") or not os.environ.get("SAM3_LOCAL_MODEL"),
    reason="real SAM3 local tests require explicit opt-in and SAM3_LOCAL_MODEL",
)
def test_real_local_sam3_smoke_optional():
    result = LocalSAM3DiscoveryBackend.from_config({}).smoke_test(prompt="object")

    assert result["status"] == "ok"
