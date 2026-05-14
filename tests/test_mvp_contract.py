from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from motionjson.masks import ExternalMaskProvider, ThresholdMaskProvider
from motionjson.pipeline import ObjectExtractionSpec, run_multi_object_pipeline, run_pipeline
from motionjson.validation import validate_output_dir
from motionjson.vectorize import build_quality_scores
from motionjson.video import VideoInfo


def make_tiny_video(path: Path, frames: int = 6) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 12, (96, 64))
    if not writer.isOpened():
        raise RuntimeError("Could not open tiny test video writer")
    for index in range(frames):
        frame = np.full((64, 96, 3), 245, dtype=np.uint8)
        cv2.circle(frame, (20 + index * 8, 32), 10, (20, 20, 230), -1)
        writer.write(frame)
    writer.release()


def test_threshold_provider_returns_binary_mask():
    provider = ThresholdMaskProvider((0, 80, 80), (12, 255, 255))
    provider.prepare(VideoInfo(width=96, height=64, source_fps=12, sample_fps=12, total_source_frames=1))
    frame = np.full((64, 96, 3), 245, dtype=np.uint8)
    cv2.circle(frame, (40, 32), 10, (20, 20, 230), -1)

    mask = provider.get_mask(0, frame)

    assert set(np.unique(mask)).issubset({0, 255})
    assert mask.sum() > 0


def test_external_mask_provider_loads_masks(tmp_path):
    mask_dir = tmp_path / "masks"
    mask_dir.mkdir()
    Image.fromarray(np.full((8, 10), 255, dtype=np.uint8)).save(mask_dir / "mask_000001.png")
    provider = ExternalMaskProvider(mask_dir)
    provider.prepare(VideoInfo(width=10, height=8, source_fps=12, sample_fps=12, total_source_frames=1))

    mask = provider.get_mask(0, np.zeros((8, 10, 3), dtype=np.uint8))

    assert mask.shape == (8, 10)
    assert mask.max() == 255


def test_vector_suitability_is_bounded():
    quality = build_quality_scores(
        [
            {"visible": True, "bbox": [0, 0, 10, 10], "area": 100, "contour_points": 24, "polygon": [[0, 0], [10, 0], [10, 10]]},
            {"visible": True, "bbox": [1, 0, 10, 10], "area": 102, "contour_points": 26, "polygon": [[1, 0], [11, 0], [11, 10]]},
        ]
    )

    assert 0 <= quality["vectorSuitability"] <= 1
    assert 0 <= quality["maskStability"] <= 1


def test_pipeline_writes_mvp_schema_and_profile(tmp_path):
    video = tmp_path / "tiny.mp4"
    out = tmp_path / "out"
    make_tiny_video(video)

    scene = run_pipeline(
        video_path=video,
        out_dir=out,
        mask_provider=ThresholdMaskProvider((0, 80, 80), (12, 255, 255)),
        sample_fps=6,
        max_frames=3,
    )

    assert scene["schema"] == "motionjson.scene_graph.v0.1"
    obj = scene["objects"][0]
    assert obj["renderMode"] == "raster_alpha_sequence"
    assert obj["motion"][0]["asset"].startswith("objects/object_0/cutouts/")
    assert "vectorSuitability" in obj["quality"]
    assert (out / "resource_profile.json").exists()
    assert (out / "web_asset_manifest.json").exists()
    assert (out / "objects" / "object_0" / "object_manifest.json").exists()
    assert (out / "preview" / "canvas_player.html").exists()
    assert (out / "preview" / "pixi_player.html").exists()
    assert (out / "preview" / "plain_js_embed.html").exists()
    assert (out / "preview" / "website_graphics_hero.html").exists()
    assert (out / "preview" / "runtime" / "index.js").exists()
    assert (out / "preview" / "object_selection_workflow.html").exists()
    assert (out / "preview" / "object_selection_workflow.js").exists()
    assert (out / "preview" / "timeline_editor.html").exists()
    assert (out / "preview" / "timeline_editor.js").exists()


def test_multi_object_pipeline_writes_independent_layers_and_legacy_aliases(tmp_path):
    video = tmp_path / "tiny.mp4"
    out = tmp_path / "out"
    make_tiny_video(video, frames=4)
    ball_masks = tmp_path / "ball_masks"
    shadow_masks = tmp_path / "shadow_masks"
    ball_masks.mkdir()
    shadow_masks.mkdir()
    for index in range(4):
        ball = np.zeros((64, 96), dtype=np.uint8)
        shadow = np.zeros((64, 96), dtype=np.uint8)
        cv2.circle(ball, (20 + index * 8, 32), 10, 255, -1)
        cv2.rectangle(shadow, (56, 42), (78, 52), 255, -1)
        Image.fromarray(ball).save(ball_masks / f"mask_{index + 1:06d}.png")
        Image.fromarray(shadow).save(shadow_masks / f"mask_{index + 1:06d}.png")

    scene = run_multi_object_pipeline(
        video_path=video,
        out_dir=out,
        object_specs=[
            ObjectExtractionSpec("ball", "Ball", ExternalMaskProvider(ball_masks), z_index=10),
            ObjectExtractionSpec("shadow", "Shadow", ExternalMaskProvider(shadow_masks), z_index=20),
        ],
        sample_fps=12,
        max_frames=3,
    )

    assert [obj["id"] for obj in scene["objects"]] == ["ball", "shadow"]
    assert [layer["object_id"] for layer in scene["layers"]] == ["ball", "shadow"]
    assert scene["layers"][1]["z_index"] == 20
    assert (out / "object_motion.json").exists()
    assert (out / "web_asset_manifest.json").exists()
    for object_id in ("ball", "shadow"):
        assert (out / "objects" / object_id / "object_manifest.json").exists()
        assert (out / "objects" / object_id / "object_motion.json").exists()
        web_manifest = (out / "objects" / object_id / "web_asset_manifest.json").read_text(encoding="utf-8")
        assert "../../scene_graph.json" in web_manifest
        assert f"../../objects/{object_id}/cutouts/" in web_manifest
    result = validate_output_dir(out, object_id="ball")
    assert result.ok, [issue.format() for issue in result.issues]


def test_multi_object_pipeline_rejects_unsafe_object_ids(tmp_path):
    video = tmp_path / "tiny.mp4"
    out = tmp_path / "out"
    make_tiny_video(video, frames=1)
    masks = tmp_path / "masks"
    masks.mkdir()
    Image.fromarray(np.full((64, 96), 255, dtype=np.uint8)).save(masks / "mask_000001.png")

    try:
        run_multi_object_pipeline(
            video_path=video,
            out_dir=out,
            object_specs=[
                ObjectExtractionSpec("../escape", "Escape", ExternalMaskProvider(masks)),
            ],
            sample_fps=12,
            max_frames=1,
        )
    except ValueError as exc:
        assert "safe path segments" in str(exc)
    else:
        raise AssertionError("unsafe object id was accepted")
