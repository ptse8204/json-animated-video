from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from motionjson.backend.assets import register_generated_asset
from motionjson.ui.server import LocalUIApp


ROOT = Path(__file__).resolve().parents[1]


def decode(body: bytes) -> dict[str, Any]:
    return json.loads(body.decode("utf-8"))


def api(
    app: LocalUIApp,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    *,
    expected_status: int = 200,
) -> dict[str, Any]:
    body = json.dumps(payload or {}).encode("utf-8") if payload is not None else b""
    status, _headers, response = app.handle(method, path, body=body)
    parsed = decode(response)
    assert status == expected_status, f"{method} {path} returned {status}: {parsed}"
    return parsed


def demo_video() -> Path:
    return ROOT / "examples" / "demo_red_ball.mp4"


def track(object_id: str, label: str, *, frame_offset: int = 0, export_status: str = "accepted") -> dict[str, Any]:
    return {
        "objectId": object_id,
        "label": label,
        "source": "mock",
        "providerName": "mock-video-tracker",
        "zIndex": 10 + frame_offset,
        "confidence": 0.91,
        "frameCount": 3,
        "visibleFrameCount": 3,
        "exportStatus": export_status,
        "warnings": [],
        "metadata": {"fixture": "phase10-track-edit-contract"},
        "frames": [
            {
                "frame": frame,
                "sourceFrameIndex": frame - 1,
                "outIndex": frame - 1,
                "t": round((frame - 1) / 12.0, 6),
                "visible": True,
                "area": 128.0,
                "bbox": [10 + frame_offset + frame, 18, 16, 16],
                "centroid": [18 + frame_offset + frame, 26],
                "contourPoints": 8,
            }
            for frame in range(1, 4)
        ],
    }


def seeded_review_app(tmp_path: Path) -> tuple[LocalUIApp, dict[str, Any], dict[str, Any]]:
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    project = api(app, "POST", "/api/projects", {"name": "Phase 10 correction QA"})["project"]
    video = api(app, "POST", "/api/videos", {"projectId": project["id"], "path": str(demo_video())})["video"]
    job = api(app, "POST", "/api/jobs", {"projectId": project["id"], "videoId": video["id"], "maskProvider": "mock", "maxFrames": 3})["job"]
    tracks_payload = {
        "format": "motionjson.tracks.v0.1",
        "provider": "mock-track-linker",
        "filterReport": {
            "format": "motionjson.track_filter_report.v0.1",
            "summary": {"tracks": 2, "acceptedTracks": 2, "rejectedTracks": 0},
            "mergeSuggestions": [{"keepObjectId": "object_0", "mergeObjectId": "object_1", "meanIou": 0.88, "reason": "duplicate_track"}],
        },
        "fallbackDiagnostics": [],
        "tracks": [track("object_0", "red ball"), track("object_1", "duplicate ball", frame_offset=2)],
    }
    scene_payload = {
        "schema": "motionjson.scene_graph.v0.1",
        "source": {"width": 96, "height": 64, "sampleFps": 12.0, "sampledFrameCount": 3},
        "canvas": {"width": 96, "height": 64, "fps": 12.0, "frame_count": 3},
        "objects": [
            {"id": "object_0", "label": "red ball", "renderMode": "raster", "motion": [{"frame": 1, "visible": True}]},
            {"id": "object_1", "label": "duplicate ball", "renderMode": "raster", "motion": [{"frame": 1, "visible": True}]},
        ],
    }
    conn = app.connection()
    try:
        register_generated_asset(
            conn,
            storage=app.storage(),
            project_id=project["id"],
            source_job_id=job["id"],
            kind="track_summary",
            data=json.dumps(tracks_payload).encode("utf-8"),
            rel_path="tracks.json",
            content_type="application/json",
            metadata={"aiUsage": "none", "fixture": "phase10-track-edit-contract"},
        )
        register_generated_asset(
            conn,
            storage=app.storage(),
            project_id=project["id"],
            source_job_id=job["id"],
            kind="scene_graph",
            data=json.dumps(scene_payload).encode("utf-8"),
            rel_path="scene_graph.json",
            content_type="application/json",
            metadata={"aiUsage": "none", "fixture": "phase10-track-edit-contract"},
        )
    finally:
        conn.close()
    return app, project, job


def tracks_by_id(review: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {track["objectId"]: track for track in review["tracks"]}


def test_phase10_track_edit_operations_update_review_state(tmp_path):
    app, _project, job = seeded_review_app(tmp_path)

    operations = [
        {"type": "relabel_track", "trackId": "object_0", "label": "Hero ball"},
        {"type": "set_track_visibility", "trackId": "object_1", "visible": False},
        {"type": "merge_tracks", "trackIds": ["object_0", "object_1"], "keepTrackId": "object_0"},
        {"type": "split_track", "trackId": "object_0", "newTrackId": "object_0_tail", "frameRange": [2, 3], "label": "Hero ball tail"},
        {
            "type": "add_object",
            "objectId": "object_2",
            "label": "Missing dot",
            "prompts": [{"kind": "positive_point", "frame_index": 1, "data": {"x": 42, "y": 25}}],
            "frameRange": [1, 1],
        },
        {"type": "delete_track", "trackId": "object_1"},
    ]

    for operation in operations:
        response = api(app, "POST", f"/api/jobs/{job['id']}/corrections", {"action": operation})
        assert response["correctionState"]["history"][-1]["type"] == operation["type"]
        assert response["correctionState"]["aiUsage"] == "none"

    review = api(app, "GET", f"/api/jobs/{job['id']}/review")["review"]
    edited = tracks_by_id(review)

    assert edited["object_0"]["label"] == "Hero ball"
    assert edited["object_1"]["visible"] is False
    assert edited["object_1"]["deleted"] is True
    assert edited["object_1"]["exportIncluded"] is False
    assert edited["object_1"]["exportStatus"] == "deleted"
    assert edited["object_0_tail"]["label"] == "Hero ball tail"
    assert edited["object_0_tail"]["source"].endswith("/split")
    assert edited["object_2"]["source"] == "correction/add_object"
    assert edited["object_2"]["exportIncluded"] is True
    assert [entry["type"] for entry in review["correctionHistory"]] == [operation["type"] for operation in operations]


def test_phase10_track_edit_state_persists_after_api_refetch_and_app_reload(tmp_path):
    app, _project, job = seeded_review_app(tmp_path)

    api(app, "POST", f"/api/jobs/{job['id']}/corrections", {"action": {"type": "relabel_track", "trackId": "object_0", "label": "Reload-safe ball"}})
    api(app, "POST", f"/api/jobs/{job['id']}/corrections", {"action": {"type": "delete_track", "trackId": "object_1"}})

    first_refetch = api(app, "GET", f"/api/jobs/{job['id']}/review")["review"]
    assert tracks_by_id(first_refetch)["object_0"]["label"] == "Reload-safe ball"
    assert tracks_by_id(first_refetch)["object_1"]["exportIncluded"] is False

    reloaded_app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    corrections = api(reloaded_app, "GET", f"/api/jobs/{job['id']}/corrections")["correctionState"]
    second_refetch = api(reloaded_app, "GET", f"/api/jobs/{job['id']}/review")["review"]

    assert [entry["type"] for entry in corrections["history"]] == ["relabel_track", "delete_track"]
    assert tracks_by_id(second_refetch)["object_0"]["label"] == "Reload-safe ball"
    assert tracks_by_id(second_refetch)["object_1"]["exportStatus"] == "deleted"


def test_phase10_export_inclusion_uses_edited_track_state(tmp_path):
    app, _project, job = seeded_review_app(tmp_path)

    api(app, "POST", f"/api/jobs/{job['id']}/corrections", {"action": {"type": "delete_track", "trackId": "object_1"}})
    api(
        app,
        "POST",
        f"/api/jobs/{job['id']}/corrections",
        {
            "action": {
                "type": "add_object",
                "objectId": "object_2",
                "label": "Manual object",
                "prompts": [{"kind": "box", "frame_index": 0, "data": {"x": 4, "y": 5, "w": 12, "h": 10}}],
                "frameRange": [0, 0],
            }
        },
    )

    review = api(app, "GET", f"/api/jobs/{job['id']}/review")["review"]
    export_state = review["export"]

    assert export_state["includedObjectIds"] == ["object_0", "object_2"]
    assert export_state["excludedObjectIds"] == ["object_1"]
    assert export_state["source"] == "edited_project_state"
    assert tracks_by_id(review)["object_1"]["exportIncluded"] is False
    assert tracks_by_id(review)["object_2"]["exportIncluded"] is True


def test_phase10_unavailable_repair_returns_useful_diagnostics(tmp_path):
    app, _project, job = seeded_review_app(tmp_path)

    response = api(
        app,
        "POST",
        f"/api/jobs/{job['id']}/corrections",
        {
            "action": {
                "type": "repair_track",
                "trackId": "object_0",
                "frameRange": [0, 2],
                "repairProvider": "sam2-local",
                "correctionRequest": {
                    "schema": "motionjson.correction_request.v0.1",
                    "objectId": "object_0",
                    "operations": [{"type": "add_point", "frame": 2, "x": 40, "y": 24, "radius": 8}],
                    "propagation": {"enabled": True, "mode": "same_coordinates", "frameRange": [1, 3]},
                    "temporalSmoothing": {"enabled": False, "radius": 1, "threshold": 0.5},
                    "aiUsage": "none",
                },
            }
        },
    )
    repair = response["repairDiagnostics"]

    assert repair["status"] == "unavailable"
    assert repair["aiUsage"] == "none"
    assert repair["trackId"] == "object_0"
    assert repair["diagnostics"][0]["code"] == "repair_provider_unavailable"
    assert repair["diagnostics"][0]["provider"] == "sam2-local"
    assert "message" in repair["diagnostics"][0]
    assert repair["diagnostics"][0]["suggestedFixes"]
    assert "traceback" not in json.dumps(repair).lower()
