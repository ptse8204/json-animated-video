from __future__ import annotations

import json
from pathlib import Path

import pytest

from motionjson import cli
from motionjson.benchmark import (
    _quality_summary,
    _validation_summary,
    generate_synthetic_fixture,
    normalize_benchmark_modes,
    normalize_fixture_names,
    run_evaluation_benchmark,
)
from motionjson.validation import validate_document, validate_file


def test_synthetic_fixture_generator_writes_video_masks_and_expected_manifest(tmp_path):
    manifest = generate_synthetic_fixture("multi_object", tmp_path / "fixture", width=64, height=48, frames=4)

    assert manifest["format"] == "motionjson.evaluation_fixture.v0.1"
    assert manifest["expected"]["objectCount"] == 2
    assert manifest["expected"]["acceptedTracks"] == 2
    assert (tmp_path / "fixture" / "video.mp4").exists()
    assert (tmp_path / "fixture" / "expected.json").exists()
    for item in manifest["objects"]:
        mask_files = sorted((tmp_path / "fixture" / item["maskDir"]).glob("mask_*.png"))
        assert len(mask_files) == 4
        assert item["minMaskArea"] > 0


def test_benchmark_runner_writes_machine_and_human_reports_without_gpu(tmp_path):
    summary = run_evaluation_benchmark(
        out_dir=tmp_path / "benchmarks",
        fixtures="red_ball,whole_frame_regression",
        modes="external",
        width=64,
        height=48,
        frames=4,
    )

    assert summary["schema"] == "motionjson.evaluation_benchmark.v0.1"
    assert summary["format"] == "motionjson.evaluation_benchmark.v0.1"
    assert validate_document(summary) == []
    assert summary["summary"]["totalRuns"] == 2
    assert summary["summary"]["passedRuns"] == 2
    assert summary["summary"]["fallbackReasonCounts"] == {"masks_too_large_whole_frame": 1}
    runs = {(run["fixture"], run["mode"]): run for run in summary["runs"]}
    assert runs[("red_ball", "external_masks")]["quality"]["acceptedTracks"] == 1
    assert runs[("red_ball", "external_masks")]["quality"]["duplicateOverlap"]["pairCount"] == 0
    whole_frame = runs[("whole_frame_regression", "external_masks")]
    assert whole_frame["quality"]["acceptedTracks"] == 0
    assert whole_frame["quality"]["rejectedTracks"] == 1
    assert whole_frame["quality"]["objectIdsMatch"]
    assert whole_frame["quality"]["fallbackReasonCounts"] == {"masks_too_large_whole_frame": 1}

    summary_json = (tmp_path / "benchmarks" / "summary.json").read_text(encoding="utf-8")
    assert str(tmp_path) not in summary_json
    assert validate_file(tmp_path / "benchmarks" / "summary.json").ok
    assert "MotionJSON Evaluation Benchmark" in (tmp_path / "benchmarks" / "summary.md").read_text(encoding="utf-8")
    assert "Duplicate max IoU" in (tmp_path / "benchmarks" / "summary.md").read_text(encoding="utf-8")
    assert (tmp_path / "benchmarks" / "runs" / "red_ball_external_masks" / "scene_graph.json").exists()


def test_benchmark_multi_object_external_masks_keeps_two_stable_tracks(tmp_path):
    summary = run_evaluation_benchmark(
        out_dir=tmp_path / "benchmarks",
        fixtures="multi_object",
        modes="external",
        width=64,
        height=48,
        frames=4,
    )

    assert summary["summary"]["passedRuns"] == 1
    run = summary["runs"][0]
    assert run["quality"]["acceptedTracks"] == 2
    assert run["quality"]["rejectedTracks"] == 0
    assert run["quality"]["expectedObjectIds"] == ["red_ball", "blue_block"]
    assert run["quality"]["sceneObjectIds"] == ["red_ball", "blue_block"]
    assert run["quality"]["fallbackReasonCounts"] == {}
    assert run["quality"]["duplicateOverlap"]["pairCount"] == 1
    assert run["quality"]["duplicateOverlap"]["maxMeanIou"] < 0.2


def test_benchmark_name_normalizers_support_documented_aliases():
    assert "whole_frame_regression" in normalize_fixture_names("synthetic")
    assert normalize_fixture_names("red_ball,small_object") == ["red_ball", "small_object"]
    assert normalize_benchmark_modes(None) == ["external_masks"]
    assert normalize_benchmark_modes("threshold,motion,mock,auto") == [
        "external_masks",
        "motion_foreground",
        "text_detector_mock",
        "sam_auto_mock",
    ]
    assert normalize_benchmark_modes("sam_auto_masks_mock") == ["sam_auto_mock"]
    with pytest.raises(ValueError, match="unknown benchmark fixture"):
        normalize_fixture_names("missing_fixture")


def test_cli_benchmark_help_and_command_write_reports(tmp_path, capsys):
    with pytest.raises(SystemExit) as help_exit:
        cli.main(["benchmark", "--help"])
    assert help_exit.value.code == 0
    assert "CPU-only synthetic fixture benchmarks" in capsys.readouterr().out

    cli.main(
        [
            "benchmark",
            "--fixtures",
            "whole_frame_regression",
            "--modes",
            "external",
            "--out",
            str(tmp_path / "cli-benchmarks"),
            "--width",
            "64",
            "--height",
            "48",
            "--frames",
            "4",
        ]
    )
    output = capsys.readouterr().out
    assert "summary.json" in output
    payload = json.loads((tmp_path / "cli-benchmarks" / "summary.json").read_text(encoding="utf-8"))
    assert payload["summary"]["passedRuns"] == 1
    assert payload["summary"]["fallbackReasonCounts"] == {"masks_too_large_whole_frame": 1}


def test_benchmark_sam_auto_mock_mode_writes_candidate_review_fixture(tmp_path):
    summary = run_evaluation_benchmark(
        out_dir=tmp_path / "benchmarks",
        fixtures="multi_object",
        modes="sam_auto_mock",
        width=64,
        height=48,
        frames=4,
        min_area=1,
    )

    assert summary["summary"]["totalRuns"] == 1
    assert validate_document(summary) == []
    run = summary["runs"][0]
    assert run["mode"] == "sam_auto_mock"
    assert run["quality"]["acceptedTracks"] >= 1
    run_dir = tmp_path / "benchmarks" / "runs" / "multi_object_sam_auto_mock"
    candidates = json.loads((run_dir / "candidates.json").read_text(encoding="utf-8"))
    assert candidates["provider"] == "sam_auto_masks"
    assert [candidate["label"] for candidate in candidates["candidates"]] == ["Visible segment 1", "Visible segment 2"]
    assert validate_file(tmp_path / "benchmarks" / "summary.json").ok


def test_benchmark_validation_checks_every_scene_object(tmp_path):
    run_evaluation_benchmark(
        out_dir=tmp_path / "benchmarks",
        fixtures="multi_object",
        modes="external",
        width=64,
        height=48,
        frames=4,
    )
    run_dir = tmp_path / "benchmarks" / "runs" / "multi_object_external_masks"
    (run_dir / "objects" / "blue_block" / "object_manifest.json").unlink()

    validation = _validation_summary(run_dir, object_ids=["red_ball", "blue_block"])

    assert not validation["ok"]
    assert validation["objectIds"] == ["red_ball", "blue_block"]
    assert any("objects/blue_block/object_manifest.json" == issue["path"] for issue in validation["issues"])


def test_benchmark_quality_regresses_when_expected_scene_object_is_missing(tmp_path):
    run_evaluation_benchmark(
        out_dir=tmp_path / "benchmarks",
        fixtures="multi_object",
        modes="external",
        width=64,
        height=48,
        frames=4,
    )
    root = tmp_path / "benchmarks"
    run_dir = root / "runs" / "multi_object_external_masks"
    manifest = json.loads((root / "fixtures" / "multi_object" / "fixture_manifest.json").read_text(encoding="utf-8"))
    scene = json.loads((run_dir / "scene_graph.json").read_text(encoding="utf-8"))
    scene["objects"] = [item for item in scene["objects"] if item["id"] != "blue_block"]

    quality = _quality_summary(fixture_manifest=manifest, run_dir=run_dir, scene=scene, elapsed_ms=1.0)

    assert not quality["passed"]
    assert not quality["objectIdsMatch"]
    assert quality["expectedObjectIds"] == ["red_ball", "blue_block"]
    assert quality["sceneObjectIds"] == ["red_ball"]
    assert quality["validation"]["objectIds"] == ["red_ball", "blue_block"]
