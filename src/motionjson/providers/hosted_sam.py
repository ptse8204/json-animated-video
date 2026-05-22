from __future__ import annotations

import base64
import io
import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlencode, urlparse, urlunparse

import numpy as np
from PIL import Image, ImageDraw

from .base import ProviderConfigError, ProviderExecutionError
from .mask_cache import normalize_binary_mask
from .sam3 import HostedSAM3DiscoveryBackend, normalize_sam3_output


def hosted_sam3_backend_from_config(config: Mapping[str, Any]) -> Any:
    profile = _profile(config, default="custom-sam3-compatible")
    if profile == "roboflow-sam3-pcs":
        return RoboflowSAM3ConceptBackend.from_config(config)
    if profile == "fal-sam3-image":
        return FalSAM3ImageBackend.from_config(config)
    return HostedSAM3DiscoveryBackend.from_config(config)


def hosted_sam2_client_from_config(source_video: str | Path, config: Mapping[str, Any]) -> Any | None:
    profile = _profile(config, default="custom-sam2-compatible")
    if profile != "replicate-sam2-video":
        return None
    return ReplicateSAM2VideoClient.from_config(source_video=source_video, config=config)


@dataclass
class ReplicateSAM2VideoClient:
    source_video: str | Path
    api_key: str | None = None
    model: str = "meta/sam-2-video"
    prompt_frame_index: int = 0
    object_id: str = "object_0"
    prompt_point: tuple[int, int] | None = None
    prompt_box: tuple[int, int, int, int] | None = None
    allow_network: bool = False
    acknowledge_cost_privacy: bool = False
    transport: Any | None = None
    downloader: Any | None = None
    _masks: list[np.ndarray] | None = field(default=None, init=False)

    @classmethod
    def from_config(cls, *, source_video: str | Path, config: Mapping[str, Any]) -> "ReplicateSAM2VideoClient":
        return cls(
            source_video=source_video,
            api_key=str(config.get("apiKey") or config.get("api_key") or os.environ.get("REPLICATE_API_TOKEN") or "").strip() or None,
            model=str(config.get("model") or config.get("selectedModel") or "meta/sam-2-video"),
            prompt_frame_index=int(config.get("promptFrame") or config.get("prompt_frame") or 0),
            object_id=str(config.get("objectId") or config.get("object_id") or "object_0"),
            prompt_point=_point(config.get("promptPoint") or config.get("prompt_point")),
            prompt_box=_box(config.get("promptBox") or config.get("prompt_box")),
            allow_network=_truthy(config.get("allowNetwork") or config.get("allow_network")),
            acknowledge_cost_privacy=_truthy(config.get("acknowledgeCostPrivacy") or config.get("acknowledge_cost_privacy")),
            transport=config.get("transport"),
            downloader=config.get("downloader"),
        )

    def smoke_test(self) -> dict[str, Any]:
        self._ensure_configured(require_network=False)
        return {
            "format": "motionjson.replicate_sam2_video_setup.v0.1",
            "status": "configured",
            "providerName": "replicate-sam2-video",
            "networkAttempted": False,
            "model": self.model,
        }

    def segment_frame(self, **payload: Any) -> Mapping[str, Any]:
        frame_index = int(payload.get("frame_index", 0))
        point = _point(payload.get("prompt_point")) or self.prompt_point
        box = _box(payload.get("prompt_box")) or self.prompt_box
        masks = self._ensure_masks(point=point, box=box)
        if not masks:
            raise ProviderExecutionError("Replicate SAM2 video response did not include black_white_masks.")
        mask = masks[min(max(frame_index, 0), len(masks) - 1)]
        return {"mask": mask}

    def _ensure_masks(self, *, point: tuple[int, int] | None, box: tuple[int, int, int, int] | None) -> list[np.ndarray]:
        if self._masks is not None:
            return self._masks
        self._ensure_configured(require_network=True)
        click = point or _box_center(box)
        if click is None:
            raise ProviderConfigError("replicate-sam2-video requires a point or box prompt.")
        input_payload = {
            "video": self._video_input(),
            "click_coordinates": f"[{click[0]},{click[1]}]",
            "click_labels": "1",
            "click_frames": str(self.prompt_frame_index),
            "click_object_ids": self.object_id or str(_numeric_object_id(self.object_id)),
            "vis_frame_stride": 1,
        }
        output = self._run_replicate(input_payload)
        records = output.get("black_white_masks") if isinstance(output, Mapping) else None
        if records is None:
            raise ProviderExecutionError("Replicate SAM2 video output must include black_white_masks.")
        self._masks = [_mask_from_reference(item, downloader=self.downloader) for item in records]
        return self._masks

    def _ensure_configured(self, *, require_network: bool) -> None:
        if not self.api_key and self.transport is None:
            raise ProviderConfigError("replicate-sam2-video requires REPLICATE_API_TOKEN or saved provider settings.")
        if require_network and (not self.allow_network or not self.acknowledge_cost_privacy):
            raise ProviderConfigError("replicate-sam2-video requires allowNetwork=true and acknowledgeCostPrivacy=true before sending video frames.")

    def _video_input(self) -> Any:
        return str(self.source_video)

    def _run_replicate(self, input_payload: Mapping[str, Any]) -> Mapping[str, Any]:
        if self.transport is not None:
            if hasattr(self.transport, "run"):
                result = self.transport.run(self.model, input=input_payload)
            elif hasattr(self.transport, "post_json"):
                result = self.transport.post_json(
                    "https://api.replicate.com/v1/models/meta/sam-2-video/predictions",
                    {"input": dict(input_payload)},
                    headers={"Authorization": f"Bearer {self.api_key or ''}", "Content-Type": "application/json"},
                )
            else:
                raise ProviderExecutionError("Replicate transport must expose run() or post_json().")
            return _prediction_output(result)
        try:
            import replicate  # type: ignore
        except ImportError as exc:
            raise ProviderConfigError("replicate-sam2-video requires the optional replicate package. Install .[hosted-sam-vendors].") from exc
        try:
            client = replicate.Client(api_token=self.api_key) if self.api_key and hasattr(replicate, "Client") else replicate
            with Path(self.source_video).open("rb") as video_file:
                payload = {**dict(input_payload), "video": video_file}
                result = client.run(self.model, input=payload)
        except Exception as exc:  # pragma: no cover - provider/client errors vary.
            raise ProviderExecutionError(f"Replicate SAM2 video request failed: {type(exc).__name__}") from exc
        return _prediction_output(result)


@dataclass
class RoboflowSAM3ConceptBackend:
    endpoint: str = "https://serverless.roboflow.com/sam3/concept_segment"
    api_key: str | None = None
    model: str = "sam3/sam3_final"
    allow_network: bool = False
    acknowledge_cost_privacy: bool = False
    transport: Any | None = None
    provider_name: str = "sam3-hosted-roboflow"

    @classmethod
    def from_config(cls, config: Mapping[str, Any]) -> "RoboflowSAM3ConceptBackend":
        return cls(
            endpoint=str(config.get("endpoint") or config.get("sam3HostedEndpoint") or os.environ.get("ROBOFLOW_SAM3_URL") or "https://serverless.roboflow.com/sam3/concept_segment"),
            api_key=str(config.get("apiKey") or config.get("api_key") or os.environ.get("ROBOFLOW_API_KEY") or "").strip() or None,
            model=str(config.get("model") or config.get("sam3HostedModel") or "sam3/sam3_final"),
            allow_network=_truthy(config.get("allowNetwork") or config.get("allow_network")),
            acknowledge_cost_privacy=_truthy(config.get("acknowledgeCostPrivacy") or config.get("acknowledge_cost_privacy")),
            transport=config.get("transport"),
        )

    def smoke_test(self, *, prompt: str = "object", frame_rgb: np.ndarray | None = None) -> dict[str, Any]:
        frame = frame_rgb if frame_rgb is not None else _synthetic_frame()
        records = self._segment_frame(frame, prompt=prompt)
        return {"status": "ok", "providerName": self.provider_name, "networkAttempted": True, "recordCount": len(records), "model": self.model}

    def discover_concept(self, video: Any, config: Mapping[str, Any], ctx: Any | None = None) -> list[dict[str, Any]]:
        prompt = str(config.get("concept") or config.get("text") or config.get("prompt") or "").strip()
        if not prompt:
            raise ProviderConfigError("roboflow-sam3-pcs requires discovery.config.concept or discovery.config.text.")
        frame_index = _frame_index(config)
        frame = video.frames[min(max(0, frame_index), max(0, len(video.frames) - 1))]
        return self._segment_frame(frame.rgb, prompt=prompt)

    def discover_auto_masks(self, video: Any, config: Mapping[str, Any], ctx: Any | None = None) -> list[dict[str, Any]]:
        return self.discover_concept(video, {**dict(config), "concept": str(config.get("concept") or config.get("text") or "object")}, ctx)

    def discover_exemplar(self, video: Any, config: Mapping[str, Any], ctx: Any | None = None) -> list[dict[str, Any]]:
        raise ProviderConfigError("roboflow-sam3-pcs supports text concept segmentation, not exemplar prompts.")

    def track_candidate(self, video: Any, *, frame_index: int, object_id: str, box: tuple[int, int, int, int] | None, mask: np.ndarray, config: Mapping[str, Any]) -> Sequence[np.ndarray]:
        return [normalize_binary_mask(mask) for _frame in video.frames]

    def _segment_frame(self, frame_rgb: np.ndarray, *, prompt: str) -> list[dict[str, Any]]:
        self._ensure_network_allowed()
        image = _encode_image_base64(frame_rgb, format="JPEG")
        payload = {
            "image": {"type": "base64", "value": image},
            "prompts": [{"type": "text", "text": prompt}],
            "format": "polygon",
            "model_id": self.model,
            "output_prob_thresh": 0.5,
        }
        url = _with_query(self.endpoint, {"api_key": self.api_key or ""})
        response = _post_json(self.transport, url, payload, headers={"Content-Type": "application/json"})
        return _roboflow_records(response, frame_rgb.shape[1], frame_rgb.shape[0], prompt)

    def _ensure_network_allowed(self) -> None:
        if not self.api_key:
            raise ProviderConfigError("roboflow-sam3-pcs requires ROBOFLOW_API_KEY or saved provider settings.")
        if not self.allow_network or not self.acknowledge_cost_privacy:
            raise ProviderConfigError("roboflow-sam3-pcs requires allowNetwork=true and acknowledgeCostPrivacy=true before sending frames.")


@dataclass
class FalSAM3ImageBackend:
    api_key: str | None = None
    model: str = "fal-ai/sam-3/image"
    allow_network: bool = False
    acknowledge_cost_privacy: bool = False
    client: Any | None = None
    downloader: Any | None = None
    provider_name: str = "sam3-hosted-fal"

    @classmethod
    def from_config(cls, config: Mapping[str, Any]) -> "FalSAM3ImageBackend":
        return cls(
            api_key=str(config.get("apiKey") or config.get("api_key") or os.environ.get("FAL_KEY") or "").strip() or None,
            model=str(config.get("model") or config.get("sam3HostedModel") or "fal-ai/sam-3/image"),
            allow_network=_truthy(config.get("allowNetwork") or config.get("allow_network")),
            acknowledge_cost_privacy=_truthy(config.get("acknowledgeCostPrivacy") or config.get("acknowledge_cost_privacy")),
            client=config.get("client"),
            downloader=config.get("downloader"),
        )

    def smoke_test(self, *, prompt: str = "object", frame_rgb: np.ndarray | None = None) -> dict[str, Any]:
        frame = frame_rgb if frame_rgb is not None else _synthetic_frame()
        records = self._segment_frame(frame, prompt=prompt)
        return {"status": "ok", "providerName": self.provider_name, "networkAttempted": True, "recordCount": len(records), "model": self.model}

    def discover_concept(self, video: Any, config: Mapping[str, Any], ctx: Any | None = None) -> list[dict[str, Any]]:
        prompt = str(config.get("concept") or config.get("text") or config.get("prompt") or "").strip()
        if not prompt:
            raise ProviderConfigError("fal-sam3-image requires discovery.config.concept or discovery.config.text.")
        frame_index = _frame_index(config)
        frame = video.frames[min(max(0, frame_index), max(0, len(video.frames) - 1))]
        return self._segment_frame(frame.rgb, prompt=prompt)

    def discover_auto_masks(self, video: Any, config: Mapping[str, Any], ctx: Any | None = None) -> list[dict[str, Any]]:
        return self.discover_concept(video, {**dict(config), "concept": str(config.get("concept") or config.get("text") or "object")}, ctx)

    def discover_exemplar(self, video: Any, config: Mapping[str, Any], ctx: Any | None = None) -> list[dict[str, Any]]:
        raise ProviderConfigError("fal-sam3-image supports text concept/point/box image prompts through its image API; exemplar video discovery is not implemented.")

    def track_candidate(self, video: Any, *, frame_index: int, object_id: str, box: tuple[int, int, int, int] | None, mask: np.ndarray, config: Mapping[str, Any]) -> Sequence[np.ndarray]:
        return [normalize_binary_mask(mask) for _frame in video.frames]

    def _segment_frame(self, frame_rgb: np.ndarray, *, prompt: str) -> list[dict[str, Any]]:
        self._ensure_network_allowed()
        client = self._client()
        image_url = self._upload_frame(client, frame_rgb)
        arguments = {
            "image_url": image_url,
            "prompt": prompt,
            "sync_mode": False,
            "return_multiple_masks": True,
            "include_scores": True,
            "include_boxes": True,
        }
        if hasattr(client, "subscribe"):
            response = client.subscribe(self.model, arguments=arguments, with_logs=False)
        elif hasattr(client, "run"):
            response = client.run(self.model, arguments=arguments)
        else:
            raise ProviderExecutionError("Fal client must expose subscribe() or run().")
        return _fal_records(response, downloader=self.downloader)

    def _client(self) -> Any:
        if self.client is not None:
            return self.client
        try:
            import fal_client  # type: ignore
        except ImportError as exc:
            raise ProviderConfigError("fal-sam3-image requires the optional fal-client package. Install .[hosted-sam-vendors].") from exc
        if self.api_key:
            os.environ.setdefault("FAL_KEY", self.api_key)
        return fal_client

    def _upload_frame(self, client: Any, frame_rgb: np.ndarray) -> str:
        if hasattr(client, "upload_file"):
            with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
                Image.fromarray(np.asarray(frame_rgb, dtype=np.uint8)).save(tmp.name)
                return str(client.upload_file(tmp.name))
        return "data:image/png;base64," + _encode_image_base64(frame_rgb, format="PNG")

    def _ensure_network_allowed(self) -> None:
        if not self.api_key and self.client is None:
            raise ProviderConfigError("fal-sam3-image requires FAL_KEY or saved provider settings.")
        if not self.allow_network or not self.acknowledge_cost_privacy:
            raise ProviderConfigError("fal-sam3-image requires allowNetwork=true and acknowledgeCostPrivacy=true before sending frames.")


def _prediction_output(result: Any) -> Mapping[str, Any]:
    if isinstance(result, Mapping):
        if isinstance(result.get("output"), Mapping):
            return result["output"]
        return result
    raise ProviderExecutionError("Hosted provider response must be a JSON object.")


def _roboflow_records(response: Any, width: int, height: int, prompt: str) -> list[dict[str, Any]]:
    if not isinstance(response, Mapping):
        return normalize_sam3_output(response)
    records: list[dict[str, Any]] = []
    for prompt_result in response.get("prompt_results", []) or []:
        for index, prediction in enumerate(prompt_result.get("predictions", []) or []):
            masks = prediction.get("masks") or prediction.get("polygons") or []
            for mask_index, polygon in enumerate(masks):
                mask = _polygon_mask(polygon, width, height)
                records.append(
                    {
                        "segmentation": mask,
                        "bbox": _mask_bbox(mask),
                        "score": prediction.get("confidence", prediction.get("score", 0.0)),
                        "label": prompt,
                        "object_id": f"roboflow_sam3_{len(records) + 1:03d}",
                        "metadata": {"promptIndex": prompt_result.get("prompt_index"), "predictionIndex": index, "maskIndex": mask_index},
                    }
                )
    if records:
        return records
    return normalize_sam3_output(response)


def _fal_records(response: Any, *, downloader: Any | None = None) -> list[dict[str, Any]]:
    if not isinstance(response, Mapping):
        return normalize_sam3_output(response)
    masks = response.get("masks") or []
    scores = response.get("scores") or []
    boxes = response.get("boxes") or []
    metadata = response.get("metadata") or []
    records: list[dict[str, Any]] = []
    for index, item in enumerate(masks):
        mask = _mask_from_reference(item, downloader=downloader)
        record: dict[str, Any] = {
            "segmentation": mask,
            "bbox": _cxcywh_to_xywh(boxes[index], mask.shape[1], mask.shape[0]) if index < len(boxes) else _mask_bbox(mask),
            "score": scores[index] if index < len(scores) else (metadata[index].get("score") if index < len(metadata) and isinstance(metadata[index], Mapping) else 0.0),
            "label": "fal sam3 mask",
            "object_id": f"fal_sam3_{index + 1:03d}",
        }
        records.append(record)
    if records:
        return records
    return normalize_sam3_output(response)


def _mask_from_reference(item: Any, *, downloader: Any | None = None) -> np.ndarray:
    if isinstance(item, np.ndarray):
        return normalize_binary_mask(item)
    if isinstance(item, Mapping):
        if "mask" in item:
            return normalize_binary_mask(np.asarray(item["mask"]))
        if "url" in item:
            return _mask_from_reference(str(item["url"]), downloader=downloader)
    if isinstance(item, str):
        if item.startswith("data:"):
            data = base64.b64decode(item.split(",", 1)[1])
            return normalize_binary_mask(np.array(Image.open(io.BytesIO(data)).convert("L")))
        if item.startswith("http://") or item.startswith("https://"):
            data = downloader(item) if downloader is not None else _download_bytes(item)
            return normalize_binary_mask(np.array(Image.open(io.BytesIO(data)).convert("L")))
    raise ProviderExecutionError("Hosted mask reference must be a mask array, data URI, or downloadable URL.")


def _post_json(transport: Any | None, url: str, payload: Mapping[str, Any], *, headers: Mapping[str, str]) -> Any:
    if transport is not None:
        return transport.post_json(url, payload, headers=headers)
    from urllib import request

    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers=dict(headers), method="POST")
    try:
        with request.urlopen(req, timeout=120) as response:  # noqa: S310 - explicit opt-in network path.
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # pragma: no cover - network/provider errors vary.
        raise ProviderExecutionError(f"Hosted SAM request failed: {type(exc).__name__}") from exc


def _download_bytes(url: str) -> bytes:
    from urllib import request

    try:
        with request.urlopen(url, timeout=120) as response:  # noqa: S310 - explicit opt-in network path.
            return response.read()
    except Exception as exc:  # pragma: no cover - network/provider errors vary.
        raise ProviderExecutionError(f"Hosted SAM mask download failed: {type(exc).__name__}") from exc


def _with_query(url: str, params: Mapping[str, str]) -> str:
    parsed = urlparse(url)
    query = urlencode({key: value for key, value in params.items() if value})
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, query, parsed.fragment))


def _encode_image_base64(frame_rgb: np.ndarray, *, format: str) -> str:
    buffer = io.BytesIO()
    Image.fromarray(np.asarray(frame_rgb, dtype=np.uint8)).convert("RGB").save(buffer, format=format)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _polygon_mask(polygon: Any, width: int, height: int) -> np.ndarray:
    image = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(image)
    points: list[tuple[float, float]] = []
    if isinstance(polygon, Mapping):
        polygon = polygon.get("points") or polygon.get("polygon") or polygon.get("mask") or []
    for point in polygon or []:
        if isinstance(point, Mapping):
            points.append((float(point.get("x", 0)), float(point.get("y", 0))))
        elif isinstance(point, Sequence) and len(point) >= 2:
            points.append((float(point[0]), float(point[1])))
    if len(points) >= 3:
        draw.polygon(points, fill=255)
    return np.asarray(image, dtype=np.uint8)


def _mask_bbox(mask: np.ndarray) -> list[int]:
    ys, xs = np.where(normalize_binary_mask(mask) > 0)
    if not len(xs):
        return [0, 0, 1, 1]
    x0, y0, x1, y1 = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
    return [x0, y0, max(1, x1 - x0), max(1, y1 - y0)]


def _cxcywh_to_xywh(box: Sequence[float], width: int, height: int) -> list[int]:
    cx, cy, bw, bh = [float(value) for value in list(box)[:4]]
    if 0 <= cx <= 1 and 0 <= cy <= 1 and 0 <= bw <= 1 and 0 <= bh <= 1:
        cx, bw = cx * width, bw * width
        cy, bh = cy * height, bh * height
    return [int(cx - bw / 2), int(cy - bh / 2), max(1, int(bw)), max(1, int(bh))]


def _point(value: Any) -> tuple[int, int] | None:
    if value is None:
        return None
    if isinstance(value, Mapping):
        return int(value.get("x", 0)), int(value.get("y", 0))
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) and len(value) >= 2:
        return int(value[0]), int(value[1])
    return None


def _box(value: Any) -> tuple[int, int, int, int] | None:
    if value is None:
        return None
    if isinstance(value, Mapping):
        return int(value.get("x", value.get("x_min", 0))), int(value.get("y", value.get("y_min", 0))), int(value.get("w", value.get("width", 1))), int(value.get("h", value.get("height", 1)))
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) and len(value) >= 4:
        return int(value[0]), int(value[1]), int(value[2]), int(value[3])
    return None


def _box_center(box: tuple[int, int, int, int] | None) -> tuple[int, int] | None:
    if box is None:
        return None
    x, y, w, h = box
    return x + max(1, w) // 2, y + max(1, h) // 2


def _numeric_object_id(object_id: str) -> int:
    digits = "".join(char for char in str(object_id) if char.isdigit())
    return int(digits or "1")


def _frame_index(config: Mapping[str, Any]) -> int:
    return int(config.get("frameIndex", config.get("frame_index", config.get("keyframe", 0))) or 0)


def _profile(config: Mapping[str, Any], *, default: str) -> str:
    return str(config.get("hostedProfile") or config.get("hosted_profile") or config.get("profile") or default)


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _synthetic_frame() -> np.ndarray:
    frame = np.zeros((16, 16, 3), dtype=np.uint8)
    frame[4:12, 4:12, :] = 255
    return frame
