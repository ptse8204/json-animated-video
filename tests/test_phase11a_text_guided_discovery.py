from __future__ import annotations

import json
import time
from pathlib import Path

from motionjson.ui.server import LocalUIApp


ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = ROOT / "src" / "motionjson" / "ui" / "static"


def demo_video() -> Path:
    return ROOT / "examples" / "demo_red_ball.mp4"


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


def text_detector_run_config(video_id: str, output_dir: Path) -> dict:
    return {
        "schema": "motionjson.extraction_run_config.v0.1",
        "input": {"path": f"local-ui://assets/{video_id}"},
        "output": {"directory": str(output_dir)},
        "objects": [{"object_id": "object_0", "label": "Text targets"}],
        "sampling": {"sample_fps": 12.0, "max_frames": 2},
        "provider": {
            "name": "mock",
            "threshold": {"lower_hsv": [0, 80, 80], "upper_hsv": [12, 255, 255]},
            "external": {"mask_dir": None},
            "cache": {"enabled": True, "directory": ".motionjson-cache/masks"},
        },
        "discovery": {
            "mode": "text_detector",
            "config": {"mock": True, "text": "red ball . hand", "labels": ["red ball", "hand"], "max_candidates": 2},
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


def test_phase11a_local_ui_text_detector_mock_job_routes_candidates_to_tracks(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    project = api(app, "POST", "/api/projects", {"name": "Phase 11A text discovery"})["project"]
    video = api(app, "POST", "/api/videos", {"projectId": project["id"], "path": str(demo_video())})["video"]
    run_config = text_detector_run_config(video["id"], tmp_path / "private-output")

    created = api(app, "POST", "/api/jobs", {"projectId": project["id"], "runConfig": run_config, "run": True})
    job = wait_for_job(app, created["job"]["id"])

    assert job["status"] == "succeeded"
    assert job["payload"]["mask_provider"] == "mock"
    assert job["payload"]["run_config"]["discovery"]["mode"] == "text_detector"

    artifact_payload = api(app, "GET", f"/api/jobs/{job['id']}/artifacts")
    artifact_body = json.dumps(artifact_payload, sort_keys=True)
    kinds = {artifact["kind"] for artifact in artifact_payload["artifacts"]}
    assert {"candidate_summary", "track_summary", "scene_graph"}.issubset(kinds)
    assert str(tmp_path) not in artifact_body
    assert "storage_key" not in artifact_body
    assert "file://" not in artifact_body

    review = artifact_payload["review"]
    candidate_summary = review["candidateSummary"]
    assert candidate_summary["provider"] == "text_detector"
    assert candidate_summary["config"]["mock"] is True
    assert [candidate["label"] for candidate in candidate_summary["candidates"]] == ["red ball", "hand"]
    assert all(candidate["metadata"]["maskDir"].startswith("discovery/text_detector/") for candidate in candidate_summary["candidates"])
    assert {track["objectId"] for track in review["tracks"]} == {"text_detector_red_ball", "text_detector_hand"}
    assert review["fallbackDiagnostics"] == []

    review_payload = api(app, "GET", f"/api/jobs/{job['id']}/review")["review"]
    assert review_payload["candidateSummary"]["provider"] == "text_detector"


def test_phase11a_local_ui_text_detector_real_path_surfaces_failure_diagnostics(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    project = api(app, "POST", "/api/projects", {"name": "Phase 11A real detector failure"})["project"]
    video = api(app, "POST", "/api/videos", {"projectId": project["id"], "path": str(demo_video())})["video"]
    run_config = text_detector_run_config(video["id"], tmp_path / "private-output")
    run_config["discovery"]["config"] = {"mock": False, "text": "red ball"}

    created = api(app, "POST", "/api/jobs", {"projectId": project["id"], "runConfig": run_config, "run": True})
    job = wait_for_job(app, created["job"]["id"])

    assert job["status"] == "failed"
    artifact_payload = api(app, "GET", f"/api/jobs/{job['id']}/artifacts")
    artifact_body = json.dumps(artifact_payload, sort_keys=True)
    kinds = {artifact["kind"] for artifact in artifact_payload["artifacts"]}
    assert {"failure_diagnostics", "job_logs", "provider_diagnostics"}.issubset(kinds)
    assert artifact_payload["review"]["failure"]["reasonCode"] == "provider_unavailable"
    assert "real detector adapters remain capability-gated" in artifact_body
    assert "storage_key" not in artifact_body
    assert "file://" not in artifact_body


def test_phase11a_static_ui_surfaces_candidate_summary_review():
    index = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")
    script = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")
    combined = "\n".join([index, script])

    for marker in (
        'id="candidateSummaryStatus"',
        'id="candidateSummaryList"',
        "renderCandidateSummary",
        "state.jobReview?.candidateSummary",
        "Candidate proposals appear here after text discovery writes candidates.json.",
    ):
        assert marker in combined
