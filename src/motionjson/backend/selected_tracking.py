from __future__ import annotations

import copy
import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

from motionjson.backend.assets import get_asset, list_assets_for_job
from motionjson.backend.export_workflows import materialize_job_assets
from motionjson.backend.jobs import get_job, record_job_event
from motionjson.backend.models import NotFoundError
from motionjson.backend.worker import _register_output_tree
from motionjson.config import ExtractionRunConfig
from motionjson.pipeline import run_multi_object_pipeline
from motionjson.providers.base import StorageProvider
from motionjson.providers.discovery import ExternalMasksDiscoveryProvider, object_specs_from_candidates


SELECTED_TRACKING_FORMAT = "motionjson.selected_candidate_tracking.v0.1"


def track_selected_candidates(
    conn: sqlite3.Connection,
    *,
    storage: StorageProvider,
    user_id: str,
    job_id: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    job = get_job(conn, user_id=user_id, job_id=job_id)
    source_asset = get_asset(conn, user_id=user_id, asset_id=_job_payload(job).get("asset_id"))
    candidate_asset, candidate_doc = _latest_candidate_document(conn, storage=storage, project_id=job["project_id"], job_id=job_id)
    candidate_ids = _candidate_ids(payload)
    candidates_by_id = {_candidate_id(candidate): candidate for candidate in _candidate_documents(candidate_doc)}
    missing = [candidate_id for candidate_id in candidate_ids if candidate_id not in candidates_by_id]
    if missing:
        raise ValueError(f"candidateIds do not belong to this job: {', '.join(missing)}")
    if not candidate_ids:
        raise ValueError("candidateIds must include at least one candidate")

    track_mode = str(payload.get("trackMode") or payload.get("track_mode") or "selected_only")
    if track_mode != "selected_only":
        raise ValueError("trackMode must be selected_only")
    export_review_required = _bool_payload(payload.get("exportReviewRequired", payload.get("export_review_required")), default=True)

    with tempfile.TemporaryDirectory(prefix="motionjson_track_selected_") as tmp:
        tmp_dir = Path(tmp)
        source_dir = tmp_dir / "source"
        source_dir.mkdir()
        materialize_job_assets(conn, storage=storage, project_id=job["project_id"], source_job_id=job_id, out_dir=source_dir)
        selected_objects = _selected_external_mask_objects(
            candidates_by_id,
            candidate_ids,
            source_dir=source_dir,
        )
        video_path = _write_source_video(storage, source_asset, tmp_dir)
        output_dir = tmp_dir / "tracked"
        options = _pipeline_options(job)
        scene = run_multi_object_pipeline(
            video_path=video_path,
            out_dir=output_dir,
            object_specs=[],
            candidate_provider=ExternalMasksDiscoveryProvider(),
            candidate_config={"objects": selected_objects, "source": "track_selected", "candidateIds": candidate_ids},
            candidate_to_specs=lambda candidates: object_specs_from_candidates(candidates, base_dir=output_dir),
            rights_context=_rights_context(job),
            **options,
        )
        _write_selection_review(
            output_dir,
            source_candidate_doc=candidate_doc,
            selected_ids=set(candidate_ids),
            track_mode=track_mode,
            export_review_required=export_review_required,
        )
        if export_review_required:
            _mark_export_review_pending(output_dir, selected_ids=set(candidate_ids))
        _write_selection_manifest(
            output_dir,
            candidate_asset_id=candidate_asset["id"],
            selected_ids=candidate_ids,
            track_mode=track_mode,
            export_review_required=export_review_required,
            scene=scene,
        )
        assets = _register_output_tree(
            conn,
            storage=storage,
            project_id=job["project_id"],
            job_id=job_id,
            out_dir=output_dir,
            source_asset_id=source_asset["id"],
        )
    record_job_event(
        conn,
        job_id=job_id,
        event_type="track_selected",
        message="selected candidates tracked",
        metadata={
            "candidateIds": candidate_ids,
            "trackMode": track_mode,
            "exportReviewRequired": export_review_required,
            "trackedObjects": len(selected_objects),
        },
    )
    all_assets = list_assets_for_job(conn, project_id=job["project_id"], source_job_id=job_id)
    return {
        "format": SELECTED_TRACKING_FORMAT,
        "jobId": job_id,
        "candidateIds": candidate_ids,
        "trackMode": track_mode,
        "exportReviewRequired": export_review_required,
        "trackedObjectIds": [item["object_id"] for item in selected_objects],
        "candidateAssetId": candidate_asset["id"],
        "assetIds": [asset["id"] for asset in assets],
        "assets": all_assets,
    }


def _job_payload(job: Mapping[str, Any]) -> dict[str, Any]:
    payload = json.loads(job.get("payload_json") or "{}")
    if not isinstance(payload, dict):
        raise ValueError("job payload must be a JSON object")
    return payload


def _latest_candidate_document(
    conn: sqlite3.Connection,
    *,
    storage: StorageProvider,
    project_id: str,
    job_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    candidates = [
        asset
        for asset in list_assets_for_job(conn, project_id=project_id, source_job_id=job_id)
        if str(asset.get("kind") or "") == "candidate_summary"
    ]
    if not candidates:
        raise ValueError("job has no candidate review artifact")
    asset = candidates[-1]
    document = json.loads(storage.load_bytes(asset["storage_key"]).decode("utf-8"))
    if not isinstance(document, dict):
        raise ValueError("candidate review artifact must be a JSON object")
    return asset, document


def _candidate_documents(document: Mapping[str, Any]) -> list[dict[str, Any]]:
    candidates = document.get("candidates")
    if not isinstance(candidates, list):
        return []
    return [dict(candidate) for candidate in candidates if isinstance(candidate, Mapping)]


def _candidate_id(candidate: Mapping[str, Any]) -> str:
    return str(candidate.get("candidateId") or candidate.get("candidate_id") or candidate.get("id") or "")


def _candidate_ids(payload: Mapping[str, Any]) -> list[str]:
    raw_ids = payload.get("candidateIds", payload.get("candidate_ids"))
    if not isinstance(raw_ids, Sequence) or isinstance(raw_ids, (str, bytes, bytearray)):
        raise ValueError("candidateIds must be an array")
    ids = [str(candidate_id).strip() for candidate_id in raw_ids if str(candidate_id).strip()]
    return list(dict.fromkeys(ids))


def _selected_external_mask_objects(
    candidates_by_id: Mapping[str, Mapping[str, Any]],
    candidate_ids: Sequence[str],
    *,
    source_dir: Path,
) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    for index, candidate_id in enumerate(candidate_ids):
        candidate = candidates_by_id[candidate_id]
        metadata = candidate.get("metadata") if isinstance(candidate.get("metadata"), Mapping) else {}
        if _candidate_rejected(candidate, metadata):
            raise ValueError(f"candidate {candidate_id!r} is rejected and cannot be tracked")
        mask_dir = metadata.get("maskDir") or metadata.get("mask_dir")
        if not isinstance(mask_dir, str) or not mask_dir:
            raise ValueError(f"candidate {candidate_id!r} has no maskDir for selected tracking")
        mask_path = Path(mask_dir)
        if mask_path.is_absolute() or ".." in mask_path.parts:
            raise ValueError(f"candidate {candidate_id!r} has an unsafe maskDir")
        absolute_mask_dir = source_dir / mask_path
        if not absolute_mask_dir.exists():
            raise ValueError(f"candidate {candidate_id!r} maskDir artifact is unavailable")
        objects.append(
            {
                "object_id": candidate_id,
                "label": str(candidate.get("label") or candidate_id),
                "mask_dir": str(absolute_mask_dir),
                "z_index": int(candidate.get("zIndex") or candidate.get("z_index") or 10 + index * 10),
            }
        )
    return objects


def _candidate_rejected(candidate: Mapping[str, Any], metadata: Mapping[str, Any]) -> bool:
    review_status = str(candidate.get("reviewStatus") or metadata.get("reviewStatus") or "").strip().lower()
    return bool(candidate.get("rejectionReason") or metadata.get("rejectionReason")) or review_status in {"rejected", "ignored", "excluded"}


def _write_source_video(storage: StorageProvider, source_asset: Mapping[str, Any], tmp_dir: Path) -> Path:
    suffix = Path(str(source_asset.get("uri") or source_asset.get("storage_key") or "source.mp4")).suffix or ".mp4"
    video_path = tmp_dir / f"source{suffix}"
    video_path.write_bytes(storage.load_bytes(str(source_asset["storage_key"])))
    return video_path


def _pipeline_options(job: Mapping[str, Any]) -> dict[str, Any]:
    payload = _job_payload(job)
    run_config_payload = payload.get("run_config")
    if isinstance(run_config_payload, dict):
        config = ExtractionRunConfig.from_dict(run_config_payload)
        return {
            "sample_fps": config.sampling.sample_fps,
            "max_frames": config.sampling.max_frames,
            "min_area": config.filters.min_area,
            "simplify_ratio": config.filters.simplify_ratio,
            "feather": config.export.feather,
            "layer_padding": config.export.layer_padding,
            "sprite_format": config.export.sprite_format,
            "output_mode": config.export.output_mode,
            "production_avif": config.export.production_avif,
        }
    return {
        "sample_fps": float(payload.get("sample_fps") or 12.0),
        "max_frames": payload.get("max_frames"),
        "min_area": 1.0,
        "simplify_ratio": 0.006,
        "feather": 0,
        "layer_padding": 4,
        "sprite_format": "webp",
        "output_mode": "authoring",
        "production_avif": False,
    }


def _rights_context(job: Mapping[str, Any]) -> dict[str, Any]:
    payload = _job_payload(job)
    run_config_payload = payload.get("run_config")
    if isinstance(run_config_payload, dict):
        try:
            return ExtractionRunConfig.from_dict(run_config_payload).rights.to_dict()
        except Exception:
            pass
    rights = payload.get("rights_context")
    return dict(rights) if isinstance(rights, Mapping) else {}


def _write_selection_review(
    output_dir: Path,
    *,
    source_candidate_doc: Mapping[str, Any],
    selected_ids: set[str],
    track_mode: str,
    export_review_required: bool,
) -> None:
    document = copy.deepcopy(dict(source_candidate_doc))
    document["format"] = source_candidate_doc.get("format") or "motionjson.candidates.v0.1"
    config = document.get("config") if isinstance(document.get("config"), dict) else {}
    document["config"] = {
        **config,
        "trackMode": track_mode,
        "selectedCandidateIds": sorted(selected_ids),
        "exportReviewRequired": export_review_required,
    }
    document["selection"] = {
        "format": SELECTED_TRACKING_FORMAT,
        "trackMode": track_mode,
        "selectedCandidateIds": sorted(selected_ids),
        "exportReviewRequired": export_review_required,
    }
    candidates = []
    for candidate in _candidate_documents(document):
        candidate_id = _candidate_id(candidate)
        metadata = candidate.get("metadata") if isinstance(candidate.get("metadata"), dict) else {}
        selected = candidate_id in selected_ids
        candidate["objectId"] = candidate_id if selected else candidate.get("objectId")
        candidate["defaultSelected"] = selected
        candidate["reviewStatus"] = "selected" if selected else "ignored"
        candidate["selectedForTracking"] = selected
        candidate["metadata"] = {**metadata, "selectedForTracking": selected}
        candidates.append(candidate)
    document["candidates"] = candidates
    (output_dir / "candidates.json").write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _mark_export_review_pending(output_dir: Path, *, selected_ids: set[str]) -> None:
    for rel_path in ("scene_graph.json", "tracks.json"):
        path = output_dir / rel_path
        if not path.exists():
            continue
        document = json.loads(path.read_text(encoding="utf-8"))
        if rel_path == "scene_graph.json":
            for obj in document.get("objects", []):
                if isinstance(obj, dict) and str(obj.get("id") or obj.get("objectId")) in selected_ids:
                    obj["exportStatus"] = "review_pending"
                    quality = obj.get("quality") if isinstance(obj.get("quality"), dict) else {}
                    obj["quality"] = {**quality, "reviewRequired": True}
        else:
            for track in document.get("tracks", []):
                if isinstance(track, dict) and str(track.get("objectId")) in selected_ids:
                    track["exportStatus"] = "review_pending"
                    metadata = track.get("metadata") if isinstance(track.get("metadata"), dict) else {}
                    track["metadata"] = {**metadata, "reviewRequired": True}
        path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_selection_manifest(
    output_dir: Path,
    *,
    candidate_asset_id: str,
    selected_ids: Sequence[str],
    track_mode: str,
    export_review_required: bool,
    scene: Mapping[str, Any],
) -> None:
    document = {
        "format": SELECTED_TRACKING_FORMAT,
        "candidateAssetId": candidate_asset_id,
        "selectedCandidateIds": list(selected_ids),
        "trackMode": track_mode,
        "exportReviewRequired": export_review_required,
        "trackedObjectCount": len(scene.get("objects", [])) if isinstance(scene.get("objects"), list) else 0,
    }
    path = output_dir / "review" / "selected_candidates.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _bool_payload(value: Any, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    if value is None:
        return default
    return bool(value)
