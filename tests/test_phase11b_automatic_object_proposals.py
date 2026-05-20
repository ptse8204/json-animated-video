from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from motionjson.providers.discovery import SamAutoMasksDiscoveryProvider, object_specs_from_candidates
from motionjson.tracks import RunContext, VideoSource
from motionjson.ui.server import LocalUIApp
from motionjson.video import Frame, VideoInfo


ROOT = Path(__file__).resolve().parents[1]


def demo_video() -> Path:
    return ROOT / "examples" / "demo_red_ball.mp4"


def video_source(count: int = 3) -> VideoSource:
    frames = []
    for index in range(count):
        rgb = np.full((32, 40, 3), 245, dtype=np.uint8)
        rgb[10:18, 6 + index * 3 : 14 + index * 3] = (230, 20, 20)
        rgb[4:10, 26:34] = (20, 90, 220)
        frames.append(Frame(index=index, out_index=index, time_sec=index / 12, rgb=rgb))
    return VideoSource(
        path=Path("tiny.mp4"),
        info=VideoInfo(width=40, height=32, source_fps=12, sample_fps=12, total_source_frames=count),
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


def auto_masks_run_config(video_id: str, output_dir: Path, *, mock: bool = True) -> dict:
    return {
        "schema": "motionjson.extraction_run_config.v0.1",
        "input": {"path": f"local-ui://assets/{video_id}"},
        "output": {"directory": str(output_dir)},
        "objects": [{"object_id": "object_0", "label": "Visible segments"}],
        "sampling": {"sample_fps": 12.0, "max_frames": 2},
        "provider": {
            "name": "mock",
            "threshold": {"lower_hsv": [0, 80, 80], "upper_hsv": [12, 255, 255]},
            "external": {"mask_dir": None},
            "cache": {"enabled": True, "directory": ".motionjson-cache/masks"},
        },
        "discovery": {
            "mode": "sam_auto_masks",
            "config": {
                "mock": mock,
                "keyframes": [0],
                "min_area": 1,
                "max_area_ratio": 0.65,
                "stability_threshold": 0.82,
                "overlap_threshold": 0.72,
                "max_candidates": 3,
                "reject_background": True,
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


def test_phase11b_sam_auto_mock_proposes_multiple_visible_segments_without_gpu(tmp_path):
    candidates = SamAutoMasksDiscoveryProvider().propose(
        video_source(),
        {"mock": True, "max_candidates": 3},
        RunContext(out_dir=tmp_path),
    )
    specs = object_specs_from_candidates(candidates, base_dir=tmp_path)

    assert [candidate.label for candidate in candidates] == ["Visible segment 1", "Visible segment 2", "Visible segment 3"]
    assert all(candidate.metadata["mock"] is True for candidate in candidates)
    assert all(candidate.metadata["maskDir"].startswith("discovery/sam_auto_masks/") for candidate in candidates)
    assert [spec.object_id for spec in specs] == [
        "sam_auto_masks_Visible_segment_1",
        "sam_auto_masks_Visible_segment_2",
        "sam_auto_masks_Visible_segment_3",
    ]


def test_phase11b_local_ui_sam_auto_mock_routes_candidates_to_review_tracks(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    project = api(app, "POST", "/api/projects", {"name": "Phase 11B auto proposals"})["project"]
    video = api(app, "POST", "/api/videos", {"projectId": project["id"], "path": str(demo_video())})["video"]
    run_config = auto_masks_run_config(video["id"], tmp_path / "private-output")

    created = api(app, "POST", "/api/jobs", {"projectId": project["id"], "runConfig": run_config, "run": True})
    job = wait_for_job(app, created["job"]["id"])

    assert job["status"] == "succeeded"
    assert job["payload"]["run_config"]["discovery"]["mode"] == "sam_auto_masks"

    artifact_payload = api(app, "GET", f"/api/jobs/{job['id']}/artifacts")
    artifact_body = json.dumps(artifact_payload, sort_keys=True)
    kinds = {artifact["kind"] for artifact in artifact_payload["artifacts"]}
    assert {"candidate_summary", "track_summary", "fallback_diagnostics"}.issubset(kinds)
    assert str(tmp_path) not in artifact_body
    assert "storage_key" not in artifact_body
    assert "file://" not in artifact_body

    review = artifact_payload["review"]
    candidate_summary = review["candidateSummary"]
    assert candidate_summary["provider"] == "sam_auto_masks"
    assert candidate_summary["config"]["keyframes"] == [0]
    assert [candidate["label"] for candidate in candidate_summary["candidates"]] == [
        "Visible segment 1",
        "Visible segment 2",
        "Visible segment 3",
    ]
    assert review["trackSummary"]["acceptedTracks"] >= 1
    assert len(review["tracks"]) == 3
    assert all(track["objectId"].startswith("sam_auto_masks_Visible_segment_") for track in review["tracks"])
    assert isinstance(review.get("mergeSuggestions", []), list)


def test_phase11b_local_ui_sam_auto_real_path_surfaces_failure_diagnostics(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    project = api(app, "POST", "/api/projects", {"name": "Phase 11B auto failure"})["project"]
    video = api(app, "POST", "/api/videos", {"projectId": project["id"], "path": str(demo_video())})["video"]
    run_config = auto_masks_run_config(video["id"], tmp_path / "private-output", mock=False)

    created = api(app, "POST", "/api/jobs", {"projectId": project["id"], "runConfig": run_config, "run": True})
    job = wait_for_job(app, created["job"]["id"])

    assert job["status"] == "failed"
    artifact_payload = api(app, "GET", f"/api/jobs/{job['id']}/artifacts")
    artifact_body = json.dumps(artifact_payload, sort_keys=True)
    kinds = {artifact["kind"] for artifact in artifact_payload["artifacts"]}
    assert {"failure_diagnostics", "job_logs", "provider_diagnostics"}.issubset(kinds)
    assert artifact_payload["review"]["failure"]["reasonCode"] == "provider_unavailable"
    assert "SAM2_LOCAL_CHECKPOINT" in artifact_body
    assert "storage_key" not in artifact_body
