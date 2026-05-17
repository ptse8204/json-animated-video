from __future__ import annotations

import json
import time
from pathlib import Path

from motionjson.ui.server import LocalUIApp


def demo_video() -> Path:
    return Path(__file__).resolve().parents[1] / "examples" / "demo_red_ball.mp4"


def decode(body: bytes) -> dict:
    return json.loads(body.decode("utf-8"))


def api(app: LocalUIApp, method: str, path: str, payload: dict | None = None) -> dict:
    status, _headers, body = app.handle(
        method,
        path,
        body=json.dumps(payload or {}).encode("utf-8") if payload is not None else b"",
    )
    assert status in {200, 201}, body.decode("utf-8")
    return decode(body)


def wait_for_job(app: LocalUIApp, job_id: str, *, timeout: float = 10.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = api(app, "GET", f"/api/jobs/{job_id}")["job"]
        if job["status"] in {"succeeded", "failed", "canceled"}:
            return job
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish")


def run_mock_job(app: LocalUIApp) -> dict:
    project = api(app, "POST", "/api/projects", {"name": "Correction Project"})["project"]
    video = api(app, "POST", "/api/videos", {"projectId": project["id"], "path": str(demo_video())})["video"]
    job = api(
        app,
        "POST",
        "/api/jobs",
        {"projectId": project["id"], "videoId": video["id"], "maskProvider": "mock", "maxFrames": 2, "run": True},
    )["job"]
    finished = wait_for_job(app, job["id"])
    assert finished["status"] == "succeeded"
    return finished


def review(app: LocalUIApp, job_id: str) -> dict:
    return api(app, "GET", f"/api/jobs/{job_id}/review")["review"]


def test_local_track_edit_export_inclusion_does_not_hide_track(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    job = run_mock_job(app)

    excluded = api(
        app,
        "POST",
        f"/api/jobs/{job['id']}/track-edits",
        {"action": {"type": "set_export_inclusion", "trackId": "object_0", "included": False}},
    )
    track = excluded["review"]["tracks"][0]

    assert excluded["correction"]["operation"] == "set_export_inclusion"
    assert track["visible"] is True
    assert track["exportIncluded"] is False
    assert track["exportStatus"] == "excluded"
    assert excluded["correctionState"]["history"][-1]["type"] == "set_export_inclusion"
    assert excluded["reviewStateManifest"]["kind"] == "review_state_manifest"

    artifacts = api(app, "GET", f"/api/jobs/{job['id']}/artifacts")["artifacts"]
    manifest = next(artifact for artifact in artifacts if artifact["kind"] == "review_state_manifest")
    assert manifest["contentUrl"].startswith("/api/artifacts/")
    status, _headers, body = app.handle("GET", manifest["contentUrl"])
    assert status == 200
    document = decode(body)
    assert document["format"] == "motionjson.local_ui_review_state_manifest.v0.1"
    assert document["correctionEventCount"] == 1
    assert document["review"]["export"]["includedObjectIds"] == []
    assert document["review"]["export"]["excludedObjectIds"] == ["object_0"]
    assert document["review"]["tracks"][0]["exportIncluded"] is False


def test_review_state_manifest_content_redacts_local_paths_and_storage_keys(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    job = run_mock_job(app)

    response = api(
        app,
        "POST",
        f"/api/jobs/{job['id']}/track-edits",
        {
            "action": {
                "type": "repair_track",
                "trackId": "object_0",
                "frameRange": [1, 2],
                "repairProvider": "local-repair-worker",
                "prompts": [
                    {
                        "kind": "box",
                        "frame_index": 0,
                        "data": {
                            "x": 10,
                            "y": 10,
                            "w": 20,
                            "h": 20,
                            "sourcePath": f"file://{tmp_path}/secret-mask.png",
                            "storageKey": "projects/private-job/secret-mask.png",
                        },
                    }
                ],
                "correctionRequest": {
                    "note": f"repair /Users/local/private.mov from projects/private-job/source.json and C:\\Users\\Local\\secret.png",
                    "storageNote": "projects/private-job/sidecar.json",
                },
            }
        },
    )
    manifest = response["reviewStateManifest"]

    status, _headers, body = app.handle("GET", manifest["contentUrl"])
    assert status == 200
    encoded = body.decode("utf-8")
    assert "[LOCAL_PATH_REDACTED]" in encoded
    assert "[STORAGE_KEY_REDACTED]" in encoded
    assert str(tmp_path) not in encoded
    assert "secret-mask" not in encoded
    assert "private-job" not in encoded
    assert "C:\\Users" not in encoded
    assert "storageKey" not in encoded


def test_local_track_edit_api_persists_relabel_hide_show_split_merge_and_delete(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    job = run_mock_job(app)

    relabel = api(
        app,
        "POST",
        f"/api/jobs/{job['id']}/track-edits",
        {"operation": "relabel", "objectId": "object_0", "label": "Cue Ball"},
    )
    assert relabel["correction"]["operation"] == "relabel_track"
    assert relabel["review"]["tracks"][0]["label"] == "Cue Ball"

    reloaded = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    assert review(reloaded, job["id"])["tracks"][0]["label"] == "Cue Ball"
    assert api(reloaded, "GET", f"/api/jobs/{job['id']}/corrections")["corrections"]["history"][0]["type"] == "relabel_track"

    hidden = api(
        reloaded,
        "POST",
        f"/api/jobs/{job['id']}/track-edits",
        {"operation": "hide", "objectId": "object_0"},
    )
    assert hidden["review"]["tracks"][0]["visible"] is False

    shown = api(
        reloaded,
        "POST",
        f"/api/jobs/{job['id']}/track-edits",
        {"operation": "show", "objectId": "object_0"},
    )
    assert shown["review"]["tracks"][0]["exportStatus"] == "accepted"
    assert shown["review"]["tracks"][0]["visible"] is True

    split = api(
        reloaded,
        "POST",
        f"/api/jobs/{job['id']}/track-edits",
        {"operation": "split", "objectId": "object_0", "newObjectId": "object_0_tail", "frameRange": [2, 2]},
    )
    tracks_by_id = {track["objectId"]: track for track in split["review"]["tracks"]}
    assert tracks_by_id["object_0"]["visibleFrameCount"] == 1
    assert tracks_by_id["object_0_tail"]["visibleFrameCount"] == 1

    merged = api(
        reloaded,
        "POST",
        f"/api/jobs/{job['id']}/track-edits",
        {"operation": "merge", "keepObjectId": "object_0", "mergeObjectId": "object_0_tail"},
    )
    assert {track["objectId"] for track in merged["review"]["tracks"]} >= {"object_0", "object_0_tail"}
    assert merged["review"]["tracks"][0]["visibleFrameCount"] == 2

    deleted = api(
        reloaded,
        "POST",
        f"/api/jobs/{job['id']}/track-edits",
        {"operation": "delete", "objectId": "object_0"},
    )
    deleted_track = {track["objectId"]: track for track in deleted["review"]["tracks"]}["object_0"]
    assert deleted_track["deleted"] is True
    assert deleted_track["exportIncluded"] is False

    history = api(reloaded, "GET", f"/api/jobs/{job['id']}/corrections")["corrections"]
    assert [item["type"] for item in history["history"]] == [
        "relabel_track",
        "set_track_visibility",
        "set_track_visibility",
        "split_track",
        "merge_tracks",
        "delete_track",
    ]


def test_add_object_and_repair_are_persisted_no_model_hooks(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    job = run_mock_job(app)

    repair = api(
        app,
        "POST",
        f"/api/jobs/{job['id']}/track-edits",
        {
            "operation": "repair",
            "objectId": "object_0",
            "frameRange": [1, 2],
            "prompts": [{"type": "positive_point", "frame": 1, "x": 10, "y": 12}],
        },
    )
    assert repair["repairDiagnostics"]["status"] == "unavailable"
    assert repair["repairDiagnostics"]["partialRerun"]["available"] is False
    assert repair["correctionState"]["aiUsage"] == "none"
    assert review(app, job["id"])["tracks"][0]["repairRequested"] is True

    add_object = api(
        app,
        "POST",
        f"/api/jobs/{job['id']}/track-edits",
        {
            "operation": "add-object",
            "objectId": "object_1",
            "label": "Missing ball",
            "prompt": {"type": "box", "frame": 1, "x": 8, "y": 9, "w": 20, "h": 18},
        },
    )
    assert add_object["partialRerun"]["available"] is False
    assert {track["objectId"] for track in add_object["review"]["tracks"]} >= {"object_0", "object_1"}

    history = api(app, "GET", f"/api/jobs/{job['id']}/corrections")["corrections"]["history"]
    assert [item["type"] for item in history] == ["repair_track", "add_object"]
    assert history[1]["objectId"] == "object_1"
