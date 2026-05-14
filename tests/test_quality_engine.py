import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from motionjson.masks import ExternalMaskProvider
from motionjson.pipeline import run_pipeline
from motionjson.validation import validate_output_dir
from motionjson.vectorize import build_quality_scores, recommended_output


QUALITY_SCORE_KEYS = {
    "maskStability",
    "edgeComplexity",
    "bboxStability",
    "maskDriftScore",
    "edgeQualityScore",
    "missingFrameScore",
    "occlusionRiskScore",
    "vectorSuitability",
    "productionReadinessScore",
    "visibleFrameRatio",
    "missingFrameRatio",
}

QUALITY_REQUIRED_KEYS = QUALITY_SCORE_KEYS | {
    "longestMissingFrameRun",
    "productionReadiness",
    "routingReasons",
}


def make_tiny_video(path: Path, frames: int = 4) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 12, (96, 64))
    if not writer.isOpened():
        raise RuntimeError("Could not open tiny test video writer")
    for index in range(frames):
        frame = np.full((64, 96, 3), 245, dtype=np.uint8)
        cv2.circle(frame, (24 + index * 8, 32), 10, (20, 20, 230), -1)
        writer.write(frame)
    writer.release()


def stable_metadata_frames() -> list[dict[str, object]]:
    frames = []
    for index in range(4):
        x = index * 4
        frames.append(
            {
                "visible": True,
                "bbox": [x, 10, 20, 20],
                "area": 400,
                "centroid": [x + 10, 20],
                "contour_points": 24,
                "polygon": [[x, 10], [x + 20, 10], [x + 20, 30], [x, 30]],
            }
        )
    return frames


def test_quality_scores_are_deterministic_bounded_and_rounded():
    quality = build_quality_scores(stable_metadata_frames())

    assert quality == build_quality_scores(stable_metadata_frames())
    assert QUALITY_REQUIRED_KEYS.issubset(quality)
    for key in QUALITY_SCORE_KEYS:
        assert 0 <= quality[key] <= 1
        assert quality[key] == round(quality[key], 4)
    assert quality["maskDriftScore"] == 1
    assert quality["missingFrameScore"] == 1
    assert quality["productionReadiness"] == "ready"
    assert recommended_output(quality) == "hybrid_vector_silhouette_plus_raster"


def test_missing_frames_force_raster_route_and_correction_readiness():
    frames = stable_metadata_frames()
    frames[1] = {
        "visible": False,
        "bbox": None,
        "area": 0,
        "centroid": None,
        "contour_points": 0,
        "polygon": [],
    }
    frames[2] = {
        "visible": False,
        "bbox": None,
        "area": 0,
        "centroid": None,
        "contour_points": 0,
        "polygon": [],
    }

    quality = build_quality_scores(frames)

    assert quality["missingFrameScore"] == 0.5
    assert quality["missingFrameRatio"] == 0.5
    assert quality["longestMissingFrameRun"] == 2
    assert quality["productionReadiness"] == "needs_correction"
    assert recommended_output(quality) == "raster_alpha_sequence"
    assert "missing_frame_risk_requires_raster_alpha" in quality["routingReasons"]


def test_quality_propagates_to_all_core_manifests_and_allows_null_centroid(tmp_path):
    video = tmp_path / "tiny.mp4"
    out = tmp_path / "out"
    mask_dir = tmp_path / "masks"
    mask_dir.mkdir()
    make_tiny_video(video, frames=3)

    for index, cx in enumerate((24, None, 40), start=1):
        mask = np.zeros((64, 96), dtype=np.uint8)
        if cx is not None:
            cv2.circle(mask, (cx, 32), 10, 255, -1)
        Image.fromarray(mask).save(mask_dir / f"mask_{index:06d}.png")

    scene = run_pipeline(
        video_path=video,
        out_dir=out,
        mask_provider=ExternalMaskProvider(mask_dir),
        sample_fps=12,
        max_frames=3,
    )

    quality = scene["objects"][0]["quality"]
    object_motion = json.loads((out / "object_motion.json").read_text(encoding="utf-8"))
    object_manifest = json.loads((out / "objects" / "object_0" / "object_manifest.json").read_text(encoding="utf-8"))
    web_manifest = json.loads((out / "web_asset_manifest.json").read_text(encoding="utf-8"))

    assert scene["objects"][0]["motion"][1]["centroid"] is None
    assert scene["objects"][0]["frames"][1]["centroid"] is None
    assert quality == object_motion["quality"] == object_manifest["quality"] == web_manifest["quality"]
    assert quality["missingFrameScore"] == 0.6667
    assert scene["objects"][0]["recommendedOutput"] == "raster_alpha_sequence"
    assert object_motion["recommendedOutput"] == "raster_alpha_sequence"
    assert object_manifest["recommendedOutput"] == "raster_alpha_sequence"

    result = validate_output_dir(out)
    assert result.ok, [issue.format() for issue in result.issues]
