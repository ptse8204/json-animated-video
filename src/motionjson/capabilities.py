from __future__ import annotations

import importlib.util
import json
import os
import platform
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


CAPABILITY_SCHEMA = "motionjson.provider_diagnostics.v0.1"


@dataclass(frozen=True)
class DependencyStatus:
    name: str
    module: str
    available: bool
    reason: str | None = None
    install_hint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "module": self.module,
            "available": self.available,
            "reason": self.reason,
            "installHint": self.install_hint,
        }


@dataclass(frozen=True)
class ProviderCapability:
    name: str
    kind: str
    available: bool
    status: str
    configured: bool = True
    installed: bool | None = None
    runnable: bool | None = None
    supports: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    install_hint: str | None = None
    device: str | None = None
    no_model_safe: bool = False
    network_required: bool = False
    needs_credentials: bool = False
    needs_gpu: bool = False
    needs_model_path: bool = False
    model_paths: list[dict[str, Any]] = field(default_factory=list)
    mock_available: bool = False
    optional_extra: str | None = None
    checks: list[dict[str, Any]] = field(default_factory=list)
    estimated_cost: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        installed = self.installed if self.installed is not None else self.status != "missing_dependency"
        runnable = self.runnable if self.runnable is not None else bool(self.available and not self.network_required)
        estimated_cost = self.estimated_cost or _default_estimated_cost(self.network_required)
        return {
            "name": self.name,
            "kind": self.kind,
            "available": self.available,
            "status": self.status,
            "configured": self.configured,
            "installed": bool(installed),
            "runnable": bool(runnable),
            "supports": list(self.supports),
            "reasons": list(self.reasons),
            "installHint": self.install_hint,
            "device": self.device,
            "noModelSafe": self.no_model_safe,
            "networkRequired": self.network_required,
            "needsCredentials": bool(self.needs_credentials or self.network_required),
            "needsGpu": bool(self.needs_gpu),
            "needsModelPath": bool(self.needs_model_path or self.model_paths),
            "modelPaths": [dict(path) for path in self.model_paths],
            "mockAvailable": self.mock_available,
            "optionalExtra": self.optional_extra,
            "checks": list(self.checks),
            "estimatedCost": dict(estimated_cost),
            "metadata": dict(self.metadata),
        }


def _default_estimated_cost(network_required: bool) -> dict[str, Any]:
    if network_required:
        return {
            "amount": None,
            "unit": "provider_request",
            "status": "unknown_provider_cost",
        }
    return {
        "amount": 0.0,
        "unit": "local",
        "status": "zero_local",
    }


def _check(name: str, status: str, detail: str | None = None, value: Any | None = None) -> dict[str, Any]:
    return {"name": name, "status": status, "detail": detail, "value": value}


def _module_available(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


def _dependency(name: str, module: str, install_hint: str | None = None) -> DependencyStatus:
    available = _module_available(module)
    return DependencyStatus(
        name=name,
        module=module,
        available=available,
        reason=None if available else f"Python module {module!r} is not importable.",
        install_hint=install_hint if not available else None,
    )


def _env_config(name: str) -> dict[str, Any]:
    return {"env": name, "configured": bool(os.environ.get(name))}


def _path_config_status(name: str, explicit_value: str | Path | None = None) -> dict[str, Any]:
    env_value = os.environ.get(name)
    if explicit_value is not None:
        value = str(explicit_value)
        source = "argument"
    elif env_value:
        value = env_value
        source = "environment"
    else:
        value = None
        source = "unset"
    return {
        "env": name,
        "configured": bool(value),
        "exists": bool(value and Path(value).exists()),
        "source": source,
    }


def _model_path_reasons(path_status: dict[str, Any], label: str, flag: str) -> list[str]:
    if not path_status["configured"]:
        return [f"{label} is not configured. Set {path_status['env']} or pass {flag}."]
    if not path_status["exists"]:
        return [f"Configured {label.lower()} path does not point to an existing file."]
    return []


def cuda_status() -> dict[str, Any]:
    if not _module_available("torch"):
        return {
            "torchInstalled": False,
            "available": False,
            "device": "cpu",
            "reasons": ["torch is not installed; CUDA status cannot be queried."],
            "devices": [{"name": "cpu", "available": True}],
        }
    try:
        import torch  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on local torch install
        return {
            "torchInstalled": False,
            "available": False,
            "device": "cpu",
            "reasons": [f"torch import failed: {exc}"],
            "devices": [{"name": "cpu", "available": True}],
        }

    cuda_available = bool(torch.cuda.is_available())
    mps_available = bool(getattr(getattr(torch, "backends", None), "mps", None) and torch.backends.mps.is_available())
    devices = [
        {"name": "cpu", "available": True},
        {"name": "cuda", "available": cuda_available},
        {"name": "mps", "available": mps_available},
    ]
    reasons: list[str] = []
    if not cuda_available:
        reasons.append("torch.cuda.is_available() returned false.")
    return {
        "torchInstalled": True,
        "torchVersion": getattr(torch, "__version__", None),
        "available": cuda_available,
        "device": "cuda" if cuda_available else "cpu",
        "reasons": reasons,
        "devices": devices,
    }


def ffmpeg_status() -> dict[str, Any]:
    path = shutil.which("ffmpeg")
    return {
        "available": bool(path),
        "path": path,
        "reasons": [] if path else ["ffmpeg executable was not found on PATH."],
        "installHint": None if path else "Install FFmpeg and make sure ffmpeg is on PATH for MP4/WebM exports.",
    }


def output_path_status(output_dir: str | Path | None = None) -> dict[str, Any]:
    if output_dir is None:
        return {"checked": False}
    path = Path(output_dir)
    current = path if path.exists() else path.parent
    while current and not current.exists() and current != current.parent:
        current = current.parent
    exists = current.exists()
    writable = bool(exists and os.access(current, os.W_OK))
    return {
        "checked": True,
        "path": str(path),
        "checkedPath": str(current),
        "writable": writable,
        "reasons": [] if writable else [f"{current} is not writable or does not exist."],
    }


def video_io_status(video_path: str | Path | None = None) -> dict[str, Any]:
    cv2_available = _module_available("cv2")
    status: dict[str, Any] = {
        "opencvAvailable": cv2_available,
        "checkedVideo": False,
        "readable": None,
        "reasons": [] if cv2_available else ["OpenCV is not importable; video IO cannot be checked."],
    }
    if video_path is None or not cv2_available:
        return status
    status["checkedVideo"] = True
    try:
        import cv2  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on local OpenCV install
        status["readable"] = False
        status["reasons"].append(f"OpenCV import failed: {exc}")
        return status
    cap = cv2.VideoCapture(str(video_path))
    try:
        readable = bool(cap.isOpened())
        status["readable"] = readable
        if not readable:
            status["reasons"].append(f"Could not open video: {video_path}")
    finally:
        cap.release()
    return status


def dependency_statuses() -> list[DependencyStatus]:
    return [
        _dependency("numpy", "numpy", "Install the base MotionJSON requirements."),
        _dependency("opencv-python", "cv2", "Install opencv-python for video IO and CPU mask providers."),
        _dependency("Pillow", "PIL", "Install Pillow for image mask/cutout IO."),
        _dependency("jsonschema", "jsonschema", "Install jsonschema for MotionJSON validation."),
        _dependency("tqdm", "tqdm", "Install tqdm for CLI extraction progress."),
        _dependency("sam2", "sam2", "Install SAM2 separately only when using sam2-local."),
        _dependency("torch", "torch", "Install torch separately only when using local ML providers."),
    ]


def provider_capabilities(
    *,
    sam2_checkpoint: str | Path | None = None,
    sam2_model_config: str | Path | None = None,
    hosted_allow_network: bool = False,
) -> list[ProviderCapability]:
    deps = {dep.module: dep.available for dep in dependency_statuses()}
    cv_ready = deps.get("cv2", False) and deps.get("numpy", False)
    pil_ready = deps.get("PIL", False)
    sam2_installed = deps.get("sam2", False)
    torch_info = cuda_status()
    checkpoint = _path_config_status("SAM2_LOCAL_CHECKPOINT", sam2_checkpoint)
    model_config = _path_config_status("SAM2_LOCAL_CONFIG", sam2_model_config)
    hosted_endpoint = _env_config("HOSTED_SEGMENTATION_URL")
    hosted_auth = _env_config("HOSTED_SEGMENTATION_API_KEY")
    openrouter_key = _env_config("OPENROUTER_API_KEY")
    text_detector_installed = _module_available("groundingdino")
    text_detector_model = _path_config_status("TEXT_DETECTOR_MODEL")
    class_detector_installed = _module_available("ultralytics")
    class_detector_model = _path_config_status("CLASS_DETECTOR_MODEL")
    ffmpeg = ffmpeg_status()
    sam2_local_reasons = [
        reason
        for reason in (
            None if sam2_installed else "Python module 'sam2' is not importable.",
            *_model_path_reasons(checkpoint, "SAM2 checkpoint", "--sam2-checkpoint"),
            *_model_path_reasons(model_config, "SAM2 model config", "--sam2-config"),
            None if torch_info["torchInstalled"] else "torch is not installed.",
        )
        if reason
    ]
    sam2_local_ready = bool(sam2_installed and checkpoint["exists"] and model_config["exists"] and torch_info["torchInstalled"])
    if not sam2_installed or not torch_info["torchInstalled"]:
        sam2_local_status = "missing_dependency"
    elif (checkpoint["configured"] and not checkpoint["exists"]) or (model_config["configured"] and not model_config["exists"]):
        sam2_local_status = "missing_model"
    elif not checkpoint["configured"] or not model_config["configured"]:
        sam2_local_status = "not_configured"
    elif not torch_info["available"]:
        sam2_local_status = "available_cpu_only"
    else:
        sam2_local_status = "ready"
    sam_auto_masks_status = sam2_local_status if sam2_local_status != "ready" else "not_configured"
    text_detector_reasons = [
        reason
        for reason in (
            None if text_detector_installed else "Open-vocabulary detector package 'groundingdino' is not importable.",
            *_model_path_reasons(text_detector_model, "text detector model", "--discovery-config"),
        )
        if reason
    ]
    text_detector_ready = bool(text_detector_installed and text_detector_model["exists"])
    if not text_detector_installed:
        text_detector_status = "missing_dependency"
    elif text_detector_model["configured"] and not text_detector_model["exists"]:
        text_detector_status = "missing_model"
    elif not text_detector_model["configured"]:
        text_detector_status = "not_configured"
    else:
        text_detector_status = "ready"
    text_detector_runtime_status = text_detector_status if text_detector_status != "ready" else "not_configured"
    class_detector_reasons = [
        reason
        for reason in (
            None if class_detector_installed else "Known-class detector package 'ultralytics' is not importable.",
            *_model_path_reasons(class_detector_model, "class detector model", "--discovery-config"),
        )
        if reason
    ]
    class_detector_ready = bool(class_detector_installed and class_detector_model["exists"])
    if not class_detector_installed:
        class_detector_status = "missing_dependency"
    elif class_detector_model["configured"] and not class_detector_model["exists"]:
        class_detector_status = "missing_model"
    elif not class_detector_model["configured"]:
        class_detector_status = "not_configured"
    else:
        class_detector_status = "ready"
    class_detector_runtime_status = class_detector_status if class_detector_status != "ready" else "not_configured"

    providers = [
        ProviderCapability(
            name="threshold",
            kind="mask_provider",
            available=cv_ready,
            status="ready" if cv_ready else "missing_dependency",
            supports=["hsv_threshold", "binary_mask"],
            reasons=[] if cv_ready else ["numpy and opencv-python are required for threshold masks."],
            install_hint=None if cv_ready else "Install base MotionJSON requirements.",
            device="cpu",
            no_model_safe=True,
            network_required=False,
            runnable=cv_ready,
            mock_available=True,
            metadata={"backendEligible": True},
        ),
        ProviderCapability(
            name="motion",
            kind="mask_provider",
            available=cv_ready,
            status="ready" if cv_ready else "missing_dependency",
            supports=["background_subtraction", "moving_foreground"],
            reasons=[] if cv_ready else ["numpy and opencv-python are required for motion masks."],
            install_hint=None if cv_ready else "Install opencv-python and numpy.",
            device="cpu",
            no_model_safe=True,
            network_required=False,
            runnable=cv_ready,
            mock_available=True,
            metadata={"backendEligible": False},
        ),
        ProviderCapability(
            name="external",
            kind="mask_provider",
            available=cv_ready and pil_ready,
            status="ready" if cv_ready and pil_ready else "missing_dependency",
            supports=["png_masks", "jpg_masks", "webp_masks", "external_masks"],
            reasons=[] if cv_ready and pil_ready else ["Pillow, numpy, and opencv-python are required for external mask import."],
            install_hint=None if cv_ready and pil_ready else "Install base MotionJSON requirements.",
            device="cpu",
            no_model_safe=True,
            network_required=False,
            runnable=cv_ready and pil_ready,
            mock_available=True,
            metadata={"backendEligible": True},
        ),
        ProviderCapability(
            name="mock",
            kind="mask_provider",
            available=cv_ready,
            status="ready" if cv_ready else "missing_dependency",
            supports=["deterministic_test_masks", "no_model"],
            reasons=[] if cv_ready else ["Mock segmentation uses numpy/opencv array helpers."],
            install_hint=None if cv_ready else "Install base MotionJSON requirements.",
            device="cpu",
            no_model_safe=True,
            network_required=False,
            runnable=cv_ready,
            mock_available=True,
            metadata={"backendEligible": True},
        ),
        ProviderCapability(
            name="sam2",
            kind="mask_provider",
            available=False,
            configured=False,
            installed=False,
            runnable=False,
            status="unavailable",
            supports=["legacy_stub"],
            reasons=["Legacy sam2 provider is a stub and requires an injected client; use sam2-local or sam2-hosted for explicit providers."],
            install_hint="Use --mask-provider sam2-local or sam2-hosted, or inject a client in tests.",
            device=None,
            no_model_safe=False,
            network_required=False,
            mock_available=True,
            optional_extra="sam2",
            metadata={"backendEligible": False, "legacyStub": True},
        ),
        ProviderCapability(
            name="sam2-local",
            kind="mask_provider",
            available=sam2_local_ready,
            configured=bool(checkpoint["configured"] and model_config["configured"]),
            installed=bool(sam2_installed and torch_info["torchInstalled"]),
            runnable=sam2_local_ready,
            status=sam2_local_status,
            supports=["point", "box", "video_propagation", "local_model"],
            reasons=sam2_local_reasons,
            install_hint="Install SAM2/torch separately and set SAM2_LOCAL_CHECKPOINT and SAM2_LOCAL_CONFIG.",
            device=torch_info.get("device"),
            no_model_safe=False,
            network_required=False,
            needs_model_path=True,
            model_paths=[checkpoint, model_config],
            mock_available=True,
            optional_extra="sam2",
            checks=[
                _check("sam2_import", "ok" if sam2_installed else "missing", None if sam2_installed else "sam2 package is not importable"),
                _check("torch_import", "ok" if torch_info["torchInstalled"] else "missing", None if torch_info["torchInstalled"] else "torch package is not importable"),
                _check("checkpoint", "ok" if checkpoint["exists"] else "missing", checkpoint["env"], checkpoint["exists"]),
                _check("model_config", "ok" if model_config["exists"] else "missing", model_config["env"], model_config["exists"]),
            ],
            metadata={"checkpoint": checkpoint, "modelConfig": model_config, "cuda": torch_info},
        ),
        ProviderCapability(
            name="sam2-hosted",
            kind="mask_provider",
            available=bool(hosted_endpoint["configured"] and hosted_auth["configured"]),
            configured=bool(hosted_endpoint["configured"] and hosted_auth["configured"]),
            installed=True,
            runnable=bool(hosted_endpoint["configured"] and hosted_auth["configured"] and hosted_allow_network),
            status="ready" if hosted_endpoint["configured"] and hosted_auth["configured"] else "not_configured",
            supports=["point", "box", "hosted_segmentation"],
            reasons=[
                reason
                for reason in (
                    None if hosted_endpoint["configured"] else "HOSTED_SEGMENTATION_URL is not set.",
                    None if hosted_auth["configured"] else "HOSTED_SEGMENTATION_API_KEY is not set.",
                )
                if reason
            ],
            install_hint="Set HOSTED_SEGMENTATION_URL and HOSTED_SEGMENTATION_API_KEY, then opt into hosted network use explicitly.",
            device="remote",
            no_model_safe=False,
            network_required=True,
            needs_credentials=True,
            mock_available=True,
            optional_extra="hosted-segmentation",
            checks=[
                _check("endpoint_env", "ok" if hosted_endpoint["configured"] else "missing", hosted_endpoint["env"], hosted_endpoint["configured"]),
                _check("auth_env", "ok" if hosted_auth["configured"] else "missing", hosted_auth["env"], hosted_auth["configured"]),
                _check("network_opt_in", "ok" if hosted_allow_network else "required", "Hosted segmentation requires explicit network opt-in.", hosted_allow_network),
            ],
            metadata={"endpointEnv": hosted_endpoint, "authEnv": hosted_auth, "networkDefault": "disabled", "networkOptIn": hosted_allow_network},
        ),
        ProviderCapability(
            name="openrouter",
            kind="llm_provider",
            available=bool(openrouter_key["configured"]),
            configured=bool(openrouter_key["configured"]),
            installed=True,
            runnable=bool(openrouter_key["configured"]),
            status="ready" if openrouter_key["configured"] else "not_configured",
            supports=["llm", "vlm_reasoning", "labels"],
            reasons=[] if openrouter_key["configured"] else ["OPENROUTER_API_KEY is not set."],
            install_hint="Set OPENROUTER_API_KEY only for LLM/VLM reasoning. OpenRouter is not a segmentation provider.",
            no_model_safe=False,
            network_required=True,
            needs_credentials=True,
            mock_available=True,
            optional_extra="openrouter",
            checks=[_check("api_key_env", "ok" if openrouter_key["configured"] else "missing", openrouter_key["env"], openrouter_key["configured"])],
            metadata={"apiKeyEnv": openrouter_key, "segmentationProvider": False},
        ),
        ProviderCapability(
            name="manual_prompt",
            kind="discovery_provider",
            available=True,
            configured=True,
            runnable=True,
            status="ready",
            supports=["point_candidates", "box_candidates", "mask_ref_candidates"],
            reasons=[],
            install_hint=None,
            device="cpu",
            no_model_safe=True,
            network_required=False,
            mock_available=True,
            metadata={
                "uiDescription": "User-created points, boxes, or mask references for one or more objects.",
                "whenToUse": "Use when the user knows the object and can mark it directly.",
            },
        ),
        ProviderCapability(
            name="motion_foreground",
            kind="discovery_provider",
            available=cv_ready,
            configured=True,
            runnable=cv_ready,
            status="ready" if cv_ready else "missing_dependency",
            supports=["frame_difference", "moving_foreground", "generated_mask_sequences"],
            reasons=[] if cv_ready else ["numpy and opencv-python are required for motion foreground discovery."],
            install_hint=None if cv_ready else "Install opencv-python and numpy.",
            device="cpu",
            no_model_safe=True,
            network_required=False,
            mock_available=True,
            metadata={
                "uiDescription": "CPU moving-region proposals for videos with stable backgrounds.",
                "whenToUse": "Use for simple footage where target objects move more than the background.",
            },
        ),
        ProviderCapability(
            name="external_masks",
            kind="discovery_provider",
            available=cv_ready and pil_ready,
            configured=True,
            runnable=cv_ready and pil_ready,
            status="ready" if cv_ready and pil_ready else "missing_dependency",
            supports=["mask_directories", "manifest_import", "multi_object_candidates"],
            reasons=[] if cv_ready and pil_ready else ["Pillow, numpy, and opencv-python are required for external mask discovery."],
            install_hint=None if cv_ready and pil_ready else "Install base MotionJSON requirements.",
            device="cpu",
            no_model_safe=True,
            network_required=False,
            mock_available=True,
            metadata={
                "uiDescription": "Import masks or boxes created by another tool as object candidates.",
                "whenToUse": "Use when masks already exist from SAM2, editing tools, or another pipeline.",
            },
        ),
        ProviderCapability(
            name="sam_auto_masks",
            kind="discovery_provider",
            available=False,
            configured=bool(checkpoint["configured"] and model_config["configured"]),
            installed=bool(sam2_installed and torch_info["torchInstalled"]),
            runnable=False,
            status=sam_auto_masks_status,
            supports=["automatic_keyframe_masks", "area_filter", "stability_filter", "overlap_filter"],
            reasons=[
                *sam2_local_reasons,
                "SAM automatic-mask discovery is scaffolded; configure a concrete automatic-mask backend or use mock mode.",
            ],
            install_hint="Install/configure SAM2 automatic masks, or use motion_foreground/external_masks for no-model discovery.",
            device=torch_info.get("device"),
            no_model_safe=False,
            network_required=False,
            needs_model_path=True,
            model_paths=[checkpoint, model_config],
            mock_available=True,
            optional_extra="sam2",
            metadata={
                "uiDescription": "Automatic visible-segment proposals from a configured SAM2-style backend.",
                "whenToUse": "Use when the user wants broad visible-segment proposals and local SAM2 is configured.",
            },
        ),
        ProviderCapability(
            name="text_detector",
            kind="discovery_provider",
            available=False,
            configured=bool(text_detector_model["configured"]),
            installed=text_detector_installed,
            runnable=False,
            status=text_detector_runtime_status,
            supports=["text_guided_boxes", "open_vocabulary_candidates"],
            reasons=[
                *text_detector_reasons,
                "Text detector discovery is scaffolded; configure a concrete detector backend or use mock mode.",
            ],
            install_hint="Install/configure an open-vocabulary detector, or use discovery mock mode for local smoke tests.",
            no_model_safe=False,
            network_required=False,
            needs_model_path=True,
            model_paths=[text_detector_model],
            mock_available=True,
            optional_extra="detectors",
            checks=[
                _check("groundingdino_import", "ok" if text_detector_installed else "missing", None if text_detector_installed else "groundingdino package is not importable"),
                _check("model", "ok" if text_detector_model["exists"] else "missing", text_detector_model["env"], text_detector_model["exists"]),
            ],
            metadata={
                "model": text_detector_model,
                "uiDescription": "Text prompts become detector candidates before segmentation/tracking.",
                "whenToUse": "Use when the user can describe objects with words such as 'red ball' or 'hand'.",
                "sam2DirectText": False,
            },
        ),
        ProviderCapability(
            name="class_detector",
            kind="discovery_provider",
            available=False,
            configured=bool(class_detector_model["configured"]),
            installed=class_detector_installed,
            runnable=False,
            status=class_detector_runtime_status,
            supports=["known_class_boxes", "fixed_label_candidates"],
            reasons=[
                *class_detector_reasons,
                "Class detector discovery is scaffolded; configure a concrete detector backend or use mock mode.",
            ],
            install_hint="Install/configure a known-class detector, or use discovery mock mode for local smoke tests.",
            no_model_safe=False,
            network_required=False,
            needs_model_path=True,
            model_paths=[class_detector_model],
            mock_available=True,
            optional_extra="yolo",
            checks=[
                _check("ultralytics_import", "ok" if class_detector_installed else "missing", None if class_detector_installed else "ultralytics package is not importable"),
                _check("model", "ok" if class_detector_model["exists"] else "missing", class_detector_model["env"], class_detector_model["exists"]),
            ],
            metadata={
                "model": class_detector_model,
                "uiDescription": "Known classes become detector candidates before segmentation/tracking.",
                "whenToUse": "Use when target labels are in a fixed detector class list.",
            },
        ),
        ProviderCapability(
            name="video-tracker",
            kind="video_tracker",
            available=cv_ready,
            configured=True,
            status="ready" if cv_ready else "missing_dependency",
            supports=["per_frame_mask_tracking", "mock_tracks"],
            reasons=[] if cv_ready else ["OpenCV/numpy are required for per-frame mask tracking."],
            install_hint=None if cv_ready else "Install base MotionJSON requirements.",
            device="cpu",
            no_model_safe=True,
            network_required=False,
            mock_available=True,
        ),
        ProviderCapability(
            name="track-linker",
            kind="track_linker",
            available=True,
            configured=True,
            status="ready",
            supports=["identity_linking", "duplicate_id_guard"],
            reasons=[],
            install_hint=None,
            device="cpu",
            no_model_safe=True,
            network_required=False,
            mock_available=True,
        ),
        ProviderCapability(
            name="contour-vectorizer",
            kind="vectorizer",
            available=cv_ready,
            status="ready" if cv_ready else "missing_dependency",
            supports=["largest_contour", "polygon_simplification"],
            reasons=[] if cv_ready else ["OpenCV/numpy are required for contour vectorization."],
            install_hint=None if cv_ready else "Install base MotionJSON requirements.",
            device="cpu",
            no_model_safe=True,
            network_required=False,
            mock_available=True,
        ),
        ProviderCapability(
            name="motionjson-json",
            kind="exporter",
            available=True,
            status="ready",
            supports=["scene_graph", "object_manifest", "web_manifest", "rights_manifest"],
            device="cpu",
            no_model_safe=True,
            network_required=False,
            mock_available=True,
        ),
        ProviderCapability(
            name="website-zip",
            kind="exporter",
            available=True,
            status="ready",
            supports=["website_package"],
            device="cpu",
            no_model_safe=True,
            network_required=False,
            mock_available=True,
        ),
        ProviderCapability(
            name="remotion-plan",
            kind="exporter",
            available=True,
            status="ready",
            supports=["remotion_plan"],
            device="cpu",
            no_model_safe=True,
            network_required=False,
            mock_available=True,
        ),
        ProviderCapability(
            name="silhouette-lottie",
            kind="exporter",
            available=True,
            status="ready",
            supports=["lottie_silhouette"],
            device="cpu",
            no_model_safe=True,
            network_required=False,
            mock_available=True,
        ),
        ProviderCapability(
            name="ffmpeg-video",
            kind="exporter",
            available=bool(ffmpeg["available"]),
            status="ready" if ffmpeg["available"] else "missing_dependency",
            supports=["mp4", "webm_alpha"],
            reasons=list(ffmpeg["reasons"]),
            install_hint=ffmpeg["installHint"],
            device="cpu",
            no_model_safe=True,
            network_required=False,
            mock_available=False,
            checks=[_check("ffmpeg_path", "ok" if ffmpeg["available"] else "missing", "ffmpeg executable lookup", bool(ffmpeg["available"]))],
            metadata={"ffmpeg": ffmpeg},
        ),
    ]
    return providers


def build_capability_report(
    *,
    output_dir: str | Path | None = None,
    video_path: str | Path | None = None,
    sam2_checkpoint: str | Path | None = None,
    sam2_model_config: str | Path | None = None,
    hosted_allow_network: bool = False,
) -> dict[str, Any]:
    deps = dependency_statuses()
    providers = provider_capabilities(
        sam2_checkpoint=sam2_checkpoint,
        sam2_model_config=sam2_model_config,
        hosted_allow_network=hosted_allow_network,
    )
    provider_records = [provider.to_dict() for provider in providers]
    ready_no_model = [
        provider["name"]
        for provider in provider_records
        if provider["available"] and provider["noModelSafe"] and not provider["networkRequired"]
    ]
    runnable_providers = [provider["name"] for provider in provider_records if provider["runnable"]]
    local_free_providers = [
        provider["name"]
        for provider in provider_records
        if provider["runnable"] and provider["estimatedCost"]["status"].startswith("zero_local")
    ]
    unavailable_required_setup = [
        provider.name
        for provider in providers
        if not provider.available and provider.optional_extra
    ]
    missing_optional = [
        provider.name
        for provider in providers
        if not provider.available
        and provider.name in {"sam2-local", "sam2-hosted", "openrouter", "sam_auto_masks", "text_detector", "class_detector", "ffmpeg-video"}
    ]
    return {
        "schema": CAPABILITY_SCHEMA,
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "executableName": Path(sys.executable).name,
            "platform": platform.platform(),
        },
        "environment": {
            "dependencies": [dep.to_dict() for dep in deps],
            "cuda": cuda_status(),
            "ffmpeg": ffmpeg_status(),
            "videoIO": video_io_status(video_path),
            "output": output_path_status(output_dir),
        },
        "providers": provider_records,
        "summary": {
            "providersReady": sum(1 for provider in providers if provider.available),
            "providersTotal": len(providers),
            "readyNoModelProviders": ready_no_model,
            "runnableProviders": runnable_providers,
            "localFreeRunnableProviders": local_free_providers,
            "canRunNoModelSmoke": all(name in ready_no_model for name in ("mock", "threshold", "motionjson-json")),
            "firstRun": {
                "ready": all(name in ready_no_model for name in ("mock", "threshold", "motionjson-json")),
                "recommendedCommand": "python3 -m motionjson.cli ui --no-open --mock",
                "recommendedDemoCommand": "python3 examples/make_demo_video.py --out examples/demo_red_ball.mp4 && python3 -m motionjson.cli extract examples/demo_red_ball.mp4 --out out/demo_red_ball --mask-provider threshold --lower-hsv 0,80,80 --upper-hsv 12,255,255 --sample-fps 12 --max-frames 12",
                "nextActions": [
                    "Launch the local UI in mock mode.",
                    "Run the red-ball threshold demo.",
                    "Install optional ML extras only after diagnostics show a workflow needs them.",
                ],
                "nonBlockingOptionalMissing": missing_optional,
            },
            "missingOptional": missing_optional,
            "unavailableRequiredSetup": unavailable_required_setup,
        },
    }


def capability_report_json(**kwargs: Any) -> str:
    return json.dumps(build_capability_report(**kwargs), indent=2, sort_keys=True)


def _provider_by_name(report: dict[str, Any], name: str) -> dict[str, Any] | None:
    return next((provider for provider in report.get("providers", []) if provider.get("name") == name), None)


def _first_reason(provider: dict[str, Any] | None) -> str:
    if not provider:
        return "not reported"
    reasons = provider.get("reasons") or []
    if reasons:
        return str(reasons[0])
    return str(provider.get("installHint") or "no extra setup reported")


def format_capability_report(report: dict[str, Any]) -> str:
    """Return a compact human-readable diagnostics summary."""

    summary = report.get("summary", {})
    environment = report.get("environment", {})
    python = report.get("python", {})
    cuda = environment.get("cuda", {})
    ffmpeg = environment.get("ffmpeg", {})
    video_io = environment.get("videoIO", {})
    output = environment.get("output", {})
    ready_no_model = summary.get("readyNoModelProviders") or []
    local_free = summary.get("localFreeRunnableProviders") or []
    missing_optional = summary.get("missingOptional") or []

    lines = [
        "MotionJSON diagnostics",
        f"Python: {python.get('executableName', 'python')} {python.get('version', 'unknown')} ({python.get('implementation', 'unknown')})",
        f"Providers ready: {summary.get('providersReady', 0)}/{summary.get('providersTotal', 0)}",
    ]
    if ready_no_model:
        lines.append(f"No-model providers ready: {', '.join(ready_no_model)}")
    else:
        lines.append("No-model providers ready: none reported")
    if local_free:
        lines.append(f"Runnable local/free providers: {', '.join(local_free)}")
    lines.append(
        "No-model smoke: "
        + (
            "ready - run `python3 -m motionjson.cli ui --no-open --mock` or the red-ball demo."
            if summary.get("canRunNoModelSmoke")
            else "limited - install base dependencies before running the mock UI or red-ball demo."
        )
    )
    lines.append(f"CUDA: {'ready' if cuda.get('available') else 'not available'} ({cuda.get('device', 'cpu')})")
    for reason in cuda.get("reasons") or []:
        lines.append(f"  - {reason}")
    lines.append(
        "FFmpeg: "
        + (
            f"ready ({ffmpeg.get('path')})"
            if ffmpeg.get("available")
            else f"not found - {ffmpeg.get('installHint') or 'MP4/WebM exports require FFmpeg.'}"
        )
    )
    if video_io.get("checkedVideo"):
        lines.append(f"Video probe: {'readable' if video_io.get('readable') else 'not readable'}")
        for reason in video_io.get("reasons") or []:
            lines.append(f"  - {reason}")
    if output.get("checked"):
        lines.append(f"Output probe: {'writable' if output.get('writable') else 'not writable'}")
        for reason in output.get("reasons") or []:
            lines.append(f"  - {reason}")

    if missing_optional:
        lines.append("Optional providers needing setup:")
        for name in missing_optional:
            provider = _provider_by_name(report, name)
            extra = provider.get("optionalExtra") if provider else None
            suffix = f" [{extra}]" if extra else ""
            lines.append(f"  - {name}{suffix}: {_first_reason(provider)}")
    else:
        lines.append("Optional providers needing setup: none reported")

    lines.extend(
        [
            "Provider guidance:",
            "  - Text prompts need detector candidates before SAM2 segmentation/tracking.",
            "  - Missing SAM2, detector, CUDA, FFmpeg, or credential setup is diagnostic status, not a base-install failure.",
            "Use `--json` for the full machine-readable report.",
        ]
    )
    return "\n".join(lines)
