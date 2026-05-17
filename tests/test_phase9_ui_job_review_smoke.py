from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from motionjson.backend.assets import list_assets_for_job
from motionjson.backend.worker import worker_once
from motionjson.ui.server import LocalUIApp


ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = ROOT / "src" / "motionjson" / "ui" / "static"


def decode(body: bytes) -> dict[str, Any]:
    return json.loads(body.decode("utf-8"))


def demo_video() -> Path:
    return ROOT / "examples" / "demo_red_ball.mp4"


def api(app: LocalUIApp, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = json.dumps(payload or {}).encode("utf-8") if payload is not None else b""
    status, _headers, response = app.handle(method, path, body=body)
    parsed = decode(response)
    assert status == 200, parsed
    return parsed


def stored_json(app: LocalUIApp, asset: dict[str, Any]) -> dict[str, Any]:
    return json.loads(app.storage().load_bytes(asset["storage_key"]).decode("utf-8"))


def test_phase9_local_ui_mock_job_e2e_exposes_progress_artifacts_and_review_payload(tmp_path):
    app = LocalUIApp(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage", mock_mode=True)
    project = api(app, "POST", "/api/projects", {"name": "Phase 9 smoke"})["project"]
    video = api(app, "POST", "/api/videos", {"projectId": project["id"], "path": str(demo_video())})["video"]
    job = api(app, "POST", "/api/jobs", {"projectId": project["id"], "videoId": video["id"], "maxFrames": 2})["job"]

    queued_progress = api(app, "GET", f"/api/progress?projectId={project['id']}")["progress"]
    assert queued_progress[0]["status"] == "pending"
    assert any(event["event_type"] == "queued" for event in queued_progress[0]["events"])

    conn = app.connection()
    try:
        worker_result = worker_once(conn, storage=app.storage(), max_attempts=1)
        db_assets = list_assets_for_job(conn, project_id=project["id"], source_job_id=job["id"])
    finally:
        conn.close()

    assert worker_result is not None
    assert worker_result["status"] == "succeeded"

    public_job = api(app, "GET", f"/api/jobs/{job['id']}")["job"]
    assert public_job["status"] == "succeeded"
    assert public_job["result"]["scene"]["objects"] >= 1

    events_body = app.handle("GET", f"/api/jobs/{job['id']}/events")[2].decode("utf-8")
    events = json.loads(events_body)["events"]
    event_types = {event["event_type"] for event in events}
    assert {"queued", "running", "worker_claimed", "progress", "succeeded"}.issubset(event_types)
    assert any(
        event["event_type"] == "progress" and event.get("metadata", {}).get("stage") in {"video_read", "candidate_discovery", "initial_masks", "track_linking", "export"}
        for event in events
    )
    assert any("overallRatio" in event.get("metadata", {}).get("progress", {}) for event in events)
    assert "storage_key" not in events_body
    assert "file://" not in events_body

    status, _headers, artifacts_response = app.handle("GET", f"/api/jobs/{job['id']}/artifacts")
    artifacts_body = artifacts_response.decode("utf-8")
    artifacts = json.loads(artifacts_body)["artifacts"]
    assert status == 200
    artifact_kinds = {artifact["kind"] for artifact in artifacts}
    assert {"job_events", "job_logs", "artifact_manifest", "track_summary", "fallback_diagnostics", "scene_graph"}.issubset(artifact_kinds)
    assert "storage_key" not in artifacts_body
    assert "file://" not in artifacts_body

    indexed_artifacts = api(app, "GET", f"/api/artifacts?jobId={job['id']}")["artifacts"]
    assert {artifact["id"] for artifact in indexed_artifacts} == {artifact["id"] for artifact in artifacts}

    db_assets_by_kind = {asset["kind"]: asset for asset in db_assets}
    tracks_payload = stored_json(app, db_assets_by_kind["track_summary"])
    fallback_payload = stored_json(app, db_assets_by_kind["fallback_diagnostics"])
    review_payload = {
        "jobId": job["id"],
        "tracks": tracks_payload.get("tracks") or [],
        "fallbackDiagnostics": fallback_payload.get("diagnostics") or [],
        "artifacts": artifacts,
    }

    assert review_payload["tracks"] or review_payload["fallbackDiagnostics"]
    if review_payload["tracks"]:
        track = review_payload["tracks"][0]
        assert track["objectId"]
        assert track["label"]
        assert track.get("source") or track.get("providerName")
        assert track["visibleFrameCount"] >= 1
        assert track["frameCount"] >= track["visibleFrameCount"]
        assert isinstance(track["warnings"], list)
        assert track["exportStatus"] in {"accepted", "rejected", "fallback_raster"}
        assert any(frame.get("visible") for frame in track.get("frames", []))
    else:
        diagnostic = review_payload["fallbackDiagnostics"][0]
        assert diagnostic.get("reasonCode")
        assert diagnostic.get("suggestedFixes")


def test_phase9_frontend_static_smoke_covers_run_and_review_surfaces():
    index = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")
    script = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")
    style = (STATIC_ROOT / "app.css").read_text(encoding="utf-8")
    combined = "\n".join([index, script, style]).lower()
    draw_start = script.find("function drawOverlay")
    draw_end = script.find("\n    function ", draw_start + 1)
    draw_overlay = script[draw_start : draw_end if draw_start != -1 and draw_end != -1 else len(script)]

    def api_call_mentions(fragment: str) -> bool:
        return re.search(r"api\([\s\S]{0,320}" + re.escape(fragment), script) is not None

    job_post_pattern = re.compile(
        r"api\(\s*[`'\"]/api/jobs(?:[`'\"/?$]|\$\{)[\s\S]{0,420}method\s*:\s*[`'\"]POST[`'\"]",
        re.IGNORECASE,
    )

    checks = {
        "job run control": any(
            marker in index
            for marker in (
                'id="runJobButton"',
                'data-action="run-job"',
                "Run mock extraction",
                "Run extraction",
                "Start mock job",
            )
        ),
        "POST /api/jobs from UI": job_post_pattern.search(script) is not None,
        "job selection handler": "data-job-id" in script and re.search(r"jobList[\"']\)\.addEventListener", script) is not None,
        "job event/log fetch": "jobEventLog" in index and api_call_mentions("/events"),
        "artifact fetch or browser": "artifactBrowser" in index and api_call_mentions("/artifacts"),
        "track review surface": any(
            marker in combined
            for marker in (
                'id="tracklist"',
                "track-list",
                "results review",
                "tracks",
                "visibility",
                "include in export",
                "Track Detail",
            )
        ),
        "raster fallback diagnostics": any(marker in combined for marker in ("fallback_diagnostics", "raster fallback", "rasteronlyreason", "raster-only")),
        "review overlay or preview": any(marker in draw_overlay for marker in ("state.reviewTracks", "trackFrameForDisplay", "drawTrackBox"))
        and "normalizePolygonPoints" in script,
    }

    missing = [name for name, present in checks.items() if not present]
    assert not missing, "Phase 9 frontend static smoke missing: " + ", ".join(missing)
