from __future__ import annotations

import json

from motionjson.backend.assets import get_asset, register_upload
from motionjson.backend.auth import register_user
from motionjson.backend.browser_preview import prepare_browser_preview, probe_video_file
from motionjson.backend.projects import create_project
from motionjson.providers.local_storage import LocalStorageProvider
from motionjson.ui.server import LOCAL_UI_EMAIL
from motionjson.backend.db import connect, initialize_database


def demo_video():
    from pathlib import Path

    return Path(__file__).resolve().parents[1] / "examples" / "demo_red_ball.mp4"


def test_probe_demo_video_reports_mp4v_as_not_browser_safe():
    probe = probe_video_file(demo_video())

    assert probe["status"] == "ready"
    assert probe["codec"] == "mpeg4"
    assert probe["browserSafe"] is False
    assert "browser-safe" in probe["reason"]


def test_prepare_browser_preview_transcodes_demo_video(tmp_path):
    conn = initialize_database(connect(tmp_path / "backend.sqlite"))
    storage = LocalStorageProvider(tmp_path / "storage")
    user = register_user(conn, email=LOCAL_UI_EMAIL, password="local-ui")
    project = create_project(conn, user_id=user["id"], name="Preview Project")
    source = register_upload(
        conn,
        storage=storage,
        user_id=user["id"],
        project_id=project["id"],
        path=demo_video(),
        kind="source_video",
        metadata={"rights_context": {"source_uri": str(demo_video()), "source_type": "user_upload"}},
    )

    preview = prepare_browser_preview(conn, storage=storage, user_id=user["id"], source_asset_id=source["id"], force=True)
    refreshed = get_asset(conn, user_id=user["id"], asset_id=source["id"])
    metadata = json.loads(refreshed["metadata_json"] or "{}")

    assert preview["status"] == "ready"
    assert preview["kind"] in {"source", "transcoded"}
    assert preview["contentAssetId"]
    assert metadata["browser_preview"]["status"] == "ready"
    assert metadata["browser_preview"]["contentAssetId"] == preview["contentAssetId"]
    assert preview["posterAssetId"]

