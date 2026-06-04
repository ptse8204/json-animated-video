from __future__ import annotations

import json
import re
import threading
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Protocol

from motionjson.backend.usage import utc_now
from motionjson.config import ConfigValidationError, ExtractionRunConfig, RUN_CONFIG_SCHEMA
from motionjson.provider_settings import redact_secret_text


MODEL_CONNECTOR_FORMAT = "motionjson.model_connector.v0.1"
MODEL_ESTIMATE_FORMAT = "motionjson.model_estimate.v0.1"
MODEL_PLAN_FORMAT = "motionjson.model_plan.v0.1"
MODEL_RUN_FORMAT = "motionjson.model_run.v0.1"
MODEL_RUN_STATUSES = {"pending", "running", "cancel_requested", "canceled", "succeeded", "failed"}
OpenAIResponsesTransport = Callable[[str, Mapping[str, Any], Mapping[str, str], float], Mapping[str, Any]]

GOAL_ALIASES = {
    "cut_out_one_object": "trace_one_object",
    "trace_one_object": "trace_one_object",
    "manual_prompt": "trace_one_object",
    "trace_all_objects": "discover_objects",
    "discover_objects": "discover_objects",
    "auto_object_proposals": "discover_objects",
    "find_moving_things": "find_moving_things",
    "find_moving_objects": "find_moving_things",
    "motion_foreground": "find_moving_things",
    "find_by_description": "find_objects_from_text",
    "find_objects_from_text": "find_objects_from_text",
    "text_detector": "find_objects_from_text",
    "import_masks": "import_masks",
    "external_masks": "import_masks",
    "review_previous_result": "review_existing_result",
    "review_existing": "review_existing_result",
    "review_existing_result": "review_existing_result",
}


class ModelConnectorError(ValueError):
    """Raised when a model planning connector request is invalid."""


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ModelConnectorError(f"{path}: expected object")
    return value


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip() or default


def _bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _int(value: Any, default: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float(value: Any, default: float) -> float:
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _slug(value: str, default: str = "object_0") -> str:
    text = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip()).strip("_")
    if not text or not re.match(r"^[A-Za-z0-9]", text):
        text = default
    return text[:64]


def _labels_from_text(value: str) -> list[str]:
    labels = [part.strip(" .") for part in re.split(r"[,;\n]|\s+\.\s+", value) if part.strip(" .")]
    return labels[:12]


def _normalized_goal(goal: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", goal.strip().lower()).strip("_")
    return GOAL_ALIASES.get(key, key or "trace_one_object")


def _clean_base_url(base_url: str) -> str:
    return str(base_url or "").strip().rstrip("/") or "https://api.openai.com/v1"


def _hosted_safe_text(value: Any) -> str:
    text = redact_secret_text(str(value or ""))
    text = re.sub(r"(?<![\w:])/(?:Users|private|var|tmp|Volumes|home)/[^\s\"'<>]+", "[LOCAL_PATH_REDACTED]", text)
    text = re.sub(r"(?i)\bfile://[^\s\"'<>]+", "[LOCAL_FILE_URI_REDACTED]", text)
    text = re.sub(r"(?i)(?<![\w:])(?:[A-Z]:[\\/]|\\\\)[^\s\"'<>|]+", "[LOCAL_PATH_REDACTED]", text)
    return text


def _urllib_openai_responses_transport(
    url: str,
    payload: Mapping[str, Any],
    headers: Mapping[str, str],
    timeout: float,
) -> Mapping[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=dict(headers), method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise ModelConnectorError(redact_secret_text(f"OpenAI request failed with HTTP {exc.code}: {body}")) from exc
    except urllib.error.URLError as exc:
        raise ModelConnectorError(redact_secret_text(f"OpenAI request failed: {exc.reason}")) from exc


@dataclass(frozen=True)
class ModelProviderDefinition:
    id: str
    label: str
    kind: str = "planning_provider"
    locality: str = "local"
    implemented: bool = True
    network_required: bool = False
    hosted_calls_required: bool = False
    credential_required: bool = False
    settings_provider_id: str | None = None
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": MODEL_CONNECTOR_FORMAT,
            "id": self.id,
            "label": self.label,
            "kind": self.kind,
            "locality": self.locality,
            "implemented": self.implemented,
            "networkRequired": self.network_required,
            "hostedCallsRequired": self.hosted_calls_required,
            "credentialRequired": self.credential_required,
            "settingsProviderId": self.settings_provider_id,
            "description": self.description,
        }


@dataclass(frozen=True)
class ModelPlanRequest:
    goal: str = "trace_one_object"
    prompt: str = ""
    project_id: str | None = None
    video_id: str | None = None
    source_path: str | None = None
    output_directory: str | None = None
    object_label: str = "selected_object"
    object_id: str = "object_0"
    text_prompt: str = ""
    mask_dir: str = "masks/object_0"
    sample_fps: float = 12.0
    max_frames: int = 48
    max_objects: int = 12
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ModelPlanRequest":
        payload = _mapping(data, "modelPlanRequest")
        prompt = _text(payload.get("prompt") or payload.get("description") or payload.get("intent"))
        object_label = _text(payload.get("objectLabel") or payload.get("object_label"), "selected_object")
        return cls(
            goal=_normalized_goal(_text(payload.get("goal"), "trace_one_object")),
            prompt=prompt,
            project_id=_text(payload.get("projectId") or payload.get("project_id")) or None,
            video_id=_text(payload.get("videoId") or payload.get("video_id") or payload.get("assetId") or payload.get("asset_id")) or None,
            source_path=_text(payload.get("sourcePath") or payload.get("source_path") or payload.get("videoPath") or payload.get("video_path")) or None,
            output_directory=_text(payload.get("outputDirectory") or payload.get("output_directory")) or None,
            object_label=object_label,
            object_id=_slug(_text(payload.get("objectId") or payload.get("object_id"), object_label or "object_0")),
            text_prompt=_text(payload.get("textPrompt") or payload.get("text_prompt"), prompt),
            mask_dir=_text(payload.get("maskDir") or payload.get("mask_dir"), "masks/object_0"),
            sample_fps=_float(payload.get("sampleFps") or payload.get("sample_fps"), 12.0),
            max_frames=max(1, _int(payload.get("maxFrames") or payload.get("max_frames"), 48)),
            max_objects=max(1, _int(payload.get("maxObjects") or payload.get("max_objects"), 12)),
            metadata=dict(_mapping(payload.get("metadata"), "modelPlanRequest.metadata")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "prompt": self.prompt,
            "projectId": self.project_id,
            "videoId": self.video_id,
            "sourcePath": self.source_path,
            "outputDirectory": self.output_directory,
            "objectLabel": self.object_label,
            "objectId": self.object_id,
            "textPrompt": self.text_prompt,
            "maskDir": self.mask_dir,
            "sampleFps": self.sample_fps,
            "maxFrames": self.max_frames,
            "maxObjects": self.max_objects,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ModelEstimate:
    provider_id: str
    status: str = "zero_local"
    hosted_calls_required: bool = False
    frames_leave_device: bool = False
    estimated_units: int = 0
    message: str = "Fake planner runs in process and has no hosted cost."

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": MODEL_ESTIMATE_FORMAT,
            "providerId": self.provider_id,
            "status": self.status,
            "hostedCallsRequired": self.hosted_calls_required,
            "framesLeaveDevice": self.frames_leave_device,
            "estimatedUnits": self.estimated_units,
            "message": self.message,
        }


@dataclass(frozen=True)
class ModelPlanResult:
    provider_id: str
    request: ModelPlanRequest
    goal: str
    provider_plan: dict[str, Any]
    privacy: dict[str, Any]
    estimated_cost: dict[str, Any]
    run_config: dict[str, Any]
    validation: dict[str, Any]
    requires_user_confirmation: bool = True
    status: str = "planned"
    messages: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": MODEL_PLAN_FORMAT,
            "providerId": self.provider_id,
            "status": self.status,
            "goal": self.goal,
            "request": self.request.to_dict(),
            "providerPlan": dict(self.provider_plan),
            "privacy": dict(self.privacy),
            "estimatedCost": dict(self.estimated_cost),
            "requiresUserConfirmation": self.requires_user_confirmation,
            "runConfig": dict(self.run_config),
            "validation": dict(self.validation),
            "messages": list(self.messages),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ModelPlanResult":
        payload = _mapping(data, "modelPlan")
        request_payload = payload.get("request") if isinstance(payload.get("request"), Mapping) else {}
        run_config = dict(_mapping(payload.get("runConfig"), "modelPlan.runConfig"))
        validation = validate_run_config_payload(run_config)
        return cls(
            provider_id=_text(payload.get("providerId"), "fake-local-planner"),
            request=ModelPlanRequest.from_dict(request_payload),
            goal=_normalized_goal(_text(payload.get("goal"), "trace_one_object")),
            provider_plan=dict(_mapping(payload.get("providerPlan"), "modelPlan.providerPlan")),
            privacy=dict(_mapping(payload.get("privacy"), "modelPlan.privacy")),
            estimated_cost=dict(_mapping(payload.get("estimatedCost"), "modelPlan.estimatedCost")),
            run_config=validation.get("runConfig", run_config),
            validation=validation,
            requires_user_confirmation=_bool(payload.get("requiresUserConfirmation"), True),
            status=_text(payload.get("status"), "planned"),
            messages=[str(item) for item in payload.get("messages", []) if str(item).strip()]
            if isinstance(payload.get("messages"), list)
            else [],
        )


@dataclass(frozen=True)
class ModelRunEvent:
    id: str
    run_id: str
    event_type: str
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "runId": self.run_id,
            "eventType": self.event_type,
            "message": self.message,
            "metadata": dict(self.metadata),
            "createdAt": self.created_at,
        }


@dataclass(frozen=True)
class ModelRunState:
    id: str
    provider_id: str
    status: str
    request: ModelPlanRequest
    result: ModelPlanResult | None = None
    error: str | None = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    events: list[ModelRunEvent] = field(default_factory=list)

    def to_dict(self, *, include_events: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {
            "format": MODEL_RUN_FORMAT,
            "id": self.id,
            "providerId": self.provider_id,
            "status": self.status,
            "request": self.request.to_dict(),
            "result": self.result.to_dict() if self.result else None,
            "error": self.error,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }
        if include_events:
            data["events"] = [event.to_dict() for event in self.events]
        return data


class ModelConnector(Protocol):
    provider: ModelProviderDefinition

    def readiness(self) -> dict[str, Any]:
        ...

    def test(self, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        ...

    def estimate(self, request: ModelPlanRequest) -> ModelEstimate:
        ...

    def plan(self, request: ModelPlanRequest) -> ModelPlanResult:
        ...


def validate_run_config_payload(run_config: Mapping[str, Any]) -> dict[str, Any]:
    try:
        config = ExtractionRunConfig.from_dict(run_config)
    except ConfigValidationError as exc:
        return {"valid": False, "errors": [{"message": str(exc)}], "warnings": []}
    return {"valid": True, "errors": [], "warnings": [], "runConfig": config.to_dict()}


class FakeModelConnector:
    provider = ModelProviderDefinition(
        id="fake-local-planner",
        label="Fake in-process planner",
        locality="local",
        implemented=True,
        network_required=False,
        hosted_calls_required=False,
        credential_required=False,
        description="Deterministic no-network planner for Workspace tests and smoke runs.",
    )

    def readiness(self) -> dict[str, Any]:
        return {
            "status": "ready",
            "runnable": True,
            "networkAttempted": False,
            "hostedCallsRequired": False,
            "message": "Fake in-process planner is ready. It never calls hosted APIs.",
        }

    def test(self, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return {
            "format": "motionjson.model_provider_test.v0.1",
            "providerId": self.provider.id,
            "status": "ready",
            "networkAttempted": False,
            "hostedCallsRequired": False,
            "message": "Fake in-process planner test passed without network access.",
        }

    def estimate(self, request: ModelPlanRequest) -> ModelEstimate:
        units = 1 if request.goal in {"trace_one_object", "review_existing_result"} else max(1, min(request.max_objects, 12))
        return ModelEstimate(provider_id=self.provider.id, estimated_units=units)

    def plan(self, request: ModelPlanRequest) -> ModelPlanResult:
        run_config = self._run_config(request)
        validation = validate_run_config_payload(run_config)
        if validation["valid"]:
            run_config = validation["runConfig"]
        return ModelPlanResult(
            provider_id=self.provider.id,
            request=request,
            goal=request.goal,
            provider_plan=self._provider_plan(request),
            privacy={"framesLeaveDevice": False, "hostedCallsRequired": False, "summary": "Fake planning stays local."},
            estimated_cost=self.estimate(request).to_dict(),
            run_config=run_config,
            validation=validation,
            messages=["Review and validate this proposed run config before starting extraction."],
        )

    def _provider_plan(self, request: ModelPlanRequest) -> dict[str, Any]:
        discovery_provider = {
            "trace_one_object": "manual_prompt",
            "discover_objects": "auto_object_proposals",
            "find_moving_things": "motion_foreground",
            "find_objects_from_text": "text_detector",
            "import_masks": "external_masks",
            "review_existing_result": "manual_prompt",
        }.get(request.goal, "manual_prompt")
        mask_provider = {
            "find_moving_things": "motion",
            "import_masks": "external",
        }.get(request.goal, "mock")
        return {
            "reasoningProvider": self.provider.id,
            "discoveryProvider": discovery_provider,
            "maskProvider": mask_provider,
            "trackingMode": "selected_only",
            "reviewRequired": True,
        }

    def _run_config(self, request: ModelPlanRequest) -> dict[str, Any]:
        provider_plan = self._provider_plan(request)
        provider_name = str(provider_plan["maskProvider"])
        discovery_provider = str(provider_plan["discoveryProvider"])
        source_path = f"local-ui://assets/{request.video_id}" if request.video_id else request.source_path or "examples/demo_red_ball.mp4"
        output_directory = request.output_directory or f"out/ui-runs/{request.project_id or 'local'}"
        object_id = _slug(request.object_id or request.object_label)
        object_label = request.object_label or object_id
        discovery_config: dict[str, Any] = {"keyframes": [0], "mock": True}
        if discovery_provider == "text_detector":
            labels = _labels_from_text(request.text_prompt or request.prompt or object_label)
            discovery_config = {
                "text": request.text_prompt or request.prompt or object_label,
                "labels": labels or [object_label],
                "box_threshold": 0.35,
                "text_threshold": 0.25,
                "keyframes": [0],
                "max_candidates": request.max_objects,
                "deduplicate": True,
                "send_candidates_to_sam": True,
                "mock": True,
            }
        elif discovery_provider == "auto_object_proposals":
            discovery_config = {
                "mock": True,
                "qualityPreset": "balanced",
                "intent": "discover_objects_balanced",
                "providerPreference": "mock",
                "keyframePolicy": "scene_changes",
                "keyframes": [0],
                "maxKeyframes": 5,
                "frameInterval": None,
                "maxCandidatesPerKeyframe": 64,
                "maxObjects": request.max_objects,
                "minMaskArea": 64,
                "maxMaskAreaRatio": 0.6,
                "dedupeIou": 0.84,
                "stabilityThreshold": 0.78,
                "motionScoreWeight": 0.35,
                "rejectWholeFrame": True,
                "rejectBackgroundLike": True,
                "trackSelectedOnly": True,
                "trackTopCandidates": False,
                "requireReview": True,
                "writeRejectedCandidates": True,
                "requireExplicitCostWarning": False,
            }
        elif discovery_provider == "motion_foreground":
            discovery_config = {"threshold": 32, "min_area": 100, "max_candidates": request.max_objects, "morph_open": 3, "morph_close": 5, "keyframes": [0]}
        elif discovery_provider == "external_masks":
            discovery_config = {
                "objects": [{"object_id": object_id, "label": object_label, "mask_dir": request.mask_dir, "z_index": 10}],
                "manifest": None,
            }

        return {
            "schema": RUN_CONFIG_SCHEMA,
            "input": {"path": source_path},
            "output": {"directory": output_directory},
            "objects": [
                {
                    "object_id": object_id,
                    "label": object_label,
                    **({"mask_dir": request.mask_dir} if provider_name == "external" else {}),
                }
            ],
            "sampling": {"sample_fps": request.sample_fps, "max_frames": request.max_frames},
            "provider": {
                "name": provider_name,
                "threshold": {"lower_hsv": [0, 80, 80], "upper_hsv": [12, 255, 255]},
                "external": {"mask_dir": request.mask_dir if provider_name == "external" else None},
                "sam2": {
                    "checkpoint": None,
                    "model_config": None,
                    "device": None,
                    "prompt_frame": 0,
                    "endpoint": None,
                    "auth_env": "HOSTED_SEGMENTATION_API_KEY",
                    "endpoint_env": "HOSTED_SEGMENTATION_URL",
                    "hosted_config": {},
                    "hosted_allow_network": False,
                },
                "cache": {"enabled": True, "directory": ".motionjson-cache/masks"},
                "fallback_mask_provider": None,
            },
            "discovery": {"mode": discovery_provider, "config": discovery_config},
            "prompts": [],
            "filters": {"min_area": 100.0, "simplify_ratio": 0.006},
            "export": {
                "output_mode": "authoring",
                "feather": 0,
                "layer_padding": 4,
                "sprite_format": "webp",
                "production_avif": False,
            },
            "debug": {"benchmark": False, "benchmark_iterations": 3},
            "rights": {
                "source_type": "user_upload",
                "source_uri": source_path,
                "source_asset_id": request.video_id,
                "display_text": "User uploaded source video",
                "license": "user_uploaded_unverified",
                "license_name": "User uploaded - rights unverified",
                "license_url": None,
                "license_scope": "unknown",
                "creator_approved": False,
                "creator_approval_status": None,
                "commercial_use": False,
                "commercial_use_status": None,
            },
        }


OPENAI_PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "goal",
        "objectLabels",
        "objectId",
        "textPrompt",
        "suggestedKeyframes",
        "providerPlan",
        "troubleshooting",
    ],
    "properties": {
        "goal": {
            "type": "string",
            "enum": [
                "trace_one_object",
                "find_moving_things",
                "find_objects_from_text",
                "import_masks",
                "review_existing_result",
            ],
        },
        "objectLabels": {"type": "array", "items": {"type": "string"}},
        "objectId": {"type": "string"},
        "textPrompt": {"type": "string"},
        "suggestedKeyframes": {"type": "array", "items": {"type": "integer"}},
        "providerPlan": {
            "type": "object",
            "additionalProperties": False,
            "required": ["discoveryProvider", "maskProvider", "trackingMode", "rationale"],
            "properties": {
                "discoveryProvider": {
                    "type": "string",
                    "enum": ["manual_prompt", "motion_foreground", "text_detector", "external_masks"],
                },
                "maskProvider": {"type": "string", "enum": ["mock", "motion", "external"]},
                "trackingMode": {"type": "string", "enum": ["selected_only"]},
                "rationale": {"type": "string"},
            },
        },
        "troubleshooting": {"type": "array", "items": {"type": "string"}},
    },
}


OPENAI_PLANNING_INSTRUCTIONS = """You are MotionJSON's planning assistant.
Return only JSON that matches the supplied schema. Propose a conservative
object-tracing plan; do not claim to segment pixels, inspect video frames, or
discover objects directly. Route text requests through text_detector, moving
object requests through motion_foreground, mask imports through external_masks,
and single-object prompt workflows through manual_prompt. Use mock, motion, or
external mask providers only unless a later user-reviewed stage changes the CV
provider. Keep requires-review assumptions conservative."""


def _extract_openai_output_text(response: Mapping[str, Any]) -> str:
    output_text = response.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text
    output = response.get("output")
    if isinstance(output, list):
        chunks: list[str] = []
        for item in output:
            if not isinstance(item, Mapping):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if isinstance(part, Mapping) and isinstance(part.get("text"), str):
                    chunks.append(str(part["text"]))
        if chunks:
            return "\n".join(chunks)
    choices = response.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, Mapping):
            message = first.get("message")
            if isinstance(message, Mapping) and isinstance(message.get("content"), str):
                return str(message["content"])
    raise ModelConnectorError("OpenAI response did not include structured output text.")


def _parse_openai_plan_payload(response: Mapping[str, Any]) -> dict[str, Any]:
    try:
        parsed = json.loads(_extract_openai_output_text(response))
    except json.JSONDecodeError as exc:
        raise ModelConnectorError(f"OpenAI planner returned invalid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ModelConnectorError("OpenAI planner returned a non-object plan.")
    return parsed


def _safe_keyframes(value: Any, *, max_frames: int) -> list[int]:
    if not isinstance(value, list):
        return [0]
    frames: list[int] = []
    for item in value:
        if isinstance(item, bool):
            continue
        try:
            frame = int(item)
        except (TypeError, ValueError):
            continue
        if 0 <= frame < max(max_frames, 1):
            frames.append(frame)
    return sorted(set(frames))[:8] or [0]


class OpenAIPlanningConnector:
    provider = ModelProviderDefinition(
        id="openai-planner",
        label="OpenAI planner",
        locality="hosted",
        implemented=True,
        network_required=True,
        hosted_calls_required=True,
        credential_required=True,
        settings_provider_id="openai",
        description="Server-side OpenAI Responses API planner for reviewable MotionJSON extraction plans.",
    )

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        transport: OpenAIResponsesTransport | None = None,
        timeout: float = 45.0,
        allow_network: bool = False,
    ):
        self.api_key = api_key
        self.base_url = _clean_base_url(base_url or "https://api.openai.com/v1")
        self.model = model or "gpt-5.4-mini"
        self.transport = transport
        self.timeout = timeout
        self.allow_network = allow_network

    def with_runtime_settings(
        self,
        settings: Mapping[str, Any],
        *,
        allow_network: bool = False,
    ) -> "OpenAIPlanningConnector":
        return OpenAIPlanningConnector(
            api_key=str(settings.get("api_key") or "") or self.api_key,
            base_url=str(settings.get("base_url") or "") or self.base_url,
            model=str(settings.get("selected_model") or "") or self.model,
            transport=self.transport,
            timeout=self.timeout,
            allow_network=allow_network,
        )

    def readiness(self) -> dict[str, Any]:
        return {
            "status": "ready",
            "runnable": True,
            "networkAttempted": False,
            "hostedCallsRequired": True,
            "message": "OpenAI planner can run after server settings, hosted opt-in, and per-request confirmation.",
        }

    def test(self, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return {
            "format": "motionjson.model_provider_test.v0.1",
            "providerId": self.provider.id,
            "status": "configured",
            "ready": False,
            "networkAttempted": False,
            "hostedCallsRequired": True,
            "message": "OpenAI planner setup check is no-network; model runs require explicit hosted confirmation.",
        }

    def estimate(self, request: ModelPlanRequest) -> ModelEstimate:
        units = max(1, min(len((request.prompt or request.text_prompt or "").split()) // 24 + 1, 12))
        return ModelEstimate(
            provider_id=self.provider.id,
            status="unknown_provider_cost",
            hosted_calls_required=True,
            frames_leave_device=False,
            estimated_units=units,
            message="OpenAI planner sends text intent and redacted context only; provider billing depends on the selected model.",
        )

    def plan(self, request: ModelPlanRequest) -> ModelPlanResult:
        if not self.api_key:
            raise ModelConnectorError("OPENAI_API_KEY is required for openai-planner.")
        if not self.allow_network:
            raise ModelConnectorError(
                "openai-planner does not make hosted calls by default; pass allowNetwork=true with cost/privacy acknowledgement."
            )
        transport = self.transport or _urllib_openai_responses_transport
        payload = self._request_payload(request)
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        response = transport(f"{self.base_url}/responses", payload, headers, self.timeout)
        proposed = _parse_openai_plan_payload(response)
        return self._plan_result(request, proposed)

    def _request_payload(self, request: ModelPlanRequest) -> dict[str, Any]:
        safe_context = {
            "goal": request.goal,
            "prompt": _hosted_safe_text(request.prompt),
            "objectLabel": _hosted_safe_text(request.object_label),
            "objectId": _slug(_hosted_safe_text(request.object_id), request.object_id or "object_0"),
            "textPrompt": _hosted_safe_text(request.text_prompt),
            "hasRegisteredVideo": bool(request.video_id),
            "hasSourcePath": bool(request.source_path),
            "maxFrames": request.max_frames,
            "maxObjects": request.max_objects,
            "sampleFps": request.sample_fps,
        }
        return {
            "model": self.model,
            "instructions": OPENAI_PLANNING_INSTRUCTIONS,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": json.dumps(safe_context, sort_keys=True),
                        }
                    ],
                }
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "motionjson_run_plan",
                    "strict": True,
                    "schema": OPENAI_PLAN_SCHEMA,
                }
            },
            "store": False,
        }

    def _plan_result(self, request: ModelPlanRequest, proposed: Mapping[str, Any]) -> ModelPlanResult:
        labels = [str(item).strip() for item in proposed.get("objectLabels", []) if str(item).strip()] if isinstance(proposed.get("objectLabels"), list) else []
        goal = _normalized_goal(_text(proposed.get("goal"), request.goal))
        label = _text(labels[0] if labels else proposed.get("textPrompt"), request.object_label or "selected_object")
        safe_request = ModelPlanRequest(
            goal=goal,
            prompt=request.prompt,
            project_id=request.project_id,
            video_id=request.video_id,
            source_path=request.source_path,
            output_directory=request.output_directory,
            object_label=label,
            object_id=_slug(_text(proposed.get("objectId"), request.object_id or label), "object_0"),
            text_prompt=_text(proposed.get("textPrompt"), request.text_prompt or request.prompt or label),
            mask_dir=request.mask_dir,
            sample_fps=request.sample_fps,
            max_frames=request.max_frames,
            max_objects=request.max_objects,
            metadata={**request.metadata, "modelProvider": self.provider.id, "model": self.model},
        )
        local_builder = FakeModelConnector()
        run_config = local_builder._run_config(safe_request)
        keyframes = _safe_keyframes(proposed.get("suggestedKeyframes"), max_frames=safe_request.max_frames)
        discovery_config = run_config.get("discovery", {}).get("config")
        if isinstance(discovery_config, dict):
            discovery_config["keyframes"] = keyframes
        validation = validate_run_config_payload(run_config)
        if validation["valid"]:
            run_config = validation["runConfig"]
        provider_plan = local_builder._provider_plan(safe_request)
        provider_plan.update(
            {
                "reasoningProvider": self.provider.id,
                "model": self.model,
                "reviewRequired": True,
                "modelSuggestedKeyframes": keyframes,
            }
        )
        troubleshooting = [
            _hosted_safe_text(item)
            for item in proposed.get("troubleshooting", [])
            if isinstance(item, str) and item.strip()
        ][:6]
        return ModelPlanResult(
            provider_id=self.provider.id,
            request=safe_request,
            goal=safe_request.goal,
            provider_plan=provider_plan,
            privacy={
                "framesLeaveDevice": False,
                "hostedCallsRequired": True,
                "summary": "Only the text intent and redacted project context were sent to OpenAI.",
            },
            estimated_cost=self.estimate(safe_request).to_dict(),
            run_config=run_config,
            validation=validation,
            requires_user_confirmation=True,
            messages=[
                "OpenAI proposed a plan; MotionJSON generated and validated the run config inside the Runtime API.",
                *troubleshooting,
            ],
        )


class OpenRouterSettingsModelConnector:
    provider = ModelProviderDefinition(
        id="openrouter-planner",
        label="OpenRouter planner",
        locality="hosted",
        implemented=False,
        network_required=True,
        hosted_calls_required=True,
        credential_required=True,
        settings_provider_id="openrouter",
        description=(
            "Server-side settings surface for hosted model planning. "
            "UI-MODEL-03 reports readiness only; hosted planning transport is added later."
        ),
    )

    def readiness(self) -> dict[str, Any]:
        return {
            "status": "settings_required",
            "runnable": False,
            "networkAttempted": False,
            "hostedCallsRequired": True,
            "message": "OpenRouter planner is settings-backed and is not runnable until hosted planning is implemented.",
        }

    def test(self, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return {
            "format": "motionjson.model_provider_test.v0.1",
            "providerId": self.provider.id,
            "status": "settings_required",
            "ready": False,
            "networkAttempted": False,
            "hostedCallsRequired": True,
            "message": "Use the Workspace provider settings test for OpenRouter readiness. No hosted request was made.",
        }

    def estimate(self, request: ModelPlanRequest) -> ModelEstimate:
        return ModelEstimate(
            provider_id=self.provider.id,
            status="unknown_provider_cost",
            hosted_calls_required=True,
            frames_leave_device=False,
            estimated_units=max(1, min(request.max_objects, 12)),
            message=(
                "Hosted planner cost depends on the configured OpenRouter model. "
                "No hosted estimate request is made in UI-MODEL-03."
            ),
        )

    def plan(self, request: ModelPlanRequest) -> ModelPlanResult:
        raise ModelConnectorError(
            "openrouter-planner is settings-only in UI-MODEL-03; hosted planning is not enabled."
        )


class ModelConnectorRegistry:
    def __init__(self, connectors: list[ModelConnector] | None = None):
        items = connectors or [FakeModelConnector(), OpenAIPlanningConnector(), OpenRouterSettingsModelConnector()]
        self._connectors = {connector.provider.id: connector for connector in items}

    def list(self) -> list[ModelConnector]:
        return list(self._connectors.values())

    def get(self, provider_id: str) -> ModelConnector:
        try:
            return self._connectors[provider_id]
        except KeyError as exc:
            raise ModelConnectorError(f"unknown model provider: {provider_id}") from exc

    def default_provider_id(self) -> str:
        return "fake-local-planner"


class VolatileModelRunStore:
    """Thread-safe process-local model run store for Workspace planning smoke."""

    def __init__(self, *, max_runs: int = 128):
        self.max_runs = max_runs
        self._lock = threading.Lock()
        self._runs: dict[str, ModelRunState] = {}
        self._order: list[str] = []

    def create(self, *, provider_id: str, request: ModelPlanRequest) -> ModelRunState:
        run_id = uuid.uuid4().hex
        now = utc_now()
        event = ModelRunEvent(
            id=uuid.uuid4().hex,
            run_id=run_id,
            event_type="queued",
            message="model planning run queued",
            metadata={"progress": {"overallRatio": 0.0}},
            created_at=now,
        )
        run = ModelRunState(
            id=run_id,
            provider_id=provider_id,
            status="pending",
            request=request,
            created_at=now,
            updated_at=now,
            events=[event],
        )
        with self._lock:
            self._runs[run_id] = run
            self._order.append(run_id)
            self._trim_locked()
        return run

    def get(self, run_id: str) -> ModelRunState:
        with self._lock:
            if run_id not in self._runs:
                raise ModelConnectorError("model run not found")
            return self._runs[run_id]

    def events(self, run_id: str) -> list[ModelRunEvent]:
        return list(self.get(run_id).events)

    def mark_running(self, run_id: str) -> ModelRunState:
        return self._replace(
            run_id,
            status="running",
            event_type="running",
            message="fake model planner started",
            metadata={"progress": {"overallRatio": 0.25}},
        )

    def mark_succeeded(self, run_id: str, result: ModelPlanResult) -> ModelRunState:
        return self._replace(
            run_id,
            status="succeeded",
            result=result,
            event_type="planned",
            message="fake model planner produced a reviewable plan",
            metadata={"progress": {"overallRatio": 1.0}, "valid": result.validation.get("valid") is True},
        )

    def mark_failed(self, run_id: str, error: str) -> ModelRunState:
        return self._replace(
            run_id,
            status="failed",
            error=error,
            event_type="failed",
            message=error,
            metadata={"progress": {"overallRatio": 1.0}},
        )

    def cancel(self, run_id: str, *, reason: str = "user_canceled") -> ModelRunState:
        run = self.get(run_id)
        if run.status in {"succeeded", "failed", "canceled"}:
            return self._replace(
                run_id,
                event_type="cancel_ignored",
                message="model run is already terminal",
                metadata={"reason": reason, "status": run.status},
            )
        return self._replace(
            run_id,
            status="canceled",
            event_type="canceled",
            message="model planning run canceled",
            metadata={"reason": reason, "progress": {"overallRatio": 1.0}},
        )

    def _replace(
        self,
        run_id: str,
        *,
        status: str | None = None,
        result: ModelPlanResult | None = None,
        error: str | None = None,
        event_type: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> ModelRunState:
        with self._lock:
            if run_id not in self._runs:
                raise ModelConnectorError("model run not found")
            run = self._runs[run_id]
            event = ModelRunEvent(
                id=uuid.uuid4().hex,
                run_id=run_id,
                event_type=event_type,
                message=message,
                metadata=metadata or {},
            )
            updated = ModelRunState(
                id=run.id,
                provider_id=run.provider_id,
                status=status or run.status,
                request=run.request,
                result=result if result is not None else run.result,
                error=error if error is not None else run.error,
                created_at=run.created_at,
                updated_at=event.created_at,
                events=[*run.events, event],
            )
            self._runs[run_id] = updated
            return updated

    def _trim_locked(self) -> None:
        while len(self._order) > self.max_runs:
            expired = self._order.pop(0)
            self._runs.pop(expired, None)
