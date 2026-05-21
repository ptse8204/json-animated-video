from __future__ import annotations

import re
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

from motionjson.backend.usage import utc_now
from motionjson.config import ConfigValidationError, ExtractionRunConfig, RUN_CONFIG_SCHEMA


MODEL_CONNECTOR_FORMAT = "motionjson.model_connector.v0.1"
MODEL_ESTIMATE_FORMAT = "motionjson.model_estimate.v0.1"
MODEL_PLAN_FORMAT = "motionjson.model_plan.v0.1"
MODEL_RUN_FORMAT = "motionjson.model_run.v0.1"
MODEL_RUN_STATUSES = {"pending", "running", "cancel_requested", "canceled", "succeeded", "failed"}

GOAL_ALIASES = {
    "cut_out_one_object": "trace_one_object",
    "trace_one_object": "trace_one_object",
    "manual_prompt": "trace_one_object",
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
    message: str = "Fake planner runs locally and has no provider cost."

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
        label="Fake local planner",
        locality="local",
        implemented=True,
        network_required=False,
        hosted_calls_required=False,
        credential_required=False,
        description="Deterministic no-network planner for Local UI tests and smoke runs.",
    )

    def readiness(self) -> dict[str, Any]:
        return {
            "status": "ready",
            "runnable": True,
            "networkAttempted": False,
            "hostedCallsRequired": False,
            "message": "Fake local planner is ready. It never calls hosted APIs.",
        }

    def test(self, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return {
            "format": "motionjson.model_provider_test.v0.1",
            "providerId": self.provider.id,
            "status": "ready",
            "networkAttempted": False,
            "hostedCallsRequired": False,
            "message": "Fake local planner test passed without network access.",
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


class ModelConnectorRegistry:
    def __init__(self, connectors: list[ModelConnector] | None = None):
        items = connectors or [FakeModelConnector()]
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
    """Thread-safe process-local model run store for Local UI planning smoke."""

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
