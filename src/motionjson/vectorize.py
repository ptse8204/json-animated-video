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


def _score(value: float) -> float:
    return round(_clamp01(value), 4)


def _is_visible_frame(frame: dict[str, Any]) -> bool:
    bbox = frame.get("bbox")
    return bool(frame.get("visible") and bbox and float(frame.get("area") or 0) > 0)


def _valid_centroid(frame: dict[str, Any]) -> list[float] | None:
    centroid = frame.get("centroid")
    if not isinstance(centroid, list | tuple) or len(centroid) != 2:
        return None
    try:
        return [float(centroid[0]), float(centroid[1])]
    except (TypeError, ValueError):
        return None


def _coefficient_of_variation(values: np.ndarray) -> float:
    if values.size == 0:
        return 1.0
    mean = float(np.mean(values))
    if mean <= 0:
        return 1.0
    return float(np.std(values) / mean)


def _adjacent_relative_change(values: np.ndarray) -> float:
    if values.size < 2:
        return 0.0
    previous = np.maximum(values[:-1], 1.0)
    return float(np.mean(np.abs(np.diff(values)) / previous))


def _longest_false_run(flags: list[bool]) -> int:
    longest = 0
    current = 0
    for flag in flags:
        if flag:
            current = 0
            continue
        current += 1
        longest = max(longest, current)
    return longest


def _centroid_jitter(centroids: list[list[float]], bboxes: np.ndarray) -> float:
    if len(centroids) < 3 or bboxes.size == 0:
        return 0.0
    points = np.array(centroids, dtype=float)
    velocities = np.diff(points, axis=0)
    accelerations = np.diff(velocities, axis=0)
    wh = np.maximum(bboxes[:, 2:4], 1.0)
    diag = float(np.mean(np.sqrt((wh[:, 0] ** 2) + (wh[:, 1] ** 2)))) or 1.0
    return float(np.mean(np.linalg.norm(accelerations, axis=1)) / diag)


def _readiness_label(score: float, *, missing_ratio: float, longest_missing_run: int, occlusion_risk: float) -> str:
    if missing_ratio >= 0.4 or longest_missing_run >= 4 or occlusion_risk >= 0.75:
        return "needs_correction"
    if score >= 0.82 and missing_ratio <= 0.05 and occlusion_risk <= 0.25:
        return "ready"
    if score >= 0.55:
        return "review"
    return "needs_correction"


def _routing_reasons(quality: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if quality["vectorSuitability"] < 0.82:
        reasons.append("vector_suitability_below_hybrid_threshold")
    if quality["productionReadinessScore"] < 0.82:
        reasons.append("production_readiness_below_ready_threshold")
    if quality["missingFrameRatio"] > 0.05:
        reasons.append("missing_frame_risk_requires_raster_alpha")
    if quality["occlusionRiskScore"] > 0.25:
        reasons.append("occlusion_risk_requires_raster_alpha")
    if quality["edgeQualityScore"] < 0.75:
        reasons.append("edge_quality_below_vector_threshold")
    if quality["maskDriftScore"] < 0.75:
        reasons.append("mask_drift_score_below_hybrid_threshold")
    if not reasons:
        reasons.append("hybrid_vector_silhouette_route_allowed_for_simple_stable_object")
    return reasons


def build_quality_scores(frames: list[dict[str, Any]]) -> dict[str, Any]:
    """Score extraction quality from generated metadata only.

    Scores are deterministic, bounded to 0..1, and rounded. Most scores are
    high-is-good quality scores; occlusionRiskScore is a high-is-risk exception.
    """
    total_frames = len(frames)
    visible_flags = [_is_visible_frame(frame) for frame in frames]
    visible = [frame for frame, is_visible in zip(frames, visible_flags) if is_visible]
    visible_count = len(visible)
    missing_count = total_frames - visible_count
    visible_frame_ratio = (visible_count / total_frames) if total_frames else 0.0
    missing_frame_ratio = (missing_count / total_frames) if total_frames else 1.0
    longest_missing_run = _longest_false_run(visible_flags)

    if not visible:
        quality: dict[str, Any] = {
            "maskStability": 0.0,
            "edgeComplexity": 1.0,
            "bboxStability": 0.0,
            "maskDriftScore": 0.0,
            "edgeQualityScore": 0.0,
            "missingFrameScore": 0.0,
            "occlusionRiskScore": 1.0,
            "vectorSuitability": 0.0,
            "productionReadinessScore": 0.0,
            "visibleFrameRatio": _score(visible_frame_ratio),
            "missingFrameRatio": _score(missing_frame_ratio),
            "longestMissingFrameRun": longest_missing_run,
            "productionReadiness": "needs_correction",
        }
        quality["routingReasons"] = _routing_reasons(quality)
        return quality

    areas = np.array([float(frame.get("area") or 0) for frame in visible], dtype=float)
    contour_points = np.array(
        [float(frame.get("contour_points") or len(frame.get("polygon") or [])) for frame in visible],
        dtype=float,
    )
    polygon_point_counts = np.array([float(len(frame.get("polygon") or [])) for frame in visible], dtype=float)
    bboxes = np.array([frame["bbox"] for frame in visible], dtype=float)
    wh = np.maximum(bboxes[:, 2:4], 1.0)

    area_cv = _coefficient_of_variation(areas)
    area_change = _adjacent_relative_change(areas)
    bbox_size_cv = float(np.mean(np.std(wh, axis=0) / np.maximum(np.mean(wh, axis=0), 1.0)))
    bbox_stability = _score(1.0 - bbox_size_cv)

    centroids = [centroid for frame in visible if (centroid := _valid_centroid(frame)) is not None]
    centroid_jitter = _centroid_jitter(centroids, bboxes) if len(centroids) == visible_count else 0.25

    size_change = float(np.mean([_adjacent_relative_change(wh[:, 0]), _adjacent_relative_change(wh[:, 1])]))
    mask_drift_risk = _score((area_change * 0.45) + (size_change * 0.25) + (centroid_jitter * 0.30))
    mask_drift_score = _score(1.0 - mask_drift_risk)
    mask_stability = _score(((1.0 - area_cv) * 0.50) + (bbox_stability * 0.25) + (mask_drift_score * 0.25))

    mean_edge_points = float(np.mean(contour_points))
    edge_complexity = _score(mean_edge_points / 240.0)
    polygon_presence = float(np.mean(polygon_point_counts >= 3))
    contour_cv = _coefficient_of_variation(contour_points)
    edge_quality_score = _score(((1.0 - edge_complexity) * 0.65) + (polygon_presence * 0.25) + ((1.0 - contour_cv) * 0.10))

    median_area = float(np.median(areas)) or 1.0
    area_dip = _clamp01(1.0 - (float(np.min(areas)) / median_area))
    longest_missing_ratio = (longest_missing_run / total_frames) if total_frames else 1.0
    missing_frame_score = _score(1.0 - ((missing_frame_ratio * 0.75) + (longest_missing_ratio * 0.25)))
    occlusion_risk_score = _score(
        (missing_frame_ratio * 0.45)
        + (longest_missing_ratio * 0.20)
        + (area_dip * 0.20)
        + (_clamp01(area_cv) * 0.10)
        + (_clamp01(centroid_jitter) * 0.05)
    )

    vector_suitability = _score(
        (mask_stability * 0.24)
        + (edge_quality_score * 0.34)
        + (bbox_stability * 0.14)
        + (mask_drift_score * 0.10)
        + (visible_frame_ratio * 0.10)
        + ((1.0 - occlusion_risk_score) * 0.08)
    )
    production_readiness_score = _score(
        (mask_stability * 0.25)
        + (edge_quality_score * 0.20)
        + (bbox_stability * 0.15)
        + (missing_frame_score * 0.20)
        + ((1.0 - occlusion_risk_score) * 0.20)
    )

    if missing_frame_ratio >= 0.4 or longest_missing_run >= 4 or occlusion_risk_score >= 0.75:
        production_readiness_score = min(production_readiness_score, 0.39)
    elif missing_frame_ratio >= 0.15 or longest_missing_run >= 2 or occlusion_risk_score >= 0.45:
        production_readiness_score = min(production_readiness_score, 0.69)

    quality = {
        "maskStability": mask_stability,
        "edgeComplexity": edge_complexity,
        "bboxStability": bbox_stability,
        "maskDriftScore": mask_drift_score,
        "edgeQualityScore": edge_quality_score,
        "missingFrameScore": missing_frame_score,
        "occlusionRiskScore": occlusion_risk_score,
        "vectorSuitability": vector_suitability,
        "productionReadinessScore": production_readiness_score,
        "visibleFrameRatio": _score(visible_frame_ratio),
        "missingFrameRatio": _score(missing_frame_ratio),
        "longestMissingFrameRun": longest_missing_run,
        "productionReadiness": _readiness_label(
            production_readiness_score,
            missing_ratio=missing_frame_ratio,
            longest_missing_run=longest_missing_run,
            occlusion_risk=occlusion_risk_score,
        ),
    }
    quality["routingReasons"] = _routing_reasons(quality)
    return quality


def recommended_output(quality: dict[str, Any], *, threshold: float = 0.82) -> str:
    if (
        quality.get("vectorSuitability", 0.0) >= threshold
        and quality.get("productionReadinessScore", 0.0) >= 0.82
        and quality.get("productionReadiness") == "ready"
        and quality.get("missingFrameScore", 0.0) >= 0.95
        and quality.get("occlusionRiskScore", 1.0) <= 0.25
        and quality.get("edgeQualityScore", 0.0) >= 0.75
        and quality.get("maskDriftScore", 0.0) >= 0.75
    ):
        return "hybrid_vector_silhouette_plus_raster"
    return "raster_alpha_sequence"
