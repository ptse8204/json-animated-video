from __future__ import annotations

import base64
import io
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

import numpy as np
from PIL import Image

from ..video import VideoInfo
from .base import BatchSegmentationRequest, ProviderConfigError, ProviderExecutionError
from .mask_cache import MaskCache, normalize_binary_mask

SAM2_HF_AUTO_MASKS_DEFAULT_MODEL = "facebook/sam2.1-hiera-large"


class JsonTransport(Protocol):
    def post_json(self, url: str, payload: Mapping[str, Any], *, headers: Mapping[str, str] | None = None) -> Mapping[str, Any]:
        """Post JSON and return decoded JSON."""


@dataclass
class LocalSAM2AutomaticMaskProposalBackend:
    """Optional SAM2 automatic mask proposal backend with lazy imports.

    The class is deliberately small: tests can inject a fake generator or
    generator_factory, while real local runs only import SAM2 after checkpoint
    and config paths have been supplied.
    """

    checkpoint: str | Path | None = None
    model_config: str | Path | None = None
    device: str = "cpu"
    generator: Any | None = None
    generator_factory: Any | None = None
    predictor_factory: Any | None = None
    provider_name: str = "sam2-local"
    _generator: Any | None = field(default=None, init=False)

    @classmethod
    def from_config(cls, config: Mapping[str, Any]) -> "LocalSAM2AutomaticMaskProposalBackend":
        checkpoint = (
            config.get("sam2Checkpoint")
            or config.get("sam2_checkpoint")
            or config.get("checkpoint")
            or os.environ.get("SAM2_LOCAL_CHECKPOINT")
        )
        model_config = (
            config.get("sam2ModelConfig")
            or config.get("sam2_model_config")
            or config.get("model_config")
            or os.environ.get("SAM2_LOCAL_CONFIG")
        )
        device = str(config.get("sam2Device") or config.get("sam2_device") or config.get("device") or os.environ.get("SAM2_LOCAL_DEVICE") or "cpu")
        return cls(checkpoint=checkpoint, model_config=model_config, device=device)

    def propose_masks(self, frame_rgb: np.ndarray, *, frame_index: int, config: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
        generator = self._ensure_generator()
        if hasattr(generator, "generate"):
            records = generator.generate(frame_rgb)
        elif hasattr(generator, "propose_masks"):
            records = generator.propose_masks(frame_rgb, frame_index=frame_index, config=config)
        elif callable(generator):
            try:
                records = generator(frame_rgb, frame_index=frame_index, config=config)
            except TypeError:
                records = generator(frame_rgb)
        else:
            raise ProviderExecutionError("SAM2 automatic mask generator must expose generate(), propose_masks(), or be callable.")
        return self._normalize_records(records)

    def track_candidate(
        self,
        video: Any,
        *,
        frame_index: int,
        object_id: str,
        box: tuple[int, int, int, int] | None,
        mask: np.ndarray,
        config: Mapping[str, Any],
    ) -> Sequence[np.ndarray]:
        """Propagate a selected/proposed candidate with SAM2 video prediction."""

        prompt_box = box or _mask_box(mask)
        provider = LocalSAM2SegmentationProvider(
            source_video=getattr(video, "path", ""),
            checkpoint=self.checkpoint,
            model_config=self.model_config,
            device=str(config.get("sam2Device") or config.get("sam2_device") or self.device or "cpu"),
            prompt_frame_index=frame_index,
            object_id=object_id,
            prompt_box=prompt_box,
            predictor_factory=self.predictor_factory,
        )
        provider.prepare(video.info)
        masks: list[np.ndarray] = []
        try:
            for frame in video.frames:
                frame_bgr = np.ascontiguousarray(frame.rgb[:, :, ::-1])
                masks.append(provider.segment(int(getattr(frame, "index", 0)), frame_bgr))
        finally:
            provider.close()
        return masks

    def _ensure_generator(self) -> Any:
        if self.generator is not None:
            return self.generator
        if self._generator is not None:
            return self._generator
        if self.generator_factory is None:
            self.generator_factory = self._default_generator_factory()
        self._generator = self.generator_factory()
        return self._generator

    def _default_generator_factory(self) -> Any:
        checkpoint = str(self.checkpoint or os.environ.get("SAM2_LOCAL_CHECKPOINT") or "")
        model_config = str(self.model_config or os.environ.get("SAM2_LOCAL_CONFIG") or "")
        if not checkpoint or not model_config:
            raise ProviderConfigError(
                "sam2-local automatic proposals require SAM2_LOCAL_CHECKPOINT and SAM2_LOCAL_CONFIG "
                "or discovery.config.sam2Checkpoint/sam2ModelConfig. Heavy SAM2 dependencies remain optional."
            )
        if not Path(checkpoint).exists():
            raise ProviderConfigError("Configured SAM2 checkpoint path does not point to an existing file.")
        if not Path(model_config).exists():
            raise ProviderConfigError("Configured SAM2 model config path does not point to an existing file.")
        try:
            from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator  # type: ignore
            from sam2.build_sam import build_sam2  # type: ignore
        except ImportError as exc:
            raise ProviderConfigError(
                "SAM2 automatic proposals require the optional sam2 package with automatic mask generation support. "
                "Install SAM2/torch separately or use discovery.config.mock=true."
            ) from exc

        def factory() -> Any:
            model = build_sam2(model_config, checkpoint, device=self.device)
            return SAM2AutomaticMaskGenerator(model)

        return factory

    @staticmethod
    def _normalize_records(records: Any) -> list[Mapping[str, Any]]:
        if records is None:
            return []
        if isinstance(records, Mapping):
            nested = records.get("masks")
            if nested is None:
                nested = records.get("proposals")
            if nested is None:
                return [dict(records)]
            records = nested
        if isinstance(records, np.ndarray):
            return [{"segmentation": records}]
        if not isinstance(records, Sequence) or isinstance(records, (str, bytes, bytearray)):
            raise ProviderExecutionError("SAM2 automatic mask generator returned an unsupported response shape.")
        normalized: list[Mapping[str, Any]] = []
        for item in records:
            if isinstance(item, Mapping):
                normalized.append(dict(item))
            elif isinstance(item, np.ndarray):
                normalized.append({"segmentation": item})
            else:
                raise ProviderExecutionError("SAM2 automatic mask records must be mappings or mask arrays.")
        return normalized


@dataclass
class LocalSAM2HFAutomaticMaskProposalBackend:
    """SAM2 automatic masks through Hugging Face Transformers.

    This is intentionally separate from the official local SAM2 checkpoint and
    YAML-config provider. It accepts only `from_pretrained` inputs: a Hugging
    Face repo id or a local HF model directory.
    """

    model: str | Path | None = None
    device: str = "cpu"
    generator: Any | None = None
    generator_factory: Any | None = None
    provider_name: str = "sam2-hf-auto-masks"
    _generator: Any | None = field(default=None, init=False)

    @classmethod
    def from_config(cls, config: Mapping[str, Any]) -> "LocalSAM2HFAutomaticMaskProposalBackend":
        model = (
            config.get("sam2HfModel")
            or config.get("sam2_hf_model")
            or config.get("sam2AutoMaskModel")
            or config.get("sam2_auto_mask_model")
            or os.environ.get("SAM2_HF_AUTO_MASKS_MODEL")
            or SAM2_HF_AUTO_MASKS_DEFAULT_MODEL
        )
        device = str(config.get("sam2HfDevice") or config.get("sam2_hf_device") or config.get("device") or os.environ.get("SAM2_HF_DEVICE") or "cpu")
        return cls(model=model, device=device)

    def propose_masks(self, frame_rgb: np.ndarray, *, frame_index: int, config: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
        generator = self._ensure_generator(config)
        image = Image.fromarray(np.asarray(frame_rgb, dtype=np.uint8)).convert("RGB")
        if hasattr(generator, "generate"):
            records = generator.generate(np.asarray(image))
        elif hasattr(generator, "propose_masks"):
            records = generator.propose_masks(np.asarray(image), frame_index=frame_index, config=config)
        elif callable(generator):
            try:
                records = generator(image, points_per_batch=int(config.get("pointsPerBatch") or config.get("points_per_batch") or 64))
            except TypeError:
                try:
                    records = generator(np.asarray(image), frame_index=frame_index, config=config)
                except TypeError:
                    records = generator(image)
        else:
            raise ProviderExecutionError("SAM2 HF automatic mask generator must expose generate(), propose_masks(), or be callable.")
        return LocalSAM2AutomaticMaskProposalBackend._normalize_records(records)

    def _ensure_generator(self, config: Mapping[str, Any]) -> Any:
        if self.generator is not None:
            return self.generator
        if self._generator is not None:
            return self._generator
        if self.generator_factory is not None:
            self._generator = self.generator_factory()
            return self._generator
        model_id = _hf_sam2_model_id(config, fallback=self.model)
        try:
            from transformers import pipeline  # type: ignore
        except ImportError as exc:
            raise ProviderConfigError(
                "SAM2 HF automatic masks require Hugging Face Transformers. Use Model setup to install/cache "
                "the SAM2 HF fallback, or choose official SAM2 prompt tracking in Advanced."
            ) from exc
        try:
            self._generator = pipeline("mask-generation", model=model_id, device=_transformers_device(self.device))
        except Exception as exc:  # pragma: no cover - depends on optional runtime/model access.
            raise ProviderConfigError(f"SAM2 HF automatic-mask pipeline could not be initialized: {exc}") from exc
        return self._generator


def _hf_sam2_model_id(config: Mapping[str, Any], *, fallback: str | Path | None = None) -> str:
    value = (
        config.get("sam2HfModel")
        or config.get("sam2_hf_model")
        or config.get("sam2AutoMaskModel")
        or config.get("sam2_auto_mask_model")
        or os.environ.get("SAM2_HF_AUTO_MASKS_MODEL")
        or fallback
        or SAM2_HF_AUTO_MASKS_DEFAULT_MODEL
    )
    raw = str(value or "").strip() or SAM2_HF_AUTO_MASKS_DEFAULT_MODEL
    if "/" in raw and not raw.startswith(("/", ".", "~")) and not raw.endswith(".pt"):
        return raw
    path = Path(raw).expanduser()
    if path.exists() and path.is_dir():
        return str(path)
    if path.is_file() or raw.endswith(".pt"):
        raise ProviderConfigError(
            "SAM2 HF automatic masks use a Hugging Face repo id or local HF model directory. "
            "A single .pt checkpoint belongs to the official SAM2 prompt-tracking setup, not the SAM2 HF automatic-mask fallback."
        )
    raise ProviderConfigError(
        f"SAM2 HF automatic-mask model is neither a repo id nor an existing local model directory: {raw}. "
        "Use facebook/sam2.1-hiera-large or cache a local HF model directory from Model setup."
    )


def _transformers_device(device: str) -> int | str:
    normalized = str(device or "").strip().lower()
    if normalized.startswith("cuda"):
        return 0
    if normalized == "mps":
        return "mps"
    return -1


@dataclass
class LocalSAM2SegmentationProvider:
    """SAM2-compatible local video segmentation provider with optional imports."""

    source_video: str | Path
    checkpoint: str | Path | None = None
    model_config: str | Path | None = None
    device: str = "cpu"
    prompt_frame_index: int = 0
    object_id: str = "object_0"
    sam2_object_id: int = 1
    prompt_point: tuple[int, int] | None = None
    prompt_box: tuple[int, int, int, int] | None = None
    predictor: Any | None = None
    predictor_factory: Any | None = None
    mask_cache: MaskCache | None = None
    cache_config: Mapping[str, Any] | None = None
    video_metadata: VideoInfo | None = field(default=None, init=False)
    state: Any | None = field(default=None, init=False)
    _masks: dict[int, np.ndarray] = field(default_factory=dict, init=False)
    _prompted: bool = field(default=False, init=False)
    provider_name: str = "sam2-local"

    def prepare(self, video_metadata: VideoInfo) -> None:
        self.video_metadata = video_metadata
        if self.predictor is None:
            self.predictor = self._build_predictor()
        if hasattr(self.predictor, "init_state"):
            try:
                self.state = self.predictor.init_state(video_path=str(self.source_video))
            except TypeError:
                self.state = self.predictor.init_state(str(self.source_video))
        elif hasattr(self.predictor, "prepare"):
            self.state = self.predictor.prepare(str(self.source_video), video_metadata)
        else:
            self.state = None

    def segment(
        self,
        frame_index: int,
        frame_bgr: np.ndarray,
        *,
        prompt_point: tuple[int, int] | None = None,
        prompt_box: tuple[int, int, int, int] | None = None,
    ) -> np.ndarray:
        point = prompt_point or self.prompt_point
        box = prompt_box or self.prompt_box
        cache_key = self._cache_key(frame_index, point, box)
        if self.mask_cache is not None:
            cached = self.mask_cache.get(cache_key, frame_index=frame_index)
            if cached is not None:
                return cached

        if frame_index not in self._masks:
            self._ensure_prompted(point, box)
        if frame_index not in self._masks:
            self._masks[frame_index] = self._direct_segment(frame_index, frame_bgr, point, box)

        mask = normalize_binary_mask(self._masks[frame_index])
        if self.mask_cache is not None:
            self.mask_cache.set(cache_key, mask, frame_index=frame_index, metadata={"provider": "sam2-local", "object_id": self.object_id})
        return mask

    def segment_batch(self, requests: Sequence[BatchSegmentationRequest]) -> Sequence[np.ndarray]:
        requests = list(requests)
        if not requests:
            return []
        if self.mask_cache is None:
            if self.predictor is not None and hasattr(self.predictor, "segment_batch"):
                result = list(self.predictor.segment_batch(requests))
                if len(result) != len(requests):
                    raise ProviderExecutionError("SAM2 batch predictor returned a different number of masks than requested.")
                return [normalize_binary_mask(mask) for mask in result]
            return [
                self.segment(
                    request.frame_index,
                    request.frame_bgr,
                    prompt_point=request.prompt_point,
                    prompt_box=request.prompt_box,
                )
                for request in requests
            ]

        results: list[np.ndarray | None] = [None] * len(requests)
        misses: list[tuple[int, BatchSegmentationRequest, tuple[int, int] | None, tuple[int, int, int, int] | None, str]] = []
        for index, request in enumerate(requests):
            point = request.prompt_point or self.prompt_point
            box = request.prompt_box or self.prompt_box
            cache_key = self._cache_key(request.frame_index, point, box)
            cached = self.mask_cache.get(cache_key, frame_index=request.frame_index)
            if cached is not None:
                results[index] = cached
            else:
                misses.append((index, request, point, box, cache_key))

        if misses and self.predictor is not None and hasattr(self.predictor, "segment_batch"):
            miss_requests = [
                BatchSegmentationRequest(
                    frame_index=request.frame_index,
                    frame_bgr=request.frame_bgr,
                    prompt_point=point,
                    prompt_box=box,
                )
                for _index, request, point, box, _cache_key in misses
            ]
            batch_result = list(self.predictor.segment_batch(miss_requests))
            if len(batch_result) != len(misses):
                raise ProviderExecutionError("SAM2 batch predictor returned a different number of masks than requested.")
            for (index, request, _point, _box, cache_key), mask in zip(misses, batch_result):
                normalized = normalize_binary_mask(mask)
                self._masks[request.frame_index] = normalized
                self.mask_cache.set(cache_key, normalized, frame_index=request.frame_index, metadata={"provider": "sam2-local", "object_id": self.object_id})
                results[index] = normalized
        else:
            for index, request, point, box, _cache_key in misses:
                results[index] = self.segment(
                    request.frame_index,
                    request.frame_bgr,
                    prompt_point=point,
                    prompt_box=box,
                )

        complete_results: list[np.ndarray] = []
        for mask in results:
            if mask is None:
                raise ProviderExecutionError("SAM2 batch segmentation did not produce masks for all requests.")
            complete_results.append(mask)
        return complete_results

    def close(self) -> None:
        if self.predictor is not None and hasattr(self.predictor, "close"):
            self.predictor.close()

    def performance_summary(self) -> dict[str, Any]:
        return {
            "providerName": self.provider_name,
            "cost": {"estimatedCostUnits": 0.0, "unit": "local", "costStatus": "zero_local_runtime"},
            "cache": self.mask_cache.summary() if self.mask_cache is not None else None,
        }

    def _build_predictor(self) -> Any:
        if self.predictor_factory is None:
            if not self.checkpoint or not self.model_config:
                raise ProviderConfigError(
                    "sam2-local requires --sam2-checkpoint and --sam2-model-config unless a predictor or predictor_factory is injected. "
                    "Install SAM2 separately and keep torch/SAM2 out of default MotionJSON dependencies. "
                    "Run `python3 -m motionjson.cli backend diagnostics --text` for setup status."
                )
            try:
                from sam2.build_sam import build_sam2_video_predictor  # type: ignore
            except ImportError as exc:
                raise ProviderConfigError(
                    "SAM2 is not installed. Install Meta SAM2 and torch in your local environment, then pass "
                    "--sam2-checkpoint and --sam2-model-config, or inject a fake predictor for tests. "
                    "Run `python3 -m motionjson.cli backend diagnostics --text` for setup status."
                ) from exc
            self.predictor_factory = build_sam2_video_predictor

        model_cfg = str(self.model_config) if self.model_config else None
        checkpoint = str(self.checkpoint) if self.checkpoint else None
        try:
            return self.predictor_factory(
                model_cfg=model_cfg,
                checkpoint=checkpoint,
                device=self.device,
            )
        except TypeError:
            try:
                return self.predictor_factory(model_cfg, checkpoint, device=self.device)
            except TypeError:
                return self.predictor_factory()

    def _ensure_prompted(self, prompt_point: tuple[int, int] | None, prompt_box: tuple[int, int, int, int] | None) -> None:
        if self._prompted:
            return
        if prompt_point is None and prompt_box is None:
            raise ProviderConfigError("sam2-local requires a --prompt-point x,y or --prompt-box x,y,w,h prompt.")
        if self.predictor is None:
            raise ProviderExecutionError("sam2-local predictor was not initialized.")

        if hasattr(self.predictor, "reset_state") and self.state is not None:
            self.predictor.reset_state(self.state)

        if hasattr(self.predictor, "add_new_points_or_box"):
            points = np.array([prompt_point], dtype=np.float32) if prompt_point is not None else None
            labels = np.array([1], dtype=np.int32) if prompt_point is not None else None
            box = np.array(self._box_xyxy(prompt_box), dtype=np.float32) if prompt_box is not None else None
            result = self.predictor.add_new_points_or_box(
                inference_state=self.state,
                frame_idx=self.prompt_frame_index,
                obj_id=self.sam2_object_id,
                points=points,
                labels=labels,
                box=box,
            )
            self._store_result(result)
        elif hasattr(self.predictor, "add_prompt"):
            result = self.predictor.add_prompt(
                self.state,
                frame_index=self.prompt_frame_index,
                object_id=self.object_id,
                point=prompt_point,
                box=prompt_box,
            )
            self._store_result(result)
        else:
            raise ProviderExecutionError("SAM2 predictor does not expose add_new_points_or_box() or add_prompt().")

        if hasattr(self.predictor, "propagate_in_video"):
            for result in self.predictor.propagate_in_video(self.state):
                self._store_result(result)
        self._prompted = True

    def _direct_segment(
        self,
        frame_index: int,
        frame_bgr: np.ndarray,
        prompt_point: tuple[int, int] | None,
        prompt_box: tuple[int, int, int, int] | None,
    ) -> np.ndarray:
        if self.predictor is None:
            raise ProviderExecutionError("sam2-local predictor was not initialized.")
        if hasattr(self.predictor, "segment"):
            return normalize_binary_mask(
                self.predictor.segment(frame_index, frame_bgr, prompt_point=prompt_point, prompt_box=prompt_box)
            )
        if hasattr(self.predictor, "get_mask"):
            return normalize_binary_mask(self.predictor.get_mask(frame_index, frame_bgr))
        raise ProviderExecutionError(f"SAM2 propagation did not return frame {frame_index} and no direct segment method is available.")

    def _store_result(self, result: Any) -> None:
        if result is None:
            return
        if isinstance(result, Mapping):
            frame_index = int(result.get("frame_index", result.get("frame_idx", self.prompt_frame_index)))
            mask = result.get("mask", result.get("mask_logits"))
            if mask is not None:
                self._masks[frame_index] = normalize_binary_mask(_to_numpy(mask))
            return
        if isinstance(result, tuple) and len(result) >= 3:
            frame_index = int(result[0])
            object_ids = list(result[1])
            masks = result[2]
            if self.sam2_object_id in object_ids:
                mask_index = object_ids.index(self.sam2_object_id)
            elif self.object_id in object_ids:
                mask_index = object_ids.index(self.object_id)
            else:
                mask_index = 0
            self._masks[frame_index] = normalize_binary_mask(_to_numpy(masks[mask_index]))

    def _cache_key(self, frame_index: int, prompt_point: tuple[int, int] | None, prompt_box: tuple[int, int, int, int] | None) -> str:
        if self.mask_cache is None:
            return ""
        return self.mask_cache.key_for(
            provider="sam2-local",
            config={
                "checkpoint": str(self.checkpoint) if self.checkpoint else None,
                "model_config": str(self.model_config) if self.model_config else None,
                "device": self.device,
                "prompt_frame_index": self.prompt_frame_index,
                "sam2_object_id": self.sam2_object_id,
                **dict(self.cache_config or {}),
            },
            source=self.source_video,
            prompt={"point": prompt_point, "box": prompt_box},
            frame_index=frame_index,
            object_id=self.object_id,
            metadata=self._metadata_for_cache(),
        )

    def _metadata_for_cache(self) -> Mapping[str, Any]:
        if self.video_metadata is None:
            return {}
        return {
            "width": self.video_metadata.width,
            "height": self.video_metadata.height,
            "source_fps": self.video_metadata.source_fps,
            "sample_fps": self.video_metadata.sample_fps,
        }

    @staticmethod
    def _box_xyxy(box: tuple[int, int, int, int] | None) -> tuple[int, int, int, int] | None:
        if box is None:
            return None
        x, y, w, h = box
        return x, y, x + w, y + h


@dataclass
class HostedSAM2SegmentationProvider:
    """Hosted SAM2-compatible provider with injected client/transport by default."""

    source_video: str | Path
    endpoint: str | None = None
    api_key: str | None = None
    config: Mapping[str, Any] | None = None
    auth_env: str = "HOSTED_SEGMENTATION_API_KEY"
    endpoint_env: str = "HOSTED_SEGMENTATION_URL"
    prompt_frame_index: int = 0
    object_id: str = "object_0"
    prompt_point: tuple[int, int] | None = None
    prompt_box: tuple[int, int, int, int] | None = None
    client: Any | None = None
    transport: JsonTransport | None = None
    allow_network: bool = False
    mask_cache: MaskCache | None = None
    video_metadata: VideoInfo | None = field(default=None, init=False)
    _endpoint: str | None = field(default=None, init=False)
    _token: str | None = field(default=None, init=False)
    provider_name: str = "sam2-hosted"

    def prepare(self, video_metadata: VideoInfo) -> None:
        self.video_metadata = video_metadata
        self._endpoint = self.endpoint or os.environ.get(self.endpoint_env)
        self._token = self.api_key or (os.environ.get(self.auth_env) if self.auth_env else None)
        if self.client is None:
            from .hosted_sam import hosted_sam2_client_from_config

            base_config = dict(self.config or {})
            runtime_config = {
                **base_config,
                "apiKey": self._token or base_config.get("apiKey") or base_config.get("api_key"),
                "endpoint": self._endpoint or base_config.get("endpoint"),
                "promptFrame": self.prompt_frame_index,
                "objectId": self.object_id,
                "promptPoint": self.prompt_point,
                "promptBox": self.prompt_box,
            }
            self.client = hosted_sam2_client_from_config(self.source_video, runtime_config)
            if self.client is not None:
                return
        if self.client is not None:
            return
        if not self._endpoint:
            raise ProviderConfigError(f"sam2-hosted requires --sam2-endpoint or {self.endpoint_env}.")
        if not self._token:
            raise ProviderConfigError(f"sam2-hosted requires auth in {self.auth_env}; no token was read.")
        if self.transport is None:
            if not self.allow_network:
                raise ProviderConfigError(
                    "sam2-hosted does not make network calls by default. Inject a client/transport for tests or pass "
                    "--sam2-hosted-allow-network with an explicit endpoint and auth env for real hosted use."
                )
            self.transport = _UrlLibJsonTransport()

    def segment(
        self,
        frame_index: int,
        frame_bgr: np.ndarray,
        *,
        prompt_point: tuple[int, int] | None = None,
        prompt_box: tuple[int, int, int, int] | None = None,
    ) -> np.ndarray:
        point = prompt_point or self.prompt_point
        box = prompt_box or self.prompt_box
        cache_key = self._cache_key(frame_index, point, box)
        if self.mask_cache is not None:
            cached = self.mask_cache.get(cache_key, frame_index=frame_index)
            if cached is not None:
                return cached

        if point is None and box is None:
            raise ProviderConfigError("sam2-hosted requires a --prompt-point x,y or --prompt-box x,y,w,h prompt.")
        response = self._call_hosted(frame_index, point, box)
        mask = normalize_binary_mask(self._extract_mask(response))
        if self.mask_cache is not None:
            self.mask_cache.set(cache_key, mask, frame_index=frame_index, metadata={"provider": "sam2-hosted", "object_id": self.object_id})
        return mask

    def segment_batch(self, requests: Sequence[BatchSegmentationRequest]) -> Sequence[np.ndarray]:
        requests = list(requests)
        if not requests:
            return []
        if self.mask_cache is None:
            if self.client is not None and hasattr(self.client, "segment_batch"):
                responses = list(
                    self.client.segment_batch(
                        [
                            {
                                "frame_index": request.frame_index,
                                "prompt_point": request.prompt_point or self.prompt_point,
                                "prompt_box": request.prompt_box or self.prompt_box,
                            }
                            for request in requests
                        ]
                    )
                )
                if len(responses) != len(requests):
                    raise ProviderExecutionError("Hosted SAM2 batch client returned a different number of masks than requested.")
                return [normalize_binary_mask(self._extract_mask(response)) for response in responses]
            return [
                self.segment(
                    request.frame_index,
                    request.frame_bgr,
                    prompt_point=request.prompt_point,
                    prompt_box=request.prompt_box,
                )
                for request in requests
            ]

        results: list[np.ndarray | None] = [None] * len(requests)
        misses: list[tuple[int, BatchSegmentationRequest, tuple[int, int] | None, tuple[int, int, int, int] | None, str]] = []
        for index, request in enumerate(requests):
            point = request.prompt_point or self.prompt_point
            box = request.prompt_box or self.prompt_box
            cache_key = self._cache_key(request.frame_index, point, box)
            cached = self.mask_cache.get(cache_key, frame_index=request.frame_index)
            if cached is not None:
                results[index] = cached
            else:
                misses.append((index, request, point, box, cache_key))

        if misses and self.client is not None and hasattr(self.client, "segment_batch"):
            responses = list(
                self.client.segment_batch(
                    [
                        {
                            "frame_index": request.frame_index,
                            "prompt_point": point,
                            "prompt_box": box,
                        }
                        for _index, request, point, box, _cache_key in misses
                    ]
                )
            )
            if len(responses) != len(misses):
                raise ProviderExecutionError("Hosted SAM2 batch client returned a different number of masks than requested.")
            for (index, request, _point, _box, cache_key), response in zip(misses, responses):
                mask = normalize_binary_mask(self._extract_mask(response))
                self.mask_cache.set(cache_key, mask, frame_index=request.frame_index, metadata={"provider": "sam2-hosted", "object_id": self.object_id})
                results[index] = mask
        else:
            for index, request, point, box, _cache_key in misses:
                results[index] = self.segment(
                    request.frame_index,
                    request.frame_bgr,
                    prompt_point=point,
                    prompt_box=box,
                )

        complete_results: list[np.ndarray] = []
        for mask in results:
            if mask is None:
                raise ProviderExecutionError("Hosted SAM2 batch segmentation did not produce masks for all requests.")
            complete_results.append(mask)
        return complete_results

    def close(self) -> None:
        if self.client is not None and hasattr(self.client, "close"):
            self.client.close()

    def performance_summary(self) -> dict[str, Any]:
        return {
            "providerName": self.provider_name,
            "cost": {"estimatedCostUnits": None, "unit": "provider_request", "costStatus": "unknown_hosted_provider"},
            "cache": self.mask_cache.summary() if self.mask_cache is not None else None,
        }

    def _call_hosted(
        self,
        frame_index: int,
        prompt_point: tuple[int, int] | None,
        prompt_box: tuple[int, int, int, int] | None,
    ) -> Mapping[str, Any] | np.ndarray:
        payload = {
            "source_video": str(self.source_video),
            "frame_index": frame_index,
            "prompt_frame_index": self.prompt_frame_index,
            "object_id": self.object_id,
            "prompt_point": prompt_point,
            "prompt_box": prompt_box,
            "config": dict(self.config or {}),
            "video": self._metadata_for_request(),
        }
        if self.client is not None:
            if hasattr(self.client, "segment_frame"):
                return self.client.segment_frame(**payload)
            if hasattr(self.client, "segment"):
                return self.client.segment(**payload)
            raise ProviderExecutionError("Hosted SAM2 client must expose segment_frame() or segment().")

        if self.transport is None or self._endpoint is None:
            raise ProviderConfigError("sam2-hosted is not configured with a client, transport, or endpoint.")
        headers = {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}
        return self.transport.post_json(self._endpoint, payload, headers=headers)

    def _extract_mask(self, response: Mapping[str, Any] | np.ndarray) -> np.ndarray:
        if isinstance(response, np.ndarray):
            return response
        if "mask" in response:
            return np.asarray(response["mask"])
        if "mask_png_base64" in response:
            data = base64.b64decode(response["mask_png_base64"])
            return np.array(Image.open(io.BytesIO(data)).convert("L"))
        raise ProviderExecutionError("Hosted SAM2 response must include 'mask' or 'mask_png_base64'.")

    def _cache_key(self, frame_index: int, prompt_point: tuple[int, int] | None, prompt_box: tuple[int, int, int, int] | None) -> str:
        if self.mask_cache is None:
            return ""
        return self.mask_cache.key_for(
            provider="sam2-hosted",
            config={
                "endpoint": self._endpoint or self.endpoint or os.environ.get(self.endpoint_env),
                "prompt_frame_index": self.prompt_frame_index,
                **dict(self.config or {}),
            },
            source=self.source_video,
            prompt={"point": prompt_point, "box": prompt_box},
            frame_index=frame_index,
            object_id=self.object_id,
            metadata=self._metadata_for_request(),
        )

    def _metadata_for_request(self) -> Mapping[str, Any]:
        if self.video_metadata is None:
            return {}
        return {
            "width": self.video_metadata.width,
            "height": self.video_metadata.height,
            "source_fps": self.video_metadata.source_fps,
            "sample_fps": self.video_metadata.sample_fps,
            "total_source_frames": self.video_metadata.total_source_frames,
        }


class _UrlLibJsonTransport:
    def post_json(self, url: str, payload: Mapping[str, Any], *, headers: Mapping[str, str] | None = None) -> Mapping[str, Any]:
        from urllib import request

        data = json.dumps(payload).encode("utf-8")
        req = request.Request(url, data=data, headers=dict(headers or {}), method="POST")
        with request.urlopen(req, timeout=120) as response:  # noqa: S310 - explicit opt-in network path.
            return json.loads(response.read().decode("utf-8"))


def _mask_box(mask: np.ndarray) -> tuple[int, int, int, int]:
    normalized = normalize_binary_mask(mask)
    ys, xs = np.where(normalized > 0)
    if not len(xs) or not len(ys):
        height, width = normalized.shape[:2]
        return 0, 0, max(1, width), max(1, height)
    x0 = int(xs.min())
    y0 = int(ys.min())
    x1 = int(xs.max()) + 1
    y1 = int(ys.max()) + 1
    return x0, y0, max(1, x1 - x0), max(1, y1 - y0)


def _to_numpy(value: Any) -> np.ndarray:
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "numpy"):
        return value.numpy()
    return np.asarray(value)


SAM2LocalSegmentationProvider = LocalSAM2SegmentationProvider
SAM2HostedSegmentationProvider = HostedSAM2SegmentationProvider
SAM2LocalAutomaticMaskProposalBackend = LocalSAM2AutomaticMaskProposalBackend
