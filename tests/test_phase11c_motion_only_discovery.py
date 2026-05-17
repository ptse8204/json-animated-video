from __future__ import annotations

import json
import time
from pathlib import Path

import cv2
import numpy as np

from motionjson.providers.discovery import MotionForegroundDiscoveryProvider, object_specs_from_candidates
from motionjson.tracks import RunContext, VideoSource
from motionjson.ui.server import LocalUIApp
from motionjson.video import Frame, VideoInfo


ROOT = Path(__file__).resolve().parents[1]


def demo_video() -> Path:
    return ROOT / "examples" / "demo_red_ball.mp4"


def moving_video_source(count: int = 4) -> VideoSource:
    frames = []
    for index in range(count):
        rgb = np.full((48, 64, 3), 244, dtype=np.uint8)
        cv2.circle(rgb, (18 + index * 5, 24), 7, (230, 20, 20), -1)
        frames.append(Frame(index=index, out_index=index, time_sec=index / 12, rgb=rgb))
    return VideoSource(
        path=Path("moving.mp4"),
        info=VideoInfo(width=64, height=48, source_fps=12, sample_fps=12, total_source_frames=count),
        frames=frames,
    )


def decode(body: bytes) -> dict:
    return json.loads(body.decode("utf-8"))


def api(app: LocalUIApp, method: str, path: str, payload: dict | None = None) -> dict:
    body = json.dumps(payload or {}).encode("utf-8") if payload is not None else b""
    status, _headers, response = app.handle(method, path, body=body)
    parsed = decode(response)
    assert status == 200, parsed
    return parsed


def wait_for_job(app: LocalUIApp, job_id: str, *, timeout: float = 10.0) -> dict:
    deadline = time.time() + timeout
    last_job: dict = {}
    while time.time() < deadline:
        last_job = api(app, "GET", f"/api/jobs/{job_id}")["job"]
        if last_job["status"] in {"succeeded", "failed", "canceled"}:
            return last_job
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish; last status: {last_job}")


def motion_run_config(video_id: str, output_dir: Path) -> dict:
    return {
        "schema": "motionjson.extraction_run_config.v0.1",
        "input": {"path": f"local-ui://assets/{video_id}"},
        "output": {"directory": str(output_dir)},
        "objects": [{"object_id": "object_0", "label": "Moving object"}],
        "sampling": {"sample_fps": 12.0, "max_frames": 4},
        "provider": {
            "name": "motion",
            "threshold": {"lower_hsv": [0, 80, 80], "upper_hsv": [12, 255, 255]},
            "external": {"mask_dir": None},
            "cache": {"enabled": True, "directory": ".motionjson-cache/masks"},
        },
        "discovery": {
            "mode": "motion_foreground",
            "config": {
                "threshold": 8,
                "min_area": 1,
                "max_candidates": 2,
                "morph_open": 1,
                "morph_close": 3,
                "keyframes": [0],
            },
        },
        "prompts": [],
        "filters": {"min_area": 1, "simplify_ratio": 0.006},
        "export": {"output_mode": "authoring", "feather": 0, "layer_padding": 4, "sprite_format": "webp", "production_avif": False},
        "rights": {
            "source_type": "user_upload",
            "source_uri": f"local-ui://assets/{video_id}",
            "source_asset_id": video_id,
            "display_text": "Local UI source video",
            "license": "user_uploaded_unverified",
            "license_name": "User uploaded - rights unverified",
            "license_scope": "unknown",
        },
    }


def test_phase11c_motion_foreground_candidates_include_cpu_confidence_without_gpu(tmp_path):
    candidates = MotionForegroundDiscoveryProvider().propose(
        moving_video_source(),
        {"threshold": 8, "min_area": 1, "max_candidates": 2, "morph_open": 1, "morph_close": 3},
        RunContext(out_dir=tmp_path),
    )
    specs = object_specs_from_candidates(candidates, base_dir=tmp_path)

    assert candidates
    assert candidates[0].source == "motion_foreground"
    assert candidates[0].score is not None and candidates[0].score > 0
    assert candidates[0].metadata["maskDir"].startswith("discovery/motion_foreground/")
    assert candidates[0].metadata["filters"]["threshold"] == 8
    assert specs[0].object_id.startswith("motion_")


def test_phase11c_local_ui_motion_foreground_routes_tracks_with_confidence(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    project = api(app, "POST", "/api/projects", {"name": "Phase 11C motion discovery"})["project"]
    video = api(app, "POST", "/api/videos", {"projectId": project["id"], "path": str(demo_video())})["video"]
    run_config = motion_run_config(video["id"], tmp_path / "private-output")

    created = api(app, "POST", "/api/jobs", {"projectId": project["id"], "runConfig": run_config, "run": True})
    job = wait_for_job(app, created["job"]["id"])

    assert job["status"] == "succeeded"
    assert job["payload"]["mask_provider"] == "motion"
    assert job["payload"]["run_config"]["discovery"]["mode"] == "motion_foreground"

    artifact_payload = api(app, "GET", f"/api/jobs/{job['id']}/artifacts")
    artifact_body = json.dumps(artifact_payload, sort_keys=True)
    kinds = {artifact["kind"] for artifact in artifact_payload["artifacts"]}
    assert {"candidate_summary", "track_summary", "fallback_diagnostics"}.issubset(kinds)
    assert str(tmp_path) not in artifact_body
    assert "storage_key" not in artifact_body
    assert "file://" not in artifact_body

    review = artifact_payload["review"]
    candidate_summary = review["candidateSummary"]
    assert candidate_summary["provider"] == "motion_foreground"
    assert candidate_summary["config"]["threshold"] == 8
    assert candidate_summary["candidates"][0]["score"] > 0
    assert review["tracks"]
    assert review["tracks"][0]["confidence"] == candidate_summary["candidates"][0]["score"]
    assert review["tracks"][0]["objectId"].startswith("motion_")
