from __future__ import annotations

import json
import time
from pathlib import Path

from motionjson.providers.discovery import ClassDetectorDiscoveryProvider, object_specs_from_candidates
from motionjson.tracks import RunContext, VideoSource
from motionjson.ui.server import LocalUIApp
from motionjson.video import Frame, VideoInfo


ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = ROOT / "src" / "motionjson" / "ui" / "static"


def demo_video() -> Path:
    return ROOT / "examples" / "demo_red_ball.mp4"


def video_source(count: int = 3) -> VideoSource:
    import numpy as np

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


def class_detector_run_config(video_id: str, output_dir: Path, *, mock: bool = True) -> dict:
    return {
        "schema": "motionjson.extraction_run_config.v0.1",
        "input": {"path": f"local-ui://assets/{video_id}"},
        "output": {"directory": str(output_dir)},
        "objects": [{"object_id": "object_0", "label": "Known class targets"}],
        "sampling": {"sample_fps": 12.0, "max_frames": 2},
        "provider": {
            "name": "mock",
            "threshold": {"lower_hsv": [0, 80, 80], "upper_hsv": [12, 255, 255]},
            "external": {"mask_dir": None},
            "cache": {"enabled": True, "directory": ".motionjson-cache/masks"},
        },
        "discovery": {
            "mode": "class_detector",
            "config": {
                "mock": mock,
                "class_preset": "vehicles",
                "classes": ["forklift"],
                "confidence_threshold": 0.4,
                "max_candidates": 3,
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


def test_phase11d_class_detector_preset_proposes_known_classes_without_gpu(tmp_path):
    candidates = ClassDetectorDiscoveryProvider().propose(
        video_source(),
        {"mock": True, "class_preset": "vehicles", "classes": ["forklift"], "confidence_threshold": 0.4, "max_candidates": 3},
        RunContext(out_dir=tmp_path),
    )
    specs = object_specs_from_candidates(candidates, base_dir=tmp_path)

    assert [candidate.label for candidate in candidates] == ["car", "truck", "bus"]
    assert candidates[0].source == "class_detector"
    assert candidates[0].metadata["classPreset"] == "vehicles"
    assert candidates[0].metadata["filters"]["requestedClasses"][-1] == "forklift"
    assert candidates[0].metadata["maskDir"].startswith("discovery/class_detector/")
    assert [spec.object_id for spec in specs] == ["class_detector_car", "class_detector_truck", "class_detector_bus"]


def test_phase11d_local_ui_class_detector_mock_routes_candidates_to_review_tracks(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    project = api(app, "POST", "/api/projects", {"name": "Phase 11D class presets"})["project"]
    video = api(app, "POST", "/api/videos", {"projectId": project["id"], "path": str(demo_video())})["video"]
    run_config = class_detector_run_config(video["id"], tmp_path / "private-output")

    created = api(app, "POST", "/api/jobs", {"projectId": project["id"], "runConfig": run_config, "run": True})
    job = wait_for_job(app, created["job"]["id"])

    assert job["status"] == "succeeded"
    assert job["payload"]["mask_provider"] == "mock"
    assert job["payload"]["run_config"]["discovery"]["mode"] == "class_detector"

    artifact_payload = api(app, "GET", f"/api/jobs/{job['id']}/artifacts")
    artifact_body = json.dumps(artifact_payload, sort_keys=True)
    kinds = {artifact["kind"] for artifact in artifact_payload["artifacts"]}
    assert {"candidate_summary", "track_summary", "fallback_diagnostics"}.issubset(kinds)
    assert str(tmp_path) not in artifact_body
    assert "storage_key" not in artifact_body
    assert "file://" not in artifact_body

    review = artifact_payload["review"]
    candidate_summary = review["candidateSummary"]
    assert candidate_summary["provider"] == "class_detector"
    assert candidate_summary["config"]["class_preset"] == "vehicles"
    assert candidate_summary["config"]["classes"] == ["forklift"]
    assert [candidate["label"] for candidate in candidate_summary["candidates"]] == ["car", "truck", "bus"]
    assert all(candidate["metadata"]["mock"] is True for candidate in candidate_summary["candidates"])
    assert {track["objectId"] for track in review["tracks"]} == {
        "class_detector_car",
        "class_detector_truck",
        "class_detector_bus",
    }
    assert review["fallbackDiagnostics"] == []


def test_phase11d_local_ui_class_detector_real_path_surfaces_failure_diagnostics(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    project = api(app, "POST", "/api/projects", {"name": "Phase 11D class failure"})["project"]
    video = api(app, "POST", "/api/videos", {"projectId": project["id"], "path": str(demo_video())})["video"]
    run_config = class_detector_run_config(video["id"], tmp_path / "private-output", mock=False)

    created = api(app, "POST", "/api/jobs", {"projectId": project["id"], "runConfig": run_config, "run": True})
    job = wait_for_job(app, created["job"]["id"])

    assert job["status"] == "failed"
    artifact_payload = api(app, "GET", f"/api/jobs/{job['id']}/artifacts")
    artifact_body = json.dumps(artifact_payload, sort_keys=True)
    kinds = {artifact["kind"] for artifact in artifact_payload["artifacts"]}
    assert {"failure_diagnostics", "job_logs", "provider_diagnostics"}.issubset(kinds)
    assert artifact_payload["review"]["failure"]["reasonCode"] == "provider_unavailable"
    assert "real discovery adapters remain capability-gated" in artifact_body
    assert "storage_key" not in artifact_body
    assert "file://" not in artifact_body


def test_phase11d_static_ui_exposes_known_class_preset_controls():
    index = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")
    script = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")
    combined = "\n".join([index, script])

    for marker in (
        'data-preset="class_detector"',
        'id="classPreset"',
        'id="classList"',
        "Find known classes",
        "class_detector",
        "class_preset",
    ):
        assert marker in combined
