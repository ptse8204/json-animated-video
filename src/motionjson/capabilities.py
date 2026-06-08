from __future__ import annotations

import importlib.util
import json
import os
import platform
import subprocess
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from motionjson.providers.sam2 import SAM2_HF_AUTO_MASKS_DEFAULT_MODEL
from motionjson.providers.sam3 import (
    SAM3_HF_REPO_ID,
    describe_sam3_model_path,
    describe_sam3_tracker_model,
    sam3_tracker_video_runtime_status,
)


CAPABILITY_SCHEMA = "motionjson.provider_diagnostics.v0.1"
ENVIRONMENT_PROFILE_FORMAT = "motionjson.local_environment_profile.v0.1"
RUNTIME_ENVIRONMENT_FORMAT = "motionjson.runtime_environment.v0.2"
GPU_MODEL_RECOMMENDATION_FORMAT = "motionjson.gpu_model_recommendation.v0.1"
RUNTIME_PROOF_FORMAT = "motionjson.runtime_proof.v0.1"


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


def _default_runtime_proof(provider_id: str, message: str) -> dict[str, Any]:
    return {
        "format": RUNTIME_PROOF_FORMAT,
        "providerId": provider_id,
        "proofRequired": True,
        "proofStatus": "missing",
        "runtimeProofStatus": "missing",
        "allowsRun": False,
        "verified": False,
        "reasonCodes": ["runtime_proof_missing"],
        "message": message,
        "remediation": "Open Model setup, cache the selected model if needed, then run a bounded smoke test.",
    }


def _module_available(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def _module_attr_available(module: str, attr: str) -> bool:
    if not _module_available(module):
        return False
    try:
        imported = __import__(module, fromlist=[attr])
    except Exception:
        return False
    return hasattr(imported, attr)


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


def _settings_presence_config(
    name: str,
    provider_settings: Mapping[str, Mapping[str, Any]] | None,
    provider_id: str,
    setting_key: str,
) -> dict[str, Any]:
    entry = dict((provider_settings or {}).get(provider_id, {}))
    env_configured = bool(os.environ.get(name))
    settings_configured = bool(entry.get(setting_key))
    if env_configured:
        source = "environment"
    elif settings_configured:
        source = "local_settings"
    else:
        source = "unset"
    return {"env": name, "configured": bool(env_configured or settings_configured), "source": source}


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


def _sam3_model_path_status(explicit_value: str | Path | None = None) -> dict[str, Any]:
    env_value = os.environ.get("SAM3_LOCAL_MODEL")
    if explicit_value is not None:
        value = str(explicit_value)
        source = "argument"
    elif env_value:
        value = env_value
        source = "environment"
    else:
        value = None
        source = "unset"
    return describe_sam3_model_path(value, env="SAM3_LOCAL_MODEL", source=source)


def _model_path_reasons(path_status: dict[str, Any], label: str, flag: str) -> list[str]:
    if not path_status["configured"]:
        return [str(path_status.get("reason") or f"{label} is not configured. Set {path_status['env']} or pass {flag}.")]
    if not path_status.get("valid", path_status["exists"]):
        if path_status.get("reason"):
            return [str(path_status["reason"])]
        return [f"Configured {label.lower()} path does not point to an existing file."]
    return []


def cuda_status() -> dict[str, Any]:
    if not _module_available("torch"):
        return {
            "torchInstalled": False,
            "available": False,
            "device": "cpu",
            "torchVersion": None,
            "torchCudaBuild": None,
            "cudaAvailable": False,
            "mpsAvailable": False,
            "mpsBuilt": False,
            "xpuAvailable": False,
            "hipVersion": None,
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
            "torchVersion": None,
            "torchCudaBuild": None,
            "cudaAvailable": False,
            "mpsAvailable": False,
            "mpsBuilt": False,
            "xpuAvailable": False,
            "hipVersion": None,
            "reasons": [f"torch import failed: {exc}"],
            "devices": [{"name": "cpu", "available": True}],
        }

    cuda_available = bool(torch.cuda.is_available())
    mps_backend = getattr(getattr(torch, "backends", None), "mps", None)
    mps_available = bool(mps_backend and mps_backend.is_available())
    mps_built_check = getattr(mps_backend, "is_built", None)
    mps_built = bool(mps_backend and (mps_built_check() if callable(mps_built_check) else False))
    xpu_backend = getattr(torch, "xpu", None)
    try:
        xpu_available = bool(xpu_backend and xpu_backend.is_available())
    except Exception:
        xpu_available = False
    torch_version = getattr(torch, "version", None)
    cuda_build = getattr(torch_version, "cuda", None)
    hip_version = getattr(torch_version, "hip", None)
    cuda_devices: list[dict[str, Any]] = []
    if cuda_available:
        try:
            count = int(torch.cuda.device_count())
        except Exception:  # pragma: no cover - depends on local torch build
            count = 0
        for index in range(max(count, 1)):
            try:
                name = torch.cuda.get_device_name(index)
            except Exception:  # pragma: no cover - depends on local torch build
                name = "cuda"
            cuda_devices.append({"name": "cuda", "available": True, "index": index, "deviceName": name})
    devices = [
        {"name": "cpu", "available": True},
        {"name": "cuda", "available": cuda_available},
        {"name": "mps", "available": mps_available},
        {"name": "xpu", "available": xpu_available},
        *cuda_devices,
    ]
    reasons: list[str] = []
    if not cuda_available:
        reasons.append("torch.cuda.is_available() returned false.")
    return {
        "torchInstalled": True,
        "torchVersion": getattr(torch, "__version__", None),
        "torchCudaBuild": cuda_build,
        "cudaAvailable": cuda_available,
        "mpsAvailable": mps_available,
        "mpsBuilt": mps_built,
        "xpuAvailable": xpu_available,
        "hipVersion": hip_version,
        "available": cuda_available,
        "device": "cuda" if cuda_available else "mps" if mps_available else "xpu" if xpu_available else "cpu",
        "reasons": reasons,
        "devices": devices,
    }


def _host_runtime() -> tuple[str, str]:
    system = platform.system() or "Unknown"
    if os.environ.get("COLAB_RELEASE_TAG") or os.environ.get("COLAB_GPU"):
        return "google_colab", "Google Colab"
    if os.environ.get("KAGGLE_KERNEL_RUN_TYPE"):
        return "kaggle", "Kaggle notebook"
    if os.environ.get("CODESPACES"):
        return "codespaces", "GitHub Codespaces"
    if os.environ.get("CI"):
        return "ci", "CI runner"
    if system == "Darwin":
        return "local_mac", "macOS runtime"
    if system == "Linux":
        return "local_linux", "Linux runtime"
    if system == "Windows":
        return "local_windows", "Windows runtime"
    return "runtime", f"{system} runtime"


def _accelerator(
    *,
    kind: str,
    hardware_detected: bool,
    visible_to_torch: bool = False,
    name: str | None = None,
    memory_mb: int | None = None,
    driver: str | None = None,
    source: str = "fallback",
) -> dict[str, Any]:
    return {
        "kind": kind,
        "hardwareDetected": bool(hardware_detected),
        "visibleToTorch": bool(visible_to_torch),
        "name": name,
        "memoryMb": memory_mb,
        "driver": driver,
        "source": source,
    }


def _nvidia_smi_accelerators(timeout: float = 1.5) -> list[dict[str, Any]]:
    executable = shutil.which("nvidia-smi")
    if not executable:
        return []
    try:
        completed = subprocess.run(
            [
                executable,
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if completed.returncode != 0:
        return []
    accelerators: list[dict[str, Any]] = []
    for line in completed.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if not parts or not parts[0]:
            continue
        memory_mb: int | None = None
        if len(parts) > 1:
            try:
                memory_mb = int(float(parts[1]))
            except ValueError:
                memory_mb = None
        accelerators.append(
            _accelerator(
                kind="nvidia_cuda",
                hardware_detected=True,
                name=parts[0],
                memory_mb=memory_mb,
                driver=parts[2] if len(parts) > 2 else None,
                source="nvidia-smi",
            )
        )
    return accelerators


def _proc_nvidia_accelerator() -> dict[str, Any] | None:
    version_file = Path("/proc/driver/nvidia/version")
    try:
        if not version_file.exists():
            return None
        text = version_file.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None
    return _accelerator(
        kind="nvidia_cuda",
        hardware_detected=True,
        name="NVIDIA GPU",
        driver=text.splitlines()[0] if text else None,
        source="/proc/driver/nvidia/version",
    )


def _env_hardware_accelerators() -> list[dict[str, Any]]:
    accelerators: list[dict[str, Any]] = []
    if os.environ.get("COLAB_GPU") or os.environ.get("NVIDIA_VISIBLE_DEVICES") or os.environ.get("CUDA_VISIBLE_DEVICES"):
        accelerators.append(
            _accelerator(
                kind="nvidia_cuda",
                hardware_detected=True,
                name="NVIDIA GPU",
                source="env",
            )
        )
    if os.environ.get("HIP_VISIBLE_DEVICES") or os.environ.get("ROCR_VISIBLE_DEVICES") or os.environ.get("ROCM_PATH"):
        accelerators.append(
            _accelerator(
                kind="amd_rocm",
                hardware_detected=True,
                name="AMD ROCm accelerator",
                source="env",
            )
        )
    if os.environ.get("ONEAPI_DEVICE_SELECTOR") or os.environ.get("SYCL_DEVICE_FILTER") or os.environ.get("ZE_AFFINITY_MASK"):
        accelerators.append(
            _accelerator(
                kind="intel_xpu",
                hardware_detected=True,
                name="Intel XPU accelerator",
                source="env",
            )
        )
    return accelerators


def _torch_visible_accelerators(cuda_info: Mapping[str, Any]) -> list[dict[str, Any]]:
    accelerators: list[dict[str, Any]] = []
    device_records = [device for device in (cuda_info.get("devices") or []) if isinstance(device, Mapping)]
    for device in cuda_info.get("devices") or []:
        if not isinstance(device, Mapping):
            continue
        name = str(device.get("name") or "").lower()
        if name != "cuda" or not bool(device.get("available")):
            continue
        accelerators.append(
            _accelerator(
                kind="nvidia_cuda",
                hardware_detected=True,
                visible_to_torch=True,
                name=str(device.get("deviceName") or "CUDA GPU"),
                source="torch",
            )
        )
    if bool(cuda_info.get("mpsAvailable")) or any(str(device.get("name") or "").lower() == "mps" and bool(device.get("available")) for device in device_records):
        accelerators.append(
            _accelerator(
                kind="apple_mps",
                hardware_detected=True,
                visible_to_torch=True,
                name="Apple Silicon GPU",
                source="torch",
            )
        )
    if bool(cuda_info.get("xpuAvailable")):
        accelerators.append(
            _accelerator(
                kind="intel_xpu",
                hardware_detected=True,
                visible_to_torch=True,
                name="Intel XPU",
                source="torch",
            )
        )
    if cuda_info.get("hipVersion"):
        accelerators.append(
            _accelerator(
                kind="amd_rocm",
                hardware_detected=True,
                visible_to_torch=True,
                name="AMD ROCm accelerator",
                source="torch",
            )
        )
    return accelerators


def _dedupe_accelerators(accelerators: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for accelerator in accelerators:
        kind = str(accelerator.get("kind") or "unknown")
        existing = merged.get(kind)
        if existing is None:
            merged[kind] = dict(accelerator)
            continue
        existing["hardwareDetected"] = bool(existing.get("hardwareDetected") or accelerator.get("hardwareDetected"))
        existing["visibleToTorch"] = bool(existing.get("visibleToTorch") or accelerator.get("visibleToTorch"))
        for key in ("name", "memoryMb", "driver"):
            if not existing.get(key) and accelerator.get(key):
                existing[key] = accelerator.get(key)
        sources = [str(existing.get("source") or ""), str(accelerator.get("source") or "")]
        existing["source"] = "+".join(source for source in dict.fromkeys(sources) if source)
    return list(merged.values())


def runtime_environment(
    cuda_info: Mapping[str, Any] | None = None,
    *,
    hardware_accelerators: list[Mapping[str, Any]] | None = None,
    include_platform_hardware: bool = True,
) -> dict[str, Any]:
    """Detect hardware separately from Python/PyTorch runtime readiness."""

    cuda = dict(cuda_info or cuda_status())
    system = platform.system() or "Unknown"
    machine = platform.machine() or "unknown"
    host, _host_label = _host_runtime()
    detected: list[dict[str, Any]] = []
    if hardware_accelerators is None:
        detected.extend(_nvidia_smi_accelerators())
        if not detected:
            proc_gpu = _proc_nvidia_accelerator()
            if proc_gpu:
                detected.append(proc_gpu)
        detected.extend(_env_hardware_accelerators())
    else:
        detected.extend(dict(item) for item in hardware_accelerators)
    detected.extend(_torch_visible_accelerators(cuda))
    if include_platform_hardware and system == "Darwin" and machine.lower() in {"arm64", "aarch64"}:
        detected.append(
            _accelerator(
                kind="apple_mps",
                hardware_detected=True,
                visible_to_torch=bool(cuda.get("mpsAvailable")),
                name="Apple Silicon GPU",
                source="platform",
            )
        )
    accelerators = _dedupe_accelerators(detected)
    kinds = {str(item.get("kind") or "") for item in accelerators if item.get("hardwareDetected")}
    device_records = [device for device in (cuda.get("devices") or []) if isinstance(device, Mapping)]
    cuda_visible = bool(
        cuda.get("available")
        or cuda.get("cudaAvailable")
        or any(str(device.get("name") or "").lower() == "cuda" and bool(device.get("available")) for device in device_records)
    )
    mps_visible = bool(
        cuda.get("mpsAvailable")
        or any(str(device.get("name") or "").lower() == "mps" and bool(device.get("available")) for device in device_records)
    )
    xpu_visible = bool(
        cuda.get("xpuAvailable")
        or any(str(device.get("name") or "").lower() == "xpu" and bool(device.get("available")) for device in device_records)
    )
    rocm_visible = bool(cuda.get("hipVersion"))
    reason_codes: list[str] = []
    messages: list[str] = []
    recommended_fixes: list[str] = []
    classification = "unknown"
    confidence = "low"

    if cuda_visible:
        classification = "cuda_ready"
        confidence = "high"
        reason_codes.append("torch_cuda_available")
        messages.append("CUDA is available through PyTorch.")
    elif "nvidia_cuda" in kinds:
        classification = "cuda_hardware_runtime_missing"
        confidence = "high"
        reason_codes.extend(["nvidia_hardware_detected", "torch_cuda_unavailable"])
        if not cuda.get("torchInstalled"):
            reason_codes.append("torch_missing")
        messages.append("GPU detected, but this Python environment cannot use CUDA yet.")
        recommended_fixes.append("Install a CUDA-enabled PyTorch build for this runtime, or choose the no-model CPU fallback.")
    elif mps_visible:
        classification = "mps_ready"
        confidence = "high"
        reason_codes.append("torch_mps_available")
        messages.append("Apple Silicon detected; PyTorch MPS is available.")
    elif "apple_mps" in kinds:
        classification = "mps_hardware_runtime_missing"
        confidence = "high"
        reason_codes.extend(["apple_silicon_detected", "torch_mps_unavailable"])
        messages.append("Apple Silicon hardware detected, but PyTorch MPS is not available in this runtime.")
        recommended_fixes.append("Install a PyTorch build with MPS support, or use CPU/no-model workflows.")
    elif xpu_visible:
        classification = "xpu_ready"
        confidence = "medium"
        reason_codes.append("torch_xpu_available")
        messages.append("Intel XPU is available through PyTorch.")
    elif "intel_xpu" in kinds:
        classification = "xpu_hardware_runtime_missing"
        confidence = "medium"
        reason_codes.extend(["intel_xpu_hardware_detected", "torch_xpu_unavailable"])
        messages.append("Intel accelerator signals were detected, but PyTorch XPU is not available in this runtime.")
        recommended_fixes.append("Install an Intel/XPU-capable PyTorch runtime, or use CPU/no-model workflows.")
    elif rocm_visible:
        classification = "rocm_ready"
        confidence = "medium"
        reason_codes.append("torch_rocm_available")
        messages.append("ROCm/HIP is visible through PyTorch.")
    elif "amd_rocm" in kinds:
        classification = "rocm_hardware_runtime_missing"
        confidence = "medium"
        reason_codes.extend(["amd_rocm_hardware_detected", "torch_rocm_unavailable"])
        messages.append("AMD/ROCm accelerator signals were detected, but PyTorch ROCm is not available in this runtime.")
        recommended_fixes.append("Install a ROCm-capable PyTorch runtime, or use CPU/no-model workflows.")
    else:
        classification = "cpu_only"
        confidence = "high"
        reason_codes.append("no_accelerator_hardware_detected")
        messages.append("No accelerator hardware signals were detected; CPU/no-model workflows can run now.")

    if not accelerators:
        accelerators = [
            _accelerator(
                kind="cpu",
                hardware_detected=True,
                visible_to_torch=True,
                name="CPU",
                source="fallback",
            )
        ]
    return {
        "format": RUNTIME_ENVIRONMENT_FORMAT,
        "host": host,
        "system": system,
        "machine": machine,
        "classification": classification,
        "confidence": confidence,
        "hardware": {"accelerators": accelerators},
        "runtime": {
            "python": platform.python_version(),
            "torchInstalled": bool(cuda.get("torchInstalled")),
            "torchVersion": cuda.get("torchVersion"),
            "torchCudaBuild": cuda.get("torchCudaBuild"),
            "cudaAvailable": cuda_visible,
            "mpsAvailable": mps_visible,
            "mpsBuilt": bool(cuda.get("mpsBuilt")),
            "xpuAvailable": xpu_visible,
            "hipVersion": cuda.get("hipVersion"),
        },
        "reasonCodes": reason_codes,
        "messages": messages,
        "recommendedFixes": recommended_fixes,
    }


def local_environment_profile(
    cuda: Mapping[str, Any] | None = None,
    runtime_env: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify the local runtime for UI setup guidance without making network calls."""

    cuda_info = dict(cuda or cuda_status())
    runtime_env = dict(
        runtime_env
        or runtime_environment(
            cuda_info,
            hardware_accelerators=[] if cuda is not None else None,
            include_platform_hardware=cuda is None,
        )
    )
    system = platform.system() or "Unknown"
    machine = platform.machine() or "unknown"
    runtime_classification = str(runtime_env.get("classification") or "")
    cuda_available = bool(runtime_env.get("runtime", {}).get("cudaAvailable"))
    devices = list(cuda_info.get("devices") or [])
    mps_available = bool(runtime_env.get("runtime", {}).get("mpsAvailable"))
    if runtime_classification.startswith("cuda"):
        accelerator = "cuda"
    elif runtime_classification.startswith("mps"):
        accelerator = "mps"
    elif runtime_classification.startswith("xpu"):
        accelerator = "xpu"
    elif runtime_classification.startswith("rocm"):
        accelerator = "rocm"
    else:
        accelerator = "cpu"

    host, host_label = _host_runtime()

    if runtime_classification == "cuda_ready":
        label = f"{host_label} with CUDA GPU"
        summary = "CUDA is available through PyTorch, so GPU model setup can target SAM3 Scene Sweep."
    elif runtime_classification == "cuda_hardware_runtime_missing":
        label = f"{host_label} with GPU runtime not ready"
        summary = "GPU detected, but this Python environment cannot use CUDA yet. Install CUDA-enabled PyTorch or run the no-model CPU fallback."
    elif runtime_classification == "mps_ready":
        label = f"{host_label} with Apple MPS"
        summary = "Apple MPS is available through PyTorch. Treat SAM3 Scene Sweep as CUDA-first unless this runtime proves MPS support for the selected model."
    elif runtime_classification == "mps_hardware_runtime_missing":
        label = f"{host_label} with Apple Silicon runtime not ready"
        summary = "Apple Silicon hardware was detected, but PyTorch MPS is not ready in this runtime."
    elif accelerator in {"xpu", "rocm"}:
        label = f"{host_label} with {accelerator.upper()} runtime"
        summary = "Accelerator hardware was detected. Use provider diagnostics to confirm MotionJSON support for the selected model path."
    else:
        label = f"{host_label} CPU"
        summary = "No accelerator hardware signals were detected; use CPU-safe workflows, Apple MPS where supported, a CUDA runtime, or a hosted provider."

    notes: list[str] = []
    if not bool(cuda_info.get("torchInstalled")):
        notes.append("torch is not installed, so GPU availability may be incomplete.")
    for reason in cuda_info.get("reasons") or []:
        if reason:
            notes.append(str(reason))

    return {
        "format": ENVIRONMENT_PROFILE_FORMAT,
        "type": f"{host}_{accelerator}",
        "host": host,
        "hostLabel": host_label,
        "system": system,
        "machine": machine,
        "accelerator": accelerator,
        "classification": runtime_classification,
        "label": label,
        "summary": summary,
        "python": platform.python_version(),
        "torchInstalled": bool(cuda_info.get("torchInstalled")),
        "torchVersion": cuda_info.get("torchVersion"),
        "cudaAvailable": cuda_available,
        "mpsAvailable": mps_available,
        "devices": devices,
        "notes": notes,
        "runtimeEnvironment": runtime_env,
    }


def gpu_model_recommendation(
    provider_records: list[Mapping[str, Any]],
    environment_profile: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the UI's best model recommendation for the detected runtime."""

    providers = {str(provider.get("name") or ""): provider for provider in provider_records}
    sam3_scene_sweep = providers.get("sam3-auto-masks") or {}
    sam2_hf = providers.get("sam2-hf-auto-masks") or {}
    accelerator = str(environment_profile.get("accelerator") or "cpu")
    classification = str(environment_profile.get("classification") or "")
    if accelerator == "cuda":
        missing = list(sam3_scene_sweep.get("reasons") or [])
        status = str(sam3_scene_sweep.get("status") or "not_configured")
        runtime_missing = classification == "cuda_hardware_runtime_missing"
        runnable = bool(sam3_scene_sweep.get("runnable")) and not runtime_missing
        return {
            "format": GPU_MODEL_RECOMMENDATION_FORMAT,
            "environmentType": environment_profile.get("type"),
            "accelerator": accelerator,
            "classification": classification,
            "recommendedProviderId": "sam3_tracker_scene_sweep",
            "recommendedCapability": "sam3-auto-masks",
            "connectionId": "sam3-local",
            "model": SAM3_HF_REPO_ID,
            "label": "SAM3 Scene Sweep on CUDA",
            "reason": (
                "GPU detected, but this Python environment cannot use CUDA yet. Keep SAM3 Scene Sweep as the setup path, install a CUDA-enabled PyTorch runtime, then run proof."
                if runtime_missing
                else "A CUDA GPU is visible to PyTorch. Use SAM3 Scene Sweep with facebook/sam3 for scene-wide discovery, then review the proposed object tracks before export."
            ),
            "status": "needs_install" if runtime_missing else "ready" if runnable else status,
            "runnable": runnable,
            "missing": ["CUDA runtime is not ready for PyTorch.", *missing] if runtime_missing else missing,
            "nextActions": [
                "Install the sam3-transformers runtime if the tracker classes are missing.",
                "Check Hugging Face access when facebook/sam3 is gated.",
                "Cache facebook/sam3 from Model setup so the resolved runtime path is recorded server-side.",
                "Run a bounded smoke test before starting a real scene sweep.",
            ],
        }
    if accelerator == "mps":
        return {
            "format": GPU_MODEL_RECOMMENDATION_FORMAT,
            "environmentType": environment_profile.get("type"),
            "accelerator": accelerator,
            "classification": classification,
            "recommendedProviderId": "sam2-hf-auto-masks",
            "recommendedCapability": "sam2-hf-auto-masks",
            "connectionId": "sam2-hf-auto-masks",
            "model": SAM2_HF_AUTO_MASKS_DEFAULT_MODEL,
            "label": "SAM2 HF fallback while on Apple MPS",
            "reason": "Apple MPS is available, but MotionJSON treats SAM3 Scene Sweep as CUDA-first. Use the SAM2 HF automatic-mask fallback in this runtime, or move to a CUDA runtime for SAM3 Scene Sweep.",
            "status": str(sam2_hf.get("status") or "not_configured"),
            "runnable": bool(sam2_hf.get("runnable")),
            "missing": list(sam2_hf.get("reasons") or []),
            "nextActions": [
                "Install the sam2-transformers runtime if needed.",
                "Cache facebook/sam2.1-hiera-large from Model setup.",
                "Use CUDA Colab or a CUDA workstation for the SAM3 Scene Sweep recommendation.",
            ],
        }
    return {
        "format": GPU_MODEL_RECOMMENDATION_FORMAT,
        "environmentType": environment_profile.get("type"),
        "accelerator": accelerator,
        "classification": classification,
        "recommendedProviderId": "no_model_cpu_workflow",
        "recommendedCapability": "motion_foreground",
        "connectionId": "no_model_cpu_workflow",
        "model": "",
        "label": "No-model CPU workflow",
        "reason": "No CUDA GPU is visible to PyTorch. Start with motion foreground, external masks, or mock/no-model review, then switch to SAM3 Scene Sweep after launching a CUDA runtime.",
        "status": str((providers.get("motion_foreground") or {}).get("status") or "not_configured"),
        "runnable": bool((providers.get("motion_foreground") or {}).get("runnable")),
        "missing": list((providers.get("motion_foreground") or {}).get("reasons") or []),
        "nextActions": [
            "Use no-model CPU paths for smoke checks and simple moving-object footage.",
            "Choose a hosted provider only after explicit cost/privacy opt-in.",
            "Use a CUDA GPU runtime to run the recommended SAM3 Scene Sweep model.",
        ],
    }


def sam3_runtime_status() -> dict[str, Any]:
    minimum = (3, 12)
    current = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    return {
        "pythonVersion": current,
        "requiresPython": ">=3.12",
        "pythonSupported": sys.version_info >= minimum,
        "reasons": [] if sys.version_info >= minimum else [f"SAM3 local execution expects Python >=3.12; current Python is {current}."],
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
        _dependency("sam3", "sam3", "Install the official SAM3 package only for advanced concept/exemplar workflows."),
        _dependency("transformers", "transformers", "Install .[sam3-transformers] for SAM3 Scene Sweep; SAM2 is not required."),
        _dependency("torch", "torch", "Install torch separately only when using local ML providers."),
    ]


def provider_capabilities(
    *,
    sam2_checkpoint: str | Path | None = None,
    sam2_model_config: str | Path | None = None,
    hosted_allow_network: bool = False,
    provider_settings: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[ProviderCapability]:
    deps = {dep.module: dep.available for dep in dependency_statuses()}
    cv_ready = deps.get("cv2", False) and deps.get("numpy", False)
    pil_ready = deps.get("PIL", False)
    sam2_installed = deps.get("sam2", False)
    sam2_auto_installed = bool(sam2_installed and _module_available("sam2.automatic_mask_generator"))
    sam3_installed = deps.get("sam3", False)
    transformers_installed = deps.get("transformers", False)
    torch_info = cuda_status()
    sam3_runtime = sam3_runtime_status()
    sam2_local_settings = dict((provider_settings or {}).get("sam2-local", {}))
    sam2_hf_settings = dict((provider_settings or {}).get("sam2-hf-auto-masks", {}))
    sam3_local_settings = dict((provider_settings or {}).get("sam3-local", {}))
    sam2_hf_runtime_proof = dict(sam2_hf_settings.get("runtime_proof") or {})
    sam3_runtime_proof = dict(sam3_local_settings.get("runtime_proof") or {})
    if not sam2_hf_runtime_proof:
        sam2_hf_runtime_proof = _default_runtime_proof(
            "sam2-hf-auto-masks",
            "SAM2 HF automatic masks need runtime proof before extraction.",
        )
    if not sam3_runtime_proof:
        sam3_runtime_proof = _default_runtime_proof(
            "sam3-local",
            "SAM3 Scene Sweep needs runtime proof before extraction.",
        )
    if sam2_checkpoint is None:
        sam2_checkpoint = sam2_local_settings.get("sam2_checkpoint_path") or None
    if sam2_model_config is None:
        sam2_model_config = sam2_local_settings.get("sam2_model_config_path") or None
    checkpoint = _path_config_status("SAM2_LOCAL_CHECKPOINT", sam2_checkpoint)
    model_config = _path_config_status("SAM2_LOCAL_CONFIG", sam2_model_config)
    sam3_model_path = sam3_local_settings.get("sam3_model_path") or None
    hosted_settings = dict((provider_settings or {}).get("sam2-hosted", {}))
    sam3_hosted_settings = dict((provider_settings or {}).get("sam3-hosted", {}))
    hosted_profile = str(hosted_settings.get("hosted_profile_id") or "replicate-sam2-video")
    sam3_hosted_profile = str(sam3_hosted_settings.get("hosted_profile_id") or "roboflow-sam3-pcs")
    if not hosted_settings.get("hosted_profile_id") and os.environ.get("HOSTED_SEGMENTATION_API_KEY"):
        hosted_profile = "custom-sam2-compatible"
    if not sam3_hosted_settings.get("hosted_profile_id"):
        if os.environ.get("FAL_KEY"):
            sam3_hosted_profile = "fal-sam3-image"
        elif os.environ.get("SAM3_HOSTED_API_KEY"):
            sam3_hosted_profile = "custom-sam3-compatible"
    hosted_effective_profile = dict(hosted_settings.get("effective_profile") or {})
    sam3_effective_profile = dict(sam3_hosted_settings.get("effective_profile") or {})
    hosted_credential_fields = list(hosted_effective_profile.get("credentialFields") or [])
    sam3_credential_fields = list(sam3_effective_profile.get("credentialFields") or [])
    hosted_endpoint_field = dict(hosted_effective_profile.get("endpointField") or {})
    sam3_endpoint_field = dict(sam3_effective_profile.get("endpointField") or {})
    hosted_default_credential_env = {
        "replicate-sam2-video": "REPLICATE_API_TOKEN",
        "custom-sam2-compatible": "HOSTED_SEGMENTATION_API_KEY",
    }.get(hosted_profile, "HOSTED_SEGMENTATION_API_KEY")
    sam3_default_credential_env = {
        "roboflow-sam3-pcs": "ROBOFLOW_API_KEY",
        "fal-sam3-image": "FAL_KEY",
        "custom-sam3-compatible": "SAM3_HOSTED_API_KEY",
    }.get(sam3_hosted_profile, "SAM3_HOSTED_API_KEY")
    hosted_default_endpoint_env = "HOSTED_SEGMENTATION_URL"
    sam3_default_endpoint_env = "SAM3_HOSTED_URL" if sam3_hosted_profile == "custom-sam3-compatible" else "ROBOFLOW_SAM3_URL"
    hosted_default_endpoint_required = hosted_profile == "custom-sam2-compatible"
    sam3_default_endpoint_required = sam3_hosted_profile == "custom-sam3-compatible"
    hosted_auth = {
        "env": str((hosted_credential_fields[0] if hosted_credential_fields else {}).get("env") or hosted_default_credential_env),
        "configured": bool(hosted_settings.get("api_key_configured") or os.environ.get(hosted_default_credential_env)),
        "source": hosted_settings.get("credential_source") or "unset",
    }
    sam3_hosted_auth = {
        "env": str((sam3_credential_fields[0] if sam3_credential_fields else {}).get("env") or sam3_default_credential_env),
        "configured": bool(sam3_hosted_settings.get("api_key_configured") or os.environ.get(sam3_default_credential_env)),
        "source": sam3_hosted_settings.get("credential_source") or "unset",
    }
    if hosted_auth["source"] == "unset" and os.environ.get(str(hosted_auth["env"])):
        hosted_auth["source"] = "environment"
    if sam3_hosted_auth["source"] == "unset" and os.environ.get(str(sam3_hosted_auth["env"])):
        sam3_hosted_auth["source"] = "environment"
    hosted_endpoint = {
        "env": str(hosted_endpoint_field.get("env") or hosted_default_endpoint_env),
        "required": bool(hosted_endpoint_field.get("required", hosted_default_endpoint_required)),
        "configured": bool(hosted_settings.get("endpoint_configured") or os.environ.get(hosted_default_endpoint_env)),
        "source": hosted_settings.get("endpoint_source") or "unset",
    }
    sam3_hosted_endpoint = {
        "env": str(sam3_endpoint_field.get("env") or sam3_default_endpoint_env),
        "required": bool(sam3_endpoint_field.get("required", sam3_default_endpoint_required)),
        "configured": bool(sam3_hosted_settings.get("endpoint_configured") or os.environ.get(sam3_default_endpoint_env) or (sam3_hosted_profile == "roboflow-sam3-pcs")),
        "source": sam3_hosted_settings.get("endpoint_source") or "unset",
    }
    if hosted_endpoint["source"] == "unset" and os.environ.get(str(hosted_endpoint["env"])):
        hosted_endpoint["source"] = "environment"
    if sam3_hosted_endpoint["source"] == "unset" and os.environ.get(str(sam3_hosted_endpoint["env"])):
        sam3_hosted_endpoint["source"] = "environment"
    if sam3_hosted_endpoint["source"] == "unset" and sam3_hosted_profile == "roboflow-sam3-pcs":
        sam3_hosted_endpoint["source"] = "profile_default"
    hosted_profile_dependency = (
        "replicate" if hosted_profile == "replicate-sam2-video" else None
    )
    sam3_profile_dependency = (
        "fal_client" if sam3_hosted_profile == "fal-sam3-image" else None
    )
    hosted_profile_dependency_ready = True if hosted_profile_dependency is None else _module_available(hosted_profile_dependency)
    sam3_profile_dependency_ready = True if sam3_profile_dependency is None else _module_available(sam3_profile_dependency)
    openrouter_settings = dict((provider_settings or {}).get("openrouter", {}))
    hosted_allow_network_effective = bool(hosted_allow_network or hosted_settings.get("allow_hosted"))
    sam3_hosted_allow_network_effective = bool(hosted_allow_network or sam3_hosted_settings.get("allow_hosted"))
    sam3_model = _sam3_model_path_status(sam3_model_path)
    sam3_tracker_model_value = (
        os.environ.get("SAM3_TRACKER_MODEL")
        or sam3_local_settings.get("custom_model_id")
        or sam3_local_settings.get("selected_model")
        or SAM3_HF_REPO_ID
    )
    sam3_tracker_model_source = (
        "environment"
        if os.environ.get("SAM3_TRACKER_MODEL")
        else "local_settings"
        if sam3_local_settings.get("custom_model_id") or sam3_local_settings.get("selected_model")
        else "default"
    )
    sam3_tracker_model = describe_sam3_tracker_model(sam3_tracker_model_value, source=sam3_tracker_model_source)
    sam3_tracker_auto_masks_installed = _module_attr_available("transformers", "Sam3TrackerModel") and _module_attr_available("transformers", "Sam3TrackerProcessor")
    sam3_tracker_video_status = sam3_tracker_video_runtime_status() if transformers_installed else {}
    sam3_tracker_video_installed = bool(sam3_tracker_video_status.get("importable") and not sam3_tracker_video_status.get("knownBroken"))
    sam3_tracker_video_warning = (
        None
        if not transformers_installed or sam3_tracker_video_installed
        else str(sam3_tracker_video_status.get("message") or "SAM3 Tracker Video propagation is unavailable.")
    )
    openrouter_key = _settings_presence_config("OPENROUTER_API_KEY", provider_settings, "openrouter", "api_key_configured")
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
    sam2_auto_reasons = [
        reason
        for reason in (
            None if sam2_installed else "Python module 'sam2' is not importable.",
            None if sam2_auto_installed else "SAM2 automatic mask generator module is not importable.",
            *_model_path_reasons(checkpoint, "SAM2 checkpoint", "--sam2-checkpoint"),
            *_model_path_reasons(model_config, "SAM2 model config", "--sam2-config"),
            None if torch_info["torchInstalled"] else "torch is not installed.",
        )
        if reason
    ]
    sam2_auto_ready = bool(sam2_auto_installed and checkpoint["exists"] and model_config["exists"] and torch_info["torchInstalled"])
    sam2_hf_runtime_ready = bool(transformers_installed and torch_info["torchInstalled"])
    sam2_hf_proof_allows = bool(sam2_hf_runtime_proof.get("allowsRun"))
    sam2_hf_reasons = [
        reason
        for reason in (
            None if transformers_installed else "Python module 'transformers' is not importable.",
            None if torch_info["torchInstalled"] else "torch is not installed.",
            None
            if not sam2_hf_runtime_ready or sam2_hf_proof_allows
            else str(sam2_hf_runtime_proof.get("message") or "Run SAM2 HF smoke test before extraction."),
        )
        if reason
    ]
    sam2_hf_ready = bool(sam2_hf_runtime_ready and sam2_hf_proof_allows)
    sam2_hf_status = (
        "ready"
        if sam2_hf_ready
        else "runtime_proof_required"
        if sam2_hf_runtime_ready
        else "missing_dependency"
    )
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
    if not sam2_auto_installed or not torch_info["torchInstalled"]:
        sam_auto_masks_status = "missing_dependency"
    elif (checkpoint["configured"] and not checkpoint["exists"]) or (model_config["configured"] and not model_config["exists"]):
        sam_auto_masks_status = "missing_model"
    elif not checkpoint["configured"] or not model_config["configured"]:
        sam_auto_masks_status = "not_configured"
    elif not torch_info["available"]:
        sam_auto_masks_status = "available_cpu_only"
    else:
        sam_auto_masks_status = "ready"
    sam3_local_reasons = [
        reason
        for reason in (
            None if sam3_installed else "Python module 'sam3' is not importable.",
            *_model_path_reasons(sam3_model, "SAM3 runtime model", "SAM3_LOCAL_MODEL"),
            None if torch_info["torchInstalled"] else "torch is not installed.",
            None if sam3_runtime["pythonSupported"] else sam3_runtime["reasons"][0],
            None if torch_info["available"] else "SAM3 runtime execution expects a CUDA-compatible GPU; CUDA is not available.",
        )
        if reason
    ]
    sam3_local_ready = bool(
        sam3_installed
        and sam3_model["valid"]
        and torch_info["torchInstalled"]
        and sam3_runtime["pythonSupported"]
        and torch_info["available"]
    )
    sam3_scene_sweep_reasons = [
        reason
        for reason in (
            None if transformers_installed else "Python module 'transformers' is not importable. Use Model setup -> Install scene sweep.",
            None if not transformers_installed or sam3_tracker_auto_masks_installed else "Installed Transformers does not expose SAM3 Tracker automatic-mask classes. Upgrade the sam3-transformers extra from Model setup.",
            None if sam3_tracker_model.get("valid") else str(sam3_tracker_model.get("reason") or "SAM3 Tracker model is not a Hugging Face repo id or runtime model directory."),
            None if torch_info["torchInstalled"] else "torch is not installed.",
        )
        if reason
    ]
    sam3_scene_sweep_runtime_ready = bool(
        transformers_installed
        and sam3_tracker_auto_masks_installed
        and sam3_tracker_model.get("valid")
        and torch_info["torchInstalled"]
    )
    sam3_scene_sweep_proof_allows = bool(sam3_runtime_proof.get("allowsRun"))
    if sam3_scene_sweep_runtime_ready and not sam3_scene_sweep_proof_allows:
        sam3_scene_sweep_reasons.append(
            str(sam3_runtime_proof.get("message") or "Run SAM3 Scene Sweep smoke test before extraction.")
        )
    sam3_scene_sweep_ready = bool(sam3_scene_sweep_runtime_ready and sam3_scene_sweep_proof_allows)
    if not transformers_installed or not torch_info["torchInstalled"] or not sam3_tracker_auto_masks_installed:
        sam3_scene_sweep_status = "missing_dependency"
    elif not sam3_tracker_model.get("valid"):
        sam3_scene_sweep_status = "missing_model"
    elif not sam3_scene_sweep_proof_allows:
        sam3_scene_sweep_status = "runtime_proof_required"
    else:
        sam3_scene_sweep_status = "ready"
    if not sam3_installed or not torch_info["torchInstalled"]:
        sam3_local_status = "missing_dependency"
    elif not sam3_runtime["pythonSupported"]:
        sam3_local_status = "unsupported_runtime"
    elif sam3_model["configured"] and not sam3_model["valid"]:
        sam3_local_status = "missing_model"
    elif not sam3_model["configured"]:
        sam3_local_status = "not_configured"
    elif not torch_info["available"]:
        sam3_local_status = "available_cpu_only"
    else:
        sam3_local_status = "ready"
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

    hosted_configured = bool(hosted_settings.get("configured") or (hosted_auth["configured"] and (hosted_endpoint["configured"] or not hosted_endpoint["required"])))
    hosted_settings_only = bool(hosted_settings.get("settings_only"))
    hosted_endpoint_valid = hosted_settings.get("endpoint_valid", True) is not False
    hosted_runtime_runnable = bool(
        hosted_configured
        and hosted_endpoint_valid
        and hosted_allow_network_effective
        and not hosted_settings_only
        and hosted_profile_dependency_ready
    )
    if not hosted_profile_dependency_ready:
        hosted_status = "missing_dependency"
    elif not hosted_endpoint_valid:
        hosted_status = "invalid_configuration"
    elif hosted_settings_only and hosted_configured:
        hosted_status = "configured_settings_only"
    elif hosted_configured and not hosted_allow_network_effective:
        hosted_status = "needs_network_opt_in"
    elif hosted_configured:
        hosted_status = "ready"
    else:
        hosted_status = "not_configured"

    sam3_hosted_configured = bool(
        sam3_hosted_settings.get("configured")
        or (sam3_hosted_auth["configured"] and (sam3_hosted_endpoint["configured"] or not sam3_hosted_endpoint["required"]))
    )
    sam3_hosted_settings_only = bool(sam3_hosted_settings.get("settings_only"))
    sam3_hosted_endpoint_valid = sam3_hosted_settings.get("endpoint_valid", True) is not False
    sam3_hosted_runtime_runnable = bool(
        sam3_hosted_configured
        and sam3_hosted_endpoint_valid
        and sam3_hosted_allow_network_effective
        and not sam3_hosted_settings_only
        and sam3_profile_dependency_ready
    )
    if not sam3_profile_dependency_ready:
        sam3_hosted_status = "missing_dependency"
    elif not sam3_hosted_endpoint_valid:
        sam3_hosted_status = "invalid_configuration"
    elif sam3_hosted_settings_only and sam3_hosted_configured:
        sam3_hosted_status = "configured_settings_only"
    elif sam3_hosted_configured and not sam3_hosted_allow_network_effective:
        sam3_hosted_status = "needs_network_opt_in"
    elif sam3_hosted_configured:
        sam3_hosted_status = "ready"
    else:
        sam3_hosted_status = "not_configured"

    openrouter_configured = bool(openrouter_key["configured"])
    openrouter_settings_only = bool(openrouter_settings.get("settings_only"))
    openrouter_base_url_valid = openrouter_settings.get("base_url_valid", True) is not False
    if not openrouter_base_url_valid:
        openrouter_status = "invalid_configuration"
    elif openrouter_settings_only and openrouter_configured:
        openrouter_status = "configured_settings_only"
    elif openrouter_configured:
        openrouter_status = "ready"
    else:
        openrouter_status = "not_configured"

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
            name="sam2-hf-auto-masks",
            kind="discovery_provider",
            available=sam2_hf_runtime_ready,
            configured=True,
            installed=bool(transformers_installed and torch_info["torchInstalled"]),
            runnable=sam2_hf_ready,
            status=sam2_hf_status,
            supports=["automatic_keyframe_masks", "huggingface_transformers", "candidate_review", "sam2_hf_auto_masks"],
            reasons=sam2_hf_reasons,
            install_hint="Install .[sam2-transformers] and cache facebook/sam2.1-hiera-large from Model setup. Official SAM2 checkpoint/config is not required.",
            device=torch_info.get("device"),
            no_model_safe=False,
            network_required=False,
            needs_model_path=False,
            mock_available=True,
            optional_extra="sam2-transformers",
            checks=[
                _check("transformers_import", "ok" if transformers_installed else "missing", None if transformers_installed else "transformers package is not importable"),
                _check("torch_import", "ok" if torch_info["torchInstalled"] else "missing", None if torch_info["torchInstalled"] else "torch package is not importable"),
                _check("default_model", "ready", "Default Hugging Face model id.", SAM2_HF_AUTO_MASKS_DEFAULT_MODEL),
            ],
            metadata={
                "uiDescription": "SAM2 HF automatic masks for scene-sweep fallback, separate from official SAM2 prompt tracking.",
                "whenToUse": "Use as fallback for finding everything when SAM3 Scene Sweep is blocked.",
                "discoveryMode": "sam2_hf_auto_masks",
                "defaultModel": SAM2_HF_AUTO_MASKS_DEFAULT_MODEL,
                "officialSam2Required": False,
                "mockRunnable": cv_ready and pil_ready,
                "runtimeProof": sam2_hf_runtime_proof,
            },
        ),
        ProviderCapability(
            name="sam2-hosted",
            kind="mask_provider",
            available=hosted_configured and hosted_endpoint_valid and not hosted_settings_only and hosted_profile_dependency_ready,
            configured=hosted_configured and hosted_endpoint_valid,
            installed=hosted_profile_dependency_ready,
            runnable=hosted_runtime_runnable,
            status=hosted_status,
            supports=["point", "box", "hosted_segmentation"],
            reasons=[
                reason
                for reason in (
                    None if not hosted_profile_dependency or hosted_profile_dependency_ready else f"Python module {hosted_profile_dependency!r} is not importable.",
                    None if hosted_endpoint["configured"] or not hosted_endpoint["required"] else f"{hosted_endpoint['env']} is not set.",
                    None if hosted_auth["configured"] else f"{hosted_auth['env']} is not set.",
                    None if hosted_endpoint_valid else "Hosted segmentation endpoint must be an http:// or https:// URL.",
                    None if not hosted_settings_only or not hosted_configured else "Saved Runtime API hosted credentials are not available to the extraction runtime.",
                    None if hosted_allow_network_effective or not hosted_configured else "Hosted segmentation requires explicit network opt-in.",
                )
                if reason
            ],
            install_hint="Install .[hosted-sam-vendors] when the selected profile needs a vendor SDK, save a server-side key, and opt into hosted network use explicitly.",
            device="remote",
            no_model_safe=False,
            network_required=True,
            needs_credentials=True,
            mock_available=True,
            optional_extra="hosted-sam-vendors",
            checks=[
                _check("profile", "ok", hosted_profile, hosted_profile),
                _check("profile_dependency", "ok" if hosted_profile_dependency_ready else "missing", hosted_profile_dependency, hosted_profile_dependency_ready),
                _check("endpoint_env", "ok" if hosted_endpoint["configured"] or not hosted_endpoint["required"] else "missing", hosted_endpoint["env"], hosted_endpoint["configured"]),
                _check("auth_env", "ok" if hosted_auth["configured"] else "missing", hosted_auth["env"], hosted_auth["configured"]),
                _check("network_opt_in", "ok" if hosted_allow_network_effective else "required", "Hosted segmentation requires explicit network opt-in.", hosted_allow_network_effective),
                _check("settings_runtime", "settings_only" if hosted_settings_only else "runtime", "Runtime API saved provider keys are available to the worker runtime.", not hosted_settings_only),
            ],
            metadata={
                "hostedProfileId": hosted_profile,
                "effectiveProfile": hosted_effective_profile,
                "endpointEnv": hosted_endpoint,
                "authEnv": hosted_auth,
                "networkDefault": "disabled",
                "networkOptIn": hosted_allow_network_effective,
                "credentialSource": hosted_auth.get("source"),
                "endpointSource": hosted_endpoint.get("source"),
                "settingsOnly": hosted_settings_only,
                "profileDependency": hosted_profile_dependency,
                "selectedModel": hosted_settings.get("selected_model"),
                "runtimeProof": hosted_settings.get("runtime_proof") or {},
            },
        ),
        ProviderCapability(
            name="sam3-local",
            kind="discovery_provider",
            available=sam3_local_ready,
            configured=bool(sam3_model["configured"]),
            installed=bool(sam3_installed and torch_info["torchInstalled"]),
            runnable=sam3_local_ready,
            status=sam3_local_status,
            supports=["concept_discovery", "exemplar_discovery", "advanced_official_sam3_package", "local_checkpoint"],
            reasons=sam3_local_reasons,
            install_hint="Install the official SAM3 package and configure sam3ModelPath only for advanced concept/exemplar workflows. Use sam3-auto-masks for normal SAM3 Scene Sweep.",
            device=torch_info.get("device"),
            no_model_safe=False,
            network_required=False,
            needs_gpu=True,
            needs_model_path=True,
            model_paths=[sam3_model],
            mock_available=True,
            optional_extra="sam3",
            checks=[
                _check("sam3_import", "ok" if sam3_installed else "missing", None if sam3_installed else "sam3 package is not importable"),
                _check("transformers_import", "ok" if transformers_installed else "missing", None if transformers_installed else "transformers package is not importable"),
                _check("torch_import", "ok" if torch_info["torchInstalled"] else "missing", None if torch_info["torchInstalled"] else "torch package is not importable"),
                _check(
                    "python_runtime",
                    "ok" if sam3_runtime["pythonSupported"] else "unsupported",
                    f"Python {sam3_runtime['pythonVersion']} detected; SAM3 local expects {sam3_runtime['requiresPython']}.",
                    sam3_runtime["pythonSupported"],
                ),
                _check("cuda", "ok" if torch_info["available"] else "missing", "SAM3 local execution expects CUDA.", torch_info["available"]),
                _check("model", "ok" if sam3_model["valid"] else "missing", sam3_model.get("reason") or sam3_model["env"], sam3_model["valid"]),
            ],
            metadata={
                "model": sam3_model,
                "runtime": sam3_runtime,
                "uiDescription": "Advanced official SAM3 package adapter for concept/exemplar workflows.",
                "whenToUse": "Use only when the official SAM3 package and a local sam3.pt checkpoint are configured.",
                "semanticDiscovery": True,
                "sceneSweep": {
                    "ready": sam3_scene_sweep_ready,
                    "status": sam3_scene_sweep_status,
                    "reasons": sam3_scene_sweep_reasons,
                    "optionalExtra": "sam3-transformers",
                    "requiresSam2": False,
                    "trackerModel": sam3_tracker_model,
                    "trackerVideo": {
                        **dict(sam3_tracker_video_status),
                        "required": False,
                        "warning": sam3_tracker_video_warning,
                    },
                },
                "mockRunnable": cv_ready and pil_ready,
                "runtimeProof": sam3_runtime_proof,
            },
        ),
        ProviderCapability(
            name="sam3-hosted",
            kind="discovery_provider",
            available=sam3_hosted_configured and sam3_hosted_endpoint_valid and not sam3_hosted_settings_only and sam3_profile_dependency_ready,
            configured=sam3_hosted_configured and sam3_hosted_endpoint_valid,
            installed=sam3_profile_dependency_ready,
            runnable=sam3_hosted_runtime_runnable,
            status=sam3_hosted_status,
            supports=["concept_discovery", "exemplar_discovery", "hosted_segmentation", "hosted_tracking"],
            reasons=[
                reason
                for reason in (
                    None if not sam3_profile_dependency or sam3_profile_dependency_ready else f"Python module {sam3_profile_dependency!r} is not importable.",
                    None if sam3_hosted_endpoint["configured"] or not sam3_hosted_endpoint["required"] else f"{sam3_hosted_endpoint['env']} is not set.",
                    None if sam3_hosted_auth["configured"] else f"{sam3_hosted_auth['env']} is not set.",
                    None if sam3_hosted_endpoint_valid else "Hosted SAM3 endpoint must be an http:// or https:// URL.",
                    None if not sam3_hosted_settings_only or not sam3_hosted_configured else "Saved Runtime API SAM3 credentials are not available to the extraction runtime.",
                    None if sam3_hosted_allow_network_effective or not sam3_hosted_configured else "Hosted SAM3 requires explicit network opt-in.",
                )
                if reason
            ],
            install_hint="Install .[hosted-sam-vendors] when the selected profile needs a vendor SDK, save a server-side key, and opt into hosted network use explicitly.",
            device="remote",
            no_model_safe=False,
            network_required=True,
            needs_credentials=True,
            mock_available=True,
            optional_extra="hosted-sam-vendors",
            checks=[
                _check("profile", "ok", sam3_hosted_profile, sam3_hosted_profile),
                _check("profile_dependency", "ok" if sam3_profile_dependency_ready else "missing", sam3_profile_dependency, sam3_profile_dependency_ready),
                _check("endpoint_env", "ok" if sam3_hosted_endpoint["configured"] or not sam3_hosted_endpoint["required"] else "missing", sam3_hosted_endpoint["env"], sam3_hosted_endpoint["configured"]),
                _check("auth_env", "ok" if sam3_hosted_auth["configured"] else "missing", sam3_hosted_auth["env"], sam3_hosted_auth["configured"]),
                _check("network_opt_in", "ok" if sam3_hosted_allow_network_effective else "required", "Hosted SAM3 requires explicit network opt-in.", sam3_hosted_allow_network_effective),
                _check("settings_runtime", "settings_only" if sam3_hosted_settings_only else "runtime", "Runtime API saved SAM3 keys are available to the worker runtime.", not sam3_hosted_settings_only),
            ],
            metadata={
                "hostedProfileId": sam3_hosted_profile,
                "effectiveProfile": sam3_effective_profile,
                "endpointEnv": sam3_hosted_endpoint,
                "authEnv": sam3_hosted_auth,
                "networkDefault": "disabled",
                "networkOptIn": sam3_hosted_allow_network_effective,
                "credentialSource": sam3_hosted_auth.get("source"),
                "endpointSource": sam3_hosted_endpoint.get("source"),
                "settingsOnly": sam3_hosted_settings_only,
                "profileDependency": sam3_profile_dependency,
                "selectedModel": sam3_hosted_settings.get("selected_model"),
                "semanticDiscovery": True,
                "runtimeProof": sam3_hosted_settings.get("runtime_proof") or {},
            },
        ),
        ProviderCapability(
            name="sam3-concept",
            kind="discovery_provider",
            available=sam3_local_ready,
            configured=bool(sam3_model["configured"]),
            installed=bool(sam3_installed and torch_info["torchInstalled"]),
            runnable=sam3_local_ready,
            status=sam3_local_status,
            supports=["text_concept_discovery", "open_vocabulary_instances", "mock_concept_candidates"],
            reasons=sam3_local_reasons,
            install_hint="Use discovery.config.mock=true for local smoke checks, or configure SAM3 local/hosted support.",
            device=torch_info.get("device"),
            no_model_safe=False,
            network_required=False,
            needs_gpu=True,
            needs_model_path=True,
            model_paths=[sam3_model],
            mock_available=True,
            optional_extra="sam3",
            metadata={
                "uiDescription": "SAM3-style concept prompt discovery; mock mode is available without SAM3.",
                "whenToUse": "Use for text/concept object discovery after SAM3 setup.",
                "discoveryMode": "sam3_concept",
                "mockRunnable": cv_ready and pil_ready,
            },
        ),
        ProviderCapability(
            name="sam3-exemplar",
            kind="discovery_provider",
            available=sam3_local_ready,
            configured=bool(sam3_model["configured"]),
            installed=bool(sam3_installed and torch_info["torchInstalled"]),
            runnable=sam3_local_ready,
            status=sam3_local_status,
            supports=["exemplar_discovery", "visual_prompt_instances", "mock_exemplar_candidates"],
            reasons=sam3_local_reasons,
            install_hint="Use discovery.config.mock=true for local smoke checks, or configure SAM3 local/hosted support.",
            device=torch_info.get("device"),
            no_model_safe=False,
            network_required=False,
            needs_gpu=True,
            needs_model_path=True,
            model_paths=[sam3_model],
            mock_available=True,
            optional_extra="sam3",
            metadata={
                "uiDescription": "SAM3-style exemplar/crop discovery; mock mode is available without SAM3.",
                "whenToUse": "Use for finding objects similar to a selected reference after SAM3 setup.",
                "discoveryMode": "sam3_exemplar",
                "mockRunnable": cv_ready and pil_ready,
            },
        ),
        ProviderCapability(
            name="sam3-auto-masks",
            kind="discovery_provider",
            available=sam3_scene_sweep_runtime_ready,
            configured=sam3_scene_sweep_runtime_ready,
            installed=bool(transformers_installed and torch_info["torchInstalled"]),
            runnable=sam3_scene_sweep_ready,
            status=sam3_scene_sweep_status,
            supports=["scene_sweep", "automatic_mask_generation", "tracker_video_propagation", "mock_auto_candidates"],
            reasons=sam3_scene_sweep_reasons,
            install_hint="Use discovery.config.mock=true for local smoke checks, or install .[sam3-transformers]. SAM2 is not required.",
            device=torch_info.get("device"),
            no_model_safe=False,
            network_required=False,
            needs_gpu=False,
            needs_model_path=not bool(sam3_tracker_model.get("valid")),
            model_paths=[] if sam3_tracker_model.get("valid") else [sam3_tracker_model],
            mock_available=True,
            optional_extra="sam3-transformers",
            metadata={
                "uiDescription": "SAM3 scene sweep proposals from SAM3 Tracker image masks and Tracker Video propagation.",
                "whenToUse": "Use to find everything visible in the scene with SAM3-only dependencies.",
                "discoveryMode": "sam3_auto_masks",
                "requiresSam2": False,
                "trackerModel": sam3_tracker_model,
                "trackerVideo": {
                    **dict(sam3_tracker_video_status),
                    "required": False,
                    "warning": sam3_tracker_video_warning,
                },
                "mockRunnable": cv_ready and pil_ready,
                "runtimeProof": sam3_runtime_proof,
            },
        ),
        ProviderCapability(
            name="openrouter",
            kind="llm_provider",
            available=openrouter_configured and openrouter_base_url_valid and not openrouter_settings_only,
            configured=openrouter_configured and openrouter_base_url_valid,
            installed=True,
            runnable=bool(openrouter_configured and openrouter_base_url_valid and not openrouter_settings_only),
            status=openrouter_status,
            supports=["llm", "vlm_reasoning", "labels"],
            reasons=[
                reason
                for reason in (
                    None if openrouter_key["configured"] else "OPENROUTER_API_KEY is not set.",
                    None if openrouter_base_url_valid else "OPENROUTER_BASE_URL must be an http:// or https:// URL.",
                    None if not openrouter_settings_only or not openrouter_configured else "Saved Runtime API OpenRouter keys are settings-only; OpenRouterLLMProvider currently reads constructor values or environment variables.",
                )
                if reason
            ],
            install_hint="Set OPENROUTER_API_KEY only for LLM/VLM reasoning. OpenRouter is not a segmentation provider.",
            no_model_safe=False,
            network_required=True,
            needs_credentials=True,
            mock_available=True,
            optional_extra="openrouter",
            checks=[_check("api_key_env", "ok" if openrouter_key["configured"] else "missing", openrouter_key["env"], openrouter_key["configured"])],
            metadata={
                "apiKeyEnv": openrouter_key,
                "credentialSource": openrouter_key.get("source"),
                "baseUrlSource": openrouter_settings.get("base_url_source"),
                "settingsOnly": openrouter_settings_only,
                "selectedModel": openrouter_settings.get("selected_model"),
                "segmentationProvider": False,
            },
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
            name="auto_object_proposals",
            kind="discovery_provider",
            available=sam2_auto_ready,
            configured=bool(checkpoint["configured"] and model_config["configured"]),
            installed=bool(sam2_auto_installed and torch_info["torchInstalled"]),
            runnable=sam2_auto_ready,
            status=sam_auto_masks_status,
            supports=[
                "quality_presets",
                "automatic_keyframe_proposals",
                "sam2_automatic_mask_generation",
                "sam2_video_propagation",
                "candidate_caps",
                "review_required",
                "selected_candidate_tracking_contract",
            ],
            reasons=sam2_auto_reasons,
            install_hint="Use the clean mock/no-model path for smoke checks, or install/configure SAM2 automatic masks for real local proposals.",
            device=torch_info.get("device"),
            no_model_safe=False,
            network_required=False,
            needs_model_path=True,
            model_paths=[checkpoint, model_config],
            mock_available=True,
            optional_extra="sam2",
            checks=[
                _check("sam2_import", "ok" if sam2_installed else "missing", None if sam2_installed else "sam2 package is not importable"),
                _check("sam2_auto_mask_generator", "ok" if sam2_auto_installed else "missing", None if sam2_auto_installed else "sam2 automatic mask generator is not importable"),
                _check("torch_import", "ok" if torch_info["torchInstalled"] else "missing", None if torch_info["torchInstalled"] else "torch package is not importable"),
                _check("checkpoint", "ok" if checkpoint["exists"] else "missing", checkpoint["env"], checkpoint["exists"]),
                _check("model_config", "ok" if model_config["exists"] else "missing", model_config["env"], model_config["exists"]),
            ],
            metadata={
                "uiDescription": "Default object discovery flow with clean, balanced, maximum-recall, and Trace Everything presets.",
                "whenToUse": "Use when users should choose from API-returned object candidates before tracking.",
                "defaultQualityPreset": "clean",
                "mockRunnable": cv_ready and pil_ready,
                "requiresReview": True,
                "sam2AutomaticProposals": True,
                "selectedTracking": "SAM2 propagation when configured; otherwise review uses generated candidate mask artifacts.",
            },
        ),
        ProviderCapability(
            name="sam_auto_masks",
            kind="discovery_provider",
            available=sam2_auto_ready,
            configured=bool(checkpoint["configured"] and model_config["configured"]),
            installed=bool(sam2_auto_installed and torch_info["torchInstalled"]),
            runnable=sam2_auto_ready,
            status=sam_auto_masks_status,
            supports=["automatic_keyframe_masks", "sam2_automatic_mask_generation", "sam2_video_propagation", "area_filter", "stability_filter", "overlap_filter"],
            reasons=sam2_auto_reasons,
            install_hint="Install/configure SAM2 automatic masks, or use motion_foreground/external_masks for no-model discovery.",
            device=torch_info.get("device"),
            no_model_safe=False,
            network_required=False,
            needs_model_path=True,
            model_paths=[checkpoint, model_config],
            mock_available=True,
            optional_extra="sam2",
            checks=[
                _check("sam2_import", "ok" if sam2_installed else "missing", None if sam2_installed else "sam2 package is not importable"),
                _check("sam2_auto_mask_generator", "ok" if sam2_auto_installed else "missing", None if sam2_auto_installed else "sam2 automatic mask generator is not importable"),
                _check("torch_import", "ok" if torch_info["torchInstalled"] else "missing", None if torch_info["torchInstalled"] else "torch package is not importable"),
                _check("checkpoint", "ok" if checkpoint["exists"] else "missing", checkpoint["env"], checkpoint["exists"]),
                _check("model_config", "ok" if model_config["exists"] else "missing", model_config["env"], model_config["exists"]),
            ],
            metadata={
                "uiDescription": "Automatic visible-segment proposals from a configured SAM2-style backend.",
                "whenToUse": "Use when the user wants broad visible-segment proposals and a SAM2 runtime is configured.",
                "sam2AutomaticProposals": True,
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
    provider_settings: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    deps = dependency_statuses()
    providers = provider_capabilities(
        sam2_checkpoint=sam2_checkpoint,
        sam2_model_config=sam2_model_config,
        hosted_allow_network=hosted_allow_network,
        provider_settings=provider_settings,
    )
    provider_records = [provider.to_dict() for provider in providers]
    cuda = cuda_status()
    runtime_env = runtime_environment(cuda)
    environment_profile = local_environment_profile(cuda, runtime_env=runtime_env)
    model_recommendation = gpu_model_recommendation(provider_records, environment_profile)
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
        and provider.name
        in {
            "sam2-local",
            "sam2-hf-auto-masks",
            "sam2-hosted",
            "sam3-hosted",
            "sam3-auto-masks",
            "openrouter",
            "sam_auto_masks",
            "text_detector",
            "class_detector",
            "ffmpeg-video",
        }
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
            "profile": environment_profile,
            "runtimeEnvironment": runtime_env,
            "dependencies": [dep.to_dict() for dep in deps],
            "cuda": cuda,
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
            "runtimeFreeRunnableProviders": local_free_providers,
            "localFreeRunnableProviders": local_free_providers,
            "canRunNoModelSmoke": all(name in ready_no_model for name in ("mock", "threshold", "motionjson-json")),
            "gpuModelRecommendation": model_recommendation,
            "firstRun": {
                "ready": any(name in runnable_providers for name in ("sam2-local", "sam2-hf-auto-masks", "sam2-hosted", "sam3-auto-masks", "sam3-hosted")),
                "recommendedCommand": "python3 -m motionjson.cli ui --no-open",
                "recommendedDemoCommand": "python3 examples/make_demo_video.py --out examples/demo_red_ball.mp4 && python3 -m motionjson.cli extract examples/demo_red_ball.mp4 --out out/demo_red_ball --mask-provider threshold --lower-hsv 0,80,80 --upper-hsv 12,255,255 --sample-fps 12 --max-frames 12",
                "nextActions": [
                    "Launch the MotionJSON Workspace.",
                    "Connect a runtime or hosted SAM provider in Model Connections.",
                    "Use debug mock mode only for contributor smoke checks.",
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
    if str(provider.get("name") or "").startswith("sam3"):
        model = dict((provider.get("metadata") or {}).get("model") or {})
        if model.get("configured") and not model.get("valid") and model.get("reason"):
            return str(model["reason"])
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
        lines.append(f"Runnable runtime/free providers: {', '.join(local_free)}")
    lines.append(
        "Debug smoke: "
        + (
            "available with `python3 -m motionjson.cli ui --no-open --debug-mock` for contributor checks."
            if summary.get("canRunNoModelSmoke")
            else "limited - install base dependencies before running debug smoke checks."
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
