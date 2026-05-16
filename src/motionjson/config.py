from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


RUN_CONFIG_SCHEMA = "motionjson.extraction_run_config.v0.1"
PROJECT_CONFIG_SCHEMA = "motionjson.project_config.v0.1"

SAFE_OBJECT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")

MASK_PROVIDERS = {"external", "threshold", "motion", "mock", "sam2", "sam2-local", "sam2-hosted"}
FALLBACK_MASK_PROVIDERS = {"threshold", "motion"}
PROMPT_KINDS = {"point", "positive_point", "negative_point", "box", "mask"}
DISCOVERY_MODES = {"manual_prompt", "sam_auto_masks", "text_detector", "class_detector", "motion_foreground", "external_masks"}
OUTPUT_MODES = {"authoring", "production", "both"}
SPRITE_FORMATS = {"webp", "png"}


class ConfigValidationError(ValueError):
    """Raised when an extraction/project config is malformed."""


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ConfigValidationError(f"{path}: expected object")
    return value


def _str_value(value: Any, path: str) -> str:
    if value is None:
        raise ConfigValidationError(f"{path}: required")
    text = str(value)
    if not text:
        raise ConfigValidationError(f"{path}: required")
    return text


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _int_value(value: Any, path: str) -> int:
    if isinstance(value, bool):
        raise ConfigValidationError(f"{path}: expected integer")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigValidationError(f"{path}: expected integer") from exc


def _optional_int(value: Any, path: str) -> int | None:
    if value is None:
        return None
    return _int_value(value, path)


def _float_value(value: Any, path: str) -> float:
    if isinstance(value, bool):
        raise ConfigValidationError(f"{path}: expected number")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigValidationError(f"{path}: expected number") from exc
    if not math.isfinite(number):
        raise ConfigValidationError(f"{path}: expected finite number")
    return number


def _optional_float(value: Any, path: str) -> float | None:
    if value is None:
        return None
    return _float_value(value, path)


def _bool_value(value: Any) -> bool:
    return bool(value)


def _choice(value: str | None, path: str, choices: set[str]) -> str | None:
    if value is None:
        return None
    if value not in choices:
        allowed = ", ".join(sorted(choices))
        raise ConfigValidationError(f"{path}: expected one of {allowed}")
    return value


def _hsv(value: Any, path: str) -> tuple[int, int, int]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ConfigValidationError(f"{path}: expected three HSV integers")
    h, s, v = (_int_value(part, f"{path}[{index}]") for index, part in enumerate(value))
    if not (0 <= h <= 179 and 0 <= s <= 255 and 0 <= v <= 255):
        raise ConfigValidationError(f"{path}: expected h=0..179 and s/v=0..255")
    return h, s, v


def _json_load(path: str | Path) -> Mapping[str, Any]:
    json_path = Path(path)
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigValidationError(f"{json_path}: invalid JSON: {exc}") from exc
    return _mapping(data, str(json_path))


def _write_json(path: str | Path, data: Mapping[str, Any]) -> None:
    json_path = Path(path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


@dataclass(frozen=True)
class VideoInputConfig:
    path: str

    def __post_init__(self) -> None:
        _str_value(self.path, "input.path")

    def to_dict(self) -> dict[str, Any]:
        return {"path": self.path}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "VideoInputConfig":
        payload = _mapping(data, "input")
        return cls(path=_str_value(payload.get("path"), "input.path"))


@dataclass(frozen=True)
class OutputConfig:
    directory: str

    def __post_init__(self) -> None:
        _str_value(self.directory, "output.directory")

    def to_dict(self) -> dict[str, Any]:
        return {"directory": self.directory}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "OutputConfig":
        payload = _mapping(data, "output")
        return cls(directory=_str_value(payload.get("directory"), "output.directory"))


@dataclass(frozen=True)
class SamplingConfig:
    sample_fps: float | None = 12.0
    max_frames: int | None = None

    def __post_init__(self) -> None:
        _optional_float(self.sample_fps, "sampling.sample_fps")
        _optional_int(self.max_frames, "sampling.max_frames")

    def to_dict(self) -> dict[str, Any]:
        return {"sample_fps": self.sample_fps, "max_frames": self.max_frames}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "SamplingConfig":
        payload = _mapping(data or {}, "sampling")
        return cls(
            sample_fps=_optional_float(payload.get("sample_fps", 12.0), "sampling.sample_fps"),
            max_frames=_optional_int(payload.get("max_frames"), "sampling.max_frames"),
        )


@dataclass(frozen=True)
class ObjectTargetConfig:
    object_id: str = "object_0"
    label: str = "selected_object"
    mask_dir: str | None = None
    z_index: int | None = None

    def __post_init__(self) -> None:
        if not SAFE_OBJECT_ID_PATTERN.match(self.object_id):
            raise ConfigValidationError("objects[].object_id: must use letters, numbers, underscores, or hyphens")
        _str_value(self.label, "objects[].label")
        if self.mask_dir is not None:
            _str_value(self.mask_dir, "objects[].mask_dir")
        if self.z_index is not None:
            _int_value(self.z_index, "objects[].z_index")

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"object_id": self.object_id, "label": self.label}
        if self.mask_dir is not None:
            data["mask_dir"] = self.mask_dir
        if self.z_index is not None:
            data["z_index"] = self.z_index
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ObjectTargetConfig":
        payload = _mapping(data, "objects[]")
        return cls(
            object_id=_str_value(payload.get("object_id", "object_0"), "objects[].object_id"),
            label=_str_value(payload.get("label", payload.get("object_id", "selected_object")), "objects[].label"),
            mask_dir=_optional_str(payload.get("mask_dir")),
            z_index=_optional_int(payload.get("z_index"), "objects[].z_index"),
        )


@dataclass(frozen=True)
class PromptSpec:
    kind: str
    frame_index: int = 0
    object_id: str | None = None
    label: str | None = None
    data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _choice(self.kind, "prompts[].kind", PROMPT_KINDS)
        frame_index = _int_value(self.frame_index, "prompts[].frame_index")
        if frame_index < 0:
            raise ConfigValidationError("prompts[].frame_index: expected >= 0")
        if self.object_id is not None and not SAFE_OBJECT_ID_PATTERN.match(self.object_id):
            raise ConfigValidationError("prompts[].object_id: must use letters, numbers, underscores, or hyphens")
        payload = _mapping(self.data, "prompts[].data")
        if self.kind in {"point", "positive_point", "negative_point"}:
            x = _int_value(payload.get("x"), "prompts[].data.x")
            y = _int_value(payload.get("y"), "prompts[].data.y")
            if x < 0 or y < 0:
                raise ConfigValidationError("prompts[].data: point coordinates must be >= 0")
        if self.kind == "box":
            x = _int_value(payload.get("x"), "prompts[].data.x")
            y = _int_value(payload.get("y"), "prompts[].data.y")
            w = _int_value(payload.get("w"), "prompts[].data.w")
            h = _int_value(payload.get("h"), "prompts[].data.h")
            if x < 0 or y < 0:
                raise ConfigValidationError("prompts[].data: box origin must be >= 0")
            if w <= 0 or h <= 0:
                raise ConfigValidationError("prompts[].data: box width and height must be > 0")
        if self.kind == "mask" and not payload:
            raise ConfigValidationError("prompts[].data: mask prompt requires mask data or reference")

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "kind": self.kind,
            "frame_index": self.frame_index,
            "data": dict(self.data),
        }
        if self.object_id is not None:
            data["object_id"] = self.object_id
        if self.label is not None:
            data["label"] = self.label
        return data

    @classmethod
    def point(
        cls,
        x: int,
        y: int,
        *,
        frame_index: int = 0,
        object_id: str | None = None,
        label: str | None = None,
        kind: str = "point",
    ) -> "PromptSpec":
        return cls(kind=kind, frame_index=frame_index, object_id=object_id, label=label, data={"x": x, "y": y})

    @classmethod
    def box(
        cls,
        x: int,
        y: int,
        w: int,
        h: int,
        *,
        frame_index: int = 0,
        object_id: str | None = None,
        label: str | None = None,
    ) -> "PromptSpec":
        return cls(kind="box", frame_index=frame_index, object_id=object_id, label=label, data={"x": x, "y": y, "w": w, "h": h})

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PromptSpec":
        payload = _mapping(data, "prompts[]")
        return cls(
            kind=_str_value(payload.get("kind"), "prompts[].kind"),
            frame_index=_int_value(payload.get("frame_index", 0), "prompts[].frame_index"),
            object_id=_optional_str(payload.get("object_id")),
            label=_optional_str(payload.get("label")),
            data=dict(_mapping(payload.get("data", {}), "prompts[].data")),
        )


@dataclass(frozen=True)
class ThresholdProviderConfig:
    lower_hsv: tuple[int, int, int] = (0, 80, 80)
    upper_hsv: tuple[int, int, int] = (12, 255, 255)

    def __post_init__(self) -> None:
        _hsv(self.lower_hsv, "provider.threshold.lower_hsv")
        _hsv(self.upper_hsv, "provider.threshold.upper_hsv")

    def to_dict(self) -> dict[str, Any]:
        return {"lower_hsv": list(self.lower_hsv), "upper_hsv": list(self.upper_hsv)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "ThresholdProviderConfig":
        payload = _mapping(data or {}, "provider.threshold")
        return cls(
            lower_hsv=_hsv(payload.get("lower_hsv", (0, 80, 80)), "provider.threshold.lower_hsv"),
            upper_hsv=_hsv(payload.get("upper_hsv", (12, 255, 255)), "provider.threshold.upper_hsv"),
        )


@dataclass(frozen=True)
class ExternalMaskProviderConfig:
    mask_dir: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"mask_dir": self.mask_dir}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "ExternalMaskProviderConfig":
        payload = _mapping(data or {}, "provider.external")
        return cls(mask_dir=_optional_str(payload.get("mask_dir")))


@dataclass(frozen=True)
class SAM2ProviderConfig:
    checkpoint: str | None = None
    model_config: str | None = None
    device: str | None = None
    prompt_frame: int = 0
    endpoint: str | None = None
    auth_env: str = "HOSTED_SEGMENTATION_API_KEY"
    endpoint_env: str = "HOSTED_SEGMENTATION_URL"
    hosted_config: dict[str, Any] = field(default_factory=dict)
    hosted_allow_network: bool = False

    def __post_init__(self) -> None:
        frame = _int_value(self.prompt_frame, "provider.sam2.prompt_frame")
        if frame < 0:
            raise ConfigValidationError("provider.sam2.prompt_frame: expected >= 0")
        if not isinstance(self.hosted_config, Mapping):
            raise ConfigValidationError("provider.sam2.hosted_config: expected object")

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkpoint": self.checkpoint,
            "model_config": self.model_config,
            "device": self.device,
            "prompt_frame": self.prompt_frame,
            "endpoint": self.endpoint,
            "auth_env": self.auth_env,
            "endpoint_env": self.endpoint_env,
            "hosted_config": dict(self.hosted_config),
            "hosted_allow_network": self.hosted_allow_network,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "SAM2ProviderConfig":
        payload = _mapping(data or {}, "provider.sam2")
        return cls(
            checkpoint=_optional_str(payload.get("checkpoint")),
            model_config=_optional_str(payload.get("model_config")),
            device=_optional_str(payload.get("device")),
            prompt_frame=_int_value(payload.get("prompt_frame", 0), "provider.sam2.prompt_frame"),
            endpoint=_optional_str(payload.get("endpoint")),
            auth_env=_str_value(payload.get("auth_env", "HOSTED_SEGMENTATION_API_KEY"), "provider.sam2.auth_env"),
            endpoint_env=_str_value(payload.get("endpoint_env", "HOSTED_SEGMENTATION_URL"), "provider.sam2.endpoint_env"),
            hosted_config=dict(_mapping(payload.get("hosted_config", {}), "provider.sam2.hosted_config")),
            hosted_allow_network=_bool_value(payload.get("hosted_allow_network", False)),
        )


@dataclass(frozen=True)
class MaskCacheConfig:
    enabled: bool = True
    directory: str = ".motionjson-cache/masks"

    def __post_init__(self) -> None:
        _str_value(self.directory, "provider.cache.directory")

    def to_dict(self) -> dict[str, Any]:
        return {"enabled": self.enabled, "directory": self.directory}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "MaskCacheConfig":
        payload = _mapping(data or {}, "provider.cache")
        return cls(
            enabled=_bool_value(payload.get("enabled", True)),
            directory=_str_value(payload.get("directory", ".motionjson-cache/masks"), "provider.cache.directory"),
        )


@dataclass(frozen=True)
class ProviderConfig:
    name: str = "threshold"
    threshold: ThresholdProviderConfig = field(default_factory=ThresholdProviderConfig)
    external: ExternalMaskProviderConfig = field(default_factory=ExternalMaskProviderConfig)
    sam2: SAM2ProviderConfig = field(default_factory=SAM2ProviderConfig)
    cache: MaskCacheConfig = field(default_factory=MaskCacheConfig)
    fallback_mask_provider: str | None = None

    def __post_init__(self) -> None:
        _choice(self.name, "provider.name", MASK_PROVIDERS)
        _choice(self.fallback_mask_provider, "provider.fallback_mask_provider", FALLBACK_MASK_PROVIDERS)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "threshold": self.threshold.to_dict(),
            "external": self.external.to_dict(),
            "sam2": self.sam2.to_dict(),
            "cache": self.cache.to_dict(),
            "fallback_mask_provider": self.fallback_mask_provider,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "ProviderConfig":
        payload = _mapping(data or {}, "provider")
        return cls(
            name=_str_value(payload.get("name", "threshold"), "provider.name"),
            threshold=ThresholdProviderConfig.from_dict(payload.get("threshold")),
            external=ExternalMaskProviderConfig.from_dict(payload.get("external")),
            sam2=SAM2ProviderConfig.from_dict(payload.get("sam2")),
            cache=MaskCacheConfig.from_dict(payload.get("cache")),
            fallback_mask_provider=_optional_str(payload.get("fallback_mask_provider")),
        )


@dataclass(frozen=True)
class DiscoveryConfig:
    mode: str | None = None
    config: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _choice(self.mode, "discovery.mode", DISCOVERY_MODES)
        if not isinstance(self.config, Mapping):
            raise ConfigValidationError("discovery.config: expected object")

    def to_dict(self) -> dict[str, Any]:
        return {"mode": self.mode, "config": dict(self.config)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "DiscoveryConfig":
        payload = _mapping(data or {}, "discovery")
        return cls(
            mode=_optional_str(payload.get("mode")),
            config=dict(_mapping(payload.get("config", {}), "discovery.config")),
        )


@dataclass(frozen=True)
class FilterConfig:
    min_area: float = 100.0
    simplify_ratio: float = 0.006

    def __post_init__(self) -> None:
        min_area = _float_value(self.min_area, "filters.min_area")
        simplify = _float_value(self.simplify_ratio, "filters.simplify_ratio")
        if min_area < 0:
            raise ConfigValidationError("filters.min_area: expected >= 0")
        if not 0 <= simplify <= 1:
            raise ConfigValidationError("filters.simplify_ratio: expected 0..1")

    def to_dict(self) -> dict[str, Any]:
        return {"min_area": self.min_area, "simplify_ratio": self.simplify_ratio}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "FilterConfig":
        payload = _mapping(data or {}, "filters")
        return cls(
            min_area=_float_value(payload.get("min_area", 100.0), "filters.min_area"),
            simplify_ratio=_float_value(payload.get("simplify_ratio", 0.006), "filters.simplify_ratio"),
        )


@dataclass(frozen=True)
class ExportConfig:
    output_mode: str = "authoring"
    feather: int = 0
    layer_padding: int = 4
    sprite_format: str = "webp"
    production_avif: bool = False

    def __post_init__(self) -> None:
        _choice(self.output_mode, "export.output_mode", OUTPUT_MODES)
        feather = _int_value(self.feather, "export.feather")
        padding = _int_value(self.layer_padding, "export.layer_padding")
        if feather < 0:
            raise ConfigValidationError("export.feather: expected >= 0")
        if padding < 0:
            raise ConfigValidationError("export.layer_padding: expected >= 0")
        _choice(self.sprite_format, "export.sprite_format", SPRITE_FORMATS)

    def to_dict(self) -> dict[str, Any]:
        return {
            "output_mode": self.output_mode,
            "feather": self.feather,
            "layer_padding": self.layer_padding,
            "sprite_format": self.sprite_format,
            "production_avif": self.production_avif,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "ExportConfig":
        payload = _mapping(data or {}, "export")
        return cls(
            output_mode=_str_value(payload.get("output_mode", "authoring"), "export.output_mode"),
            feather=_int_value(payload.get("feather", 0), "export.feather"),
            layer_padding=_int_value(payload.get("layer_padding", 4), "export.layer_padding"),
            sprite_format=_str_value(payload.get("sprite_format", "webp"), "export.sprite_format"),
            production_avif=_bool_value(payload.get("production_avif", False)),
        )


@dataclass(frozen=True)
class DebugConfig:
    benchmark: bool = False
    benchmark_iterations: int = 3

    def __post_init__(self) -> None:
        iterations = _int_value(self.benchmark_iterations, "debug.benchmark_iterations")
        if iterations < 1:
            raise ConfigValidationError("debug.benchmark_iterations: expected >= 1")

    def to_dict(self) -> dict[str, Any]:
        return {"benchmark": self.benchmark, "benchmark_iterations": self.benchmark_iterations}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "DebugConfig":
        payload = _mapping(data or {}, "debug")
        return cls(
            benchmark=_bool_value(payload.get("benchmark", False)),
            benchmark_iterations=_int_value(payload.get("benchmark_iterations", 3), "debug.benchmark_iterations"),
        )


@dataclass(frozen=True)
class RightsConfig:
    source_type: str = "user_upload"
    source_uri: str | None = None
    source_asset_id: str | None = None
    display_text: str = "User uploaded source video"
    license: str = "user_uploaded_unverified"
    license_name: str = "User uploaded - rights unverified"
    license_url: str | None = None
    license_scope: str = "unknown"
    creator_approved: bool = False
    creator_approval_status: str | None = None
    commercial_use: bool = False
    commercial_use_status: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type,
            "source_uri": self.source_uri,
            "source_asset_id": self.source_asset_id,
            "display_text": self.display_text,
            "license": self.license,
            "license_name": self.license_name,
            "license_url": self.license_url,
            "license_scope": self.license_scope,
            "creator_approved": self.creator_approved,
            "creator_approval_status": self.creator_approval_status,
            "commercial_use": self.commercial_use,
            "commercial_use_status": self.commercial_use_status,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "RightsConfig":
        payload = _mapping(data or {}, "rights")
        return cls(
            source_type=_str_value(payload.get("source_type", "user_upload"), "rights.source_type"),
            source_uri=_optional_str(payload.get("source_uri")),
            source_asset_id=_optional_str(payload.get("source_asset_id")),
            display_text=_str_value(payload.get("display_text", "User uploaded source video"), "rights.display_text"),
            license=_str_value(payload.get("license", "user_uploaded_unverified"), "rights.license"),
            license_name=_str_value(payload.get("license_name", "User uploaded - rights unverified"), "rights.license_name"),
            license_url=_optional_str(payload.get("license_url")),
            license_scope=_str_value(payload.get("license_scope", "unknown"), "rights.license_scope"),
            creator_approved=_bool_value(payload.get("creator_approved", False)),
            creator_approval_status=_optional_str(payload.get("creator_approval_status")),
            commercial_use=_bool_value(payload.get("commercial_use", False)),
            commercial_use_status=_optional_str(payload.get("commercial_use_status")),
        )


@dataclass(frozen=True)
class ExtractionRunConfig:
    input_video: VideoInputConfig
    output: OutputConfig
    objects: list[ObjectTargetConfig] = field(default_factory=lambda: [ObjectTargetConfig()])
    sampling: SamplingConfig = field(default_factory=SamplingConfig)
    provider: ProviderConfig = field(default_factory=ProviderConfig)
    discovery: DiscoveryConfig = field(default_factory=DiscoveryConfig)
    prompts: list[PromptSpec] = field(default_factory=list)
    filters: FilterConfig = field(default_factory=FilterConfig)
    export: ExportConfig = field(default_factory=ExportConfig)
    debug: DebugConfig = field(default_factory=DebugConfig)
    rights: RightsConfig = field(default_factory=RightsConfig)
    schema: str = RUN_CONFIG_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != RUN_CONFIG_SCHEMA:
            raise ConfigValidationError(f"schema: expected {RUN_CONFIG_SCHEMA}")
        if not self.objects:
            raise ConfigValidationError("objects: at least one object target is required")
        object_ids = [obj.object_id for obj in self.objects]
        if len(set(object_ids)) != len(object_ids):
            raise ConfigValidationError("objects: object_id values must be unique")
        if self.provider.name == "external" and not self.provider.external.mask_dir and not any(obj.mask_dir for obj in self.objects):
            raise ConfigValidationError("provider.external.mask_dir: required when provider is external")
        if self.provider.name in {"sam2-local", "sam2-hosted"} and not any(prompt.kind in {"point", "positive_point", "box"} for prompt in self.prompts):
            raise ConfigValidationError(f"prompts: {self.provider.name} requires a point or box prompt")

    @property
    def object_id(self) -> str:
        return self.objects[0].object_id

    @property
    def label(self) -> str:
        return self.objects[0].label

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "input": self.input_video.to_dict(),
            "output": self.output.to_dict(),
            "objects": [obj.to_dict() for obj in self.objects],
            "sampling": self.sampling.to_dict(),
            "provider": self.provider.to_dict(),
            "discovery": self.discovery.to_dict(),
            "prompts": [prompt.to_dict() for prompt in self.prompts],
            "filters": self.filters.to_dict(),
            "export": self.export.to_dict(),
            "debug": self.debug.to_dict(),
            "rights": self.rights.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ExtractionRunConfig":
        payload = _mapping(data, "run_config")
        objects_payload = payload.get("objects", [{"object_id": "object_0", "label": "selected_object"}])
        if not isinstance(objects_payload, list):
            raise ConfigValidationError("objects: expected array")
        prompts_payload = payload.get("prompts", [])
        if not isinstance(prompts_payload, list):
            raise ConfigValidationError("prompts: expected array")
        return cls(
            schema=_str_value(payload.get("schema", RUN_CONFIG_SCHEMA), "schema"),
            input_video=VideoInputConfig.from_dict(_mapping(payload.get("input"), "input")),
            output=OutputConfig.from_dict(_mapping(payload.get("output"), "output")),
            objects=[ObjectTargetConfig.from_dict(item) for item in objects_payload],
            sampling=SamplingConfig.from_dict(payload.get("sampling")),
            provider=ProviderConfig.from_dict(payload.get("provider")),
            discovery=DiscoveryConfig.from_dict(payload.get("discovery")),
            prompts=[PromptSpec.from_dict(item) for item in prompts_payload],
            filters=FilterConfig.from_dict(payload.get("filters")),
            export=ExportConfig.from_dict(payload.get("export")),
            debug=DebugConfig.from_dict(payload.get("debug")),
            rights=RightsConfig.from_dict(payload.get("rights")),
        )

    @classmethod
    def from_json_file(cls, path: str | Path) -> "ExtractionRunConfig":
        return cls.from_dict(_json_load(path))

    def write_json_file(self, path: str | Path) -> None:
        _write_json(path, self.to_dict())


@dataclass(frozen=True)
class ProjectConfig:
    name: str
    runs: list[ExtractionRunConfig] = field(default_factory=list)
    schema: str = PROJECT_CONFIG_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != PROJECT_CONFIG_SCHEMA:
            raise ConfigValidationError(f"schema: expected {PROJECT_CONFIG_SCHEMA}")
        _str_value(self.name, "project.name")

    def to_dict(self) -> dict[str, Any]:
        return {"schema": self.schema, "name": self.name, "runs": [run.to_dict() for run in self.runs]}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ProjectConfig":
        payload = _mapping(data, "project")
        runs_payload = payload.get("runs", [])
        if not isinstance(runs_payload, list):
            raise ConfigValidationError("project.runs: expected array")
        return cls(
            schema=_str_value(payload.get("schema", PROJECT_CONFIG_SCHEMA), "schema"),
            name=_str_value(payload.get("name"), "project.name"),
            runs=[ExtractionRunConfig.from_dict(item) for item in runs_payload],
        )

    @classmethod
    def from_json_file(cls, path: str | Path) -> "ProjectConfig":
        return cls.from_dict(_json_load(path))

    def write_json_file(self, path: str | Path) -> None:
        _write_json(path, self.to_dict())


def load_run_config(path: str | Path) -> ExtractionRunConfig:
    return ExtractionRunConfig.from_json_file(path)


def write_run_config(config: ExtractionRunConfig, path: str | Path) -> None:
    config.write_json_file(path)


def load_project_config(path: str | Path) -> ProjectConfig:
    return ProjectConfig.from_json_file(path)


def write_project_config(config: ProjectConfig, path: str | Path) -> None:
    config.write_json_file(path)


def _assignment_pairs(values: list[tuple[str, str]], field_name: str) -> dict[str, str]:
    output: dict[str, str] = {}
    for object_id, value in values:
        if object_id in output:
            raise ConfigValidationError(f"{field_name}: duplicate object id {object_id!r}")
        output[object_id] = value
    return output


def build_extraction_run_config_from_args(args: Any) -> ExtractionRunConfig:
    prompt_frame = int(getattr(args, "sam2_prompt_frame", 0) or 0)
    object_id = str(getattr(args, "object_id", "object_0"))
    label = str(getattr(args, "label", "selected_object"))
    prompts: list[PromptSpec] = []
    prompt_point = getattr(args, "prompt_point", None)
    if prompt_point is not None:
        prompts.append(PromptSpec.point(prompt_point[0], prompt_point[1], frame_index=prompt_frame, object_id=object_id, label=label))
    prompt_box = getattr(args, "prompt_box", None)
    if prompt_box is not None:
        prompts.append(PromptSpec.box(prompt_box[0], prompt_box[1], prompt_box[2], prompt_box[3], frame_index=prompt_frame, object_id=object_id, label=label))

    object_mask_dirs = _assignment_pairs(list(getattr(args, "object_mask_dir", []) or []), "--object-mask-dir")
    object_labels = _assignment_pairs(list(getattr(args, "object_label", []) or []), "--object-label")
    missing_mask_dirs = sorted(set(object_labels) - set(object_mask_dirs))
    if missing_mask_dirs:
        raise ConfigValidationError(f"--object-label: missing --object-mask-dir for {', '.join(missing_mask_dirs)}")

    if object_mask_dirs:
        objects = [
            ObjectTargetConfig(
                object_id=current_object_id,
                label=object_labels.get(current_object_id, current_object_id),
                mask_dir=mask_dir,
                z_index=10 + index * 10,
            )
            for index, (current_object_id, mask_dir) in enumerate(object_mask_dirs.items())
        ]
    else:
        objects = [ObjectTargetConfig(object_id=object_id, label=label)]

    provider = ProviderConfig(
        name=str(getattr(args, "mask_provider", "threshold")),
        threshold=ThresholdProviderConfig(
            lower_hsv=tuple(getattr(args, "lower_hsv", (0, 80, 80))),
            upper_hsv=tuple(getattr(args, "upper_hsv", (12, 255, 255))),
        ),
        external=ExternalMaskProviderConfig(mask_dir=_optional_str(getattr(args, "mask_dir", None))),
        sam2=SAM2ProviderConfig(
            checkpoint=_optional_str(getattr(args, "sam2_checkpoint", None)),
            model_config=_optional_str(getattr(args, "sam2_model_config", None)),
            device=_optional_str(getattr(args, "sam2_device", None)),
            prompt_frame=prompt_frame,
            endpoint=_optional_str(getattr(args, "sam2_endpoint", None)),
            auth_env=str(getattr(args, "sam2_auth_env", "HOSTED_SEGMENTATION_API_KEY")),
            endpoint_env=str(getattr(args, "sam2_endpoint_env", "HOSTED_SEGMENTATION_URL")),
            hosted_config=dict(getattr(args, "sam2_hosted_config", {}) or {}),
            hosted_allow_network=bool(getattr(args, "sam2_hosted_allow_network", False)),
        ),
        cache=MaskCacheConfig(
            enabled=not bool(getattr(args, "no_mask_cache", False)),
            directory=str(getattr(args, "mask_cache_dir", ".motionjson-cache/masks")),
        ),
        fallback_mask_provider=_optional_str(getattr(args, "fallback_mask_provider", None)),
    )
    discovery_config = dict(getattr(args, "discovery_config", {}) or {})
    discovery_text = _optional_str(getattr(args, "discovery_text", None))
    if discovery_text is not None:
        discovery_config["text"] = discovery_text
    discovery_classes = list(getattr(args, "discovery_class", []) or [])
    if discovery_classes:
        discovery_config["classes"] = discovery_classes
    discovery_max_candidates = getattr(args, "discovery_max_candidates", None)
    if discovery_max_candidates is not None:
        discovery_config["max_candidates"] = _int_value(discovery_max_candidates, "discovery.config.max_candidates")
    discovery_min_area = getattr(args, "discovery_min_area", None)
    if discovery_min_area is not None:
        discovery_config["min_area"] = _float_value(discovery_min_area, "discovery.config.min_area")

    return ExtractionRunConfig(
        input_video=VideoInputConfig(path=str(getattr(args, "video"))),
        output=OutputConfig(directory=str(getattr(args, "out", "out/motionjson"))),
        objects=objects,
        sampling=SamplingConfig(
            sample_fps=_optional_float(getattr(args, "sample_fps", 12.0), "sampling.sample_fps"),
            max_frames=_optional_int(getattr(args, "max_frames", None), "sampling.max_frames"),
        ),
        provider=provider,
        discovery=DiscoveryConfig(
            mode=_optional_str(getattr(args, "discovery_provider", None)),
            config=discovery_config,
        ),
        prompts=prompts,
        filters=FilterConfig(
            min_area=_float_value(getattr(args, "min_area", 100.0), "filters.min_area"),
            simplify_ratio=_float_value(getattr(args, "simplify", 0.006), "filters.simplify_ratio"),
        ),
        export=ExportConfig(
            output_mode=str(getattr(args, "output_mode", "authoring")),
            feather=_int_value(getattr(args, "feather", 0), "export.feather"),
            layer_padding=_int_value(getattr(args, "layer_padding", 4), "export.layer_padding"),
            sprite_format=str(getattr(args, "sprite_format", "webp")),
            production_avif=bool(getattr(args, "production_avif", False)),
        ),
        debug=DebugConfig(
            benchmark=bool(getattr(args, "benchmark", False)),
            benchmark_iterations=_int_value(getattr(args, "benchmark_iterations", 3), "debug.benchmark_iterations"),
        ),
        rights=RightsConfig(
            source_type=str(getattr(args, "rights_source_type", "user_upload")),
            source_uri=_optional_str(getattr(args, "rights_source_uri", None)),
            source_asset_id=_optional_str(getattr(args, "rights_source_asset_id", None)),
            display_text=str(getattr(args, "rights_display_text", "User uploaded source video")),
            license=str(getattr(args, "license", "user_uploaded_unverified")),
            license_name=str(getattr(args, "license_name", "User uploaded - rights unverified")),
            license_url=_optional_str(getattr(args, "license_url", None)),
            license_scope=str(getattr(args, "license_scope", "unknown")),
            creator_approved=bool(getattr(args, "creator_approved", False)),
            creator_approval_status=_optional_str(getattr(args, "creator_approval_status", None)),
            commercial_use=bool(getattr(args, "commercial_use", False)),
            commercial_use_status=_optional_str(getattr(args, "commercial_use_status", None)),
        ),
    )
