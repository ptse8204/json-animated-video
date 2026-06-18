from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

from motionjson.cli import main
from motionjson.mask_fitness import validate_mask_fitness


def demo_video() -> Path:
    return Path(__file__).resolve().parents[1] / "examples" / "demo_red_ball.mp4"


def test_mask_fitness_accepts_threshold_output(tmp_path, capsys):
    out = tmp_path / "out"

    main(["extract", str(demo_video()), "--out", str(out), "--mask-provider", "threshold", "--max-frames", "2"])

    report = validate_mask_fitness(out)
    assert report["ok"]
    assert report["checkedVisibleFrames"] > 0
    capsys.readouterr()
    main(["mask-fitness", str(out)])
    assert json.loads(capsys.readouterr().out)["ok"]


def test_mask_fitness_flags_empty_visible_cutout_alpha(tmp_path):
    out = tmp_path / "out"
    main(["extract", str(demo_video()), "--out", str(out), "--mask-provider", "threshold", "--max-frames", "1"])
    scene = json.loads((out / "scene_graph.json").read_text(encoding="utf-8"))
    frame = next(item for obj in scene["objects"] for item in obj["motion"] if item["visible"])
    cutout_path = out / frame["asset"]

    cutout = Image.open(cutout_path).convert("RGBA")
    cutout.putalpha(0)
    cutout.save(cutout_path)

    report = validate_mask_fitness(out)
    assert not report["ok"]
    assert any("cutout alpha is empty" in issue for issue in report["issues"])


def test_mask_fitness_accepts_multi_object_external_masks(tmp_path):
    out = tmp_path / "external"
    red_masks = tmp_path / "red_masks"
    blue_masks = tmp_path / "blue_masks"
    red_masks.mkdir()
    blue_masks.mkdir()
    for index in range(2):
        red = Image.new("L", (640, 360), 0)
        blue = Image.new("L", (640, 360), 0)
        ImageDraw.Draw(red).rectangle((250 + index * 4, 150, 310 + index * 4, 210), fill=255)
        ImageDraw.Draw(blue).rectangle((90, 80 + index * 3, 130, 130 + index * 3), fill=255)
        red.save(red_masks / f"mask_{index:06d}.png")
        blue.save(blue_masks / f"mask_{index:06d}.png")

    main(
        [
            "extract",
            str(demo_video()),
            "--out",
            str(out),
            "--object-mask-dir",
            f"red={red_masks}",
            "--object-mask-dir",
            f"blue={blue_masks}",
            "--object-label",
            "red=Red object",
            "--object-label",
            "blue=Blue object",
            "--max-frames",
            "2",
            "--min-area",
            "1",
        ]
    )

    report = validate_mask_fitness(out)
    assert report["ok"]
    assert report["checkedVisibleFrames"] == 4
