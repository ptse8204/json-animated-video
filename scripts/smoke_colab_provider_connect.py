from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from motionjson.ui.server import LocalUIApp


def _decode(body: bytes) -> dict:
    return json.loads(body.decode("utf-8"))


def _request(app: LocalUIApp, method: str, path: str, payload: dict | None = None) -> dict:
    status, _headers, body = app.handle(
        method,
        path,
        body=json.dumps(payload or {}).encode("utf-8") if payload is not None else b"",
    )
    if status >= 400:
        raise RuntimeError(f"{method} {path} failed with {status}: {body.decode('utf-8')}")
    return _decode(body)


def run_smoke(*, mock: bool) -> dict:
    repo_root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="motionjson-colab-provider-smoke-") as tmp:
        root = Path(tmp)
        app = LocalUIApp(db_path=root / "backend.sqlite", storage_root=root / "storage", mock_mode=mock)
        health = _request(app, "GET", "/api/health")
        capabilities = _request(app, "GET", "/api/capabilities")

        video_path = root / "demo_red_ball.mp4"
        subprocess.run(
            [sys.executable, str(repo_root / "examples" / "make_demo_video.py"), "--out", str(video_path)],
            check=True,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
        )
        project_payload = _request(app, "POST", "/api/projects", {"name": "Colab provider smoke"})
        project_id = project_payload["project"]["id"]
        video_payload = _request(app, "POST", "/api/videos", {"projectId": project_id, "path": str(video_path)})

        sam2_model_dir = root / "mock-sam2-from-pretrained"
        sam2_model_dir.mkdir()
        (sam2_model_dir / "config.json").write_text('{"model_type":"sam2"}\n', encoding="utf-8")
        sam3_model_dir = root / "mock-sam3-from-pretrained"
        sam3_model_dir.mkdir()
        (sam3_model_dir / "config.json").write_text('{"model_type":"sam3"}\n', encoding="utf-8")

        sam2_cache = _request(
            app,
            "POST",
            "/api/provider-settings/sam2-hf-auto-masks/setup/start",
            {
                "action": "cache_model",
                "runInline": True,
                "allowNetwork": True,
                "allowDisk": True,
                "model": str(sam2_model_dir),
            },
        )
        sam3_cache = _request(
            app,
            "POST",
            "/api/provider-settings/sam3-local/setup/start",
            {
                "action": "cache_model",
                "runInline": True,
                "allowNetwork": True,
                "allowDisk": True,
                "model": str(sam3_model_dir),
            },
        )
        settings = _request(app, "GET", "/api/provider-settings")
        providers = {provider["id"]: provider for provider in settings["providers"]}
        return {
            "status": "ok",
            "mockMode": bool(health.get("mockMode")),
            "routesChecked": ["/api/health", "/api/capabilities", "/api/projects", "/api/provider-settings"],
            "providerCount": len(capabilities.get("providers", [])),
            "videoRegistered": bool(video_payload.get("video", {}).get("id")),
            "localModelCache": {
                "sam2-hf-auto-masks": providers["sam2-hf-auto-masks"]["modelCache"],
                "sam3-local": providers["sam3-local"]["modelCache"],
            },
            "setupJobs": {
                "sam2-hf-auto-masks": sam2_cache["setupJob"]["status"],
                "sam3-local": sam3_cache["setupJob"]["status"],
            },
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke the Colab provider-connect local/mock path without live Colab or real model downloads.")
    parser.add_argument("--mock", action="store_true", help="Run the Local UI backend in mock mode.")
    args = parser.parse_args()
    result = run_smoke(mock=args.mock)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
