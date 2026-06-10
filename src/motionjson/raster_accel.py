from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np


ACCELERATED_RASTER_OPERATIONS = [
    "mask_normalization",
    "alpha_prep",
    "crop_extraction",
    "feathering",
    "cutout_generation",
    "template_match_fallback",
    "vector_pre_contour_maps",
]
FINAL_CONTOUR_BACKEND = "cpu-opencv"
RASTER_BENCHMARK_SCHEMA = "motionjson.raster_acceleration_benchmark.v0.1"


@dataclass(frozen=True)
class RasterAccelerationStatus:
    requested_device: str
    actual_device: str
    backend: str
    acceleration_available: bool
    torch_available: bool
    reason: str
    operations: list[str]
    final_contour_backend: str = FINAL_CONTOUR_BACKEND

    @property
    def accelerated(self) -> bool:
        return self.backend in {"cuda", "mps"} and self.acceleration_available

    def to_metadata(self) -> dict[str, Any]:
        return {
            "requestedDevice": self.requested_device,
            "actualDevice": self.actual_device,
            "backend": self.backend,
            "accelerationAvailable": self.acceleration_available,
            "accelerated": self.accelerated,
            "torchAvailable": self.torch_available,
            "reason": self.reason,
            "operations": list(self.operations),
            "acceleratedOperations": _accelerated_operations(self.backend) if self.accelerated else [],
            "vectorPrepassBackend": self.backend if self.accelerated else "cpu",
            "finalContourBackend": self.final_contour_backend,
        }


def resolve_raster_acceleration(device: str | None) -> RasterAccelerationStatus:
    requested = str(device or "").strip()
    normalized = requested.lower()
    torch_module, torch_available = _optional_torch()
    requested_label = requested or "cpu"

    if normalized in {"", "cpu", "none", "off", "false"}:
        reason = "cpu_requested" if normalized == "cpu" else "no_acceleration_requested"
        return _status(requested_label, "cpu", "cpu", False, torch_available, reason)

    if torch_module is None:
        return _status(requested_label, "cpu", "cpu", False, False, "torch_unavailable")

    cuda_available = _cuda_available(torch_module)
    mps_available = _mps_available(torch_module)

    if normalized in {"auto", "auto/cpu"}:
        if cuda_available:
            return _status(requested_label, "cuda:0", "cuda", True, True, "auto_selected_cuda")
        if mps_available:
            return _status(requested_label, "mps", "mps", True, True, "auto_selected_mps")
        return _status(requested_label, "cpu", "cpu", False, True, "no_accelerator_available")

    if normalized.startswith("cuda"):
        if cuda_available:
            if not _cuda_device_requested_available(torch_module, normalized):
                return _status(requested_label, "cpu", "cpu", False, True, "cuda_device_unavailable")
            actual = normalized if ":" in normalized else "cuda:0"
            return _status(requested_label, actual, "cuda", True, True, "cuda_available")
        return _status(requested_label, "cpu", "cpu", False, True, "cuda_unavailable")

    if normalized.startswith("mps"):
        if mps_available:
            return _status(requested_label, "mps", "mps", True, True, "mps_available")
        return _status(requested_label, "cpu", "cpu", False, True, "mps_unavailable")

    return _status(requested_label, "cpu", "cpu", False, torch_available, "unsupported_device_requested")


def resolve_torch_device(device: str | None) -> Any | None:
    status = resolve_raster_acceleration(device)
    if not status.accelerated:
        return None
    torch_module, _torch_available = _optional_torch()
    if torch_module is None:
        return None
    return torch_module.device(status.actual_device)


def raster_acceleration_message(status: RasterAccelerationStatus) -> str:
    if status.accelerated:
        return (
            f"raster acceleration using {status.backend.upper()} for alpha prep, "
            "template matching, and pre-contour maps"
        )
    if status.reason in {"cuda_unavailable", "mps_unavailable", "torch_unavailable"}:
        return f"raster acceleration using CPU fallback: {status.reason}"
    return "raster acceleration using CPU path"


def benchmark_raster_operations(
    *,
    width: int = 96,
    height: int = 64,
    iterations: int = 3,
    device: str | None = None,
    feather: int = 3,
) -> dict[str, Any]:
    """Benchmark crop/alpha prep and vector pre-contour work without requiring GPU."""
    from .layers import crop_rgba_layer
    from .vectorize import mask_to_largest_polygon

    width = max(16, int(width))
    height = max(16, int(height))
    iterations = max(1, int(iterations))
    rgb, mask, bbox = _synthetic_raster_fixture(width=width, height=height)
    status = resolve_raster_acceleration(device)

    cpu_ms, cpu_pixels, cpu_points = _time_raster_loop(
        rgb=rgb,
        mask=mask,
        bbox=bbox,
        iterations=iterations,
        device="cpu",
        feather=feather,
        crop_rgba_layer=crop_rgba_layer,
        mask_to_largest_polygon=mask_to_largest_polygon,
    )
    selected_ms, selected_pixels, selected_points = _time_raster_loop(
        rgb=rgb,
        mask=mask,
        bbox=bbox,
        iterations=iterations,
        device=status.actual_device,
        feather=feather,
        crop_rgba_layer=crop_rgba_layer,
        mask_to_largest_polygon=mask_to_largest_polygon,
    )
    speedup = cpu_ms / selected_ms if selected_ms > 0 else None
    return {
        "schema": RASTER_BENCHMARK_SCHEMA,
        "benchmark": "raster_alpha_and_vector_precontour",
        "iterations": iterations,
        "frameSize": {"width": width, "height": height},
        "rasterAcceleration": status.to_metadata(),
        "cpuPath": {
            "totalMs": _round_ms(cpu_ms),
            "msPerIteration": _round_ms(cpu_ms / iterations),
            "processedPixels": cpu_pixels,
            "contourPoints": cpu_points,
        },
        "selectedPath": {
            "totalMs": _round_ms(selected_ms),
            "msPerIteration": _round_ms(selected_ms / iterations),
            "processedPixels": selected_pixels,
            "contourPoints": selected_points,
        },
        "comparison": {
            "selectedVsCpuSpeedup": round(speedup, 3) if speedup is not None else None,
        },
        "notes": [
            "Final polygon contour extraction remains CPU/OpenCV for stable vector output.",
            "CUDA/MPS paths include tensor transfer overhead; small fixtures may not show speedup.",
        ],
    }


def _status(
    requested_device: str,
    actual_device: str,
    backend: str,
    acceleration_available: bool,
    torch_available: bool,
    reason: str,
) -> RasterAccelerationStatus:
    return RasterAccelerationStatus(
        requested_device=requested_device,
        actual_device=actual_device,
        backend=backend,
        acceleration_available=acceleration_available,
        torch_available=torch_available,
        reason=reason,
        operations=list(ACCELERATED_RASTER_OPERATIONS),
    )


def _optional_torch() -> tuple[Any | None, bool]:
    try:
        import torch  # type: ignore
    except Exception:
        return None, False
    return torch, True


def _cuda_available(torch_module: Any) -> bool:
    try:
        return bool(getattr(torch_module, "cuda", None) and torch_module.cuda.is_available())
    except Exception:
        return False


def _cuda_device_requested_available(torch_module: Any, normalized_device: str) -> bool:
    if ":" not in normalized_device:
        return True
    try:
        index = int(normalized_device.split(":", 1)[1])
        count = int(torch_module.cuda.device_count())
    except Exception:
        return True
    return 0 <= index < count


def _mps_available(torch_module: Any) -> bool:
    try:
        mps = getattr(getattr(torch_module, "backends", None), "mps", None)
        return bool(mps and mps.is_available())
    except Exception:
        return False


def _accelerated_operations(backend: str) -> list[str]:
    if backend == "cuda":
        return list(ACCELERATED_RASTER_OPERATIONS)
    if backend == "mps":
        return [item for item in ACCELERATED_RASTER_OPERATIONS if item != "template_match_fallback"]
    return []


def _synthetic_raster_fixture(*, width: int, height: int) -> tuple[np.ndarray, np.ndarray, list[int]]:
    rgb = np.zeros((height, width, 3), dtype=np.uint8)
    rgb[:, :, 0] = np.linspace(24, 220, width, dtype=np.uint8)[None, :]
    rgb[:, :, 1] = np.linspace(230, 80, height, dtype=np.uint8)[:, None]
    rgb[:, :, 2] = 116
    mask = np.zeros((height, width), dtype=np.uint8)
    center = (width // 2, height // 2)
    radius = max(5, min(width, height) // 5)
    cv2.circle(mask, center, radius, 255, -1)
    bbox = [center[0] - radius, center[1] - radius, radius * 2 + 1, radius * 2 + 1]
    return rgb, mask, bbox


def _time_raster_loop(
    *,
    rgb: np.ndarray,
    mask: np.ndarray,
    bbox: list[int],
    iterations: int,
    device: str | None,
    feather: int,
    crop_rgba_layer: Any,
    mask_to_largest_polygon: Any,
) -> tuple[float, int, int]:
    pixels = 0
    contour_points = 0
    started = time.perf_counter()
    for _index in range(iterations):
        crop = crop_rgba_layer(rgb, mask, bbox, feather=feather, padding=4, device=device)
        contour = mask_to_largest_polygon(mask, min_area=1, device=device)
        pixels += int(crop.rgba.shape[0] * crop.rgba.shape[1])
        contour_points += int(contour.contour_points)
    return (time.perf_counter() - started) * 1000, pixels, contour_points


def _round_ms(value: float) -> float:
    return round(float(value), 3)
