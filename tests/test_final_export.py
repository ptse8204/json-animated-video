import copy
import json
import shutil
import zipfile
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from motionjson.backend import export_workflows
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


def add_second_scene_object(out: Path, object_id: str = "object_1") -> None:
    source_dir = out / "objects" / "object_0"
    target_dir = out / "objects" / object_id
    if target_dir.exists():
        shutil.rmtree(target_dir)
    shutil.copytree(source_dir, target_dir)
    for path in target_dir.rglob("*.json"):
        path.write_text(path.read_text(encoding="utf-8").replace("object_0", object_id), encoding="utf-8")
    scene_path = out / "scene_graph.json"
    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    obj = copy.deepcopy(scene["objects"][0])
    obj = json.loads(json.dumps(obj).replace("object_0", object_id))
    obj["id"] = object_id
    obj["label"] = "Second object"
    obj["zIndex"] = 20
    scene["objects"].append(obj)
    if scene.get("layers"):
        layer = copy.deepcopy(scene["layers"][0])
        layer = json.loads(json.dumps(layer).replace("object_0", object_id))
        layer["id"] = f"{object_id}_layer"
        layer["object_id"] = object_id
        layer["z_index"] = 20
        scene["layers"].append(layer)
    scene_path.write_text(json.dumps(scene), encoding="utf-8")


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
        quality_routing={
            "format": "motionjson.export_quality_routing.v0.1",
            "aiUsage": "none",
            "source": "cached_quality_scores_and_resource_profile",
            "objects": [{"objectId": "object_0", "selectedOutput": "raster_alpha_sequence"}],
            "preview": {"mp4Preview": {"status": "skipped", "path": "preview/preview.mp4"}},
        },
        export_warnings=[
            {
                "code": "commercial_use_review_required",
                "severity": "warn",
                "objectId": "object_0",
                "message": "object_0 requires review",
                "suggestedAction": "review rights metadata",
            }
        ],
    )
    assert validate_document(manifest) == []
    assert manifest["source"]["directory"] == "."
    assert manifest["qualityRouting"]["format"] == "motionjson.export_quality_routing.v0.1"
    assert manifest["exportWarnings"][0]["code"] == "commercial_use_review_required"


def test_export_inclusion_rejects_static_keyframe_fallback_motion():
    scene = {
        "objects": [
            {
                "id": "ball",
                "exportStatus": "reviewed",
                "quality": {},
                "discovery": {"trackingProvider": "keyframe_seed_sequence", "exportStatus": "reviewed"},
                "motion": [
                    {"frame": 1, "visible": True, "x": 6, "y": 10, "w": 8, "h": 8},
                    {"frame": 2, "visible": True, "x": 6, "y": 10, "w": 8, "h": 8},
                    {"frame": 3, "visible": True, "x": 6, "y": 10, "w": 8, "h": 8},
                ],
            }
        ]
    }

    included, excluded, diagnostics = export_workflows._included_object_ids(scene, {})
    messages = export_workflows._export_validation_messages(diagnostics, [])

    assert included == []
    assert excluded == ["ball"]
    assert diagnostics[0]["reason"] == "static_keyframe_mask_sequence"
    assert messages[0]["severity"] == "error"
    assert "would not follow the moving object" in messages[0]["message"]


def test_phase11e_delivery_fallback_chooses_smallest_ready_production_asset():
    delivery = export_workflows._candidate_delivery_from_assets(
        {
            "assets": {
                "webpSpriteAtlas": {"status": "ready", "path": "objects/object_0/spritesheet.webp", "bytes": 200},
                "transparentWebm": {"status": "ready", "path": "objects/object_0/object.webm", "bytes": 80},
                "avifSpriteAtlas": {"status": "unsupported", "path": "objects/object_0/spritesheet.avif", "bytes": 40},
            }
        }
    )

    assert delivery is not None
    assert delivery["route"] == "transparent_webm"
    assert delivery["bytes"] == 80


def test_review_required_quality_blocks_export_selection():
    included, excluded, diagnostics = export_workflows._included_object_ids(
        {"objects": [{"id": "trace_object", "quality": {"reviewRequired": True}}]},
        {},
    )

    assert included == []
    assert excluded == ["trace_object"]
    assert diagnostics == [
        {
            "code": "track_excluded_from_export",
            "objectId": "trace_object",
            "reason": "review_required",
        }
    ]


def test_explicit_review_inclusion_overrides_pending_review_gate():
    scene = {
        "objects": [
            {
                "id": "trace_object",
                "exportStatus": "review_pending",
                "quality": {"reviewRequired": True},
                "discovery": {"reviewRequired": True, "exportStatus": "review_pending"},
                "motion": [
                    {"frame": 1, "visible": True, "x": 6, "y": 10, "w": 8, "h": 8},
                    {"frame": 2, "visible": True, "x": 8, "y": 10, "w": 8, "h": 8},
                ],
            }
        ],
        "layers": [{"object_id": "trace_object", "exportStatus": "review_pending"}],
    }
    correction_state = {"trackEdits": {"trace_object": {"exportIncluded": True}}, "history": []}

    included, excluded, diagnostics = export_workflows._included_object_ids(scene, correction_state)
    exported, exported_included, _exported_excluded, _exported_diagnostics = export_workflows._sanitized_scene(scene, correction_state)

    assert included == ["trace_object"]
    assert excluded == []
    assert diagnostics == []
    assert exported_included == ["trace_object"]
    assert exported["objects"][0]["exportStatus"] == "accepted"
    assert exported["objects"][0]["quality"]["reviewRequired"] is False
    assert exported["objects"][0]["discovery"]["reviewRequired"] is False
    assert exported["layers"][0]["exportStatus"] == "accepted"


def test_export_ready_track_summary_overrides_stale_scene_review_gate():
    scene = {
        "objects": [
            {
                "id": "trace_object",
                "exportStatus": "review_pending",
                "quality": {"reviewRequired": True},
                "discovery": {"reviewRequired": True, "exportStatus": "review_pending"},
                "motion": [
                    {"frame": 1, "visible": True, "x": 6, "y": 10, "w": 8, "h": 8},
                    {"frame": 2, "visible": True, "x": 14, "y": 10, "w": 8, "h": 8},
                ],
            }
        ],
        "layers": [{"object_id": "trace_object", "exportStatus": "review_pending"}],
    }
    track_summary = {"tracks": [{"objectId": "trace_object", "exportStatus": "accepted", "exportIncluded": True}]}
    ready_ids = export_workflows._export_ready_track_ids(track_summary)

    included, excluded, diagnostics = export_workflows._included_object_ids(
        scene,
        {},
        export_ready_track_ids=ready_ids,
    )
    exported, exported_included, _exported_excluded, _exported_diagnostics = export_workflows._sanitized_scene(
        scene,
        {},
        export_ready_track_ids=ready_ids,
    )

    assert included == ["trace_object"]
    assert excluded == []
    assert diagnostics == []
    assert exported_included == ["trace_object"]
    assert exported["objects"][0]["exportStatus"] == "accepted"
    assert exported["objects"][0]["quality"]["reviewRequired"] is False
    assert exported["objects"][0]["discovery"]["reviewRequired"] is False
    assert exported["layers"][0]["exportStatus"] == "accepted"


def test_export_ready_track_summary_does_not_override_hard_rejection():
    scene = {
        "objects": [
            {
                "id": "trace_object",
                "exportStatus": "rejected",
                "quality": {"reviewRequired": False},
                "discovery": {"reviewRequired": False, "exportStatus": "rejected"},
            }
        ]
    }
    track_summary = {"tracks": [{"objectId": "trace_object", "exportStatus": "accepted", "exportIncluded": True}]}

    included, excluded, diagnostics = export_workflows._included_object_ids(
        scene,
        {},
        export_ready_track_ids=export_workflows._export_ready_track_ids(track_summary),
    )

    assert included == []
    assert excluded == ["trace_object"]
    assert diagnostics[0]["reason"] == "rejected"


def test_phase11e_mp4_preview_dry_run_and_error_cleanup(tmp_path, monkeypatch):
    scene = {"source": {"width": 4, "height": 4, "sampleFps": 12, "sampledFrameCount": 1}, "objects": []}
    export_dir = tmp_path / "export"
    monkeypatch.setattr(export_workflows.shutil, "which", lambda _name: "/usr/bin/ffmpeg")

    planned = export_workflows._write_mp4_preview(source_dir=tmp_path, export_dir=export_dir, scene=scene, include_preview=True, render=False)
    assert planned["status"] == "plan_ready"
    assert not (export_dir / "preview" / "preview.mp4").exists()

    monkeypatch.setattr(export_workflows, "render_frames", lambda **_kwargs: 1)

    def fake_run(command, **_kwargs):
        Path(command[-1]).write_bytes(b"partial")
        return SimpleNamespace(returncode=1, stderr=r"C:\Users\Alice\secret\ffmpeg.log failed", stdout="")

    monkeypatch.setattr(export_workflows.subprocess, "run", fake_run)

    failed = export_workflows._write_mp4_preview(source_dir=tmp_path, export_dir=export_dir, scene=scene, include_preview=True)

    assert failed["status"] == "error"
    assert "[LOCAL_PATH_REDACTED]" in failed["reason"]
    assert "Alice" not in failed["reason"]
    assert not (export_dir / "preview" / "preview.mp4").exists()


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
        assert "preview/object_selection_workflow.html" in names
        assert "preview/timeline_editor.html" in names
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
        assert package_manifest["objectLayerPack"] == "object_layer_pack.json"
        assert [tool["path"] for tool in package_manifest["previewTools"]] == [
            "preview/canvas_player.html",
            "preview/object_selection_workflow.html",
            "preview/timeline_editor.html",
        ]
        assert './scene_graph.json' in archive.read("index.html").decode("utf-8")
        preview_index = archive.read("preview/index.html").decode("utf-8")
        assert '../scene_graph.json' in preview_index
        assert '"./scene_graph.json"' not in preview_index
        object_layer_pack = json.loads(archive.read("object_layer_pack.json").decode("utf-8"))
        assert object_layer_pack["format"] == "motionjson.object_layer_pack.v0.1"
        assert object_layer_pack["selectedObjectIds"] == ["object_0"]
        assert "plainJs" in object_layer_pack["snippets"]


def test_website_package_can_filter_to_selected_object_layers(tmp_path):
    out = make_extraction(tmp_path)
    add_second_scene_object(out)
    package = out / "exports" / "selected_website_package.zip"

    entry = export_website_package(
        out_dir=out,
        output_path=package,
        object_ids=["object_1"],
        excluded_object_ids=["object_0"],
        validation_messages=[
            {
                "code": "auto_discovered_object_review_required",
                "severity": "warn",
                "objectId": "object_0",
                "message": "object_0 requires review before export.",
            }
        ],
    )

    assert entry["status"] == "ready"
    assert entry["selectedObjectIds"] == ["object_1"]
    assert entry["excludedObjectIds"] == ["object_0"]
    with zipfile.ZipFile(package) as archive:
        names = archive.namelist()
        scene = json.loads(archive.read("scene_graph.json").decode("utf-8"))
        package_manifest = json.loads(archive.read("package_manifest.json").decode("utf-8"))
        object_layer_pack = json.loads(archive.read("object_layer_pack.json").decode("utf-8"))

    assert [obj["id"] for obj in scene["objects"]] == ["object_1"]
    assert "objects/object_1/object_manifest.json" in names
    assert "objects/object_0/object_manifest.json" not in names
    assert package_manifest["selectedObjectIds"] == ["object_1"]
    assert package_manifest["excludedObjectIds"] == ["object_0"]
    assert object_layer_pack["selectedObjectIds"] == ["object_1"]
    assert object_layer_pack["excludedObjectIds"] == ["object_0"]
    assert object_layer_pack["validationMessages"][0]["code"] == "auto_discovered_object_review_required"


def test_website_package_rejects_unknown_selected_object_ids(tmp_path):
    out = make_extraction(tmp_path)

    with pytest.raises(ValueError, match="objectIds not found"):
        export_website_package(out_dir=out, output_path=out / "exports" / "missing.zip", object_ids=["missing_object"])


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
    assert plan["composition"]["componentContract"]["props"]["objectIds"] == ["object_0"]
    assert plan["objectLayerPack"]["format"] == "motionjson.object_layer_pack.v0.1"


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
