from __future__ import annotations

import base64
import json
import sqlite3

import pytest

from motionjson.backend.api import MotionJSONAPI
from motionjson.backend.api_keys import create_api_key
from motionjson.backend.assets import register_upload
from motionjson.backend.auth import create_session, register_user
from motionjson.backend.db import initialize_database
from motionjson.backend.library import (
    add_asset_to_collection,
    create_collection,
    create_creator_pack,
    list_creator_packs,
    list_library_assets,
    save_library_asset,
)
from motionjson.backend.models import BackendError, NotFoundError
from motionjson.backend.projects import create_project
from motionjson.backend.rights import list_audit_events
from motionjson.backend.usage import summarize_usage
from motionjson.cli import main
from motionjson.providers.local_storage import LocalStorageProvider


def backend(tmp_path):
    conn = sqlite3.connect(tmp_path / "backend.sqlite")
    conn.row_factory = sqlite3.Row
    initialize_database(conn)
    storage = LocalStorageProvider(tmp_path / "storage")
    user = register_user(conn, email="library@example.com", password="pw")
    project = create_project(conn, user_id=user["id"], name="Library Project")
    return conn, storage, user, project


def upload_asset(tmp_path, conn, storage, user, project, *, filename="clip.mp4", rights_context=None):
    source = tmp_path / filename
    source.write_bytes(b"fake video bytes")
    return register_upload(
        conn,
        storage=storage,
        user_id=user["id"],
        project_id=project["id"],
        path=source,
        kind="source_video",
        metadata={"rights_context": rights_context or {"source_uri": f"local://{filename}"}},
    )


def approved_rights():
    return {
        "source_uri": "local://approved.mp4",
        "display_text": "Creator approved demo",
        "license": "creator_pack_license",
        "license_name": "Creator Pack License",
        "license_url": "https://example.test/license",
        "license_scope": "commercial",
        "creator_approved": True,
        "creator_approval_status": "approved",
        "commercial_use": True,
        "commercial_use_status": "approved",
    }


def assert_public_library_payload(payload):
    raw = json.dumps(payload)
    assert "storage_key" not in raw
    assert "storage-key" not in raw
    assert "storageKey" not in raw
    assert "token_hash" not in raw
    assert "tokenHash" not in raw
    assert "key_hash" not in raw
    assert "password_hash" not in raw
    assert "dataBase64" not in raw
    assert "fake video bytes" not in raw


def test_save_library_asset_derives_rights_and_searches_without_ai_usage(tmp_path):
    conn, storage, user, project = backend(tmp_path)
    source = upload_asset(tmp_path, conn, storage, user, project, rights_context=approved_rights())

    library_asset = save_library_asset(
        conn,
        user_id=user["id"],
        project_id=project["id"],
        asset_id=source["id"],
        type="motion_sticker",
        title="Launch Ball",
        description="Reusable red ball motion sticker",
        tags=["Hero", "Red", "hero"],
    )

    assert library_asset["type"] == "motion_sticker"
    assert library_asset["tags"] == ["hero", "red"]
    assert library_asset["license"] == "creator_pack_license"
    assert library_asset["licenseScope"] == "commercial"
    assert library_asset["creatorApproved"] is True
    assert library_asset["creatorApprovalStatus"] == "approved"
    assert library_asset["commercialUse"] is True
    assert library_asset["commercialUseStatus"] == "approved"
    assert library_asset["rightsMetadataId"]
    assert library_asset["sourceAsset"]["id"] == source["id"]
    assert library_asset["aiUsage"] == "none"
    assert_public_library_payload(library_asset)

    by_query = list_library_assets(conn, user_id=user["id"], filters={"q": "launch"})
    by_tag = list_library_assets(conn, user_id=user["id"], filters={"tag": "hero"})
    by_license = list_library_assets(conn, user_id=user["id"], filters={"licenseScope": "commercial", "creatorApproved": "true"})
    usage = summarize_usage(conn, project_id=project["id"])

    assert by_query["aiUsage"] == "none"
    assert [asset["id"] for asset in by_query["assets"]] == [library_asset["id"]]
    assert [asset["id"] for asset in by_tag["assets"]] == [library_asset["id"]]
    assert [asset["id"] for asset in by_license["assets"]] == [library_asset["id"]]
    assert "provider_attempts" not in usage["totals"]
    assert any(event["event_type"] == "library_asset_saved" for event in list_audit_events(conn, asset_id=source["id"]))


def test_public_library_collection_and_pack_metadata_omit_sensitive_fields(tmp_path):
    conn, storage, user, project = backend(tmp_path)
    source = upload_asset(tmp_path, conn, storage, user, project, rights_context=approved_rights())

    library_asset = save_library_asset(
        conn,
        user_id=user["id"],
        project_id=project["id"],
        asset_id=source["id"],
        type="motion_sticker",
        title="Launch storage_key=private-leak",
        description="Bearer secret-token dataBase64=AAAA",
        tags=["safe", "storage_key=projects/private/file.mp4", "token_hash=abc123"],
        metadata={
            "safe": "visible",
            "storage_key": "private-storage-leak",
            "nested": {
                "token_hash": "private-token-hash",
                "notes": "Bearer nested-secret at https://example.test/path?token=abc",
            },
            "items": [{"dataBase64": "private-bytes", "label": "ok"}],
        },
    )
    collection = create_collection(
        conn,
        user_id=user["id"],
        project_id=project["id"],
        title="Brand token_hash=private-hash",
        metadata={"apiKey": "sk-private-secret-value", "safe": "collection"},
    )
    add_asset_to_collection(conn, user_id=user["id"], collection_id=collection["id"], library_asset_id=library_asset["id"])
    pack = create_creator_pack(
        conn,
        user_id=user["id"],
        collection_id=collection["id"],
        title="Pack signingSecret=private-secret",
        library_asset_ids=[library_asset["id"], library_asset["id"]],
        metadata={"webhookSecret": "private-webhook-secret", "safe": "pack"},
    )

    for payload in (library_asset, collection, pack):
        assert_public_library_payload(payload)
        raw = json.dumps(payload)
        assert "private-storage-leak" not in raw
        assert "private-token-hash" not in raw
        assert "private-bytes" not in raw
        assert "private-secret" not in raw

    assert library_asset["metadata"]["safe"] == "visible"
    assert library_asset["tags"] == ["safe"]
    assert "storage_key" not in library_asset["metadata"]
    assert "token_hash" not in library_asset["metadata"]["nested"]
    assert library_asset["metadata"]["nested"]["notes"] == "Bearer [REDACTED] at https://example.test/path"
    assert library_asset["metadata"]["items"][0] == {"label": "ok"}
    assert "uri" not in library_asset["sourceAsset"]
    assert list_library_assets(conn, user_id=user["id"], filters={"tag": "storage_key=projects/private/file.mp4"}) == {"assets": [], "aiUsage": "none"}
    assert list_library_assets(conn, user_id=user["id"], filters={"tag": "token_hash=abc123"}) == {"assets": [], "aiUsage": "none"}
    assert collection["metadata"] == {"safe": "collection"}
    assert pack["assetCount"] == 1
    assert pack["metadata"] == {"safe": "pack"}


def test_collections_and_creator_packs_require_approved_collection_assets(tmp_path):
    conn, storage, user, project = backend(tmp_path)
    approved_source = upload_asset(tmp_path, conn, storage, user, project, filename="approved.mp4", rights_context=approved_rights())
    unapproved_source = upload_asset(tmp_path, conn, storage, user, project, filename="unapproved.mp4")
    approved_asset = save_library_asset(
        conn,
        user_id=user["id"],
        project_id=project["id"],
        asset_id=approved_source["id"],
        type="saved_asset",
        title="Approved layer",
        tags=["brand"],
    )
    unapproved_asset = save_library_asset(
        conn,
        user_id=user["id"],
        project_id=project["id"],
        asset_id=unapproved_source["id"],
        type="saved_asset",
        title="Needs review",
        tags=["brand"],
    )
    collection = create_collection(conn, user_id=user["id"], project_id=project["id"], title="Spring Brand")

    add_asset_to_collection(conn, user_id=user["id"], collection_id=collection["id"], library_asset_id=approved_asset["id"])
    add_asset_to_collection(conn, user_id=user["id"], collection_id=collection["id"], library_asset_id=unapproved_asset["id"])

    collection_assets = list_library_assets(conn, user_id=user["id"], filters={"collectionId": collection["id"]})
    assert {asset["id"] for asset in collection_assets["assets"]} == {approved_asset["id"], unapproved_asset["id"]}

    with pytest.raises(BackendError):
        create_creator_pack(conn, user_id=user["id"], collection_id=collection["id"], title="Creator pack")

    pack = create_creator_pack(
        conn,
        user_id=user["id"],
        collection_id=collection["id"],
        title="Approved creator pack",
        library_asset_ids=[approved_asset["id"]],
    )
    assert pack["assetCount"] == 1
    assert pack["aiUsage"] == "none"
    assert list_creator_packs(conn, user_id=user["id"])["packs"][0]["id"] == pack["id"]
    pack_assets = list_library_assets(conn, user_id=user["id"], filters={"packId": pack["id"]})
    assert [asset["id"] for asset in pack_assets["assets"]] == [approved_asset["id"]]

    audit_types = {event["event_type"] for event in list_audit_events(conn, project_id=project["id"])}
    assert {"collection_created", "collection_asset_added", "creator_pack_created"}.issubset(audit_types)


def test_library_assets_are_owner_scoped(tmp_path):
    conn, storage, owner, project = backend(tmp_path)
    other = register_user(conn, email="other-library@example.com", password="pw")
    source = upload_asset(tmp_path, conn, storage, owner, project, rights_context=approved_rights())
    library_asset = save_library_asset(
        conn,
        user_id=owner["id"],
        project_id=project["id"],
        asset_id=source["id"],
        type="saved_asset",
        title="Owner only",
    )

    assert list_library_assets(conn, user_id=owner["id"])["assets"][0]["id"] == library_asset["id"]
    assert list_library_assets(conn, user_id=other["id"])["assets"] == []
    with pytest.raises(NotFoundError):
        create_collection(conn, user_id=other["id"], project_id=project["id"], title="Other")


def test_rest_api_exposes_asset_library_routes_without_sensitive_fields(tmp_path):
    conn, storage, user, project = backend(tmp_path)
    source = upload_asset(tmp_path, conn, storage, user, project, rights_context=approved_rights())
    key = create_api_key(conn, user_id=user["id"], name="Library API")["apiKey"]
    conn.close()
    api = MotionJSONAPI(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage")
    headers = {"authorization": f"Bearer {key}"}

    status, _headers, body = api.handle(
        "POST",
        f"/v1/projects/{project['id']}/library-assets",
        headers,
        json.dumps({"assetId": source["id"], "type": "motion_sticker", "title": "API Sticker", "tags": ["api"]}).encode(),
    )
    assert status == 201
    library_asset = json.loads(body)
    assert library_asset["aiUsage"] == "none"
    assert_public_library_payload(library_asset)

    status, _headers, body = api.handle("GET", "/v1/library/assets?q=sticker&tag=api&creatorApproved=true", headers, b"")
    assert status == 200
    listed = json.loads(body)
    assert listed["aiUsage"] == "none"
    assert listed["assets"][0]["id"] == library_asset["id"]
    assert_public_library_payload(listed)

    status, _headers, body = api.handle(
        "POST",
        "/v1/library/collections",
        headers,
        json.dumps({"projectId": project["id"], "title": "API Brand"}).encode(),
    )
    assert status == 201
    collection = json.loads(body)

    status, _headers, body = api.handle(
        "POST",
        f"/v1/library/collections/{collection['id']}/assets",
        headers,
        json.dumps({"libraryAssetId": library_asset["id"]}).encode(),
    )
    assert status == 201
    assert json.loads(body)["aiUsage"] == "none"

    status, _headers, body = api.handle(
        "POST",
        "/v1/library/packs",
        headers,
        json.dumps({"collectionId": collection["id"], "title": "API Pack"}).encode(),
    )
    assert status == 201
    pack = json.loads(body)
    assert pack["assetCount"] == 1

    status, _headers, body = api.handle("GET", f"/v1/library/assets?packId={pack['id']}", headers, b"")
    assert json.loads(body)["assets"][0]["id"] == library_asset["id"]


def test_cli_exposes_library_workflow(tmp_path, monkeypatch, capsys):
    db_path = tmp_path / "backend.sqlite"
    storage_root = tmp_path / "storage"
    conn, storage, user, project = backend(tmp_path)
    source = upload_asset(tmp_path, conn, storage, user, project, rights_context=approved_rights())
    session = create_session(conn, user_id=user["id"])
    conn.close()
    monkeypatch.setenv("MJ_TEST_TOKEN", session.token)
    common = ["--db", str(db_path), "--storage-root", str(storage_root), "--session-token-env", "MJ_TEST_TOKEN"]

    main(
        [
            "backend",
            "save-library-asset",
            *common,
            "--project-id",
            project["id"],
            "--asset-id",
            source["id"],
            "--title",
            "CLI Sticker",
            "--type",
            "motion_sticker",
            "--tag",
            "cli",
        ]
    )
    saved = json.loads(capsys.readouterr().out)
    assert saved["aiUsage"] == "none"
    assert_public_library_payload(saved)

    main(["backend", "list-library-assets", *common, "--tag", "cli"])
    listed = json.loads(capsys.readouterr().out)
    assert listed["assets"][0]["id"] == saved["id"]

    main(["backend", "create-brand-collection", *common, "--project-id", project["id"], "--title", "CLI Brand"])
    collection = json.loads(capsys.readouterr().out)
    main(["backend", "add-collection-asset", *common, "--collection-id", collection["id"], "--library-asset-id", saved["id"]])
    assert json.loads(capsys.readouterr().out)["aiUsage"] == "none"
    main(["backend", "create-creator-pack", *common, "--collection-id", collection["id"], "--title", "CLI Pack"])
    assert json.loads(capsys.readouterr().out)["assetCount"] == 1
