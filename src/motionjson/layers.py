from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

from .raster_accel import resolve_torch_device


@dataclass(frozen=True)
class LayerCrop:
    rgba: np.ndarray
    bbox: list[int]
    anchor: list[float]


def crop_rgba_layer(
    rgb: np.ndarray,
    mask: np.ndarray,
    bbox: list[int],
    *,
    centroid: list[float] | None = None,
    feather: int = 0,
    padding: int = 4,
    device: str | None = None,
) -> LayerCrop:
    """Create a cropped RGBA object layer from a full-frame RGB image and mask."""
    if mask.ndim != 2:
        raise ValueError("mask must be a 2D array")
    if rgb.shape[:2] != mask.shape[:2]:
        raise ValueError("rgb and mask dimensions must match")

    frame_h, frame_w = mask.shape[:2]
    x, y, w, h = [int(round(v)) for v in bbox]
    pad = max(0, int(padding))
    x0 = max(0, x - pad)
    y0 = max(0, y - pad)
    x1 = min(frame_w, x + w + pad)
    y1 = min(frame_h, y + h + pad)

    if x1 <= x0 or y1 <= y0:
        empty = np.zeros((1, 1, 4), dtype=np.uint8)
        return LayerCrop(rgba=empty, bbox=[0, 0, 1, 1], anchor=[0.5, 0.5])

    rgba = _rgba_crop(rgb, mask, x0=x0, y0=y0, x1=x1, y1=y1, feather=feather, device=device)
    if centroid:
        anchor = [round(float(centroid[0]) - x0, 3), round(float(centroid[1]) - y0, 3)]
    else:
        anchor = [round((x1 - x0) / 2, 3), round((y1 - y0) / 2, 3)]

    return LayerCrop(rgba=rgba, bbox=[x0, y0, x1 - x0, y1 - y0], anchor=anchor)


def _rgba_crop(
    rgb: np.ndarray,
    mask: np.ndarray,
    *,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    feather: int,
    device: str | None,
) -> np.ndarray:
    torch_device = resolve_torch_device(device)
    if torch_device is None:
        alpha = mask[y0:y1, x0:x1].copy()
        if feather > 0:
            k = max(3, int(feather) | 1)
            alpha = cv2.GaussianBlur(alpha, (k, k), 0)
        crop_rgb = rgb[y0:y1, x0:x1]
        return np.dstack([crop_rgb, alpha]).astype(np.uint8)
    try:
        import torch  # type: ignore
        import torch.nn.functional as F  # type: ignore
    except ImportError:
        alpha = mask[y0:y1, x0:x1].copy()
        if feather > 0:
            k = max(3, int(feather) | 1)
            alpha = cv2.GaussianBlur(alpha, (k, k), 0)
        crop_rgb = rgb[y0:y1, x0:x1]
        return np.dstack([crop_rgb, alpha]).astype(np.uint8)

    crop_rgb = torch.as_tensor(rgb[y0:y1, x0:x1], device=torch_device, dtype=torch.uint8)
    alpha = torch.as_tensor(mask[y0:y1, x0:x1], device=torch_device, dtype=torch.float32)
    if feather > 0:
        alpha = _gaussian_blur_alpha(alpha, feather, F)
    alpha = alpha.clamp(0, 255).to(torch.uint8)
    rgba = torch.cat([crop_rgb, alpha.unsqueeze(-1)], dim=2)
    return rgba.cpu().numpy()


def _gaussian_blur_alpha(alpha: Any, feather: int, functional: Any) -> Any:
    import torch  # type: ignore

    radius = max(1, int(feather))
    kernel_size = max(3, radius * 2 + 1)
    coords = alpha.new_tensor(np.arange(kernel_size, dtype=np.float32)) - (kernel_size - 1) / 2
    sigma = max(float(radius) / 2.0, 1.0)
    kernel_1d = torch.exp(-(coords**2) / (2 * sigma * sigma))
    kernel_1d = kernel_1d / kernel_1d.sum()
    kernel_x = kernel_1d.view(1, 1, 1, kernel_size)
    kernel_y = kernel_1d.view(1, 1, kernel_size, 1)
    value = alpha.unsqueeze(0).unsqueeze(0)
    value = functional.pad(value, (kernel_size // 2, kernel_size // 2, 0, 0), mode="reflect")
    value = functional.conv2d(value, kernel_x)
    value = functional.pad(value, (0, 0, kernel_size // 2, kernel_size // 2), mode="reflect")
    value = functional.conv2d(value, kernel_y)
    return value[0, 0]


def build_raster_motion_layer(*, object_id: str, fps: float, frames: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the browser-facing JSON layer from per-frame object metadata."""
    layer_frames: list[dict[str, Any]] = []
    asset_ext = "png"
    for frame in frames:
        render = frame.get("render", {})
        if render.get("asset"):
            asset_ext = Path(render["asset"]).suffix.lstrip(".") or asset_ext
        layer_frames.append(
            {
                "frame": frame["out_index"],
                "t": frame["t"],
                "visible": bool(frame.get("visible") and render.get("asset")),
                "asset": render.get("asset"),
                "x": render.get("x"),
                "y": render.get("y"),
                "width": render.get("width"),
                "height": render.get("height"),
                "anchor": render.get("anchor"),
                "centroid": frame.get("centroid"),
                "opacity": 1,
                "scale": 1,
                "rotation": 0,
            }
        )

    return {
        "id": f"{object_id}_raster_layer",
        "object_id": object_id,
        "type": "raster_sequence",
        "asset_type": f"cropped_rgba_{asset_ext}_sequence",
        "fps": fps,
        "z_index": 10,
        "blend_mode": "source-over",
        "frames": layer_frames,
        "controls": {
            "editable": ["x", "y", "scale", "rotation", "opacity", "visible", "z_index"],
            "json_edit_example": {
                "translate": [40, -20],
                "scale": 1.12,
                "rotation": 0.08,
                "opacity": 0.92,
            },
        },
    }


def write_spritesheet(
    *,
    cutout_paths: list[Path],
    output_path: Path,
    format: str = "WEBP",
    quality: int = 82,
) -> dict[str, Any] | None:
    """Pack cropped RGBA cutouts into a simple row-major sprite sheet."""
    images = [Image.open(path).convert("RGBA") for path in cutout_paths if path.exists()]
    if not images:
        return None

    max_w = max(image.width for image in images)
    max_h = max(image.height for image in images)
    columns = max(1, int(np.ceil(np.sqrt(len(images)))))
    rows = int(np.ceil(len(images) / columns))
    sheet = Image.new("RGBA", (columns * max_w, rows * max_h), (0, 0, 0, 0))

    frames: list[dict[str, int]] = []
    for index, image in enumerate(images):
        col = index % columns
        row = index // columns
        x = col * max_w
        y = row * max_h
        sheet.alpha_composite(image, (x, y))
        frames.append({"x": x, "y": y, "w": image.width, "h": image.height})

    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_kwargs: dict[str, Any] = {}
    if format.upper() == "WEBP":
        save_kwargs = {"format": "WEBP", "quality": quality, "method": 4}
    else:
        save_kwargs = {"format": format}
    sheet.save(output_path, **save_kwargs)

    return {
        "path": str(output_path),
        "width": sheet.width,
        "height": sheet.height,
        "columns": columns,
        "rows": rows,
        "cellWidth": max_w,
        "cellHeight": max_h,
        "frames": frames,
    }
