from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np


@dataclass(frozen=True)
class ContourResult:
    visible: bool
    polygon: list[list[float]]
    bbox: list[int] | None
    centroid: list[float] | None
    area: float
    contour_points: int = 0


def mask_to_largest_polygon(mask: np.ndarray, min_area: float = 100.0, simplify_ratio: float = 0.006) -> ContourResult:
    """Extract the largest external contour from a mask and simplify it."""
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return ContourResult(False, [], None, None, 0.0, 0)

    contour = max(contours, key=cv2.contourArea)
    area = float(cv2.contourArea(contour))
    if area < min_area:
        return ContourResult(False, [], None, None, area, int(len(contour)))

    perimeter = float(cv2.arcLength(contour, True))
    epsilon = max(1.0, simplify_ratio * perimeter)
    approx = cv2.approxPolyDP(contour, epsilon, True)
    points = approx.reshape(-1, 2).astype(float)

    x, y, w, h = cv2.boundingRect(approx)
    m = cv2.moments(approx)
    if m["m00"] != 0:
        cx = float(m["m10"] / m["m00"])
        cy = float(m["m01"] / m["m00"])
    else:
        cx = float(x + w / 2)
        cy = float(y + h / 2)

    return ContourResult(
        visible=True,
        polygon=points.tolist(),
        bbox=[int(x), int(y), int(w), int(h)],
        centroid=[cx, cy],
        area=area,
        contour_points=int(len(contour)),
    )


def rgba_cutout(rgb: np.ndarray, mask: np.ndarray, feather: int = 0) -> np.ndarray:
    """Combine an RGB frame and mask into an RGBA cutout."""
    alpha = mask.copy()
    if feather > 0:
        k = max(3, int(feather) | 1)
        alpha = cv2.GaussianBlur(alpha, (k, k), 0)
    return np.dstack([rgb, alpha]).astype(np.uint8)


def polygon_to_lottie_shape(polygon: list[list[float]]) -> dict[str, Any]:
    """Convert a polygon to a Lottie shape path with straight-line tangents."""
    vertices = [[round(float(x), 3), round(float(y), 3)] for x, y in polygon]
    tangents = [[0, 0] for _ in vertices]
    return {"i": tangents, "o": tangents, "v": vertices, "c": True}


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def build_quality_scores(frames: list[dict[str, Any]]) -> dict[str, float]:
    """Estimate mask stability and whether vector export is likely useful.

    This is a conservative MVP heuristic. It favors raster output unless masks
    have stable area and simple outlines.
    """
    visible = [frame for frame in frames if frame.get("visible") and frame.get("bbox")]
    if not visible:
        return {"maskStability": 0.0, "edgeComplexity": 1.0, "bboxStability": 0.0, "vectorSuitability": 0.0}

    areas = np.array([float(frame.get("area") or 0) for frame in visible], dtype=float)
    contour_points = np.array([float(frame.get("contour_points") or len(frame.get("polygon") or [])) for frame in visible], dtype=float)
    bboxes = np.array([frame["bbox"] for frame in visible], dtype=float)

    mean_area = float(np.mean(areas)) or 1.0
    area_cv = float(np.std(areas) / mean_area)
    mask_stability = _clamp01(1.0 - area_cv)

    mean_edge_points = float(np.mean(contour_points))
    edge_complexity = _clamp01(mean_edge_points / 240.0)

    wh = np.maximum(bboxes[:, 2:4], 1)
    size_cv = float(np.mean(np.std(wh, axis=0) / np.maximum(np.mean(wh, axis=0), 1)))
    bbox_stability = _clamp01(1.0 - size_cv)

    vector_suitability = _clamp01((mask_stability * 0.45) + ((1.0 - edge_complexity) * 0.4) + (bbox_stability * 0.15))
    return {
        "maskStability": round(mask_stability, 4),
        "edgeComplexity": round(edge_complexity, 4),
        "bboxStability": round(bbox_stability, 4),
        "vectorSuitability": round(vector_suitability, 4),
    }


def recommended_output(quality: dict[str, float], *, threshold: float = 0.72) -> str:
    if quality.get("vectorSuitability", 0.0) >= threshold:
        return "hybrid_vector_silhouette_plus_raster"
    return "raster_alpha_sequence"
