import json
from pathlib import Path

import cv2
import numpy as np
from jsonschema import Draft202012Validator

from motionjson.masks import ThresholdMaskProvider
from motionjson.pipeline import run_pipeline
from motionjson.schemas import SCHEMA_IDS
from motionjson.validation import load_schema, validate_document, validate_file, validate_output_dir


def make_tiny_video(path: Path, frames: int = 4) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 12, (96, 64))
    if not writer.isOpened():
        raise RuntimeError("Could not open tiny test video writer")
    for index in range(frames):
        frame = np.full((64, 96, 3), 245, dtype=np.uint8)
        cv2.circle(frame, (20 + index * 8, 32), 10, (20, 20, 230), -1)
        writer.write(frame)
    writer.release()


def test_packaged_schemas_are_valid_draft_2020_12():
    for schema_id in SCHEMA_IDS:
        Draft202012Validator.check_schema(load_schema(schema_id))


def test_pipeline_outputs_validate_against_packaged_schemas(tmp_path):
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

    assert validate_document(scene) == []

    result = validate_output_dir(out)
    assert result.ok, [issue.format() for issue in result.issues]
    assert out / "objects" / "object_0" / "object_motion.json" in result.checked
    assert out / "objects" / "object_0" / "web_asset_manifest.json" in result.checked
    assert out / "silhouette_lottie.json" in result.skipped


def test_validate_output_dir_accepts_legacy_placeholder_rights(tmp_path):
    video = tmp_path / "tiny.mp4"
    out = tmp_path / "out"
    make_tiny_video(video)
    run_pipeline(
        video_path=video,
        out_dir=out,
        mask_provider=ThresholdMaskProvider((0, 80, 80), (12, 255, 255)),
        sample_fps=6,
        max_frames=3,
    )
    legacy_rights = {
        "sourceAttribution": True,
        "license": "user_uploaded_placeholder",
        "notes": "Rights and likeness review required before remixing third-party footage.",
    }
    scene_path = out / "scene_graph.json"
    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    scene.pop("rightsManifest", None)
    scene["objects"][0]["rights"] = legacy_rights
    scene_path.write_text(json.dumps(scene), encoding="utf-8")

    object_manifest_path = out / "objects" / "object_0" / "object_manifest.json"
    object_manifest = json.loads(object_manifest_path.read_text(encoding="utf-8"))
    object_manifest["rights"] = legacy_rights
    object_manifest_path.write_text(json.dumps(object_manifest), encoding="utf-8")

    web_manifest_path = out / "web_asset_manifest.json"
    web_manifest = json.loads(web_manifest_path.read_text(encoding="utf-8"))
    web_manifest.pop("rightsManifest", None)
    web_manifest["rights"] = legacy_rights
    web_manifest_path.write_text(json.dumps(web_manifest), encoding="utf-8")
    (out / "rights_manifest.json").unlink()

    result = validate_output_dir(out)

    assert result.ok, [issue.format() for issue in result.issues]
    assert out / "rights_manifest.json" not in result.checked


def test_resource_profile_schema_accepts_pre_phase16_profiles(tmp_path):
    video = tmp_path / "tiny.mp4"
    out = tmp_path / "out"
    make_tiny_video(video)
    run_pipeline(
        video_path=video,
        out_dir=out,
        mask_provider=ThresholdMaskProvider((0, 80, 80), (12, 255, 255)),
        sample_fps=6,
        max_frames=3,
    )
    profile_path = out / "resource_profile.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    for key in ("providerPerformance", "latencyMetrics", "costDashboard", "compressionOptimizer"):
        profile.pop(key, None)
    profile_path.write_text(json.dumps(profile), encoding="utf-8")

    assert validate_file(profile_path).ok


def test_validate_file_reports_schema_errors(tmp_path):
    path = tmp_path / "object_motion.json"
    path.write_text(
        '{"schema":"motionjson.object_motion.v0.1","objectId":"object_0","fps":12,"motion":[]}',
        encoding="utf-8",
    )

    result = validate_file(path)

    assert not result.ok
    assert any("quality" in issue.message for issue in result.issues)


def test_validate_file_requires_core_motionjson_schema(tmp_path):
    path = tmp_path / "silhouette_lottie.json"
    path.write_text('{"v":"5.7.0","layers":[]}', encoding="utf-8")

    result = validate_file(path)

    assert not result.ok
    assert "schema" in result.issues[0].message


def test_validate_output_dir_requires_core_artifacts(tmp_path):
    out = tmp_path / "out"
    out.mkdir()

    result = validate_output_dir(out)

    assert not result.ok
    assert len(result.issues) == 6
    assert all("missing" in issue.message for issue in result.issues)
