from __future__ import annotations

import json
import zipfile
from pathlib import Path

import cv2
import numpy as np

from motionjson.exporters.final_render import final_export_entry, write_final_export_manifest
from motionjson.exporters.website_package import export_website_package
from motionjson.masks import ThresholdMaskProvider
from motionjson.pipeline import run_pipeline
from motionjson.validation import validate_document


def make_tiny_video(path: Path, frames: int = 4) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 12, (96, 64))
    if not writer.isOpened():
        raise RuntimeError("Could not open tiny test video writer")
    for index in range(frames):
        frame = np.full((64, 96, 3), 245, dtype=np.uint8)
        cv2.circle(frame, (22 + index * 8, 32), 10, (20, 20, 230), -1)
        writer.write(frame)
    writer.release()


def test_pipeline_writes_structured_rights_and_valid_rights_manifest(tmp_path):
    video = tmp_path / "tiny.mp4"
    out = tmp_path / "out"
    make_tiny_video(video)

    scene = run_pipeline(
        video_path=video,
        out_dir=out,
        mask_provider=ThresholdMaskProvider((0, 80, 80), (12, 255, 255)),
        sample_fps=6,
        max_frames=3,
        rights_context={
            "source_uri": "tests://tiny.mp4",
            "display_text": "Tiny test source",
            "license": "internal_test_license",
            "license_name": "Internal test fixture",
            "license_scope": "test_only",
            "creator_approved": True,
            "creator_approval_status": "approved",
            "commercial_use": True,
            "commercial_use_status": "approved",
        },
    )

    rights = scene["objects"][0]["rights"]
    rights_manifest = json.loads((out / "rights_manifest.json").read_text(encoding="utf-8"))
    object_manifest = json.loads((out / "objects" / "object_0" / "object_manifest.json").read_text(encoding="utf-8"))
    web_manifest = json.loads((out / "web_asset_manifest.json").read_text(encoding="utf-8"))

    assert scene["rightsManifest"] == "rights_manifest.json"
    assert rights["sourceAttribution"]["displayText"] == "Tiny test source"
    assert rights["license"] == "internal_test_license"
    assert rights["creatorApproval"]["approved"] is True
    assert rights["commercialUse"] is True
    assert rights["commercialUseStatus"] == "approved"
    assert object_manifest["rights"] == rights
    assert web_manifest["rights"] == rights
    assert web_manifest["rightsManifest"] == "rights_manifest.json"
    assert rights_manifest["objects"]["object_0"] == rights
    assert rights_manifest["summary"]["commercialUseApproved"] is True
    assert validate_document(rights_manifest) == []
    assert validate_document(scene) == []
    assert validate_document(web_manifest) == []


def test_final_and_website_exports_preserve_rights_manifest(tmp_path):
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

    entry = final_export_entry(
        export_type="test_export",
        format_name="json",
        output_path=out / "exports" / "placeholder.json",
        out_dir=out,
        status="ready",
        mime_type="application/json",
    )
    final_manifest = write_final_export_manifest(
        manifest_path=out / "exports" / "final_export_manifest.json",
        out_dir=out,
        scene=scene,
        exports=[entry],
        object_id="object_0",
    )
    package_path = out / "exports" / "website_package.zip"
    package_entry = export_website_package(out_dir=out, output_path=package_path)

    assert final_manifest["rightsManifest"] == "rights_manifest.json"
    assert final_manifest["rights"]["license"] == "user_uploaded_unverified"
    assert validate_document(final_manifest) == []
    assert package_entry["aiUsage"] == "none"
    assert package_entry["rightsManifest"] == "rights_manifest.json"
    with zipfile.ZipFile(package_path) as archive:
        names = archive.namelist()
        package_manifest = json.loads(archive.read("package_manifest.json").decode("utf-8"))
        rights_manifest = json.loads(archive.read("rights_manifest.json").decode("utf-8"))
    assert "rights_manifest.json" in names
    assert package_manifest["rightsManifest"] == "rights_manifest.json"
    assert package_manifest["rightsSummary"] == rights_manifest["summary"]
