#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from motionjson.backend.assets import register_generated_asset  # noqa: E402
from motionjson.ui.server import LocalUIApp  # noqa: E402


def decode(body: bytes) -> dict[str, Any]:
    return json.loads(body.decode("utf-8"))


def api(app: LocalUIApp, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = json.dumps(payload or {}).encode("utf-8") if payload is not None else b""
    status, _headers, response = app.handle(method, path, body=body)
    parsed = decode(response)
    if status != 200:
        raise RuntimeError(f"{method} {path} returned {status}: {parsed}")
    return parsed


def seed_job(app: LocalUIApp) -> dict[str, Any]:
    project = api(app, "POST", "/api/projects", {"name": "Phase 10 correction smoke"})["project"]
    video = api(app, "POST", "/api/videos", {"projectId": project["id"], "path": str(ROOT / "examples" / "demo_red_ball.mp4")})["video"]
    job = api(app, "POST", "/api/jobs", {"projectId": project["id"], "videoId": video["id"], "maskProvider": "mock", "maxFrames": 2})["job"]
    tracks = {
        "format": "motionjson.tracks.v0.1",
        "provider": "mock-track-linker",
        "filterReport": {"summary": {"tracks": 2, "acceptedTracks": 2, "rejectedTracks": 0}, "mergeSuggestions": []},
        "fallbackDiagnostics": [],
        "tracks": [
            {
                "objectId": "object_0",
                "label": "red ball",
                "source": "mock",
                "providerName": "mock-video-tracker",
                "frameCount": 2,
                "visibleFrameCount": 2,
                "exportStatus": "accepted",
                "warnings": [],
                "frames": [
                    {"frame": 1, "sourceFrameIndex": 0, "outIndex": 0, "t": 0, "visible": True, "area": 100, "bbox": [10, 20, 14, 14], "centroid": [17, 27], "contourPoints": 8},
                    {"frame": 2, "sourceFrameIndex": 1, "outIndex": 1, "t": 0.083333, "visible": True, "area": 100, "bbox": [11, 20, 14, 14], "centroid": [18, 27], "contourPoints": 8},
                ],
            },
            {
                "objectId": "object_1",
                "label": "duplicate ball",
                "source": "mock",
                "providerName": "mock-video-tracker",
                "frameCount": 2,
                "visibleFrameCount": 2,
                "exportStatus": "accepted",
                "warnings": [],
                "frames": [
                    {"frame": 1, "sourceFrameIndex": 0, "outIndex": 0, "t": 0, "visible": True, "area": 90, "bbox": [12, 20, 14, 14], "centroid": [19, 27], "contourPoints": 8},
                    {"frame": 2, "sourceFrameIndex": 1, "outIndex": 1, "t": 0.083333, "visible": True, "area": 90, "bbox": [13, 20, 14, 14], "centroid": [20, 27], "contourPoints": 8},
                ],
            },
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
            data=json.dumps(tracks).encode("utf-8"),
            rel_path="tracks.json",
            content_type="application/json",
            metadata={"aiUsage": "none", "fixture": "phase10-correction-smoke"},
        )
    finally:
        conn.close()
    return {"project": project, "job": job}


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="motionjson_phase10_smoke_") as tmp:
        root = Path(tmp)
        app = LocalUIApp(db_path=root / "backend.sqlite", storage_root=root / "storage", mock_mode=True)
        seeded = seed_job(app)
        job_id = seeded["job"]["id"]

        api(app, "POST", f"/api/jobs/{job_id}/corrections", {"action": {"type": "relabel_track", "trackId": "object_0", "label": "Smoke-tested ball"}})
        api(app, "POST", f"/api/jobs/{job_id}/corrections", {"action": {"type": "delete_track", "trackId": "object_1"}})
        api(
            app,
            "POST",
            f"/api/jobs/{job_id}/corrections",
            {
                "action": {
                    "type": "add_object",
                    "objectId": "object_2",
                    "label": "Manual smoke object",
                    "prompts": [{"kind": "positive_point", "frame_index": 0, "data": {"x": 32, "y": 24}}],
                    "frameRange": [0, 0],
                }
            },
        )

        reloaded = LocalUIApp(db_path=root / "backend.sqlite", storage_root=root / "storage", mock_mode=True)
        review = api(reloaded, "GET", f"/api/jobs/{job_id}/review")["review"]
        repair = api(
            reloaded,
            "POST",
            f"/api/jobs/{job_id}/corrections",
            {
                "action": {
                    "type": "repair_track",
                    "trackId": "object_0",
                    "frameRange": [0, 1],
                    "repairProvider": "sam2-local",
                    "correctionRequest": {
                        "schema": "motionjson.correction_request.v0.1",
                        "objectId": "object_0",
                        "operations": [{"type": "add_point", "frame": 1, "x": 32, "y": 24, "radius": 8}],
                        "propagation": {"enabled": True, "mode": "same_coordinates", "frameRange": [1, 2]},
                        "temporalSmoothing": {"enabled": False, "radius": 1, "threshold": 0.5},
                        "aiUsage": "none",
                    },
                }
            },
        )["repairDiagnostics"]

        summary = {
            "jobId": job_id,
            "tracks": [track["objectId"] for track in review["tracks"]],
            "includedObjectIds": review["export"]["includedObjectIds"],
            "excludedObjectIds": review["export"]["excludedObjectIds"],
            "repairStatus": repair["status"],
            "diagnosticCodes": [diagnostic["code"] for diagnostic in repair["diagnostics"]],
        }
        print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
