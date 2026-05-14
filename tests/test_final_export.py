import json
import shutil
import zipfile
from pathlib import Path

import cv2
import numpy as np
import pytest

from motionjson.cli import main
from motionjson.exporters.final_render import export_mp4, write_final_export_manifest
from motionjson.exporters.remotion import write_remotion_plan
from motionjson.exporters.website_package import export_website_package
from motionjson.masks import ThresholdMaskProvider
from motionjson.pipeline import run_pipeline
from motionjson.validation import validate_document, validate_output_dir


def make_tiny_video(path: Path, frames: int = 4) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 12, (96, 64))
    if not writer.isOpened():
        raise RuntimeError("Could not open tiny test video writer")
    for index in range(frames):
        frame = np.full((64, 96, 3), 245, dtype=np.uint8)
        cv2.circle(frame, (22 + index * 8, 32), 10, (20, 20, 230), -1)
        writer.write(frame)
    writer.release()


def make_extraction(tmp_path: Path) -> Path:
    video = tmp_path / "tiny.mp4"
    out = tmp_path / "out"
    make_tiny_video(video)
    run_pipeline(
        video_path=video,
        out_dir=out,
        mask_provider=ThresholdMaskProvider((0, 80, 80), (12, 255, 255)),
        sample_fps=12,
        max_frames=3,
        output_mode="both",
    )
    return out


def test_mp4_final_render_reports_cached_no_ai_manifest(tmp_path):
    out = make_extraction(tmp_path)
    mp4 = out / "exports" / "final.mp4"

    entry = export_mp4(out_dir=out, output_path=mp4, background_color="#fbfaf6")

    assert entry["aiUsage"] == "none"
    assert entry["source"] == "cached_assets_and_json_transforms"
    if shutil.which("ffmpeg"):
        assert entry["status"] == "ready"
        assert mp4.stat().st_size > 0
        assert entry["encoder"] == "ffmpeg libx264"
        assert entry["pixelFormat"] == "yuv420p"
    else:
        assert entry["status"] == "unavailable"
        assert "ffmpeg" in entry["reason"]

    scene = json.loads((out / "scene_graph.json").read_text(encoding="utf-8"))
    manifest = write_final_export_manifest(
        manifest_path=out / "exports" / "final_export_manifest.json",
        out_dir=out,
        scene=scene,
        exports=[entry],
        object_id="object_0",
    )
    assert validate_document(manifest) == []


def test_mp4_export_handles_odd_canvas_dimensions(tmp_path):
    out = make_extraction(tmp_path)
    scene_path = out / "scene_graph.json"
    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    scene["source"]["width"] = 95
    scene["source"]["height"] = 63
    scene["canvas"]["width"] = 95
    scene["canvas"]["height"] = 63
    scene_path.write_text(json.dumps(scene), encoding="utf-8")
    mp4 = out / "exports" / "odd.mp4"

    entry = export_mp4(out_dir=out, output_path=mp4, background_color="#fbfaf6")

    assert entry["aiUsage"] == "none"
    if shutil.which("ffmpeg"):
        assert entry["status"] == "ready"
        assert mp4.stat().st_size > 0
    else:
        assert entry["status"] == "unavailable"


def test_cli_webm_alpha_export_preserves_phase5_no_ai_contract(tmp_path):
    out = make_extraction(tmp_path)
    webm = out / "exports" / "object_0.webm"

    if shutil.which("ffmpeg"):
        main(["export", str(out), "--format", "webm-alpha", "--out", str(webm), "--object-id", "object_0"])
        assert webm.stat().st_size > 0
        manifest = json.loads((out / "exports" / "final_export_manifest.json").read_text(encoding="utf-8"))
        assert manifest["exports"][0]["status"] == "ready"
        assert manifest["exports"][0]["aiUsage"] == "none"
        assert manifest["exports"][0]["cachedSource"] == "cached_rgba_cutout_png_sequence"
        assert validate_document(manifest) == []
    else:
        with pytest.raises(SystemExit) as exc:
            main(["export", str(out), "--format", "webm-alpha", "--out", str(webm), "--object-id", "object_0"])
        assert "ffmpeg" in str(exc.value)


def test_website_package_zip_is_relative_self_contained_and_excludes_debug_assets(tmp_path):
    out = make_extraction(tmp_path)
    package = out / "exports" / "website_package.zip"

    entry = export_website_package(out_dir=out, output_path=package)

    assert entry["status"] == "ready"
    assert entry["aiUsage"] == "none"
    with zipfile.ZipFile(package) as archive:
        names = archive.namelist()
        assert "index.html" in names
        assert "preview/index.html" in names
        assert "scene_graph.json" in names
        assert "web_asset_manifest.json" in names
        assert "object_motion.json" in names
        assert "resource_profile.json" in names
        assert "objects/object_0/object_manifest.json" in names
        assert "objects/object_0/spritesheet.webp" in names
        assert "runtime/index.js" in names
        assert "preview/canvas_player.html" in names
        assert "preview/website_templates/hero.html" in names
        assert "preview/website_templates/ecommerce.html" in names
        assert "preview/website_templates/education.html" in names
        assert "preview/website_snippets/webflow-style.html" in names
        assert "preview/website_snippets/framer-style.html" in names
        assert "preview/website_snippets/react-embed.jsx" in names
        assert "templates/hero.html" in names
        assert "templates/ecommerce.html" in names
        assert "templates/education.html" in names
        assert "snippets/webflow-style.html" in names
        assert "snippets/framer-style.html" in names
        assert "snippets/react-embed.jsx" in names
        assert "package_manifest.json" in names
        assert all(not Path(name).is_absolute() for name in names)
        assert all(".." not in Path(name).parts for name in names)
        assert not any(name.startswith("frames/") for name in names)
        assert not any(name.startswith("masks/") for name in names)
        assert not any(".env" in Path(name).name for name in names)
        package_manifest = json.loads(archive.read("package_manifest.json").decode("utf-8"))
        assert package_manifest["aiUsage"] == "none"
        assert package_manifest["rights"]["object_0"]["license"] == "user_uploaded_unverified"
        assert package_manifest["rightsManifest"] == "rights_manifest.json"
        assert package_manifest["templates"] == ["templates/ecommerce.html", "templates/education.html", "templates/hero.html"]
        assert package_manifest["snippets"] == [
            "snippets/framer-style.html",
            "snippets/react-embed.jsx",
            "snippets/webflow-style.html",
        ]


def test_website_package_ignores_unsafe_scene_asset_paths(tmp_path):
    out = make_extraction(tmp_path)
    scene_path = out / "scene_graph.json"
    manifest_path = out / "web_asset_manifest.json"
    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    web_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    scene["objects"][0]["motion"][0]["asset"] = "../leak.png"
    web_manifest["assets"]["sequence"][0]["asset"] = "../leak.png"
    scene_path.write_text(json.dumps(scene), encoding="utf-8")
    manifest_path.write_text(json.dumps(web_manifest), encoding="utf-8")
    (out.parent / "leak.png").write_bytes(b"not a package asset")
    package = out / "exports" / "website_package.zip"

    entry = export_website_package(out_dir=out, output_path=package)

    assert entry["status"] == "ready"
    with zipfile.ZipFile(package) as archive:
        names = archive.namelist()
    assert "../leak.png" not in names
    assert "leak.png" not in names


def test_remotion_adapter_writes_plan_without_dependency_or_network(tmp_path):
    out = make_extraction(tmp_path)
    plan_path = out / "exports" / "remotion_export_plan.json"

    entry = write_remotion_plan(out_dir=out, output_path=plan_path)

    assert entry["status"] == "plan_ready"
    assert entry["npmInvoked"] is False
    assert entry["networkInvoked"] is False
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert plan["status"] == "plan_ready"
    assert plan["dependencyPolicy"]["remotionDependencyAdded"] is False
    assert plan["composition"]["componentContract"]["component"] == "MotionJSONComposition"


def test_cli_all_writes_every_export_and_validates_output_dir_when_ffmpeg_available(tmp_path):
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg is required for direct CLI --format all")
    out = make_extraction(tmp_path)
    exports = out / "exports"

    main(["export", str(out), "--format", "all", "--out", str(exports), "--background-color", "#fbfaf6"])

    assert (exports / "final.mp4").stat().st_size > 0
    assert (exports / "object_0.webm").stat().st_size > 0
    assert (exports / "website_package.zip").stat().st_size > 0
    assert (exports / "remotion_export_plan.json").stat().st_size > 0
    manifest = json.loads((exports / "final_export_manifest.json").read_text(encoding="utf-8"))
    assert {entry["format"] for entry in manifest["exports"]} == {"mp4", "webm-alpha", "zip", "json"}
    assert validate_document(manifest) == []
    result = validate_output_dir(out)
    assert result.ok, [issue.format() for issue in result.issues]
