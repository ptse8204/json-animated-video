from __future__ import annotations

import json
import time
from pathlib import Path

from motionjson.backend.job_lifecycle import job_lifecycle_summary
from motionjson.backend.jobs import record_job_event
from motionjson.ui.server import LocalUIApp


def decode(body: bytes) -> dict:
    return json.loads(body.decode("utf-8"))


def demo_video() -> Path:
    return Path(__file__).resolve().parents[1] / "examples" / "demo_red_ball.mp4"


def wait_for_job(app: LocalUIApp, job_id: str, *, timeout: float = 10.0) -> dict:
    deadline = time.time() + timeout
    last_job = {}
    while time.time() < deadline:
        status, _headers, body = app.handle("GET", f"/api/jobs/{job_id}")
        assert status == 200
        last_job = decode(body)["job"]
        if last_job["status"] in {"succeeded", "failed", "canceled"}:
            return last_job
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish; last status: {last_job}")


def test_job_lifecycle_reports_unknown_progress_without_precision():
    job = {
        "id": "job_queued",
        "project_id": "project_1",
        "type": "extract",
        "status": "pending",
        "payload": {"mask_provider": "sam2-local"},
        "result": {},
    }

    lifecycle = job_lifecycle_summary(job)

    assert lifecycle["status"] == "queued"
    assert lifecycle["phase"] == "queued"
    assert lifecycle["progress"] == {"known": False, "percent": 0, "label": "Queued"}
    assert lifecycle["provider"]["label"] == "SAM2 local"
    assert lifecycle["actions"]["canCancel"] is True


def test_job_lifecycle_uses_event_progress_when_known():
    job = {
        "id": "job_running",
        "project_id": "project_1",
        "type": "extract",
        "status": "running",
        "payload": {"run_config": {"provider": {"name": "sam3-hosted", "sam3": {"hosted_config": {"profile": "roboflow-sam3-pcs"}}}}},
        "result": {},
    }
    events = [
        {
            "event_type": "progress",
            "message": "discovering candidates",
            "metadata": {"stage": "candidate_discovery", "progress": {"overallRatio": 0.42}},
            "created_at": "2026-05-24T00:00:00+00:00",
        }
    ]

    lifecycle = job_lifecycle_summary(job, events=events)

    assert lifecycle["status"] == "running"
    assert lifecycle["phase"] == "discovering"
    assert lifecycle["progress"] == {"known": True, "percent": 42, "label": "Candidate discovery"}
    assert lifecycle["provider"]["connectionId"] == "sam3-hosted:roboflow-sam3-pcs"
    assert lifecycle["provider"]["label"] == "Roboflow SAM3"
    assert lifecycle["provider"]["engine"] == "sam3"


def test_job_lifecycle_provider_matrix_keeps_ids_labels_and_locality():
    cases = [
        (
            "sam2 hosted",
            {
                "payload": {
                    "run_config": {
                        "provider": {
                            "name": "sam2-hosted",
                            "sam2": {"hosted_config": {"profile": "replicate-sam2-video"}, "hosted_allow_network": True},
                        }
                    }
                }
            },
            {
                "id": "sam2-hosted",
                "connectionId": "sam2-hosted:replicate-sam2-video",
                "label": "Replicate SAM2 video",
                "engine": "sam2",
                "locality": "hosted",
                "hostedCallsAllowed": True,
            },
        ),
        (
            "sam3 hosted",
            {
                "payload": {
                    "run_config": {
                        "provider": {
                            "name": "sam3-hosted",
                            "sam3": {"hosted_config": {"profile": "fal-sam3-image"}, "hostedAllowNetwork": True},
                        },
                        "discovery": {"mode": "sam3_exemplar"},
                    }
                }
            },
            {
                "id": "sam3-hosted",
                "connectionId": "sam3-hosted:fal-sam3-image",
                "label": "Fal SAM3 image",
                "engine": "sam3",
                "locality": "hosted",
                "hostedCallsAllowed": True,
            },
        ),
        (
            "motion foreground",
            {"payload": {"mask_provider": "motion_foreground"}},
            {
                "id": "motion_foreground",
                "connectionId": "motion_foreground",
                "label": "Motion foreground",
                "engine": "motion",
                "locality": "no_model",
                "hostedCallsAllowed": False,
            },
        ),
        (
            "imported masks",
            {"payload": {"run_config": {"provider": {"name": "external_masks"}, "discovery": {"mode": "external_masks"}}}},
            {
                "id": "external_masks",
                "connectionId": "external_masks",
                "label": "Imported masks",
                "engine": "external_masks",
                "locality": "no_model",
                "hostedCallsAllowed": False,
            },
        ),
        (
            "sam3 scene sweep runtime",
            {"payload": {"run_config": {"provider": {"name": "sam3-local"}, "discovery": {"mode": "sam3_auto_masks"}}}},
            {
                "id": "sam3-local",
                "connectionId": "sam3-local",
                "label": "SAM3 Scene Sweep runtime",
                "engine": "sam3",
                "locality": "local",
                "hostedCallsAllowed": False,
            },
        ),
    ]

    for name, partial_job, expected in cases:
        job = {
            "id": f"job_{name.replace(' ', '_')}",
            "project_id": "project_1",
            "type": "extract",
            "status": "pending",
            "result": {},
            **partial_job,
        }

        lifecycle = job_lifecycle_summary(job)

        assert lifecycle["provider"] == expected


def test_job_lifecycle_canceled_job_has_no_cancel_or_retry_actions():
    job = {
        "id": "job_canceled",
        "project_id": "project_1",
        "type": "extract",
        "status": "canceled",
        "payload": {"mask_provider": "mock"},
        "result": {},
    }
    events = [{"event_type": "canceled", "message": "User canceled the extraction."}]

    lifecycle = job_lifecycle_summary(job, events=events)

    assert lifecycle["status"] == "canceled"
    assert lifecycle["phase"] == "complete"
    assert lifecycle["failure"]["reasonCode"] == "user_canceled"
    assert lifecycle["actions"]["canCancel"] is False
    assert lifecycle["actions"]["canRetry"] is False
    assert lifecycle["nextAction"]["label"] == "Open logs"


def test_job_lifecycle_success_event_overrides_late_cancel_requested_status():
    job = {
        "id": "job_late_cancel",
        "project_id": "project_1",
        "type": "extract",
        "status": "cancel_requested",
        "payload": {"run_config": {"provider": {"name": "sam3-local"}}},
        "result": {},
    }
    events = [
        {
            "event_type": "job_succeeded",
            "message": "job completed",
            "metadata": {"stage": "succeeded"},
            "created_at": "2026-06-04T04:14:08Z",
        },
        {
            "event_type": "cancellation_requested",
            "message": "user_canceled",
            "metadata": {"reason": "user_canceled"},
            "created_at": "2026-06-04T04:17:51Z",
        },
    ]

    lifecycle = job_lifecycle_summary(job, events=events)

    assert lifecycle["status"] == "succeeded"
    assert lifecycle["rawStatus"] == "cancel_requested"
    assert lifecycle["phase"] == "complete"
    assert lifecycle["progress"]["percent"] == 100
    assert lifecycle["actions"]["canCancel"] is False


def test_job_lifecycle_finalizes_review_assets_until_readiness_is_true():
    job = {
        "id": "job_finalizing",
        "project_id": "project_1",
        "type": "extract",
        "status": "succeeded",
        "payload": {"run_config": {"provider": {"name": "sam3-local"}, "discovery": {"mode": "sam3_auto_masks"}}},
        "readiness": {
            "workerComplete": True,
            "artifactsRegistered": True,
            "reviewPayloadReady": True,
            "previewToolsReady": False,
            "readyForReview": False,
            "blockedReasonCode": "preview_tools_missing",
            "blockedReason": "Preview tools are missing: preview/canvas_player.html.",
        },
        "result": {},
    }
    events = [
        {
            "event_type": "succeeded",
            "message": "job completed",
            "metadata": {"stage": "succeeded", "progress": {"overallRatio": 1.0}},
            "created_at": "2026-06-04T04:14:08Z",
        }
    ]

    lifecycle = job_lifecycle_summary(job, events=events)

    assert lifecycle["status"] == "finalizing_review"
    assert lifecycle["phase"] == "finalizing_review_assets"
    assert lifecycle["progress"]["percent"] == 99
    assert lifecycle["nextAction"]["label"] == "Wait for review assets"
    assert lifecycle["actions"]["canExport"] is False


def test_job_lifecycle_summarizes_failure_and_recovery_action():
    job = {
        "id": "job_failed",
        "project_id": "project_1",
        "type": "extract",
        "status": "failed",
        "payload": {"run_config": {"provider": {"name": "sam3-local"}}},
        "error": "SAM3 model path is not configured",
        "result": {},
    }

    lifecycle = job_lifecycle_summary(job)

    assert lifecycle["status"] == "failed"
    assert lifecycle["phase"] == "failed"
    assert lifecycle["progress"] == {"known": False, "percent": 0, "label": "Failed"}
    assert lifecycle["failure"]["headline"] == "SAM3 is not ready"
    assert lifecycle["failure"]["reasonCode"] == "provider_unavailable"
    assert lifecycle["nextAction"]["label"] == "Open logs"
    assert lifecycle["actions"]["canRetry"] is False


def test_job_lifecycle_summarizes_asset_preparation_stall():
    job = {
        "id": "job_asset_stalled",
        "project_id": "project_1",
        "type": "extract",
        "status": "failed",
        "payload": {"run_config": {"provider": {"name": "sam3-local"}}},
        "error": "Raster asset preparation stalled after frame 1/48 for sam3_grid_024. No export artifacts were produced.",
        "result": {},
    }
    events = [
        {
            "event_type": "asset_preparation_stalled",
            "message": "Raster asset preparation stalled after frame 1/48 for sam3_grid_024. No export artifacts were produced.",
            "metadata": {
                "stage": "asset_preparation",
                "reasonCode": "asset_preparation_stalled",
                "objectId": "sam3_grid_024",
            },
            "created_at": "2026-06-03T04:45:37+00:00",
        }
    ]

    lifecycle = job_lifecycle_summary(job, events=events)

    assert lifecycle["status"] == "failed"
    assert lifecycle["failure"]["headline"] == "Raster asset preparation stalled"
    assert lifecycle["failure"]["reasonCode"] == "asset_preparation_stalled"
    assert lifecycle["failure"]["suggestedAction"] == "Retry asset preparation from the current setup, or return to Model setup before starting a new run."
    assert lifecycle["actions"]["canRetry"] is True
    assert lifecycle["actions"]["canRetryAssetPreparation"] is True
    assert lifecycle["actions"]["canExport"] is False
    assert lifecycle["nextAction"]["label"] == "Retry asset prep"


def test_job_lifecycle_summarizes_typed_asset_preparation_failures():
    frame_timeout_job = {
        "id": "job_asset_frame_timeout",
        "project_id": "project_1",
        "type": "extract",
        "status": "failed",
        "payload": {"run_config": {"provider": {"name": "sam3-local"}}},
        "error": "Raster asset preparation timed out on frame 13/48 for sam3_grid_024. No frame-finished event arrived.",
        "result": {},
    }
    heartbeat_job = {
        **frame_timeout_job,
        "id": "job_worker_heartbeat_stale",
        "error": "Worker heartbeat stopped during asset preparation after frame 1/48 for sam3_grid_024. No export artifacts were produced.",
    }

    frame_timeout = job_lifecycle_summary(frame_timeout_job)
    heartbeat_stale = job_lifecycle_summary(heartbeat_job)

    assert frame_timeout["failure"]["headline"] == "Asset prep frame timed out"
    assert frame_timeout["failure"]["reasonCode"] == "asset_preparation_frame_timeout"
    assert frame_timeout["actions"]["canRetryAssetPreparation"] is True
    assert frame_timeout["nextAction"]["label"] == "Retry asset prep"
    assert heartbeat_stale["failure"]["headline"] == "Worker heartbeat stopped"
    assert heartbeat_stale["failure"]["reasonCode"] == "worker_heartbeat_stale"
    assert heartbeat_stale["actions"]["canRetryAssetPreparation"] is True
    assert heartbeat_stale["nextAction"]["label"] == "Retry asset prep"


def test_job_lifecycle_gates_candidates_tracks_and_exports():
    job = {
        "id": "job_review",
        "project_id": "project_1",
        "type": "extract",
        "status": "succeeded",
        "payload": {"run_config": {"provider": {"name": "mock"}, "discovery": {"mode": "auto_object_proposals"}}},
        "result": {},
    }

    candidates = job_lifecycle_summary(
        job,
        review={
            "candidateSummary": {"candidateCount": 2, "defaultSelectedCount": 1},
            "candidates": [{"candidateId": "cand_001"}, {"candidateId": "cand_002"}],
            "tracks": [],
        },
    )
    assert candidates["status"] == "waiting_review"
    assert candidates["review"]["candidateCount"] == 2
    assert candidates["review"]["selectedCandidateCount"] == 1
    assert candidates["actions"]["canTrackSelected"] is True
    assert candidates["actions"]["canExport"] is False

    pending_tracks = job_lifecycle_summary(
        job,
        review={"tracks": [{"objectId": "cand_001", "exportStatus": "review_pending"}]},
    )
    assert pending_tracks["status"] == "waiting_review"
    assert pending_tracks["review"]["trackCount"] == 1
    assert pending_tracks["review"]["exportableTrackCount"] == 0
    assert pending_tracks["nextAction"]["label"] == "Mark reviewed"

    export_ready = job_lifecycle_summary(
        job,
        review={"tracks": [{"objectId": "object_0", "exportStatus": "accepted", "exportIncluded": True}]},
    )
    assert export_ready["status"] == "succeeded"
    assert export_ready["actions"]["canExport"] is True
    assert export_ready["nextAction"]["label"] == "Export reviewed objects"


def test_local_ui_progress_and_workspace_include_job_center_lifecycle(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)

    status, _headers, body = app.handle("POST", "/api/projects", body=json.dumps({"name": "Lifecycle Project"}).encode("utf-8"))
    project = decode(body)["project"]
    status, _headers, body = app.handle(
        "POST",
        "/api/videos",
        body=json.dumps({"projectId": project["id"], "path": str(demo_video())}).encode("utf-8"),
    )
    video = decode(body)["video"]
    status, _headers, body = app.handle(
        "POST",
        "/api/jobs",
        body=json.dumps({"projectId": project["id"], "videoId": video["id"], "maskProvider": "mock", "maxFrames": 2}).encode("utf-8"),
    )
    job = decode(body)["job"]
    assert status == 200
    assert job["lifecycle"]["status"] == "queued"

    conn = app.connection()
    try:
        record_job_event(
            conn,
            job_id=job["id"],
            event_type="progress",
            message="candidate discovery",
            metadata={"stage": "candidate_discovery", "progress": {"overallRatio": 0.5}},
        )
    finally:
        conn.close()

    status, _headers, body = app.handle("GET", f"/api/progress?projectId={project['id']}")
    payload = decode(body)
    lifecycle = payload["progress"][0]["lifecycle"]
    assert status == 200
    assert lifecycle["progress"]["known"] is True
    assert lifecycle["progress"]["percent"] == 50
    assert payload["jobCenter"]["selectedJobId"] == job["id"]
    assert payload["jobCenter"]["activeJobsCount"] == 1

    status, _headers, body = app.handle("GET", "/api/workspace")
    workspace = decode(body)
    assert status == 200
    assert workspace["jobCenter"]["recentJobs"][0]["lifecycle"]["jobId"] == job["id"]
    assert "storage_key" not in body.decode("utf-8")


def test_local_ui_job_lifecycle_redacts_failure_paths(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    status, _headers, body = app.handle("POST", "/api/projects", body=json.dumps({"name": "Redacted Failure"}).encode("utf-8"))
    project = decode(body)["project"]
    status, _headers, body = app.handle(
        "POST",
        "/api/videos",
        body=json.dumps({"projectId": project["id"], "path": str(demo_video())}).encode("utf-8"),
    )
    video = decode(body)["video"]
    status, _headers, body = app.handle(
        "POST",
        "/api/jobs",
        body=json.dumps({"projectId": project["id"], "videoId": video["id"], "maskProvider": "sam3-local", "maxFrames": 1}).encode("utf-8"),
    )
    job = decode(body)["job"]
    conn = app.connection()
    try:
        conn.execute(
            "UPDATE jobs SET status = 'failed', error = ? WHERE id = ?",
            (f"SAM3 model path is not configured at {tmp_path / 'private' / 'sam3.pt'}", job["id"]),
        )
        conn.commit()
    finally:
        conn.close()

    status, _headers, body = app.handle("GET", f"/api/jobs/{job['id']}")
    payload = decode(body)
    public_text = body.decode("utf-8")

    assert status == 200
    assert payload["job"]["lifecycle"]["failure"]["reasonCode"] == "provider_unavailable"
    assert "[LOCAL_PATH_REDACTED]" in public_text
    assert str(tmp_path) not in public_text


def test_local_ui_job_poll_reconciles_stale_asset_preparation(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    status, _headers, body = app.handle("POST", "/api/projects", body=json.dumps({"name": "Stale Asset Prep"}).encode("utf-8"))
    project = decode(body)["project"]
    status, _headers, body = app.handle(
        "POST",
        "/api/videos",
        body=json.dumps({"projectId": project["id"], "path": str(demo_video())}).encode("utf-8"),
    )
    video = decode(body)["video"]
    status, _headers, body = app.handle(
        "POST",
        "/api/jobs",
        body=json.dumps({"projectId": project["id"], "videoId": video["id"], "maskProvider": "sam3-local", "maxFrames": 48}).encode("utf-8"),
    )
    job = decode(body)["job"]
    stale_at = "2000-01-01T00:00:00+00:00"
    conn = app.connection()
    try:
        conn.execute("UPDATE jobs SET status = 'running', updated_at = ? WHERE id = ?", (stale_at, job["id"]))
        conn.execute("UPDATE queue_items SET status = 'running' WHERE job_id = ?", (job["id"],))
        conn.execute("UPDATE job_events SET created_at = ? WHERE job_id = ?", ("1999-12-31T23:59:00+00:00", job["id"]))
        conn.commit()
        event = record_job_event(
            conn,
            job_id=job["id"],
            event_type="progress",
            message="prepared raster asset frame 1/48 for sam3_grid_024",
            metadata={
                "stage": "asset_preparation",
                "progress": {"overallRatio": 0.73, "current": 1, "total": 48},
                "metadata": {"objectId": "sam3_grid_024"},
            },
        )
        conn.execute("UPDATE job_events SET created_at = ? WHERE id = ?", (stale_at, event["id"]))
        conn.commit()
    finally:
        conn.close()

    status, _headers, body = app.handle("GET", f"/api/jobs/{job['id']}")
    payload = decode(body)

    assert status == 200
    assert payload["job"]["status"] == "failed"
    assert payload["job"]["lifecycle"]["failure"]["reasonCode"] == "worker_heartbeat_stale"
    assert payload["job"]["lifecycle"]["nextAction"]["label"] == "Retry asset prep"
    assert payload["job"]["lifecycle"]["actions"]["canRetryAssetPreparation"] is True
    assert any(event["event_type"] == "worker_heartbeat_stale" for event in payload["job"]["events"])


def test_completed_mock_job_lifecycle_reports_review_export_gate(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    status, _headers, body = app.handle("POST", "/api/projects", body=json.dumps({"name": "Review Lifecycle"}).encode("utf-8"))
    project = decode(body)["project"]
    status, _headers, body = app.handle(
        "POST",
        "/api/videos",
        body=json.dumps({"projectId": project["id"], "path": str(demo_video())}).encode("utf-8"),
    )
    video = decode(body)["video"]
    status, _headers, body = app.handle(
        "POST",
        "/api/jobs",
        body=json.dumps({"projectId": project["id"], "videoId": video["id"], "maskProvider": "mock", "maxFrames": 2, "run": True}).encode("utf-8"),
    )
    job = wait_for_job(app, decode(body)["job"]["id"])

    status, _headers, body = app.handle("GET", f"/api/jobs/{job['id']}")
    lifecycle = decode(body)["job"]["lifecycle"]

    assert status == 200
    assert lifecycle["status"] in {"succeeded", "waiting_review"}
    assert lifecycle["review"]["trackCount"] >= 1
    assert lifecycle["actions"]["canReview"] is True
    assert lifecycle["review"]["exportableTrackCount"] >= 1


def test_object_manifest_review_surfaces_partial_track_metadata():
    review = {"objects": [], "tracks": []}
    document = {
        "format": "motionjson.object_manifest.v0.1",
        "objectId": "sam3_grid_023",
        "label": "SAM3 grid 023",
        "renderMode": "raster_alpha_sequence",
        "recommendedOutput": "raster_alpha_sequence",
        "motion": [
            {
                "frame": 1,
                "sourceFrameIndex": 0,
                "t": 0.0,
                "visible": True,
                "x": 10,
                "y": 12,
                "w": 24,
                "h": 18,
                "asset": "objects/sam3_grid_023/cutouts/cutout_000001.png",
                "mask": "masks/sam3_grid_023/mask_000001.png",
            }
        ],
        "discovery": {"candidateProvider": "sam3_auto_masks"},
    }

    LocalUIApp._apply_object_manifest_review(review, document)
    LocalUIApp._apply_object_manifest_review(review, document)

    assert len(review["objects"]) == 1
    assert len(review["tracks"]) == 1
    assert review["objects"][0]["objectId"] == "sam3_grid_023"
    assert review["objects"][0]["visibleFrameCount"] == 1
    assert review["tracks"][0]["metadata"]["partialObjectManifest"] is True
    assert review["tracks"][0]["frames"][0]["asset"] == "objects/sam3_grid_023/cutouts/cutout_000001.png"
