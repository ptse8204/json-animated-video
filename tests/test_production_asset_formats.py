from pathlib import Path
import shutil

import cv2
import numpy as np

from motionjson.masks import ThresholdMaskProvider
from motionjson.pipeline import run_pipeline
from motionjson.validation import validate_output_dir


def profile_payload_sizes(out: Path) -> dict[str, int]:
    production_dir = out / "objects" / "object_0" / "production"
    return {
        "scene_graph_json_bytes": (out / "scene_graph.json").stat().st_size,
        "object_motion_json_bytes": (out / "object_motion.json").stat().st_size,
        "object_manifest_json_bytes": (out / "objects" / "object_0" / "object_manifest.json").stat().st_size,
        "web_asset_manifest_json_bytes": (out / "web_asset_manifest.json").stat().st_size,
        "silhouette_lottie_json_bytes": (out / "silhouette_lottie.json").stat().st_size,
        "sampled_frame_debug_png_bytes": sum(path.stat().st_size for path in (out / "frames").glob("*.png")),
        "mask_sequence_bytes": sum(path.stat().st_size for path in (out / "masks" / "object_0").glob("*.png")),
        "cutout_sequence_png_bytes": sum(path.stat().st_size for path in (out / "objects" / "object_0" / "cutouts").glob("*.png")),
        "spritesheet_bytes": (out / "objects" / "object_0" / "spritesheet.webp").stat().st_size,
        "production_webp_sprite_atlas_bytes": (production_dir / "sprite_atlas.webp").stat().st_size if (production_dir / "sprite_atlas.webp").exists() else 0,
        "production_avif_sprite_atlas_bytes": (production_dir / "sprite_atlas.avif").stat().st_size if (production_dir / "sprite_atlas.avif").exists() else 0,
        "production_transparent_webm_bytes": (production_dir / "transparent_layer.webm").stat().st_size if (production_dir / "transparent_layer.webm").exists() else 0,
        "production_asset_bytes": sum(path.stat().st_size for path in production_dir.glob("*")) if production_dir.exists() else 0,
        "preview_html_bytes": sum(path.stat().st_size for path in (out / "preview").rglob("*") if path.is_file()),
        "benchmark_report_json_bytes": (out / "benchmark_report.json").stat().st_size if (out / "benchmark_report.json").exists() else 0,
    }


def assert_profile_payloads_match_files(profile_payloads: dict[str, int], actual_payloads: dict[str, int]) -> None:
    for key, expected in actual_payloads.items():
        if key in {"scene_graph_json_bytes", "web_asset_manifest_json_bytes"}:
            # These JSON files include profile-derived JSON byte counts, so they can
            # settle into a tiny self-referential oscillation as digit widths change.
            assert abs(profile_payloads[key] - expected) <= 4
        else:
            assert profile_payloads[key] == expected


def make_tiny_video(path: Path, frames: int = 4) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 12, (96, 64))
    if not writer.isOpened():
        raise RuntimeError("Could not open tiny test video writer")
    for index in range(frames):
        frame = np.full((64, 96, 3), 245, dtype=np.uint8)
        cv2.circle(frame, (24 + index * 8, 32), 10, (20, 20, 230), -1)
        writer.write(frame)
    writer.release()


def test_production_mode_exports_cached_asset_formats_and_validates(tmp_path):
    video = tmp_path / "tiny.mp4"
    out = tmp_path / "out"
    make_tiny_video(video)

    scene = run_pipeline(
        video_path=video,
        out_dir=out,
        mask_provider=ThresholdMaskProvider((0, 80, 80), (12, 255, 255)),
        sample_fps=12,
        max_frames=3,
        output_mode="both",
        production_avif=True,
    )

    production = scene["objects"][0]["assets"]["production"]
    assert production["aiUsage"] == "none"
    assert production["source"] == "cached_cutout_pngs_and_motion_json"

    webp = production["assets"]["webpSpriteAtlas"]
    assert webp["status"] == "ready"
    assert webp["path"].endswith("production/sprite_atlas.webp")
    assert (out / webp["path"]).stat().st_size > 0
    assert len(webp["frames"]) == 3

    avif = production["assets"]["avifSpriteAtlas"]
    assert avif["status"] in {"ready", "unsupported", "error"}
    if avif["status"] == "ready":
        assert avif["path"].endswith("production/sprite_atlas.avif")
        assert (out / avif["path"]).stat().st_size > 0
    else:
        assert avif["reason"]

    webm = production["assets"]["transparentWebm"]
    assert webm["aiUsage"] == "none"
    assert webm["cachedSource"] == "cached_rgba_cutout_png_sequence"
    if shutil.which("ffmpeg"):
        assert webm["status"] == "ready"
        assert webm["path"].endswith("production/transparent_layer.webm")
        assert (out / webm["path"]).stat().st_size > 0
    else:
        assert webm["status"] == "unavailable"
        assert "ffmpeg" in webm["reason"]

    profile = scene["resource_profile"]
    assert profile["productionAssets"]["assets"]["webpSpriteAtlas"]["status"] == "ready"
    assert profile["resourceComparison"]["productionPackageBytes"] > 0
    assert profile["sizes"]["payloads"]["production_webp_sprite_atlas_bytes"] > 0
    assert_profile_payloads_match_files(profile["sizes"]["payloads"], profile_payload_sizes(out))

    result = validate_output_dir(out)
    assert result.ok, [issue.format() for issue in result.issues]


def test_authoring_mode_does_not_emit_production_assets(tmp_path):
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

    assert "production" not in scene["objects"][0]["assets"]
    assert not (out / "objects" / "object_0" / "production").exists()
    assert scene["resource_profile"]["productionAssets"] is None

    result = validate_output_dir(out)
    assert result.ok, [issue.format() for issue in result.issues]
