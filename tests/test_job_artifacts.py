from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from motionjson.backend.assets import list_assets_for_job, register_upload
from motionjson.backend.auth import register_user
from motionjson.backend.db import initialize_database
from motionjson.backend.jobs import enqueue_extract_job, list_job_events
from motionjson.backend.projects import create_project
from motionjson.backend.queue import request_cancel_job
from motionjson.backend.worker import worker_once
from motionjson.cli import main
from motionjson.job_artifacts import LocalJobRun
from motionjson.providers.local_storage import LocalStorageProvider
from motionjson.validation import validate_output_dir


def demo_video() -> Path:
    return Path(__file__).resolve().parents[1] / "examples" / "demo_red_ball.mp4"


def backend(tmp_path):
    conn = sqlite3.connect(tmp_path / "backend.sqlite")
    conn.row_factory = sqlite3.Row
    initialize_database(conn)
    storage = LocalStorageProvider(tmp_path / "storage")
    user = register_user(conn, email="job-artifacts@example.com", password="pw")
    project = create_project(conn, user_id=user["id"], name="Job Artifacts")
    return conn, storage, user, project


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_events(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_cli_extract_job_artifacts_preserve_legacy_outputs(tmp_path, capsys):
    out = tmp_path / "out"

    main(["extract", str(demo_video()), "--out", str(out), "--mask-provider", "threshold", "--max-frames", "2"])

    stdout = capsys.readouterr().out
    assert "scene_graph.json" in stdout
    assert (out / "scene_graph.json").exists()
    assert (out / "object_motion.json").exists()
    assert (out / "web_asset_manifest.json").exists()
    assert (out / "run_config.json").exists()
    assert (out / "job.json").exists()
    assert (out / "events.jsonl").exists()
    assert (out / "logs.txt").exists()
    assert (out / "metrics.json").exists()
    assert (out / "artifacts.json").exists()
    assert (out / "provider_diagnostics.json").exists()
    assert (out / "candidates.json").exists()
    assert (out / "tracks.json").exists()
    assert (out / "fallback_diagnostics.json").exists()

    job = read_json(out / "job.json")
    metrics = read_json(out / "metrics.json")
    artifacts = read_json(out / "artifacts.json")["artifacts"]
    events = read_events(out / "events.jsonl")
    stages = {event["stage"] for event in events}
    stage_statuses = {(event["stage"], event["status"]) for event in events}

    assert job["status"] == "succeeded"
    assert metrics["latencyMetrics"]["sampledFrames"] == 2
    assert {
        "run_config.json",
        "scene_graph.json",
        "events.jsonl",
        "metrics.json",
        "candidates.json",
        "tracks.json",
        "fallback_diagnostics.json",
    }.issubset({artifact["path"] for artifact in artifacts})
    assert {
        "validating_config",
        "video_read",
        "keyframe_selection",
        "candidate_discovery",
        "initial_masks",
        "propagation",
        "track_linking",
        "vectorization",
        "export",
    }.issubset(stages)
    assert {
        ("candidate_discovery", "succeeded"),
        ("initial_masks", "succeeded"),
        ("propagation", "succeeded"),
        ("track_linking", "succeeded"),
        ("vectorization", "succeeded"),
    }.issubset(stage_statuses)
    assert not any(event["stage"] in {"candidate_discovery", "propagation", "track_linking"} and event["status"] == "skipped" for event in events)
    assert validate_output_dir(out).ok


def test_cli_extract_failure_writes_diagnostics_and_traceback(tmp_path):
    out = tmp_path / "failed"
    empty_masks = tmp_path / "empty_masks"
    empty_masks.mkdir()

    with pytest.raises(FileNotFoundError):
        main(
            [
                "extract",
                str(demo_video()),
                "--out",
                str(out),
                "--mask-provider",
                "external",
                "--mask-dir",
                str(empty_masks),
                "--max-frames",
                "1",
            ]
        )

    job = read_json(out / "job.json")
    failure = read_json(out / "failure.json")
    logs = (out / "logs.txt").read_text(encoding="utf-8")
    events = read_events(out / "events.jsonl")

    assert job["status"] == "failed"
    assert failure["reasonCode"] == "missing_input_or_artifact"
    assert "No mask images found" in failure["message"]
    assert "Traceback:" in logs
    assert events[-1]["status"] == "failed"


def test_cli_extract_reusing_output_clears_stale_failure_and_cancel_marker(tmp_path):
    out = tmp_path / "rerun"
    empty_masks = tmp_path / "empty_masks"
    empty_masks.mkdir()
    with pytest.raises(FileNotFoundError):
        main(
            [
                "extract",
                str(demo_video()),
                "--out",
                str(out),
                "--mask-provider",
                "external",
                "--mask-dir",
                str(empty_masks),
                "--max-frames",
                "1",
            ]
        )
    assert (out / "failure.json").exists()
    (out / "cancel.requested").write_text("stale", encoding="utf-8")

    main(["extract", str(demo_video()), "--out", str(out), "--mask-provider", "threshold", "--max-frames", "1"])

    job = read_json(out / "job.json")
    artifact_paths = {artifact["path"] for artifact in read_json(out / "artifacts.json")["artifacts"]}
    assert job["status"] == "succeeded"
    assert not (out / "failure.json").exists()
    assert not (out / "cancel.requested").exists()
    assert "failure.json" not in artifact_paths


def test_cli_extract_success_then_failure_does_not_manifest_stale_outputs(tmp_path):
    out = tmp_path / "success-then-failure"
    empty_masks = tmp_path / "empty_masks"
    empty_masks.mkdir()

    main(["extract", str(demo_video()), "--out", str(out), "--mask-provider", "threshold", "--max-frames", "1"])
    assert (out / "scene_graph.json").exists()
    assert (out / "objects").exists()

    with pytest.raises(FileNotFoundError):
        main(
            [
                "extract",
                str(demo_video()),
                "--out",
                str(out),
                "--mask-provider",
                "external",
                "--mask-dir",
                str(empty_masks),
                "--max-frames",
                "1",
            ]
        )

    artifact_paths = {artifact["path"] for artifact in read_json(out / "artifacts.json")["artifacts"]}
    assert "failure.json" in artifact_paths
    assert "scene_graph.json" not in artifact_paths
    assert all(not path.startswith(("objects/", "masks/", "preview/")) for path in artifact_paths)


def test_backend_extract_job_registers_structured_artifacts_and_progress(tmp_path):
    conn, storage, user, project = backend(tmp_path)
    upload = register_upload(conn, storage=storage, user_id=user["id"], project_id=project["id"], path=demo_video(), kind="source_video")
    job = enqueue_extract_job(conn, user_id=user["id"], project_id=project["id"], asset_id=upload["id"], mask_provider="mock", max_frames=2)

    result = worker_once(conn, storage=storage)
    assets = list_assets_for_job(conn, project_id=project["id"], source_job_id=job["id"])
    kinds = {asset["kind"] for asset in assets}
    events = list_job_events(conn, job_id=job["id"])

    assert result["status"] == "succeeded"
    assert {"run_config", "job_state", "job_events", "job_logs", "job_metrics", "artifact_manifest", "provider_diagnostics"}.issubset(kinds)
    assert {"candidate_summary", "track_summary", "fallback_diagnostics"}.issubset(kinds)
    assert {"scene_graph", "object_manifest", "web_manifest"}.issubset(kinds)
    assert {"debug_frame", "mask", "cutout", "preview"}.issubset(kinds)
    assert any(event["event_type"] == "progress" and "video" in event["message"] for event in events)


def test_backend_failed_job_registers_failure_artifacts_and_traceback(tmp_path):
    conn, storage, user, project = backend(tmp_path)
    upload = register_upload(conn, storage=storage, user_id=user["id"], project_id=project["id"], path=demo_video(), kind="source_video")
    job = enqueue_extract_job(conn, user_id=user["id"], project_id=project["id"], asset_id=upload["id"], mask_provider="external", max_frames=1)

    result = worker_once(conn, storage=storage, max_attempts=1)
    assets = list_assets_for_job(conn, project_id=project["id"], source_job_id=job["id"])
    kinds = {asset["kind"] for asset in assets}
    failure_assets = [asset for asset in assets if asset["kind"] == "failure_diagnostics"]
    logs_assets = [asset for asset in assets if asset["kind"] == "job_logs"]

    assert result["status"] == "failed"
    assert {"run_config", "failure_diagnostics", "job_logs", "artifact_manifest"}.issubset(kinds)
    failure = json.loads(storage.load_bytes(failure_assets[0]["storage_key"]))
    logs = storage.load_bytes(logs_assets[0]["storage_key"]).decode("utf-8")
    assert failure["reasonCode"] == "invalid_run_config"
    assert "mask_dir is required" in failure["message"]
    assert "Traceback:" in logs


def test_backend_cancel_pending_job_before_worker_runs(tmp_path):
    conn, storage, user, project = backend(tmp_path)
    upload = register_upload(conn, storage=storage, user_id=user["id"], project_id=project["id"], path=demo_video(), kind="source_video")
    job = enqueue_extract_job(conn, user_id=user["id"], project_id=project["id"], asset_id=upload["id"], mask_provider="threshold", max_frames=1)

    canceled = request_cancel_job(conn, job_id=job["id"])
    result = worker_once(conn, storage=storage)
    events = list_job_events(conn, job_id=job["id"])

    assert canceled["status"] == "canceled"
    assert result is None
    assert any(event["event_type"] == "canceled" for event in events)


def test_backend_running_job_cancel_request_finishes_as_canceled(tmp_path, monkeypatch):
    from motionjson.backend import worker as worker_module

    conn, storage, user, project = backend(tmp_path)
    upload = register_upload(conn, storage=storage, user_id=user["id"], project_id=project["id"], path=demo_video(), kind="source_video")
    job = enqueue_extract_job(conn, user_id=user["id"], project_id=project["id"], asset_id=upload["id"], mask_provider="threshold", max_frames=1)

    def fake_run_pipeline(**kwargs):
        requested = request_cancel_job(conn, job_id=job["id"], reason="test_cancel")
        assert requested["status"] == "cancel_requested"
        kwargs["job_context"].check_cancel("fake_stage")
        raise AssertionError("cancel check should raise")

    monkeypatch.setattr(worker_module, "run_pipeline", fake_run_pipeline)

    result = worker_once(conn, storage=storage)
    events = list_job_events(conn, job_id=job["id"])

    assert result["status"] == "canceled"
    assert result["error"] == "job canceled during fake_stage"
    assert any(event["event_type"] == "canceled" for event in events)


def test_backend_running_job_cancel_request_before_finalize_keeps_artifacts_canceled(tmp_path, monkeypatch):
    from motionjson.backend import worker as worker_module

    conn, storage, user, project = backend(tmp_path)
    upload = register_upload(conn, storage=storage, user_id=user["id"], project_id=project["id"], path=demo_video(), kind="source_video")
    job = enqueue_extract_job(conn, user_id=user["id"], project_id=project["id"], asset_id=upload["id"], mask_provider="threshold", max_frames=1)

    def fake_run_pipeline(**kwargs):
        Path(kwargs["out_dir"]).mkdir(parents=True, exist_ok=True)
        (Path(kwargs["out_dir"]) / "scene_graph.json").write_text("{}", encoding="utf-8")
        request_cancel_job(conn, job_id=job["id"], reason="late_cancel")
        return {"source": {"sampledFrameCount": 1}, "objects": [], "latencyMetrics": {}, "providerPerformance": {}, "costDashboard": {}}

    monkeypatch.setattr(worker_module, "run_pipeline", fake_run_pipeline)

    result = worker_once(conn, storage=storage)
    assets = list_assets_for_job(conn, project_id=project["id"], source_job_id=job["id"])
    failure_asset = next(asset for asset in assets if asset["kind"] == "failure_diagnostics")
    state_asset = next(asset for asset in assets if asset["kind"] == "job_state")
    failure = json.loads(storage.load_bytes(failure_asset["storage_key"]))
    state = json.loads(storage.load_bytes(state_asset["storage_key"]))

    assert result["status"] == "canceled"
    assert failure["reasonCode"] == "user_canceled"
    assert state["status"] == "canceled"


def test_job_progress_overall_ratio_is_monotonic(tmp_path):
    out = tmp_path / "progress"
    main(["extract", str(demo_video()), "--out", str(out), "--mask-provider", "threshold", "--max-frames", "2"])

    ratios = [
        event["progress"]["overallRatio"]
        for event in read_events(out / "events.jsonl")
        if isinstance(event.get("progress"), dict) and "overallRatio" in event["progress"]
    ]

    assert ratios == sorted(ratios)
    assert ratios[-1] == 1.0


def test_job_stage_ratio_is_monotonic_per_stage_and_object(tmp_path):
    run = LocalJobRun(
        run_dir=tmp_path / "stage-ratios",
        run_config={
            "schema": "motionjson.extraction_run_config.v0.1",
            "input": {"path": str(demo_video())},
            "output": {"directory": str(tmp_path / "stage-ratios")},
        },
    )
    run.initialize(video_path=demo_video(), output_dir=tmp_path / "stage-ratios")
    run.start()

    run.emit("initial_masks", "running", "object a later frame", progress={"overallRatio": 0.2, "stageRatio": 0.8}, metadata={"objectId": "a"})
    run.emit("initial_masks", "running", "object a stale frame", progress={"overallRatio": 0.3, "stageRatio": 0.4}, metadata={"objectId": "a"})
    run.emit("initial_masks", "running", "object b first frame", progress={"overallRatio": 0.4, "stageRatio": 0.1}, metadata={"objectId": "b"})

    events = read_events(tmp_path / "stage-ratios" / "events.jsonl")
    progress_events = [event for event in events if event["stage"] == "initial_masks"]

    assert progress_events[0]["progress"]["stageRatio"] == 0.8
    assert progress_events[1]["progress"]["stageRatio"] == 0.8
    assert progress_events[2]["progress"]["stageRatio"] == 0.1
