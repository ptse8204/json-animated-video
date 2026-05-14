import numpy as np
import pytest

from motionjson.cli import build_parser, build_provider
from motionjson.providers.base import BatchSegmentationRequest, ProviderConfigError, ProviderExecutionError
from motionjson.providers.mask_cache import MaskCache
from motionjson.providers.sam2 import HostedSAM2SegmentationProvider, LocalSAM2SegmentationProvider
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


def test_local_sam2_provider_lazy_import_failure_is_config_error():
    provider = LocalSAM2SegmentationProvider(source_video="input.mp4")

    with pytest.raises(ProviderConfigError, match="sam2-local requires"):
        provider.prepare(VideoInfo(width=8, height=6, source_fps=12, sample_fps=12, total_source_frames=3))


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


def test_hosted_sam2_provider_uses_injected_client_without_env_or_network(monkeypatch):
    monkeypatch.delenv("HOSTED_SEGMENTATION_API_KEY", raising=False)
    client = FakeHostedClient()
    provider = HostedSAM2SegmentationProvider(source_video="input.mp4", client=client, endpoint="https://example.invalid/sam2")
    provider.prepare(VideoInfo(width=5, height=4, source_fps=12, sample_fps=12, total_source_frames=1))

    mask = provider.segment(0, np.zeros((4, 5, 3), dtype=np.uint8), prompt_box=(2, 1, 2, 2))

    assert client.calls[0]["prompt_box"] == (2, 1, 2, 2)
    assert client.calls[0]["source_video"] == "input.mp4"
    assert mask.sum() == 4 * 255


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
