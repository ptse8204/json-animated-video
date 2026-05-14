from __future__ import annotations

import json
import mimetypes
import sqlite3
import tempfile
import uuid
import zipfile
from pathlib import Path
from typing import Any

from motionjson.exporters.website_package import export_website_package
from motionjson.masks import ExternalMaskProvider, ThresholdMaskProvider
from motionjson.pipeline import run_pipeline
from motionjson.providers.base import StorageProvider
from motionjson.providers.mocks import MockSegmentationProvider
from motionjson.providers.segmentation import SegmentationMaskProvider

from .assets import _asset_row, list_assets_for_job, register_generated_asset
from .jobs import record_job_event
from .models import validate_extract_provider_policy
from .queue import claim_next, mark_failed, mark_running, mark_succeeded
from .rights import record_asset_lineage, record_audit_event, record_rights_metadata
from .usage import record_usage_event


def _json(row: dict[str, Any], field: str) -> dict[str, Any]:
    parsed = json.loads(row[field] or "{}")
    if not isinstance(parsed, dict):
        raise ValueError(f"{field} must contain a JSON object")
    return parsed


def _kind_for_rel_path(rel_path: str) -> str:
    name = Path(rel_path).name
    if rel_path == "scene_graph.json":
        return "scene_graph"
    if rel_path == "rights_manifest.json":
        return "rights_manifest"
    if name == "object_manifest.json":
        return "object_manifest"
    if name == "web_asset_manifest.json":
        return "web_manifest"
    if rel_path == "resource_profile.json":
        return "resource_profile"
    if rel_path == "silhouette_lottie.json":
        return "lottie_silhouette"
    return "extraction_file"


def _object_id_for_rel_path(rel_path: str) -> str | None:
    parts = Path(rel_path.replace("\\", "/")).parts
    if len(parts) >= 2 and parts[0] == "objects":
        return parts[1]
    if len(parts) >= 2 and parts[0] in {"masks"}:
        return parts[1]
    return None


def _register_output_tree(
    conn: sqlite3.Connection,
    *,
    storage: StorageProvider,
    project_id: str,
    job_id: str,
    out_dir: Path,
    source_asset_id: str | None = None,
) -> list[dict]:
    assets: list[dict] = []
    rights_manifest: dict[str, Any] = {}
    rights_path = out_dir / "rights_manifest.json"
    if rights_path.exists():
        rights_manifest = json.loads(rights_path.read_text(encoding="utf-8"))
    object_rights = rights_manifest.get("objects", {}) if isinstance(rights_manifest.get("objects"), dict) else {}
    for path in sorted(out_dir.rglob("*")):
        if not path.is_file():
            continue
        rel_path = str(path.relative_to(out_dir)).replace("\\", "/")
        object_id = _object_id_for_rel_path(rel_path)
        asset = register_generated_asset(
            conn,
            storage=storage,
            project_id=project_id,
            kind=_kind_for_rel_path(rel_path),
            source_job_id=job_id,
            path=path,
            rel_path=rel_path,
            content_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        )
        assets.append(asset)
        record_asset_lineage(
            conn,
            project_id=project_id,
            source_asset_id=source_asset_id,
            derived_asset_id=asset["id"],
            job_id=job_id,
            operation="extract_object_layer" if object_id else "extract_manifest",
            object_id=object_id,
            metadata={"rel_path": rel_path, "kind": asset["kind"]},
        )
        rights = object_rights.get(object_id) if object_id else None
        if isinstance(rights, dict):
            record_rights_metadata(conn, project_id=project_id, asset_id=asset["id"], object_id=object_id, job_id=job_id, rights=rights)
        record_audit_event(
            conn,
            project_id=project_id,
            job_id=job_id,
            asset_id=asset["id"],
            object_id=object_id,
            event_type="generated_asset_registered",
            metadata={"rel_path": rel_path, "kind": asset["kind"]},
        )
    return assets


def _materialize_job_assets(
    conn: sqlite3.Connection,
    *,
    storage: StorageProvider,
    project_id: str,
    source_job_id: str,
    out_dir: Path,
) -> None:
    for asset in list_assets_for_job(conn, project_id=project_id, source_job_id=source_job_id):
        metadata = json.loads(asset["metadata_json"] or "{}")
        rel_path = metadata.get("rel_path")
        if not isinstance(rel_path, str) or not rel_path:
            continue
        safe_parts = Path(rel_path.replace("\\", "/")).parts
        if Path(rel_path).is_absolute() or ".." in safe_parts:
            raise ValueError(f"unsafe asset rel_path: {rel_path}")
        dest = out_dir / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(storage.load_bytes(asset["storage_key"]))


def _run_extract(conn: sqlite3.Connection, *, storage: StorageProvider, job: dict[str, Any]) -> dict[str, Any]:
    payload = _json(job, "payload_json")
    provider_name = validate_extract_provider_policy(str(payload.get("mask_provider") or "threshold"))
    source_asset = _asset_row(conn, str(payload["asset_id"]))
    source_bytes = storage.load_bytes(source_asset["storage_key"])
    source_metadata = json.loads(source_asset["metadata_json"] or "{}")
    source_rights_context = source_metadata.get("rights_context") if isinstance(source_metadata.get("rights_context"), dict) else {}
    rights_context = {**source_rights_context, **dict(payload.get("rights_context") or {})}
    if not rights_context.get("source_asset_id"):
        rights_context["source_asset_id"] = source_asset["id"]
    if not rights_context.get("source_uri"):
        rights_context["source_uri"] = source_rights_context.get("source_uri") or source_metadata.get("filename") or source_asset.get("uri")

    with tempfile.TemporaryDirectory(prefix="motionjson_backend_extract_") as tmp:
        tmp_dir = Path(tmp)
        suffix = Path(json.loads(source_asset["metadata_json"] or "{}").get("filename", "source.mp4")).suffix or ".mp4"
        video_path = tmp_dir / f"source{suffix}"
        video_path.write_bytes(source_bytes)
        out_dir = tmp_dir / "out"

        if provider_name == "external":
            mask_dir = payload.get("mask_dir")
            if not mask_dir:
                raise ValueError("mask_dir is required for external mask provider")
            mask_provider = ExternalMaskProvider(mask_dir)
        elif provider_name == "mock":
            mask_provider = SegmentationMaskProvider(MockSegmentationProvider())
        else:
            lower = tuple(int(v) for v in payload.get("lower_hsv", [0, 80, 80]))
            upper = tuple(int(v) for v in payload.get("upper_hsv", [12, 255, 255]))
            mask_provider = ThresholdMaskProvider(lower, upper)

        scene = run_pipeline(
            video_path=video_path,
            out_dir=out_dir,
            mask_provider=mask_provider,
            sample_fps=float(payload.get("sample_fps") or 12.0),
            max_frames=payload.get("max_frames"),
            rights_context=rights_context,
        )
        assets = _register_output_tree(
            conn,
            storage=storage,
            project_id=job["project_id"],
            job_id=job["id"],
            out_dir=out_dir,
            source_asset_id=source_asset["id"],
        )

    frames = int(scene.get("source", {}).get("sampledFrameCount") or 0)
    objects = len(scene.get("objects", []))
    record_usage_event(conn, user_id=job["created_by_user_id"], project_id=job["project_id"], job_id=job["id"], event_type="frames_processed", quantity=frames, unit="frame")
    record_usage_event(conn, user_id=job["created_by_user_id"], project_id=job["project_id"], job_id=job["id"], event_type="objects_extracted", quantity=objects, unit="object")
    record_audit_event(
        conn,
        user_id=job["created_by_user_id"],
        project_id=job["project_id"],
        job_id=job["id"],
        asset_id=source_asset["id"],
        event_type="extract_completed",
        metadata={"frames": frames, "objects": objects, "maskProvider": provider_name},
    )
    return {"scene": {"frames": frames, "objects": objects}, "assetIds": [asset["id"] for asset in assets]}


def _source_asset_for_extraction(conn: sqlite3.Connection, *, source_job_id: str) -> str | None:
    row = conn.execute(
        """
        SELECT source_asset_id
        FROM asset_lineage
        WHERE job_id = ? AND source_asset_id IS NOT NULL
        ORDER BY created_at, id
        LIMIT 1
        """,
        (source_job_id,),
    ).fetchone()
    return row["source_asset_id"] if row else None


def _run_export(conn: sqlite3.Connection, *, storage: StorageProvider, job: dict[str, Any]) -> dict[str, Any]:
    payload = _json(job, "payload_json")
    if payload.get("format") != "website-zip":
        raise ValueError("backend export currently supports website-zip")
    source_job_id = str(payload["source_job_id"])
    with tempfile.TemporaryDirectory(prefix="motionjson_backend_export_") as tmp:
        tmp_dir = Path(tmp)
        extraction_dir = tmp_dir / "extraction"
        extraction_dir.mkdir()
        _materialize_job_assets(conn, storage=storage, project_id=job["project_id"], source_job_id=source_job_id, out_dir=extraction_dir)
        output_path = tmp_dir / "website_package.zip"
        entry = export_website_package(out_dir=extraction_dir, output_path=output_path)
        source_asset_id = _source_asset_for_extraction(conn, source_job_id=source_job_id)
        asset = register_generated_asset(
            conn,
            storage=storage,
            project_id=job["project_id"],
            kind="website_package",
            source_job_id=job["id"],
            path=output_path,
            rel_path="exports/website_package.zip",
            content_type="application/zip",
            metadata={"aiUsage": "none", "exportEntry": entry},
        )
        record_asset_lineage(
            conn,
            project_id=job["project_id"],
            source_asset_id=source_asset_id,
            derived_asset_id=asset["id"],
            job_id=job["id"],
            operation="export_website_package",
            metadata={"format": "website-zip", "sourceJobId": source_job_id},
        )
        with zipfile.ZipFile(output_path) as archive:
            rights_manifest = json.loads(archive.read("rights_manifest.json").decode("utf-8"))
        for object_id, rights in (rights_manifest.get("objects") or {}).items():
            if isinstance(rights, dict):
                record_rights_metadata(conn, project_id=job["project_id"], asset_id=asset["id"], object_id=object_id, job_id=job["id"], rights=rights)
        record_audit_event(
            conn,
            user_id=job["created_by_user_id"],
            project_id=job["project_id"],
            job_id=job["id"],
            asset_id=asset["id"],
            event_type="website_package_exported",
            metadata={"format": "website-zip", "aiUsage": "none"},
        )
    record_usage_event(conn, user_id=job["created_by_user_id"], project_id=job["project_id"], job_id=job["id"], event_type="exports_produced", quantity=1, unit="export", metadata={"format": "website-zip", "assetId": asset["id"]})
    return {"assetId": asset["id"], "format": "website-zip", "aiUsage": "none"}


def process_job(conn: sqlite3.Connection, *, storage: StorageProvider, job: dict[str, Any]) -> dict[str, Any]:
    mark_running(conn, job_id=job["id"])
    record_job_event(conn, job_id=job["id"], event_type="worker_claimed", message="worker claimed job")
    fresh_job = dict(conn.execute("SELECT * FROM jobs WHERE id = ?", (job["id"],)).fetchone())
    if fresh_job["type"] == "extract":
        return _run_extract(conn, storage=storage, job=fresh_job)
    if fresh_job["type"] == "export":
        return _run_export(conn, storage=storage, job=fresh_job)
    raise ValueError(f"unsupported job type: {fresh_job['type']}")


def worker_once(
    conn: sqlite3.Connection,
    *,
    storage: StorageProvider,
    worker_id: str | None = None,
    max_attempts: int = 1,
) -> dict[str, Any] | None:
    claimed = claim_next(conn, worker_id=worker_id or f"worker-{uuid.uuid4().hex[:8]}")
    if claimed is None:
        return None
    try:
        result = process_job(conn, storage=storage, job=claimed)
    except Exception as exc:
        mark_failed(conn, job_id=claimed["id"], error=str(exc), max_attempts=max_attempts)
        return dict(conn.execute("SELECT * FROM jobs WHERE id = ?", (claimed["id"],)).fetchone())
    return mark_succeeded(conn, job_id=claimed["id"], result=result)
