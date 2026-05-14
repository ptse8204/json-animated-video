from __future__ import annotations

import json
import mimetypes
import sqlite3
import tempfile
import uuid
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
    if name == "object_manifest.json":
        return "object_manifest"
    if name == "web_asset_manifest.json":
        return "web_manifest"
    if rel_path == "resource_profile.json":
        return "resource_profile"
    if rel_path == "silhouette_lottie.json":
        return "lottie_silhouette"
    return "extraction_file"


def _register_output_tree(
    conn: sqlite3.Connection,
    *,
    storage: StorageProvider,
    project_id: str,
    job_id: str,
    out_dir: Path,
) -> list[dict]:
    assets: list[dict] = []
    for path in sorted(out_dir.rglob("*")):
        if not path.is_file():
            continue
        rel_path = str(path.relative_to(out_dir)).replace("\\", "/")
        assets.append(
            register_generated_asset(
                conn,
                storage=storage,
                project_id=project_id,
                kind=_kind_for_rel_path(rel_path),
                source_job_id=job_id,
                path=path,
                rel_path=rel_path,
                content_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
            )
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
        )
        assets = _register_output_tree(conn, storage=storage, project_id=job["project_id"], job_id=job["id"], out_dir=out_dir)

    frames = int(scene.get("source", {}).get("sampledFrameCount") or 0)
    objects = len(scene.get("objects", []))
    record_usage_event(conn, user_id=job["created_by_user_id"], project_id=job["project_id"], job_id=job["id"], event_type="frames_processed", quantity=frames, unit="frame")
    record_usage_event(conn, user_id=job["created_by_user_id"], project_id=job["project_id"], job_id=job["id"], event_type="objects_extracted", quantity=objects, unit="object")
    return {"scene": {"frames": frames, "objects": objects}, "assetIds": [asset["id"] for asset in assets]}


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
