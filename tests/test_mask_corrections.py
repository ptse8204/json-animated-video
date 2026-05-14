import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from motionjson.corrections import apply_correction_request, build_correction_request
from motionjson.cli import build_parser, build_correction_request_from_args
from motionjson.masks import ThresholdMaskProvider
from motionjson.pipeline import run_pipeline
from motionjson.validation import validate_document, validate_output_dir


def make_tiny_video(path: Path, frames: int = 4) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 12, (96, 64))
    if not writer.isOpened():
        raise RuntimeError("Could not open tiny test video writer")
    for index in range(frames):
        frame = np.full((64, 96, 3), 245, dtype=np.uint8)
        cv2.circle(frame, (24 + index * 8, 32), 10, (20, 20, 230), -1)
        writer.write(frame)
    writer.release()


def write_source_masks(root: Path, count: int = 3) -> Path:
    mask_dir = root / "masks" / "object_0"
    mask_dir.mkdir(parents=True)
    for index in range(1, count + 1):
        mask = np.zeros((32, 32), dtype=np.uint8)
        if index == 2:
            mask[12:20, 12:20] = 255
        Image.fromarray(mask).save(mask_dir / f"mask_{index:06d}.png")
    return mask_dir


def read_mask(path: Path) -> np.ndarray:
    return np.array(Image.open(path).convert("L"))


def test_deterministic_add_remove_box_and_brush_operations(tmp_path):
    source = tmp_path / "source"
    write_source_masks(source)
    request = build_correction_request(
        object_id="object_0",
        operations=[
            {"type": "add_point", "x": 5, "y": 5, "frame": 1, "radius": 3},
            {"type": "remove_point", "x": 15, "y": 15, "frame": 2, "radius": 5},
            {"type": "box", "x": 2, "y": 2, "w": 8, "h": 6, "frame": 3, "mode": "replace"},
            {"type": "brush", "points": [[20, 20], [24, 24]], "frame": 3, "radius": 2, "mode": "add"},
        ],
    )

    corrected = apply_correction_request(source, request, work_dir=tmp_path / "work")

    frame1 = read_mask(corrected.mask_dir / "mask_000001.png")
    frame2 = read_mask(corrected.mask_dir / "mask_000002.png")
    frame3 = read_mask(corrected.mask_dir / "mask_000003.png")
    assert frame1[5, 5] == 255
    assert frame2[15, 15] == 0
    assert frame3[3, 3] == 255
    assert frame3[24, 24] == 255
    assert corrected.changed_frames == [1, 2, 3]


def test_optional_operation_modes_have_executable_defaults(tmp_path):
    source = tmp_path / "source"
    write_source_masks(source)
    request = build_correction_request(
        object_id="object_0",
        operations=[
            {"type": "box", "x": 14, "y": 14, "w": 3, "h": 3, "frame": 2},
            {"type": "brush", "points": [[4, 4], [6, 6]], "frame": 1, "radius": 1},
        ],
    )

    assert not validate_document(request)
    corrected = apply_correction_request(source, request, work_dir=tmp_path / "work")
    frame1 = read_mask(corrected.mask_dir / "mask_000001.png")
    frame2 = read_mask(corrected.mask_dir / "mask_000002.png")

    assert frame1[4, 4] == 255
    assert frame2[15, 15] == 255
    assert frame2[13, 13] == 0


def test_box_constrain_keeps_only_existing_mask_inside_box(tmp_path):
    source = tmp_path / "source"
    write_source_masks(source)
    request = build_correction_request(
        object_id="object_0",
        operations=[{"type": "box", "x": 14, "y": 14, "w": 3, "h": 3, "frame": 2, "mode": "constrain"}],
    )

    corrected = apply_correction_request(source, request, work_dir=tmp_path / "work")
    frame2 = read_mask(corrected.mask_dir / "mask_000002.png")

    assert frame2[15, 15] == 255
    assert frame2[13, 13] == 0
    assert frame2[18, 18] == 0


def test_box_correction_clips_to_true_frame_intersection(tmp_path):
    source = tmp_path / "source"
    write_source_masks(source)
    outside = build_correction_request(
        object_id="object_0",
        operations=[{"type": "box", "x": -10, "y": -10, "w": 5, "h": 5, "frame": 1, "mode": "replace"}],
    )
    partial = build_correction_request(
        object_id="object_0",
        operations=[{"type": "box", "x": -2, "y": -2, "w": 5, "h": 5, "frame": 1, "mode": "replace"}],
    )

    outside_result = apply_correction_request(source, outside, work_dir=tmp_path / "outside")
    partial_result = apply_correction_request(source, partial, work_dir=tmp_path / "partial")
    outside_mask = read_mask(outside_result.mask_dir / "mask_000001.png")
    partial_mask = read_mask(partial_result.mask_dir / "mask_000001.png")

    assert outside_mask.sum() == 0
    assert partial_mask[:3, :3].sum() == 9 * 255
    assert partial_mask.sum() == 9 * 255


def test_temporal_smoothing_and_propagation_are_local_and_deterministic(tmp_path):
    source = tmp_path / "source"
    write_source_masks(source)
    request = build_correction_request(
        object_id="object_0",
        operations=[{"type": "add_point", "x": 10, "y": 10, "frame": 1, "radius": 2}],
        propagate=True,
        smooth=True,
        smooth_radius=1,
    )

    corrected = apply_correction_request(source, request, work_dir=tmp_path / "work")
    masks = [read_mask(corrected.mask_dir / f"mask_{index:06d}.png") for index in range(1, 4)]

    assert all(mask[10, 10] == 255 for mask in masks)
    assert corrected.changed_frames == [1, 2, 3]
    assert request["aiUsage"] == "none"


def test_centroid_delta_propagation_shifts_operations_with_mask_motion(tmp_path):
    source = tmp_path / "source"
    mask_dir = source / "masks" / "object_0"
    mask_dir.mkdir(parents=True)
    for index, x in enumerate((5, 10, 15), start=1):
        mask = np.zeros((24, 24), dtype=np.uint8)
        mask[5, x] = 255
        Image.fromarray(mask).save(mask_dir / f"mask_{index:06d}.png")

    request = build_correction_request(
        object_id="object_0",
        operations=[{"type": "add_point", "x": 5, "y": 10, "frame": 1, "radius": 1}],
        propagate=True,
        propagation_mode="centroid_delta",
        frame_range=[1, 3],
    )

    corrected = apply_correction_request(source, request, work_dir=tmp_path / "work")
    masks = [read_mask(corrected.mask_dir / f"mask_{index:06d}.png") for index in range(1, 4)]

    assert masks[0][10, 5] == 255
    assert masks[1][10, 10] == 255
    assert masks[2][10, 15] == 255
    assert masks[1][10, 5] == 0


def test_propagation_frame_range_limits_same_coordinate_edits(tmp_path):
    source = tmp_path / "source"
    write_source_masks(source, count=5)
    request = build_correction_request(
        object_id="object_0",
        operations=[{"type": "add_point", "x": 8, "y": 8, "frame": 3, "radius": 1}],
        propagate=True,
        frame_range=[2, 4],
    )

    corrected = apply_correction_request(source, request, work_dir=tmp_path / "work")
    masks = [read_mask(corrected.mask_dir / f"mask_{index:06d}.png") for index in range(1, 6)]

    assert masks[0][8, 8] == 0
    assert masks[1][8, 8] == 255
    assert masks[2][8, 8] == 255
    assert masks[3][8, 8] == 255
    assert masks[4][8, 8] == 0


def test_temporal_smoothing_preserves_explicit_frame_edits(tmp_path):
    source = tmp_path / "source"
    write_source_masks(source)
    request = build_correction_request(
        object_id="object_0",
        operations=[{"type": "add_point", "x": 10, "y": 10, "frame": 1, "radius": 2}],
        smooth=True,
        smooth_radius=1,
    )

    corrected = apply_correction_request(source, request, work_dir=tmp_path / "work")
    frame1 = read_mask(corrected.mask_dir / "mask_000001.png")
    frame2 = read_mask(corrected.mask_dir / "mask_000002.png")

    assert frame1[10, 10] == 255
    assert frame2[10, 10] == 0


def test_correct_cli_regenerates_manifests_quality_and_validates(tmp_path):
    video = tmp_path / "tiny.mp4"
    out = tmp_path / "out"
    corrected = tmp_path / "out_corrected"
    make_tiny_video(video)
    run_pipeline(
        video_path=video,
        out_dir=out,
        mask_provider=ThresholdMaskProvider((0, 80, 80), (12, 255, 255)),
        sample_fps=12,
        max_frames=3,
    )
    request = build_correction_request(
        object_id="object_0",
        operations=[{"type": "box", "x": 12, "y": 18, "w": 30, "h": 24, "frame": 1, "mode": "replace"}],
        smooth=True,
    )
    request_path = tmp_path / "correction_request.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "motionjson.cli",
            "correct",
            str(out),
            "--out",
            str(corrected),
            "--request",
            str(request_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (corrected / "correction_manifest.json").exists()
    assert (corrected / "correction_request.json").exists()
    manifest = json.loads((corrected / "correction_manifest.json").read_text(encoding="utf-8"))
    scene = json.loads((corrected / "scene_graph.json").read_text(encoding="utf-8"))
    web = json.loads((corrected / "web_asset_manifest.json").read_text(encoding="utf-8"))
    assert manifest["aiUsage"] == "none"
    assert manifest["providerPolicy"] == "deterministic_local_correction_only"
    assert manifest["quality"] == scene["objects"][0]["quality"] == web["quality"]
    assert manifest["recommendedOutput"] == scene["objects"][0]["recommendedOutput"]
    validation = validate_output_dir(corrected)
    assert validation.ok, [issue.format() for issue in validation.issues]


def test_correction_code_does_not_call_network_or_openrouter():
    source = (Path(__file__).resolve().parents[1] / "src" / "motionjson" / "corrections.py").read_text(encoding="utf-8").lower()

    assert "openrouter" not in source
    assert "requests" not in source
    assert "urllib" not in source
    assert "http://" not in source
    assert "https://" not in source


def test_correction_request_schema_rejects_incomplete_or_mismatched_operations():
    incomplete = build_correction_request(object_id="object_0", operations=[{"type": "add_point", "frame": 1}])
    wrong_mode = build_correction_request(
        object_id="object_0",
        operations=[{"type": "brush", "frame": 1, "points": [[1, 2]], "mode": "replace"}],
    )

    assert validate_document(incomplete)
    assert validate_document(wrong_mode)


def test_cli_rejects_invalid_correction_request_before_regeneration(tmp_path):
    request = build_correction_request(object_id="object_0", operations=[{"type": "add_point", "frame": 1}])
    path = tmp_path / "bad_request.json"
    path.write_text(json.dumps(request), encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(["correct", str(tmp_path / "out"), "--request", str(path)])

    try:
        build_correction_request_from_args(args)
    except SystemExit as exc:
        assert "Invalid correction request" in str(exc)
    else:
        raise AssertionError("invalid correction request should fail before regeneration")


def test_cli_reports_malformed_correction_request_json(tmp_path):
    path = tmp_path / "bad_request.json"
    path.write_text("{not json", encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(["correct", str(tmp_path / "out"), "--request", str(path)])

    try:
        build_correction_request_from_args(args)
    except SystemExit as exc:
        assert "Invalid correction request JSON" in str(exc)
    else:
        raise AssertionError("malformed correction JSON should fail cleanly")
