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
    supports: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    install_hint: str | None = None
    device: str | None = None
    no_model_safe: bool = False
    network_required: bool = False
    mock_available: bool = False
    optional_extra: str | None = None
    checks: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "available": self.available,
            "status": self.status,
            "configured": self.configured,
            "supports": list(self.supports),
            "reasons": list(self.reasons),
            "installHint": self.install_hint,
            "device": self.device,
            "noModelSafe": self.no_model_safe,
            "networkRequired": self.network_required,
            "mockAvailable": self.mock_available,
            "optionalExtra": self.optional_extra,
            "checks": list(self.checks),
            "metadata": dict(self.metadata),
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
            mock_available=True,
            metadata={"backendEligible": True},
        ),
        ProviderCapability(
            name="sam2",
            kind="mask_provider",
            available=False,
            configured=False,
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
            status=sam2_local_status,
            supports=["point", "box", "video_propagation", "local_model"],
            reasons=sam2_local_reasons,
            install_hint="Install SAM2/torch separately and set SAM2_LOCAL_CHECKPOINT and SAM2_LOCAL_CONFIG.",
            device=torch_info.get("device"),
            no_model_safe=False,
            network_required=False,
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
            mock_available=True,
            optional_extra="hosted-segmentation",
            checks=[
                _check("endpoint_env", "ok" if hosted_endpoint["configured"] else "missing", hosted_endpoint["env"], hosted_endpoint["configured"]),
                _check("auth_env", "ok" if hosted_auth["configured"] else "missing", hosted_auth["env"], hosted_auth["configured"]),
                _check("network_default", "skipped", "Diagnostics does not make hosted network calls.", "disabled"),
            ],
            metadata={"endpointEnv": hosted_endpoint, "authEnv": hosted_auth, "networkDefault": "disabled"},
        ),
        ProviderCapability(
            name="openrouter",
            kind="llm_provider",
            available=bool(openrouter_key["configured"]),
            configured=bool(openrouter_key["configured"]),
            status="ready" if openrouter_key["configured"] else "not_configured",
            supports=["llm", "vlm_reasoning", "labels"],
            reasons=[] if openrouter_key["configured"] else ["OPENROUTER_API_KEY is not set."],
            install_hint="Set OPENROUTER_API_KEY only for LLM/VLM reasoning. OpenRouter is not a segmentation provider.",
            no_model_safe=False,
            network_required=True,
            mock_available=True,
            optional_extra="openrouter",
            checks=[_check("api_key_env", "ok" if openrouter_key["configured"] else "missing", openrouter_key["env"], openrouter_key["configured"])],
            metadata={"apiKeyEnv": openrouter_key, "segmentationProvider": False},
        ),
        ProviderCapability(
            name="text-detector",
            kind="detector",
            available=False,
            configured=False,
            status="not_implemented",
            supports=["text_guided_boxes"],
            reasons=["Text detector provider interface is planned but not implemented until a later phase."],
            install_hint="Use mock/no-model workflows until text detector providers are added.",
            no_model_safe=False,
            network_required=False,
            mock_available=True,
        ),
        ProviderCapability(
            name="class-detector",
            kind="detector",
            available=False,
            configured=False,
            status="not_implemented",
            supports=["known_classes"],
            reasons=["Known-class detector provider interface is planned but not implemented until a later phase."],
            install_hint="Use threshold, motion, external, or mock providers for current no-model runs.",
            no_model_safe=False,
            network_required=False,
            mock_available=True,
        ),
        ProviderCapability(
            name="video-tracker",
            kind="video_tracker",
            available=False,
            configured=False,
            status="not_implemented",
            supports=["track_linking", "mask_propagation"],
            reasons=["Dedicated video tracker abstraction is planned for Phase 4."],
            install_hint="Current extraction uses mask providers per sampled frame.",
            no_model_safe=False,
            network_required=False,
            mock_available=True,
        ),
        ProviderCapability(
            name="track-linker",
            kind="track_linker",
            available=False,
            configured=False,
            status="not_implemented",
            supports=["multi_keyframe_identity"],
            reasons=["Dedicated track linker abstraction is planned for Phase 4."],
            install_hint="Current multi-object support is deterministic external mask extraction.",
            no_model_safe=False,
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
) -> dict[str, Any]:
    deps = dependency_statuses()
    providers = provider_capabilities(sam2_checkpoint=sam2_checkpoint, sam2_model_config=sam2_model_config)
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
        "providers": [provider.to_dict() for provider in providers],
        "summary": {
            "providersReady": sum(1 for provider in providers if provider.available),
            "providersTotal": len(providers),
            "missingOptional": [provider.name for provider in providers if not provider.available and provider.name in {"sam2-local", "sam2-hosted", "openrouter", "ffmpeg-video"}],
        },
    }


def capability_report_json(**kwargs: Any) -> str:
    return json.dumps(build_capability_report(**kwargs), indent=2, sort_keys=True)
