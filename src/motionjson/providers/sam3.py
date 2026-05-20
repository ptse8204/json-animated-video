from __future__ import annotations

import base64
import io
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

import numpy as np
from PIL import Image

from .base import ProviderConfigError, ProviderExecutionError
from .mask_cache import normalize_binary_mask


def _to_numpy(value: Any) -> Any:
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "numpy"):
        try:
            return value.numpy()
        except TypeError:
            pass
    return value


def _as_sequence(value: Any) -> list[Any]:
    value = _to_numpy(value)
    if value is None:
        return []
    if isinstance(value, np.ndarray):
        if value.ndim == 0:
            return [value.item()]
        return [value[index] for index in range(value.shape[0])]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return [value]


def _first_present(mapping: Mapping[str, Any], keys: Sequence[str]) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None


def normalize_sam3_output(output: Any) -> list[dict[str, Any]]:
    """Normalize SAM3-style image/video outputs into proposal records.

    The official SAM3 examples expose dictionaries with `masks`, `boxes`, and
    `scores`. Tests and downstream adapters may also return `outputs`,
    `objects`, `tracks`, or already-normalized lists of dictionaries.
    """

    output = _to_numpy(output)
    if output is None:
        return []
    if isinstance(output, Mapping):
        for key in ("outputs", "objects", "tracks", "predictions", "segments", "instances"):
            nested = output.get(key)
            if nested is not None:
                return normalize_sam3_output(nested)
        if "masks" in output:
            raw_masks = _to_numpy(output.get("masks"))
            masks = [raw_masks] if isinstance(raw_masks, np.ndarray) and raw_masks.ndim == 2 else _as_sequence(raw_masks)
            raw_boxes = _first_present(output, ("boxes", "bboxes"))
            boxes = _as_sequence(raw_boxes) if raw_boxes is not None else ([output["bbox"]] if "bbox" in output else [])
            raw_scores = _first_present(output, ("scores", "confidences"))
            scores = _as_sequence(raw_scores) if raw_scores is not None else ([output["score"]] if "score" in output else _as_sequence(output.get("confidence")))
            raw_labels = _first_present(output, ("labels", "phrases"))
            labels = _as_sequence(raw_labels) if raw_labels is not None else ([output["label"]] if "label" in output else _as_sequence(output.get("text")))
            raw_object_ids = _first_present(output, ("object_ids", "objectIds", "ids"))
            object_ids = _as_sequence(raw_object_ids) if raw_object_ids is not None else ([output["object_id"]] if "object_id" in output else [])
            if (
                len(masks) > 1
                and ("object_id" in output or "objectId" in output or "label" in output)
                and len(boxes) <= 1
                and len(scores) <= 1
            ):
                record = dict(output)
                record["mask_sequence"] = masks
                record["segmentation"] = masks[0]
                if boxes:
                    record["bbox"] = _to_numpy(boxes[0])
                if scores:
                    record["score"] = _scalar(scores[0])
                return [record]
            records: list[dict[str, Any]] = []
            for index, mask in enumerate(masks):
                record: dict[str, Any] = {"segmentation": _to_numpy(mask)}
                if index < len(boxes):
                    record["bbox"] = _to_numpy(boxes[index])
                if index < len(scores):
                    record["score"] = _scalar(scores[index])
                if index < len(labels):
                    record["label"] = str(labels[index])
                if index < len(object_ids):
                    record["object_id"] = str(object_ids[index])
                records.append(record)
            return records
        return [dict(output)]
    if isinstance(output, Sequence) and not isinstance(output, (str, bytes, bytearray)):
        records: list[dict[str, Any]] = []
        for item in output:
            if isinstance(item, Mapping):
                records.extend(normalize_sam3_output(item))
            else:
                records.append({"segmentation": _to_numpy(item)})
        return records
    raise ProviderExecutionError("SAM3 adapter returned an unsupported response shape.")


@dataclass
class LocalSAM3DiscoveryBackend:
    """Optional SAM3 local discovery backend with lazy imports.

    The default import path follows the official SAM3 examples:
    `build_sam3_image_model`, `Sam3Processor`, and `build_sam3_video_predictor`.
    Tests can inject processors or predictor factories so CI never imports SAM3
    or requires GPU/model access.
    """

    model_path: str | Path | None = None
    device: str = "cuda"
    image_processor: Any | None = None
    image_model_factory: Any | None = None
    processor_factory: Any | None = None
    video_predictor: Any | None = None
    video_predictor_factory: Any | None = None
    provider_name: str = "sam3-local"
    _image_processor: Any | None = field(default=None, init=False)
    _video_predictor: Any | None = field(default=None, init=False)

    @classmethod
    def from_config(cls, config: Mapping[str, Any]) -> "LocalSAM3DiscoveryBackend":
        model_path = (
            config.get("sam3Model")
            or config.get("sam3_model")
            or config.get("sam3ModelPath")
            or config.get("sam3_model_path")
            or config.get("modelPath")
            or config.get("model_path")
            or os.environ.get("SAM3_LOCAL_MODEL")
        )
        device = str(config.get("sam3Device") or config.get("sam3_device") or config.get("device") or os.environ.get("SAM3_LOCAL_DEVICE") or "cuda")
        return cls(model_path=model_path, device=device)

    def smoke_test(self, *, prompt: str = "object") -> dict[str, Any]:
        processor = self._ensure_image_processor()
        image = Image.fromarray(np.zeros((8, 8, 3), dtype=np.uint8))
        state = self._set_image(processor, image)
        output = self._set_text_prompt(processor, state, prompt)
        records = normalize_sam3_output(output)
        return {"status": "ok", "providerName": self.provider_name, "recordCount": len(records)}

    def discover_concept(self, video: Any, config: Mapping[str, Any], ctx: Any | None = None) -> list[dict[str, Any]]:
        prompt = str(config.get("concept") or config.get("text") or config.get("prompt") or "").strip()
        if not prompt:
            raise ProviderConfigError("sam3_concept requires discovery.config.concept or discovery.config.text.")
        frame_index = _frame_index(config)
        if _bool_config(config, "useVideoSession", True):
            return self._video_prompt_records(video, frame_index=frame_index, text=prompt, config=config)
        return self._image_prompt_records(video, frame_index=frame_index, text=prompt, config=config)

    def discover_exemplar(self, video: Any, config: Mapping[str, Any], ctx: Any | None = None) -> list[dict[str, Any]]:
        frame_index = _frame_index(config)
        exemplars = config.get("exemplars") or config.get("exemplarRefs") or config.get("exemplar_refs")
        box = _config_box(config)
        if not exemplars and box is None:
            raise ProviderConfigError("sam3_exemplar requires discovery.config.exemplars or discovery.config.box.")
        if _bool_config(config, "useVideoSession", True):
            return self._video_prompt_records(video, frame_index=frame_index, exemplars=exemplars, box=box, config=config)
        return self._image_prompt_records(video, frame_index=frame_index, exemplars=exemplars, box=box, config=config)

    def discover_auto_masks(self, video: Any, config: Mapping[str, Any], ctx: Any | None = None) -> list[dict[str, Any]]:
        auto_config = dict(config)
        auto_config.setdefault("concept", str(config.get("concept") or config.get("text") or "object"))
        return self.discover_concept(video, auto_config, ctx)

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
        records = self._video_prompt_records(video, frame_index=frame_index, box=box, mask=mask, config=config)
        masks = _first_mask_sequence(records)
        if not masks:
            raise ProviderExecutionError("SAM3 video tracking did not return a mask sequence.")
        return masks

    def _image_prompt_records(
        self,
        video: Any,
        *,
        frame_index: int,
        config: Mapping[str, Any],
        text: str | None = None,
        exemplars: Any | None = None,
        box: tuple[int, int, int, int] | None = None,
    ) -> list[dict[str, Any]]:
        processor = self._ensure_image_processor()
        frame = video.frames[min(max(0, frame_index), len(video.frames) - 1)]
        state = self._set_image(processor, Image.fromarray(frame.rgb))
        if text:
            output = self._set_text_prompt(processor, state, text)
        else:
            output = self._set_visual_prompt(processor, state, exemplars=exemplars, box=box)
        return normalize_sam3_output(output)

    def _video_prompt_records(
        self,
        video: Any,
        *,
        frame_index: int,
        config: Mapping[str, Any],
        text: str | None = None,
        exemplars: Any | None = None,
        box: tuple[int, int, int, int] | None = None,
        mask: np.ndarray | None = None,
    ) -> list[dict[str, Any]]:
        predictor = self._ensure_video_predictor()
        if not hasattr(predictor, "handle_request"):
            raise ProviderExecutionError("SAM3 video predictor must expose handle_request().")
        try:
            started = predictor.handle_request(request={"type": "start_session", "resource_path": str(video.path)})
        except TypeError:
            started = predictor.handle_request({"type": "start_session", "resource_path": str(video.path)})
        session_id = None
        if isinstance(started, Mapping):
            session_id = started.get("session_id") or started.get("sessionId")
        if not session_id:
            raise ProviderExecutionError("SAM3 video predictor did not return a session_id.")
        request: dict[str, Any] = {"type": "add_prompt", "session_id": session_id, "frame_index": frame_index}
        if text:
            request["text"] = text
        if exemplars is not None:
            request["exemplars"] = exemplars
        if box is not None:
            request["box"] = list(box)
        if mask is not None and bool(config.get("sendMaskPrompt", False)):
            request["mask"] = normalize_binary_mask(mask)
        try:
            response = predictor.handle_request(request=request)
        except TypeError:
            response = predictor.handle_request(request)
        return normalize_sam3_output(response)

    def _ensure_image_processor(self) -> Any:
        if self.image_processor is not None:
            return self.image_processor
        if self._image_processor is not None:
            return self._image_processor
        if self.processor_factory is not None:
            self._image_processor = self.processor_factory()
            return self._image_processor
        self._validate_model_path()
        try:
            from sam3.model.sam3_image_processor import Sam3Processor  # type: ignore
            from sam3.model_builder import build_sam3_image_model  # type: ignore
        except ImportError as exc:
            raise ProviderConfigError(
                "SAM3 local discovery requires the optional sam3 package. Install the official SAM3 repo "
                "separately, configure SAM3_LOCAL_MODEL, or use discovery.config.mock=true."
            ) from exc
        model = self._call_builder(self.image_model_factory or build_sam3_image_model)
        self._image_processor = Sam3Processor(model)
        return self._image_processor

    def _ensure_video_predictor(self) -> Any:
        if self.video_predictor is not None:
            return self.video_predictor
        if self._video_predictor is not None:
            return self._video_predictor
        if self.video_predictor_factory is not None:
            self._video_predictor = self.video_predictor_factory()
            return self._video_predictor
        self._validate_model_path()
        try:
            from sam3.model_builder import build_sam3_video_predictor  # type: ignore
        except ImportError as exc:
            raise ProviderConfigError(
                "SAM3 video tracking requires the optional sam3 package. Install the official SAM3 repo "
                "separately, configure SAM3_LOCAL_MODEL, or use discovery.config.mock=true."
            ) from exc
        self._video_predictor = self._call_builder(build_sam3_video_predictor)
        return self._video_predictor

    def _validate_model_path(self) -> Path:
        raw_model_path = str(self.model_path or os.environ.get("SAM3_LOCAL_MODEL") or "").strip()
        if not raw_model_path:
            raise ProviderConfigError("SAM3 local adapter requires SAM3_LOCAL_MODEL or discovery.config.sam3ModelPath.")
        model_path = Path(raw_model_path)
        if not model_path.exists():
            raise ProviderConfigError("Configured SAM3_LOCAL_MODEL path does not exist.")
        return model_path

    def _call_builder(self, builder: Any) -> Any:
        model_path = str(self._validate_model_path())
        attempts = (
            {"checkpoint_path": model_path, "device": self.device},
            {"model_path": model_path, "device": self.device},
            {"checkpoint": model_path, "device": self.device},
            {"device": self.device},
            {},
        )
        last_error: TypeError | None = None
        for kwargs in attempts:
            try:
                return builder(**kwargs)
            except TypeError as exc:
                last_error = exc
                continue
        if last_error is not None:
            raise ProviderExecutionError(f"SAM3 model builder rejected supported call shapes: {last_error}") from last_error
        raise ProviderExecutionError("SAM3 model builder could not be called.")

    @staticmethod
    def _set_image(processor: Any, image: Image.Image) -> Any:
        if not hasattr(processor, "set_image"):
            raise ProviderExecutionError("SAM3 image processor must expose set_image().")
        return processor.set_image(image)

    @staticmethod
    def _set_text_prompt(processor: Any, state: Any, prompt: str) -> Any:
        if not hasattr(processor, "set_text_prompt"):
            raise ProviderExecutionError("SAM3 image processor must expose set_text_prompt().")
        fn = processor.set_text_prompt
        attempts = (
            lambda: fn(state=state, prompt=prompt),
            lambda: fn(state, prompt),
            lambda: fn(prompt=prompt),
        )
        return _call_first(attempts, "SAM3 text prompt call failed")

    @staticmethod
    def _set_visual_prompt(processor: Any, state: Any, *, exemplars: Any | None, box: tuple[int, int, int, int] | None) -> Any:
        prompt_methods = ("set_exemplar_prompt", "set_visual_prompt", "set_image_prompt", "set_box_prompt")
        for method_name in prompt_methods:
            if not hasattr(processor, method_name):
                continue
            fn = getattr(processor, method_name)
            attempts = []
            if box is not None:
                attempts.extend(
                    (
                        lambda fn=fn: fn(state=state, box=box),
                        lambda fn=fn: fn(state, box),
                    )
                )
            if exemplars is not None:
                attempts.extend(
                    (
                        lambda fn=fn: fn(state=state, exemplars=exemplars),
                        lambda fn=fn: fn(state, exemplars),
                    )
                )
            try:
                return _call_first(attempts, "SAM3 visual prompt call failed")
            except ProviderExecutionError:
                continue
        raise ProviderConfigError(
            "sam3_exemplar requires a SAM3 processor with set_exemplar_prompt(), set_visual_prompt(), "
            "set_image_prompt(), or set_box_prompt()."
        )


@dataclass
class HostedSAM3DiscoveryBackend:
    """SAM3-compatible hosted backend gated behind explicit network opt-in."""

    endpoint: str | None = None
    api_key: str | None = None
    model: str | None = None
    allow_network: bool = False
    acknowledge_cost_privacy: bool = False
    timeout_seconds: float = 60.0
    retries: int = 1
    transport: Any | None = None
    endpoint_env: str = "SAM3_HOSTED_URL"
    api_key_env: str = "SAM3_HOSTED_API_KEY"
    model_env: str = "SAM3_HOSTED_MODEL"
    provider_name: str = "sam3-hosted"

    @classmethod
    def from_config(cls, config: Mapping[str, Any]) -> "HostedSAM3DiscoveryBackend":
        model = (
            config.get("sam3HostedModel")
            or config.get("sam3_hosted_model")
            or config.get("model")
            or config.get("modelName")
            or os.environ.get("SAM3_HOSTED_MODEL")
            or "auto"
        )
        timeout = config.get("timeoutSeconds", config.get("timeout_seconds", 60.0))
        retries = config.get("retries", config.get("retry_count", 1))
        return cls(
            endpoint=config.get("sam3HostedEndpoint") or config.get("sam3_hosted_endpoint") or config.get("endpoint"),
            api_key=None,
            model=str(model or "auto"),
            allow_network=_bool_config(config, "allowNetwork", False)
            or _bool_config(config, "allowHostedNetwork", False)
            or _bool_config(config, "hostedAllowNetwork", False),
            acknowledge_cost_privacy=_bool_config(config, "acknowledgeCostPrivacy", False)
            or _bool_config(config, "costPrivacyAcknowledged", False)
            or _bool_config(config, "hostedCostPrivacyAcknowledged", False),
            timeout_seconds=_float_or_default(timeout, 60.0),
            retries=max(0, int(_float_or_default(retries, 1.0))),
        )

    def setup_status(self) -> dict[str, Any]:
        endpoint = self._resolve_endpoint()
        token = self._resolve_api_key()
        endpoint_valid = _valid_http_url(endpoint)
        return {
            "format": "motionjson.sam3_hosted_setup.v0.1",
            "providerName": self.provider_name,
            "networkAttempted": False,
            "configured": bool(endpoint and token and endpoint_valid),
            "endpointConfigured": bool(endpoint),
            "endpointValid": endpoint_valid,
            "apiKeyConfigured": bool(token),
            "model": self._resolve_model(),
        }

    def smoke_test(self, *, prompt: str = "object", frame_rgb: np.ndarray | None = None) -> dict[str, Any]:
        response = self._call_hosted(
            {
                "task": "sam3_smoke_test",
                "prompt": prompt or "object",
                "maxCandidates": 1,
                "frame": _encoded_frame(frame_rgb if frame_rgb is not None else _synthetic_smoke_frame()),
            }
        )
        records = normalize_sam3_output(response)
        if not records:
            raise ProviderExecutionError("Hosted SAM3 smoke test response did not include any candidate records.")
        return {
            "format": "motionjson.sam3_hosted_smoke.v0.1",
            "status": "ok",
            "providerName": self.provider_name,
            "networkAttempted": True,
            "recordCount": len(records),
            "model": self._resolve_model(),
            "responseSchema": "sam3-compatible",
        }

    def discover_concept(self, video: Any, config: Mapping[str, Any], ctx: Any | None = None) -> list[dict[str, Any]]:
        prompt = str(config.get("concept") or config.get("text") or config.get("prompt") or "").strip()
        if not prompt:
            raise ProviderConfigError("sam3_concept hosted discovery requires discovery.config.concept or discovery.config.text.")
        frame_index = _frame_index(config)
        return self._discover_from_frame(video, config, task="sam3_concept", frame_index=frame_index, prompt=prompt)

    def discover_exemplar(self, video: Any, config: Mapping[str, Any], ctx: Any | None = None) -> list[dict[str, Any]]:
        frame_index = _frame_index(config)
        exemplars = config.get("exemplars") or config.get("exemplarRefs") or config.get("exemplar_refs")
        box = _config_box(config)
        if not exemplars and box is None:
            raise ProviderConfigError("sam3_exemplar hosted discovery requires discovery.config.exemplars or discovery.config.box.")
        return self._discover_from_frame(
            video,
            config,
            task="sam3_exemplar",
            frame_index=frame_index,
            exemplars=exemplars,
            box=box,
        )

    def discover_auto_masks(self, video: Any, config: Mapping[str, Any], ctx: Any | None = None) -> list[dict[str, Any]]:
        frame_index = _frame_index(config)
        prompt = str(config.get("concept") or config.get("text") or "object")
        return self._discover_from_frame(video, config, task="sam3_auto_masks", frame_index=frame_index, prompt=prompt)

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
        payload = {
            "task": "sam3_track_candidate",
            "sourceVideo": str(getattr(video, "path", "")),
            "frameIndex": int(frame_index),
            "objectId": object_id,
            "box": list(box) if box else None,
            "mask": _encoded_mask(mask),
            "video": _video_metadata(video),
        }
        response = self._call_hosted(payload)
        records = normalize_sam3_output(response)
        masks = _first_mask_sequence(records)
        if not masks:
            raise ProviderExecutionError("Hosted SAM3 tracking response did not include a mask sequence.")
        return masks

    def _discover_from_frame(
        self,
        video: Any,
        config: Mapping[str, Any],
        *,
        task: str,
        frame_index: int,
        prompt: str | None = None,
        exemplars: Any | None = None,
        box: tuple[int, int, int, int] | None = None,
    ) -> list[dict[str, Any]]:
        frame_index = min(max(0, frame_index), max(0, len(video.frames) - 1))
        frame = video.frames[frame_index]
        payload = {
            "task": task,
            "prompt": prompt,
            "exemplars": exemplars,
            "box": list(box) if box else None,
            "frameIndex": frame_index,
            "frame": _encoded_frame(frame.rgb),
            "video": _video_metadata(video),
            "maxCandidates": config.get("maxCandidates") or config.get("max_candidates") or config.get("maxCandidatesPerKeyframe"),
        }
        response = self._call_hosted(payload)
        records = normalize_sam3_output(response)
        if not records:
            raise ProviderExecutionError(f"Hosted SAM3 {task} response did not include any candidate records.")
        return records

    def _call_hosted(self, payload: Mapping[str, Any]) -> Mapping[str, Any] | Sequence[Any]:
        self._ensure_network_allowed()
        endpoint = self._resolve_endpoint()
        token = self._resolve_api_key()
        if not endpoint or not _valid_http_url(endpoint):
            raise ProviderConfigError("sam3-hosted requires a valid http:// or https:// endpoint.")
        if not token:
            raise ProviderConfigError(f"sam3-hosted requires auth in {self.api_key_env}; no token was read.")
        request_payload = {
            "model": self._resolve_model(),
            "provider": self.provider_name,
            **dict(payload),
        }
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        transport = self.transport or _UrlLibJsonTransport(timeout_seconds=self.timeout_seconds)
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                return _post_json(transport, endpoint, request_payload, headers=headers, timeout_seconds=self.timeout_seconds)
            except Exception as exc:  # pragma: no cover - exact transport errors vary.
                last_error = exc
                if attempt >= self.retries:
                    break
                time.sleep(min(0.25 * (attempt + 1), 1.0))
        raise ProviderExecutionError(f"Hosted SAM3 request failed: {last_error}") from last_error

    def _ensure_network_allowed(self) -> None:
        if not self.allow_network or not self.acknowledge_cost_privacy:
            raise ProviderConfigError(
                "sam3-hosted requires explicit allowNetwork=true and acknowledgeCostPrivacy=true before sending frames."
            )

    def _resolve_endpoint(self) -> str:
        return str(self.endpoint or os.environ.get(self.endpoint_env) or "").strip()

    def _resolve_api_key(self) -> str:
        return str(self.api_key or os.environ.get(self.api_key_env) or "").strip()

    def _resolve_model(self) -> str:
        return str(self.model or os.environ.get(self.model_env) or "auto").strip() or "auto"


class _UrlLibJsonTransport:
    def __init__(self, *, timeout_seconds: float = 60.0) -> None:
        self.timeout_seconds = timeout_seconds

    def post_json(
        self,
        url: str,
        payload: Mapping[str, Any],
        *,
        headers: Mapping[str, str] | None = None,
        timeout_seconds: float | None = None,
    ) -> Mapping[str, Any] | Sequence[Any]:
        from urllib import request

        data = json.dumps(payload).encode("utf-8")
        req = request.Request(url, data=data, headers=dict(headers or {}), method="POST")
        with request.urlopen(req, timeout=timeout_seconds or self.timeout_seconds) as response:  # noqa: S310 - explicit opt-in path.
            parsed = json.loads(response.read().decode("utf-8"))
        if not isinstance(parsed, (Mapping, list, tuple)):
            raise ProviderExecutionError("Hosted SAM3 response must be a JSON object or list.")
        return parsed


def _post_json(
    transport: Any,
    endpoint: str,
    payload: Mapping[str, Any],
    *,
    headers: Mapping[str, str],
    timeout_seconds: float,
) -> Mapping[str, Any] | Sequence[Any]:
    try:
        return transport.post_json(endpoint, payload, headers=headers, timeout_seconds=timeout_seconds)
    except TypeError:
        return transport.post_json(endpoint, payload, headers=headers)


def _encoded_frame(frame_rgb: np.ndarray) -> dict[str, Any]:
    image = Image.fromarray(np.asarray(frame_rgb, dtype=np.uint8)).convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return {"format": "png_base64", "data": base64.b64encode(buffer.getvalue()).decode("ascii")}


def _encoded_mask(mask: np.ndarray) -> dict[str, Any]:
    image = Image.fromarray(normalize_binary_mask(np.asarray(mask))).convert("L")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return {"format": "png_base64", "data": base64.b64encode(buffer.getvalue()).decode("ascii")}


def _synthetic_smoke_frame() -> np.ndarray:
    frame = np.zeros((16, 16, 3), dtype=np.uint8)
    frame[5:11, 5:11] = (230, 40, 40)
    return frame


def _video_metadata(video: Any) -> dict[str, Any]:
    info = getattr(video, "info", None)
    if info is None:
        return {}
    return {
        "width": getattr(info, "width", None),
        "height": getattr(info, "height", None),
        "sourceFps": getattr(info, "source_fps", None),
        "sampleFps": getattr(info, "sample_fps", None),
        "totalSourceFrames": getattr(info, "total_source_frames", None),
    }


def _valid_http_url(value: str) -> bool:
    parsed = urlparse(str(value or ""))
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _float_or_default(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _call_first(attempts: Sequence[Any], message: str) -> Any:
    last_error: TypeError | None = None
    for attempt in attempts:
        try:
            return attempt()
        except TypeError as exc:
            last_error = exc
            continue
    raise ProviderExecutionError(f"{message}: {last_error}") from last_error


def _frame_index(config: Mapping[str, Any]) -> int:
    value = config.get("frameIndex", config.get("frame_index", config.get("promptFrame", 0)))
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _bool_config(config: Mapping[str, Any], name: str, default: bool) -> bool:
    if name in config:
        return bool(config[name])
    snake = "".join([f"_{char.lower()}" if char.isupper() else char for char in name]).lstrip("_")
    if snake in config:
        return bool(config[snake])
    return default


def _config_box(config: Mapping[str, Any]) -> tuple[int, int, int, int] | None:
    raw = config.get("box") or config.get("bbox") or config.get("exemplarBox") or config.get("exemplar_box")
    if isinstance(raw, Mapping):
        try:
            return (
                int(raw.get("x", 0)),
                int(raw.get("y", 0)),
                int(raw.get("w", raw.get("width", 1))),
                int(raw.get("h", raw.get("height", 1))),
            )
        except (TypeError, ValueError):
            return None
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray)) and len(raw) >= 4:
        try:
            return (int(raw[0]), int(raw[1]), int(raw[2]), int(raw[3]))
        except (TypeError, ValueError):
            return None
    return None


def _first_mask_sequence(records: Sequence[Mapping[str, Any]]) -> list[np.ndarray]:
    for record in records:
        raw = record.get("mask_sequence") or record.get("maskSequence") or record.get("masks")
        if raw is None:
            continue
        raw = _to_numpy(raw)
        items = [raw] if isinstance(raw, np.ndarray) and raw.ndim == 2 else _as_sequence(raw)
        masks = [normalize_binary_mask(np.asarray(_to_numpy(mask))) for mask in items]
        if masks:
            return masks
        if record.get("segmentation") is not None:
            return [normalize_binary_mask(np.asarray(_to_numpy(record["segmentation"])))]
    return []


def _scalar(value: Any) -> float:
    value = _to_numpy(value)
    if isinstance(value, np.ndarray):
        if value.size == 0:
            return 0.0
        value = value.reshape(-1)[0]
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


SAM3LocalDiscoveryBackend = LocalSAM3DiscoveryBackend
SAM3HostedDiscoveryBackend = HostedSAM3DiscoveryBackend
