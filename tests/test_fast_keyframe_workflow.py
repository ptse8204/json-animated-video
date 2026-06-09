from __future__ import annotations

import json

from motionjson.backend.assets import list_assets_for_job
from motionjson.backend.jobs import list_job_events
from motionjson.ui.server import LocalUIApp

from test_local_ui_api import decode, demo_video, wait_for_job


def test_keyframe_scan_stops_after_candidates_and_child_tracking_tracks_only_selected(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)

    status, _headers, body = app.handle("POST", "/api/projects", body=json.dumps({"name": "Fast pick"}).encode("utf-8"))
    project = decode(body)["project"]
    status, _headers, body = app.handle(
        "POST",
        "/api/videos",
        body=json.dumps({"projectId": project["id"], "path": str(demo_video())}).encode("utf-8"),
    )
    video = decode(body)["video"]

    keyframe_scan_config = {
        "schema": "motionjson.extraction_run_config.v0.1",
        "input": {"path": f"local-ui://assets/{video['id']}"},
        "output": {"directory": str(tmp_path / "scan-output")},
        "objects": [{"object_id": "object_0", "label": "selected_object"}],
        "sampling": {"sample_fps": 1.0, "max_frames": 1},
        "provider": {"name": "mock"},
        "discovery": {
            "mode": "sam3_auto_masks",
            "config": {
                "mock": True,
                "fastFramePick": True,
                "keyframes": [0],
                "frameIndex": 0,
                "maxCandidatesPerKeyframe": 4,
                "maxObjects": 2,
                "writeRejectedCandidates": True,
            },
        },
        "prompts": [],
        "filters": {"min_area": 1, "simplify_ratio": 0.006},
        "export": {"output_mode": "authoring", "feather": 0, "layer_padding": 4, "sprite_format": "webp", "production_avif": False},
    }
    status, _headers, body = app.handle(
        "POST",
        "/api/jobs",
        body=json.dumps({"projectId": project["id"], "runConfig": keyframe_scan_config, "run": True}).encode("utf-8"),
    )
    scan_job = wait_for_job(app, decode(body)["job"]["id"])
    assert scan_job["status"] == "succeeded"

    status, _headers, body = app.handle("GET", f"/api/jobs/{scan_job['id']}/review")
    review = decode(body)["review"]
    assert status == 200
    assert len(review["candidates"]) >= 1
    assert review["tracks"] == []
    selected_id = review["candidates"][0]["candidateId"]
    assert review["candidates"][0]["scanFrameIndex"] == 0
    assert review["candidates"][0]["labelSource"] in {"provider", "classifier"}

    conn = app.connection()
    try:
        assets = list_assets_for_job(conn, project_id=scan_job["project_id"], source_job_id=scan_job["id"])
        events = list_job_events(conn, job_id=scan_job["id"])
    finally:
        conn.close()
    assert any(event["event_type"] == "candidate_artifacts_registered" for event in events)
    preview_assets = [
        asset
        for asset in assets
        if json.loads(asset["metadata_json"] or "{}").get("rel_path", "").startswith("discovery/")
        and asset["content_type"].startswith("image/")
    ]
    assert preview_assets
    candidate_summary_asset = next(asset for asset in assets if asset["kind"] == "candidate_summary")
    candidate_summary = json.loads(app.storage().load_bytes(candidate_summary_asset["storage_key"]).decode("utf-8"))
    accepted = [item for item in candidate_summary["candidates"] if item["metadata"].get("defaultSelected") is True]
    assert accepted
    assert accepted[0]["metadata"]["fastFramePick"] is True
    assert accepted[0]["metadata"]["maskFiles"] == 1
    assert accepted[0]["metadata"]["fullVideoTrackingDeferred"] is True

    tracking_config = {
        "schema": "motionjson.extraction_run_config.v0.1",
        "input": {"path": f"local-ui://assets/{video['id']}"},
        "output": {"directory": str(tmp_path / "tracking-output")},
        "objects": [{"object_id": "object_0", "label": "selected_object"}],
        "sampling": {"sample_fps": 12.0, "max_frames": 2},
        "provider": {"name": "mock"},
        "discovery": {"mode": "auto_object_proposals", "config": {"mock": True}},
        "prompts": [],
        "filters": {"min_area": 1, "simplify_ratio": 0.006},
        "export": {"output_mode": "authoring", "feather": 0, "layer_padding": 4, "sprite_format": "webp", "production_avif": False},
    }
    status, _headers, body = app.handle(
        "POST",
        f"/api/jobs/{scan_job['id']}/track-selected",
        body=json.dumps(
            {
                "candidateIds": [selected_id],
                "trackMode": "keyframe_selected_only",
                "candidateEdits": [{"candidateId": selected_id, "label": "Hero ball"}],
                "trackingRunConfig": tracking_config,
                "exportReviewRequired": True,
            }
        ).encode("utf-8"),
    )
    payload = decode(body)
    assert status == 202
    assert payload["trackSelected"]["trackMode"] == "keyframe_selected_only"
    tracking_job = wait_for_job(app, payload["trackingJob"]["id"])
    assert tracking_job["status"] == "succeeded"

    status, _headers, body = app.handle("GET", f"/api/jobs/{tracking_job['id']}/review")
    tracked_review = decode(body)["review"]
    assert status == 200
    assert len(tracked_review["tracks"]) == 1
    assert tracked_review["tracks"][0]["label"] == "Hero ball"
    assert tracked_review["tracks"][0]["metadata"]["labelSource"] == "user"
