from __future__ import annotations

import json
import sqlite3
import zipfile
from pathlib import Path

from motionjson.backend.assets import list_assets_for_job, register_upload
from motionjson.backend.auth import register_user
from motionjson.backend.db import initialize_database
from motionjson.backend.jobs import enqueue_export_job, enqueue_extract_job
from motionjson.backend.projects import create_project
from motionjson.backend.rights import list_asset_lineage, list_asset_rights, list_audit_events
from motionjson.backend.worker import worker_once
from motionjson.providers.local_storage import LocalStorageProvider


def backend(tmp_path):
    conn = sqlite3.connect(tmp_path / "backend.sqlite")
    conn.row_factory = sqlite3.Row
    initialize_database(conn)
    storage = LocalStorageProvider(tmp_path / "storage")
    user = register_user(conn, email="rights@example.com", password="pw")
    project = create_project(conn, user_id=user["id"], name="Rights Project")
    return conn, storage, user, project


def demo_video() -> Path:
    return Path(__file__).resolve().parents[1] / "examples" / "demo_red_ball.mp4"


def test_backend_upload_extract_and_export_record_rights_lineage_and_audit(tmp_path):
    conn, storage, user, project = backend(tmp_path)
    upload = register_upload(
        conn,
        storage=storage,
        user_id=user["id"],
        project_id=project["id"],
        path=demo_video(),
        kind="source_video",
        metadata={
            "rights_context": {
                "source_uri": "examples/demo_red_ball.mp4",
                "display_text": "Demo red ball source",
                "license": "user_uploaded_unverified",
            }
        },
    )

    upload_rights = list_asset_rights(conn, asset_id=upload["id"])
    assert len(upload_rights) == 1
    assert json.loads(upload_rights[0]["rights_json"])["sourceAttribution"]["displayText"] == "Demo red ball source"
    assert any(event["event_type"] == "asset_uploaded" for event in list_audit_events(conn, asset_id=upload["id"]))

    extract = enqueue_extract_job(
        conn,
        user_id=user["id"],
        project_id=project["id"],
        asset_id=upload["id"],
        mask_provider="threshold",
        max_frames=2,
        rights_context={"display_text": "Demo red ball source", "source_uri": "examples/demo_red_ball.mp4"},
    )
    assert worker_once(conn, storage=storage)["status"] == "succeeded"

    extract_assets = list_assets_for_job(conn, project_id=project["id"], source_job_id=extract["id"])
    kinds = {asset["kind"] for asset in extract_assets}
    assert "rights_manifest" in kinds
    assert any(row["source_asset_id"] == upload["id"] for row in list_asset_lineage(conn, asset_id=upload["id"]))
    assert conn.execute("SELECT COUNT(*) FROM rights_metadata WHERE object_id = 'object_0'").fetchone()[0] > 0
    assert any(event["event_type"] == "extract_completed" for event in list_audit_events(conn, job_id=extract["id"]))

    export = enqueue_export_job(
        conn,
        user_id=user["id"],
        project_id=project["id"],
        source_job_id=extract["id"],
        format="website-zip",
    )
    assert worker_once(conn, storage=storage)["status"] == "succeeded"

    package_asset = next(asset for asset in list_assets_for_job(conn, project_id=project["id"], source_job_id=export["id"]) if asset["kind"] == "website_package")
    package_rights = list_asset_rights(conn, asset_id=package_asset["id"])
    package_lineage = list_asset_lineage(conn, asset_id=package_asset["id"])
    package_path = tmp_path / "package.zip"
    package_path.write_bytes(storage.load_bytes(package_asset["storage_key"]))

    assert json.loads(package_rights[0]["rights_json"])["sourceAttribution"]["displayText"] == "Demo red ball source"
    assert package_lineage[0]["operation"] == "export_website_package"
    assert package_lineage[0]["source_asset_id"] == upload["id"]
    assert any(event["event_type"] == "website_package_exported" for event in list_audit_events(conn, job_id=export["id"]))
    with zipfile.ZipFile(package_path) as archive:
        assert "rights_manifest.json" in archive.namelist()


def test_backend_extract_defaults_preserve_uploaded_source_attribution(tmp_path):
    conn, storage, user, project = backend(tmp_path)
    upload = register_upload(
        conn,
        storage=storage,
        user_id=user["id"],
        project_id=project["id"],
        path=demo_video(),
        kind="source_video",
        metadata={
            "rights_context": {
                "source_uri": "original://demo_red_ball.mp4",
                "display_text": "Original uploaded source",
                "license": "uploaded_source_license",
                "license_name": "Uploaded source license",
                "license_scope": "commercial",
                "creator_approved": True,
                "creator_approval_status": "approved",
                "commercial_use": True,
                "commercial_use_status": "approved",
            }
        },
    )
    upload_rights = json.loads(list_asset_rights(conn, asset_id=upload["id"])[0]["rights_json"])
    extract = enqueue_extract_job(
        conn,
        user_id=user["id"],
        project_id=project["id"],
        asset_id=upload["id"],
        mask_provider="threshold",
        max_frames=1,
    )

    assert upload_rights["assetLineage"]["operations"] == []
    assert worker_once(conn, storage=storage)["status"] == "succeeded"
    object_rights_row = conn.execute(
        "SELECT rights_json FROM rights_metadata WHERE job_id = ? AND object_id = 'object_0' ORDER BY created_at, id LIMIT 1",
        (extract["id"],),
    ).fetchone()
    object_rights = json.loads(object_rights_row["rights_json"])

    assert object_rights["sourceAttribution"]["sourceAssetId"] == upload["id"]
    assert object_rights["sourceAttribution"]["sourceUri"] == "original://demo_red_ball.mp4"
    assert object_rights["sourceAttribution"]["displayText"] == "Original uploaded source"
    assert object_rights["license"] == "uploaded_source_license"
    assert object_rights["licenseDetails"]["name"] == "Uploaded source license"
    assert object_rights["licenseDetails"]["scope"] == "commercial"
    assert object_rights["creatorApproval"]["approved"] is True
    assert object_rights["commercialUse"] is True
    assert object_rights["commercialUseStatus"] == "approved"
