import builtins
import sys
import types
from pathlib import Path

import numpy as np
import pytest

from motionjson.cli import build_parser, build_provider
from motionjson.providers.base import BatchSegmentationRequest, ProviderConfigError, ProviderExecutionError
from motionjson.providers.mask_cache import MaskCache
from motionjson.providers.sam2 import (
    SAM2_HF_AUTO_MASKS_DEFAULT_MODEL,
    HostedSAM2SegmentationProvider,
    LocalSAM2AutomaticMaskProposalBackend,
    LocalSAM2HFAutomaticMaskProposalBackend,
    LocalSAM2SegmentationProvider,
)
from motionjson.video import VideoInfo


class FakeSAM2Predictor:
    def __init__(self):
        self.added = []
        self.propagated = False

    def init_state(self, video_path):
        return {"video_path": video_path}

    def reset_state(self, state):
        state["reset"] = True

    def add_new_points_or_box(self, **kwargs):
        self.added.append(kwargs)
        mask = np.zeros((1, 6, 8), dtype=np.float32)
        mask[:, 1:4, 2:5] = 3.0
        return kwargs["frame_idx"], [kwargs["obj_id"]], mask

    def propagate_in_video(self, state):
        self.propagated = True
        for frame_index in range(3):
            mask = np.zeros((1, 6, 8), dtype=np.float32)
            mask[:, 1 + frame_index : 4 + frame_index, 2:5] = 3.0
            yield frame_index, ["object_0"], mask


class FakeBatchSAM2Predictor:
    def __init__(self, response_count=None):
        self.calls = 0
        self.response_count = response_count

    def init_state(self, video_path):
        return {"video_path": video_path}

    def segment_batch(self, requests):
        self.calls += 1
        masks = []
        selected = requests if self.response_count is None else requests[: self.response_count]
        for request in selected:
            mask = np.zeros(request.frame_bgr.shape[:2], dtype=np.uint8)
            mask[1:3, 2:4] = 255
            masks.append(mask)
        return masks


class FakeHFAutoMaskGenerator:
    def __init__(self):
        self.calls = []

    def __call__(self, image, *, points_per_batch=64):
        self.calls.append({"pointsPerBatch": points_per_batch})
        mask = np.zeros((8, 8), dtype=np.uint8)
        mask[2:6, 2:6] = 255
        return {"masks": [mask], "boxes": [[2, 2, 4, 4]], "scores": [0.92]}


def test_local_sam2_provider_uses_injected_predictor_and_propagates_masks(tmp_path):
    predictor = FakeSAM2Predictor()
    cache = MaskCache(tmp_path / "cache")
    provider = LocalSAM2SegmentationProvider(
        source_video="input.mp4",
        predictor=predictor,
        prompt_frame_index=0,
        object_id="object_0",
        mask_cache=cache,
    )
    provider.prepare(VideoInfo(width=8, height=6, source_fps=12, sample_fps=12, total_source_frames=3))

    mask = provider.segment(2, np.zeros((6, 8, 3), dtype=np.uint8), prompt_point=(3, 2))
    cached = provider.segment(2, np.zeros((6, 8, 3), dtype=np.uint8), prompt_point=(3, 2))

    assert predictor.propagated
    assert predictor.added[0]["points"].tolist() == [[3.0, 2.0]]
    assert set(np.unique(mask)).issubset({0, 255})
    assert mask.sum() == 9 * 255
    assert cached.tolist() == mask.tolist()


def test_local_sam2_batch_provider_uses_mask_cache_for_native_batches(tmp_path):
    predictor = FakeBatchSAM2Predictor()
    cache = MaskCache(tmp_path / "cache")
    provider = LocalSAM2SegmentationProvider(
        source_video="input.mp4",
        predictor=predictor,
        prompt_point=(3, 2),
        mask_cache=cache,
    )
    provider.prepare(VideoInfo(width=5, height=4, source_fps=12, sample_fps=12, total_source_frames=2))
    requests = [
        BatchSegmentationRequest(frame_index=0, frame_bgr=np.zeros((4, 5, 3), dtype=np.uint8)),
        BatchSegmentationRequest(frame_index=1, frame_bgr=np.zeros((4, 5, 3), dtype=np.uint8)),
    ]

    first = provider.segment_batch(requests)
    second = provider.segment_batch(requests)
    summary = cache.summary()

    assert predictor.calls == 1
    assert len(first) == 2
    assert [mask.tolist() for mask in second] == [mask.tolist() for mask in first]
    assert summary["entries"] == 1
    assert summary["maskCount"] == 2
    assert summary["misses"] == 2
    assert summary["hits"] == 2


def test_local_sam2_native_batch_validates_response_count_without_cache():
    predictor = FakeBatchSAM2Predictor(response_count=1)
    provider = LocalSAM2SegmentationProvider(
        source_video="input.mp4",
        predictor=predictor,
        prompt_point=(3, 2),
    )
    provider.prepare(VideoInfo(width=5, height=4, source_fps=12, sample_fps=12, total_source_frames=2))
    requests = [
        BatchSegmentationRequest(frame_index=0, frame_bgr=np.zeros((4, 5, 3), dtype=np.uint8)),
        BatchSegmentationRequest(frame_index=1, frame_bgr=np.zeros((4, 5, 3), dtype=np.uint8)),
    ]

    with pytest.raises(ProviderExecutionError, match="different number of masks"):
        provider.segment_batch(requests)


def test_local_sam2_provider_accepts_injected_factory_without_checkpoint():
    calls = []

    def factory():
        calls.append("called")
        return FakeSAM2Predictor()

    provider = LocalSAM2SegmentationProvider(source_video="input.mp4", predictor_factory=factory)
    provider.prepare(VideoInfo(width=8, height=6, source_fps=12, sample_fps=12, total_source_frames=3))
    mask = provider.segment(0, np.zeros((6, 8, 3), dtype=np.uint8), prompt_box=(2, 1, 3, 3))

    assert calls == ["called"]
    assert mask.sum() == 9 * 255


def test_local_sam2_provider_normalizes_absolute_config_path_for_hydra(tmp_path):
    checkpoint = tmp_path / "sam2.1_hiera_large.pt"
    checkpoint.write_bytes(b"checkpoint")
    config = tmp_path / "sam2" / "configs" / "sam2.1" / "sam2.1_hiera_l.yaml"
    config.parent.mkdir(parents=True)
    config.write_text("model: test\n")
    frames = tmp_path / "frames"
    frames.mkdir()
    calls = {}

    def factory(model_cfg=None, checkpoint=None, device=None):
        calls["model_cfg"] = model_cfg
        calls["checkpoint"] = checkpoint
        calls["device"] = device
        return FakeSAM2Predictor()

    provider = LocalSAM2SegmentationProvider(
        source_video=frames,
        checkpoint=checkpoint,
        model_config=config,
        device="cuda",
        predictor_factory=factory,
    )

    provider.prepare(VideoInfo(width=8, height=6, source_fps=12, sample_fps=12, total_source_frames=3))

    assert calls == {
        "model_cfg": "configs/sam2.1/sam2.1_hiera_l.yaml",
        "checkpoint": str(checkpoint),
        "device": "cuda",
    }


def test_local_sam2_provider_exports_video_file_to_frame_directory(tmp_path, monkeypatch):
    video_path = tmp_path / "input.mp4"
    video_path.write_bytes(b"placeholder")
    frames_written = []

    class FakeVideoCapture:
        def __init__(self, path):
            self.path = path
            self.index = 0

        def isOpened(self):
            return True

        def read(self):
            if self.index >= 2:
                return False, None
            self.index += 1
            return True, np.zeros((4, 5, 3), dtype=np.uint8)

        def release(self):
            pass

    def fake_imwrite(path, frame):
        frames_written.append(path)
        Path(path).write_bytes(b"jpg")
        return True

    monkeypatch.setitem(sys.modules, "cv2", types.SimpleNamespace(VideoCapture=FakeVideoCapture, imwrite=fake_imwrite))
    predictor = FakeSAM2Predictor()
    provider = LocalSAM2SegmentationProvider(source_video=video_path, predictor=predictor)

    provider.prepare(VideoInfo(width=5, height=4, source_fps=12, sample_fps=12, total_source_frames=2))
    frame_dir = Path(provider.state["video_path"])

    assert frame_dir.is_dir()
    assert [Path(path).name for path in frames_written] == ["000000.jpg", "000001.jpg"]
    provider.close()
    assert not frame_dir.exists()


def test_local_sam2_provider_lazy_import_failure_is_config_error():
    provider = LocalSAM2SegmentationProvider(source_video="input.mp4")

    with pytest.raises(ProviderConfigError, match="sam2-local requires"):
        provider.prepare(VideoInfo(width=8, height=6, source_fps=12, sample_fps=12, total_source_frames=3))


def test_local_sam2_auto_proposal_backend_uses_injected_generator_without_checkpoint():
    class FakeGenerator:
        def generate(self, frame_rgb):
            mask = np.zeros(frame_rgb.shape[:2], dtype=np.uint8)
            mask[1:3, 2:4] = 255
            return [{"segmentation": mask, "bbox": [2, 1, 2, 2], "predicted_iou": 0.9}]

    backend = LocalSAM2AutomaticMaskProposalBackend(generator=FakeGenerator())

    records = backend.propose_masks(np.zeros((4, 5, 3), dtype=np.uint8), frame_index=0, config={})

    assert len(records) == 1
    assert records[0]["bbox"] == [2, 1, 2, 2]


def test_local_sam2_auto_proposal_backend_validates_missing_model_paths(tmp_path):
    backend = LocalSAM2AutomaticMaskProposalBackend(
        checkpoint=tmp_path / "missing-checkpoint.pt",
        model_config=tmp_path / "missing-config.yaml",
    )

    with pytest.raises(ProviderConfigError, match="checkpoint path"):
        backend.propose_masks(np.zeros((4, 5, 3), dtype=np.uint8), frame_index=0, config={})


def test_local_sam2_auto_proposal_backend_lazy_import_failure_after_valid_paths(tmp_path, monkeypatch):
    checkpoint = tmp_path / "sam2.pt"
    model_config = tmp_path / "sam2.yaml"
    checkpoint.write_text("checkpoint")
    model_config.write_text("config")
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("sam2"):
            raise ImportError("test missing sam2")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    backend = LocalSAM2AutomaticMaskProposalBackend(checkpoint=checkpoint, model_config=model_config)

    with pytest.raises(ProviderConfigError, match="optional sam2 package"):
        backend.propose_masks(np.zeros((4, 5, 3), dtype=np.uint8), frame_index=0, config={})


def test_local_sam2_hf_auto_masks_defaults_to_facebook_model(monkeypatch):
    captured = {}

    def fake_pipeline(task, *, model, device):
        captured["task"] = task
        captured["model"] = model
        captured["device"] = device
        return FakeHFAutoMaskGenerator()

    monkeypatch.setitem(sys.modules, "transformers", types.SimpleNamespace(pipeline=fake_pipeline))
    backend = LocalSAM2HFAutomaticMaskProposalBackend()

    records = backend.propose_masks(np.zeros((8, 8, 3), dtype=np.uint8), frame_index=0, config={})

    assert captured["task"] == "mask-generation"
    assert captured["model"] == SAM2_HF_AUTO_MASKS_DEFAULT_MODEL
    assert len(records) == 1


def test_local_sam2_hf_auto_masks_rejects_official_checkpoint_file(tmp_path, monkeypatch):
    checkpoint = tmp_path / "sam2.1_hiera_large.pt"
    checkpoint.write_bytes(b"placeholder")

    def fail_pipeline(*args, **kwargs):
        raise AssertionError("pipeline should not be called for official SAM2 checkpoint files")

    monkeypatch.setitem(sys.modules, "transformers", types.SimpleNamespace(pipeline=fail_pipeline))
    backend = LocalSAM2HFAutomaticMaskProposalBackend(model=str(checkpoint))

    with pytest.raises(ProviderConfigError, match="official SAM2 prompt-tracking setup"):
        backend.propose_masks(np.zeros((8, 8, 3), dtype=np.uint8), frame_index=0, config={})


def test_local_sam2_hf_auto_masks_rejects_checkpoint_before_transformers_import(tmp_path, monkeypatch):
    checkpoint = tmp_path / "sam2.1_hiera_large.pt"
    checkpoint.write_bytes(b"placeholder")
    real_import = builtins.__import__

    def fail_transformers_import(name, *args, **kwargs):
        if name == "transformers" or name.startswith("transformers."):
            raise AssertionError("transformers should not be imported for invalid SAM2 HF model input")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fail_transformers_import)
    backend = LocalSAM2HFAutomaticMaskProposalBackend(model=str(checkpoint))

    with pytest.raises(ProviderConfigError, match="official SAM2 prompt-tracking setup"):
        backend.propose_masks(np.zeros((8, 8, 3), dtype=np.uint8), frame_index=0, config={})


def test_local_sam2_hf_auto_masks_does_not_import_official_sam2(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "sam2" or name.startswith("sam2."):
            raise AssertionError("SAM2 HF automatic masks should not import official sam2")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    backend = LocalSAM2HFAutomaticMaskProposalBackend(generator=FakeHFAutoMaskGenerator())

    records = backend.propose_masks(np.zeros((8, 8, 3), dtype=np.uint8), frame_index=0, config={})

    assert len(records) == 1


class FakeHostedClient:
    def __init__(self):
        self.calls = []

    def segment_frame(self, **payload):
        self.calls.append(payload)
        mask = np.zeros((4, 5), dtype=np.uint8)
        mask[1:3, 2:4] = 255
        return {"mask": mask}


class FakeHostedBatchClient:
    def __init__(self, response_count=None):
        self.calls = 0
        self.payloads = []
        self.response_count = response_count

    def segment_batch(self, payloads):
        self.calls += 1
        self.payloads.append(payloads)
        responses = []
        selected = payloads if self.response_count is None else payloads[: self.response_count]
        for payload in selected:
            mask = np.zeros((4, 5), dtype=np.uint8)
            offset = payload["frame_index"]
            mask[1:3, 1 + offset : 3 + offset] = 255
            responses.append({"mask": mask})
        return responses


class FakeReplicateTransport:
    def __init__(self):
        self.calls = []

    def run(self, model, *, input):
        self.calls.append({"model": model, "input": dict(input)})
        first = np.zeros((4, 5), dtype=np.uint8)
        second = np.zeros((4, 5), dtype=np.uint8)
        first[1:3, 1:3] = 255
        second[1:3, 2:4] = 255
        return {"black_white_masks": [first, second]}


def test_hosted_sam2_provider_uses_injected_client_without_env_or_network(monkeypatch):
    monkeypatch.delenv("HOSTED_SEGMENTATION_API_KEY", raising=False)
    client = FakeHostedClient()
    provider = HostedSAM2SegmentationProvider(source_video="input.mp4", client=client, endpoint="https://example.invalid/sam2")
    provider.prepare(VideoInfo(width=5, height=4, source_fps=12, sample_fps=12, total_source_frames=1))

    mask = provider.segment(0, np.zeros((4, 5, 3), dtype=np.uint8), prompt_box=(2, 1, 2, 2))

    assert client.calls[0]["prompt_box"] == (2, 1, 2, 2)
    assert client.calls[0]["source_video"] == "input.mp4"
    assert mask.sum() == 4 * 255


def test_hosted_sam2_replicate_profile_downloads_video_masks_without_legacy_endpoint(monkeypatch):
    monkeypatch.delenv("HOSTED_SEGMENTATION_URL", raising=False)
    monkeypatch.delenv("HOSTED_SEGMENTATION_API_KEY", raising=False)
    transport = FakeReplicateTransport()
    provider = HostedSAM2SegmentationProvider(
        source_video="input.mp4",
        api_key="replicate-test-token-abcdef",
        config={
            "profile": "replicate-sam2-video",
            "model": "meta/sam-2-video",
            "allowNetwork": True,
            "acknowledgeCostPrivacy": True,
            "transport": transport,
        },
        prompt_point=(2, 1),
    )
    provider.prepare(VideoInfo(width=5, height=4, source_fps=12, sample_fps=12, total_source_frames=2))

    mask = provider.segment(1, np.zeros((4, 5, 3), dtype=np.uint8))

    assert mask[1, 2] == 255
    assert transport.calls[0]["model"] == "meta/sam-2-video"
    assert transport.calls[0]["input"]["click_coordinates"] == "[2,1]"
    assert transport.calls[0]["input"]["click_labels"] == "1"
    assert "black_white_masks" not in transport.calls[0]["input"]


def test_hosted_sam2_replicate_profile_requires_network_acknowledgement():
    provider = HostedSAM2SegmentationProvider(
        source_video="input.mp4",
        api_key="replicate-test-token-abcdef",
        config={"profile": "replicate-sam2-video", "transport": FakeReplicateTransport()},
        prompt_point=(2, 1),
    )
    provider.prepare(VideoInfo(width=5, height=4, source_fps=12, sample_fps=12, total_source_frames=2))

    with pytest.raises(ProviderConfigError, match="allowNetwork=true"):
        provider.segment(0, np.zeros((4, 5, 3), dtype=np.uint8))


def test_hosted_sam2_batch_provider_uses_mask_cache_for_native_batches(tmp_path):
    client = FakeHostedBatchClient()
    cache = MaskCache(tmp_path / "cache")
    provider = HostedSAM2SegmentationProvider(
        source_video="input.mp4",
        client=client,
        endpoint="https://example.invalid/sam2",
        prompt_box=(1, 1, 2, 2),
        mask_cache=cache,
    )
    provider.prepare(VideoInfo(width=5, height=4, source_fps=12, sample_fps=12, total_source_frames=2))
    requests = [
        BatchSegmentationRequest(frame_index=0, frame_bgr=np.zeros((4, 5, 3), dtype=np.uint8)),
        BatchSegmentationRequest(frame_index=1, frame_bgr=np.zeros((4, 5, 3), dtype=np.uint8)),
    ]

    first = provider.segment_batch(requests)
    second = provider.segment_batch(requests)
    summary = cache.summary()

    assert client.calls == 1
    assert client.payloads[0][0]["prompt_box"] == (1, 1, 2, 2)
    assert len(first) == 2
    assert [mask.tolist() for mask in second] == [mask.tolist() for mask in first]
    assert summary["entries"] == 1
    assert summary["maskCount"] == 2
    assert summary["misses"] == 2
    assert summary["hits"] == 2


def test_hosted_sam2_native_batch_validates_response_count_without_cache():
    client = FakeHostedBatchClient(response_count=1)
    provider = HostedSAM2SegmentationProvider(
        source_video="input.mp4",
        client=client,
        endpoint="https://example.invalid/sam2",
        prompt_box=(1, 1, 2, 2),
    )
    provider.prepare(VideoInfo(width=5, height=4, source_fps=12, sample_fps=12, total_source_frames=2))
    requests = [
        BatchSegmentationRequest(frame_index=0, frame_bgr=np.zeros((4, 5, 3), dtype=np.uint8)),
        BatchSegmentationRequest(frame_index=1, frame_bgr=np.zeros((4, 5, 3), dtype=np.uint8)),
    ]

    with pytest.raises(ProviderExecutionError, match="different number of masks"):
        provider.segment_batch(requests)


def test_hosted_sam2_provider_fails_before_network_when_unconfigured(monkeypatch):
    monkeypatch.delenv("HOSTED_SEGMENTATION_URL", raising=False)
    monkeypatch.delenv("HOSTED_SEGMENTATION_API_KEY", raising=False)
    provider = HostedSAM2SegmentationProvider(source_video="input.mp4")

    with pytest.raises(ProviderConfigError, match="sam2-hosted requires"):
        provider.prepare(VideoInfo(width=5, height=4, source_fps=12, sample_fps=12, total_source_frames=1))


def test_hosted_sam2_provider_requires_explicit_network_opt_in(monkeypatch):
    monkeypatch.setenv("HOSTED_SEGMENTATION_API_KEY", "test-token")
    provider = HostedSAM2SegmentationProvider(source_video="input.mp4", endpoint="https://example.invalid/sam2")

    with pytest.raises(ProviderConfigError, match="does not make network calls by default"):
        provider.prepare(VideoInfo(width=5, height=4, source_fps=12, sample_fps=12, total_source_frames=1))


def test_cli_supports_explicit_sam2_modes_and_cache_disable():
    parser = build_parser()
    args = parser.parse_args(["extract", "input.mp4", "--mask-provider", "sam2-local", "--prompt-point", "3,2", "--no-mask-cache"])

    provider = build_provider(args)

    assert provider.segmentation_provider.mask_cache is None
    assert isinstance(provider.segmentation_provider, LocalSAM2SegmentationProvider)


def test_cli_reads_local_sam2_defaults_from_env(monkeypatch):
    monkeypatch.setenv("SAM2_LOCAL_CHECKPOINT", "/tmp/checkpoint.pt")
    monkeypatch.setenv("SAM2_LOCAL_CONFIG", "configs/sam2.yaml")
    monkeypatch.setenv("SAM2_LOCAL_DEVICE", "mps")
    parser = build_parser()
    args = parser.parse_args(["extract", "input.mp4", "--mask-provider", "sam2-local", "--prompt-box", "1,2,3,4", "--no-mask-cache"])

    provider = build_provider(args)

    assert provider.segmentation_provider.checkpoint == "/tmp/checkpoint.pt"
    assert provider.segmentation_provider.model_config == "configs/sam2.yaml"
    assert provider.segmentation_provider.device == "mps"
