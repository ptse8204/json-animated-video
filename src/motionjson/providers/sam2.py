from __future__ import annotations

import base64
import io
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Protocol

import numpy as np
from PIL import Image

from ..video import VideoInfo
from .base import ProviderConfigError, ProviderExecutionError
from .mask_cache import MaskCache, normalize_binary_mask


class JsonTransport(Protocol):
    def post_json(self, url: str, payload: Mapping[str, Any], *, headers: Mapping[str, str] | None = None) -> Mapping[str, Any]:
        """Post JSON and return decoded JSON."""


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

    def close(self) -> None:
        if self.predictor is not None and hasattr(self.predictor, "close"):
            self.predictor.close()

    def _build_predictor(self) -> Any:
        if self.predictor_factory is None:
            if not self.checkpoint or not self.model_config:
                raise ProviderConfigError(
                    "sam2-local requires --sam2-checkpoint and --sam2-model-config unless a predictor or predictor_factory is injected. "
                    "Install SAM2 separately and keep torch/SAM2 out of default MotionJSON dependencies."
                )
            try:
                from sam2.build_sam import build_sam2_video_predictor  # type: ignore
            except ImportError as exc:
                raise ProviderConfigError(
                    "SAM2 is not installed. Install Meta SAM2 and torch in your local environment, then pass "
                    "--sam2-checkpoint and --sam2-model-config, or inject a fake predictor for tests."
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

    def prepare(self, video_metadata: VideoInfo) -> None:
        self.video_metadata = video_metadata
        self._endpoint = self.endpoint or os.environ.get(self.endpoint_env)
        self._token = os.environ.get(self.auth_env) if self.auth_env else None
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

    def close(self) -> None:
        if self.client is not None and hasattr(self.client, "close"):
            self.client.close()

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
