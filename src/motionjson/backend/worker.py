from __future__ import annotations

import json
import mimetypes
import os
import sqlite3
import tempfile
import uuid
import zipfile
from pathlib import Path
from typing import Any, Mapping
import shutil

import numpy as np
from PIL import Image

from motionjson.config import (
    ExtractionRunConfig,
    ExternalMaskProviderConfig,
    OutputConfig,
    ProviderConfig,
    SamplingConfig,
    ThresholdProviderConfig,
    VideoInputConfig,
)
from motionjson.capabilities import cuda_status
from motionjson.exporters.final_render import export_mp4, final_export_entry, load_scene, write_final_export_manifest
from motionjson.exporters.production_assets import export_transparent_webm_object
from motionjson.exporters.remotion import write_remotion_plan
from motionjson.exporters.website_package import export_website_package
from motionjson.job_artifacts import JobCanceled, LocalJobRun, artifact_kind_for_rel_path
from motionjson.masks import ExternalMaskProvider, MotionMaskProvider, ThresholdMaskProvider
from motionjson.pipeline import ObjectExtractionSpec, run_multi_object_pipeline, run_pipeline
from motionjson.provider_settings import provider_runtime_settings
from motionjson.providers.base import ProviderConfigError, StorageProvider
from motionjson.providers.discovery import (
    ClassDetectorDiscoveryProvider,
    MockObjectDiscoveryProvider,
    MotionForegroundDiscoveryProvider,
    SAM2AutomaticProposalDiscoveryProvider,
    SAM2HFAutomaticMasksDiscoveryProvider,
    SAM3AutoMasksDiscoveryProvider,
    SAM3ConceptDiscoveryProvider,
    SAM3ExemplarDiscoveryProvider,
    SamAutoMasksDiscoveryProvider,
    TextDetectorDiscoveryProvider,
    _template_match_mask_sequence,
    _write_single_mask_frame,
    object_specs_from_candidates,
)
from motionjson.providers.mocks import MockSegmentationProvider
from motionjson.providers.sam2 import HostedSAM2SegmentationProvider, LocalSAM2AutomaticMaskProposalBackend, LocalSAM2HFAutomaticMaskProposalBackend, LocalSAM2SegmentationProvider
from motionjson.providers.sam3 import LocalSAM3DiscoveryBackend
from motionjson.providers.segmentation import SegmentationMaskProvider
from motionjson.tracks import Box, VideoSource
from motionjson.video import iter_sampled_frames

from .assets import _asset_row, list_assets_for_job, register_generated_asset, register_generated_asset_once
from .db import connect
from .partial_review import synthesize_partial_review_payload
from .sam3_discovery_subprocess import SubprocessSAM3AutoMasksDiscoveryProvider
from .selected_tracking import (
    _candidate_documents,
    _candidate_id,
    _candidate_label_overrides,
    _latest_candidate_document,
    _mark_export_review_pending,
    _selected_external_mask_objects,
    _write_selection_manifest,
    _write_selection_review,
)
from .jobs import get_job, record_job_event
from .models import validate_extract_provider_policy
from .queue import claim_next, mark_canceled, mark_failed, mark_running, mark_succeeded
from .readiness import job_readiness
from .rights import record_asset_lineage, record_audit_event, record_rights_metadata
from .usage import record_usage_event
from .webhooks import WebhookTransport, deliver_event


def _json(row: dict[str, Any], field: str) -> dict[str, Any]:
    parsed = json.loads(row[field] or "{}")
    if not isinstance(parsed, dict):
        raise ValueError(f"{field} must contain a JSON object")
    return parsed


def _server_runtime_value(config_value: Any, runtime_value: Any) -> Any:
    text = str(config_value or "").strip()
    if not text or text == "[LOCAL_PATH_REDACTED]" or text.startswith("<redacted:"):
        return runtime_value
    return config_value


def _kind_for_rel_path(rel_path: str) -> str:
    job_kind = artifact_kind_for_rel_path(rel_path)
    if job_kind != "extraction_file":
        return job_kind
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
    if rel_path == "partial_review.json":
        return "partial_review"
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
    object_id_filter: str | None = None,
    rel_path_filter: set[str] | None = None,
    replace_existing: bool = False,
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
        if rel_path_filter is not None and rel_path not in rel_path_filter:
            continue
        object_id = _object_id_for_rel_path(rel_path)
        if object_id_filter is not None and object_id != object_id_filter:
            continue
        asset, created = register_generated_asset_once(
            conn,
            storage=storage,
            project_id=project_id,
            kind=_kind_for_rel_path(rel_path),
            source_job_id=job_id,
            path=path,
            rel_path=rel_path,
            content_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
            replace_existing=replace_existing,
        )
        assets.append(asset)
        if not created:
            continue
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


def _asset_rel_path(asset: dict[str, Any]) -> str:
    try:
        metadata = json.loads(asset.get("metadata_json") or "{}")
    except (TypeError, json.JSONDecodeError):
        metadata = {}
    rel_path = metadata.get("rel_path") if isinstance(metadata, dict) else ""
    return rel_path.replace("\\", "/").lstrip("/") if isinstance(rel_path, str) else ""


def _event_mirror(conn: sqlite3.Connection, job_id: str):
    def mirror(event: dict[str, Any]) -> None:
        raw_type = str(event.get("type") or "")
        if raw_type == "progress":
            event_type = "progress"
        elif raw_type == "job":
            event_type = f"job_{event.get('status', 'event')}"
        else:
            event_type = raw_type or f"job_{event.get('status', 'event')}"
        record_job_event(
            conn,
            job_id=job_id,
            event_type=event_type,
            message=str(event.get("message") or event.get("stage") or "job event"),
            metadata=event,
        )

    return mirror


def _connection_database_path(conn: sqlite3.Connection) -> str | None:
    try:
        rows = conn.execute("PRAGMA database_list").fetchall()
    except sqlite3.DatabaseError:
        return None
    for row in rows:
        name = row["name"] if isinstance(row, sqlite3.Row) else row[1]
        path = row["file"] if isinstance(row, sqlite3.Row) else row[2]
        if name == "main" and isinstance(path, str) and path:
            return path
    return None


def _event_mirror_for_db_path(db_path: str, job_id: str):
    def mirror(event: dict[str, Any]) -> None:
        event_conn = connect(db_path)
        try:
            _event_mirror(event_conn, job_id)(event)
        finally:
            event_conn.close()

    return mirror


def _object_failure_diagnostic_from_output(out_dir: Path, exc: BaseException, *, reason_code: str) -> dict[str, Any]:
    latest_failure: dict[str, Any] | None = None
    latest_mtime = -1.0
    for path in sorted((out_dir / "objects").glob("*/failure.json")):
        try:
            mtime = path.stat().st_mtime
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(document, dict) and mtime >= latest_mtime:
            latest_failure = document
            latest_mtime = mtime
    message = str(exc) or type(exc).__name__
    if latest_failure:
        return {
            **latest_failure,
            "reasonCode": latest_failure.get("reasonCode") or reason_code,
            "message": latest_failure.get("message") or message,
        }
    return {
        "format": "motionjson.object_failure.v0.1",
        "reasonCode": reason_code,
        "exceptionType": type(exc).__name__,
        "message": message,
        "reviewRequired": True,
    }


def _synthesize_partial_review_for_failure(
    job_run: LocalJobRun,
    *,
    out_dir: Path,
    video_path: Path,
    job_id: str,
    exc: BaseException,
    reason_code: str,
    runtime_proof: dict[str, Any],
) -> dict[str, Any]:
    diagnostic = _object_failure_diagnostic_from_output(out_dir, exc, reason_code=reason_code)
    result = synthesize_partial_review_payload(
        out_dir,
        video_path=video_path,
        job_id=job_id,
        diagnostic=diagnostic,
        runtime_proof=runtime_proof,
    )
    if result.get("status") == "ready":
        job_run.emit(
            "partial_review",
            "running",
            "partial review payload synthesized from completed object checkpoints",
            event_type="partial_review_payload_ready",
            progress={"overallRatio": 0.965},
            metadata=result,
        )
        job_run.emit(
            "partial_review",
            "succeeded",
            "partial preview tools ready",
            event_type="partial_preview_tools_ready",
            progress={"overallRatio": 0.97},
            metadata=result,
        )
    return result


def _try_synthesize_partial_review_for_failure(
    job_run: LocalJobRun,
    *,
    out_dir: Path,
    video_path: Path,
    job_id: str,
    exc: BaseException,
    reason_code: str,
    runtime_proof: dict[str, Any],
) -> dict[str, Any]:
    try:
        return _synthesize_partial_review_for_failure(
            job_run,
            out_dir=out_dir,
            video_path=video_path,
            job_id=job_id,
            exc=exc,
            reason_code=reason_code,
            runtime_proof=runtime_proof,
        )
    except Exception as synthesis_exc:
        job_run.log(f"partial review synthesis failed: {type(synthesis_exc).__name__}: {synthesis_exc}")
        try:
            job_run.emit(
                "partial_review",
                "failed",
                str(synthesis_exc) or type(synthesis_exc).__name__,
                event_type="partial_review_payload_failed",
                metadata={
                    "reasonCode": "partial_review_synthesis_failed",
                    "errorType": type(synthesis_exc).__name__,
                    "originalReasonCode": reason_code,
                    "originalErrorType": type(exc).__name__,
                },
            )
        except Exception:
            pass
        return {
            "format": "motionjson.partial_review_payload.v0.1",
            "status": "failed",
            "reasonCode": "partial_review_synthesis_failed",
            "message": str(synthesis_exc) or type(synthesis_exc).__name__,
        }


def _backend_cancel_requested(conn: sqlite3.Connection, job_id: str) -> bool:
    row = conn.execute("SELECT status FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return bool(row and row["status"] in {"cancel_requested", "canceled"})


def _run_config_from_backend_payload(
    *,
    video_path: Path,
    out_dir: Path,
    provider_name: str,
    payload: dict[str, Any],
) -> ExtractionRunConfig:
    return ExtractionRunConfig(
        input_video=VideoInputConfig(path=str(video_path)),
        output=OutputConfig(directory=str(out_dir)),
        sampling=SamplingConfig(
            sample_fps=float(payload.get("sample_fps") or 12.0),
            max_frames=payload.get("max_frames"),
        ),
        provider=ProviderConfig(
            name=provider_name,
            threshold=ThresholdProviderConfig(
                lower_hsv=tuple(int(v) for v in payload.get("lower_hsv", [0, 80, 80])),
                upper_hsv=tuple(int(v) for v in payload.get("upper_hsv", [12, 255, 255])),
            ),
            external=ExternalMaskProviderConfig(mask_dir=payload.get("mask_dir")),
        ),
    )


def _runtime_run_config_payload(config: ExtractionRunConfig, *, video_path: Path, out_dir: Path) -> dict[str, Any]:
    payload = config.to_dict()
    payload["input"] = {**dict(payload.get("input") or {}), "path": str(video_path)}
    payload["output"] = {**dict(payload.get("output") or {}), "directory": str(out_dir)}
    return payload


def _stored_run_config(payload: dict[str, Any]) -> ExtractionRunConfig | None:
    run_config_payload = payload.get("run_config")
    if not isinstance(run_config_payload, dict):
        return None
    return ExtractionRunConfig.from_dict(run_config_payload)


def _single_object_pipeline_options(run_config: ExtractionRunConfig | None, payload: dict[str, Any]) -> dict[str, Any]:
    if run_config is None:
        return {
            "object_id": "object_0",
            "object_label": "selected_object",
            "sample_fps": float(payload.get("sample_fps") or 12.0),
            "max_frames": payload.get("max_frames"),
            "min_area": 100.0,
            "simplify_ratio": 0.006,
            "feather": 0,
            "layer_padding": 4,
            "sprite_format": "webp",
            "output_mode": "authoring",
            "production_avif": False,
        }
    return {
        "object_id": run_config.object_id,
        "object_label": run_config.label,
        "sample_fps": run_config.sampling.sample_fps,
        "max_frames": run_config.sampling.max_frames,
        "min_area": run_config.filters.min_area,
        "simplify_ratio": run_config.filters.simplify_ratio,
        "feather": run_config.export.feather,
        "layer_padding": run_config.export.layer_padding,
        "sprite_format": run_config.export.sprite_format,
        "output_mode": run_config.export.output_mode,
        "production_avif": run_config.export.production_avif,
    }


def _prompt_point_and_box(run_config: ExtractionRunConfig) -> tuple[tuple[int, int] | None, tuple[int, int, int, int] | None]:
    for prompt in run_config.prompts:
        if prompt.kind in {"point", "positive_point"}:
            data = prompt.data
            if "x" in data and "y" in data:
                return (int(data["x"]), int(data["y"])), None
    for prompt in run_config.prompts:
        if prompt.kind == "box":
            data = prompt.data
            if all(key in data for key in ("x", "y", "w", "h")):
                return None, (int(data["x"]), int(data["y"]), int(data["w"]), int(data["h"]))
    return None, None


def _hosted_sam3_discovery_runtime(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    discovery_config: dict[str, Any],
) -> tuple[dict[str, Any], Any | None]:
    provider_preference = str(discovery_config.get("providerPreference") or discovery_config.get("provider_preference") or "").strip()
    if provider_preference != "sam3-hosted" and not discovery_config.get("hosted") and not discovery_config.get("useHosted"):
        return discovery_config, None
    settings = provider_runtime_settings(conn, user_id=user_id, provider_id="sam3-hosted")
    hosted_allowed = bool(discovery_config.get("allowNetwork") and settings.get("allow_hosted"))
    public_config = {
        **discovery_config,
        "providerPreference": "sam3-hosted",
        "hosted": True,
        "hostedProfile": settings.get("hosted_profile_id"),
        "model": settings.get("selected_model"),
        "allowNetwork": hosted_allowed,
        "acknowledgeCostPrivacy": bool(discovery_config.get("acknowledgeCostPrivacy") and settings.get("allow_hosted")),
    }
    runtime_config = {
        **public_config,
        "apiKey": settings.get("api_key"),
        "endpoint": settings.get("endpoint"),
    }
    from motionjson.providers.hosted_sam import hosted_sam3_backend_from_config

    return public_config, hosted_sam3_backend_from_config(runtime_config)


def _apply_sam3_provider_runtime(run_config: ExtractionRunConfig, discovery_config: dict[str, Any]) -> dict[str, Any]:
    provider_name = str(run_config.provider.name or "").strip()
    if provider_name not in {"sam3-local", "sam3-hosted"}:
        return discovery_config
    sam3_config = run_config.provider.sam3
    config = dict(discovery_config)
    if provider_name == "sam3-local":
        config.setdefault("providerPreference", "sam3-local")
    else:
        config.setdefault("providerPreference", "sam3-hosted")
        config.setdefault("hosted", True)
        config.setdefault("allowNetwork", bool(sam3_config.hosted_allow_network))
        config.setdefault("acknowledgeCostPrivacy", bool(sam3_config.hosted_allow_network))
    if sam3_config.model_path and not any(key in config for key in ("sam3ModelPath", "sam3_model_path", "model_path")):
        config["sam3ModelPath"] = sam3_config.model_path
    if sam3_config.device and not any(key in config for key in ("sam3Device", "sam3_device", "device")):
        config["sam3Device"] = sam3_config.device
    if sam3_config.endpoint and "endpoint" not in config:
        config["endpoint"] = sam3_config.endpoint
    hosted_profile = str(sam3_config.hosted_config.get("hostedProfile") or sam3_config.hosted_config.get("profile") or "").strip()
    if hosted_profile and not any(key in config for key in ("hostedProfile", "profile")):
        config["hostedProfile"] = hosted_profile
    hosted_model = str(sam3_config.hosted_config.get("model") or "").strip()
    if hosted_model and "model" not in config:
        config["model"] = hosted_model
    return config


def _without_runtime_model_keys(config: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    safe = dict(config)
    for key in keys:
        safe.pop(key, None)
    return safe


def _cached_local_runtime_discovery_provider(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    discovery_mode: str | None,
    discovery_config: dict[str, Any],
) -> tuple[tuple[Any, str, bool, dict[str, Any]] | None, dict[str, Any]]:
    config = dict(discovery_config)
    if config.get("mock"):
        return None, config
    provider_preference = str(config.get("providerPreference") or config.get("provider_preference") or "").strip()
    if discovery_mode == "sam2_hf_auto_masks" or provider_preference == "sam2-hf-auto-masks":
        runtime = provider_runtime_settings(conn, user_id=user_id, provider_id="sam2-hf-auto-masks")
        model_cache = runtime.get("model_cache") if isinstance(runtime.get("model_cache"), dict) else {}
        verification = runtime.get("runtime_verification") if isinstance(runtime.get("runtime_verification"), dict) else {}
        if not _runtime_verified_for_extraction(verification):
            raise ProviderConfigError(
                "SAM2 HF automatic masks are cached but not verified for extraction. Run Prepare local model or Run smoke test before starting extraction."
            )
        sam2_device_requested = str(config.get("sam2HfDevice") or config.get("sam2_hf_device") or runtime.get("sam2_hf_device") or "cpu")
        runtime_model = str(runtime.get("runtime_model") or "").strip()
        if runtime_model and model_cache.get("cached") is True:
            safe_config = _without_runtime_model_keys(
                config,
                ("sam2HfModel", "sam2_hf_model", "sam2AutoMaskModel", "sam2_auto_mask_model"),
            )
            backend = LocalSAM2HFAutomaticMaskProposalBackend(
                model=runtime_model,
                device=sam2_device_requested,
            )
            public_contract = _resolved_runtime_contract_public(
                "sam2-hf-auto-masks",
                runtime,
                device_requested=sam2_device_requested,
            )
            safe_config["runtimeContractPublic"] = public_contract
            return (
                SAM2HFAutomaticMasksDiscoveryProvider(backend=backend),
                "SAM2 HF automatic masks configured from server-side cached model",
                False,
                {"runtimeContract": public_contract},
            ), safe_config
    if discovery_mode == "sam3_auto_masks" and provider_preference != "sam3-hosted" and not config.get("hosted") and not config.get("useHosted"):
        runtime = provider_runtime_settings(conn, user_id=user_id, provider_id="sam3-local")
        model_cache = runtime.get("model_cache") if isinstance(runtime.get("model_cache"), dict) else {}
        verification = runtime.get("runtime_verification") if isinstance(runtime.get("runtime_verification"), dict) else {}
        sam3_device = str(config.get("sam3Device") or config.get("sam3_device") or runtime.get("sam3_device") or "cuda")
        if not _runtime_verified_for_extraction(verification):
            raise ProviderConfigError(
                "SAM3 Scene Sweep is cached but not verified for extraction. Run Prepare local model or Run smoke test so the model loads on the selected device and completes warmup."
            )
        _raise_if_requested_cuda_not_loaded("sam3-local", verification, device_requested=sam3_device)
        runtime_model = str(runtime.get("runtime_model") or "").strip()
        if runtime_model and model_cache.get("cached") is True:
            safe_config = _without_runtime_model_keys(
                config,
                ("sam3TrackerModel", "sam3_tracker_model", "sam3HfModel", "sam3_hf_model", "model"),
            )
            backend = SubprocessSAM3AutoMasksDiscoveryProvider(
                model_path=runtime_model,
                device=sam3_device,
                timeout_seconds=_sam3_extraction_timeout_seconds(config),
            )
            public_contract = _resolved_runtime_contract_public(
                "sam3-local",
                runtime,
                device_requested=sam3_device,
            )
            safe_config["runtimeContractPublic"] = public_contract
            return (
                backend,
                "SAM3 Scene Sweep configured from server-side cached model",
                False,
                {"runtimeContract": public_contract},
            ), safe_config
    return None, config


def _runtime_verified_for_extraction(verification: dict[str, Any]) -> bool:
    return bool(verification.get("verified") is True and str(verification.get("warmupStatus") or "") == "succeeded")


def _raise_if_requested_cuda_not_loaded(provider_id: str, verification: dict[str, Any], *, device_requested: str) -> None:
    if provider_id != "sam3-local":
        return
    if str(device_requested or "").strip().lower().startswith("cuda") and verification.get("loadedOnCuda") is not True:
        actual = str(verification.get("deviceActual") or "unknown")
        status = str(verification.get("runtimeProofStatus") or "not_verified")
        raise ProviderConfigError(
            "gpu_device_mismatch: SAM3 Scene Sweep requested CUDA but runtime proof did not load on CUDA "
            f"(actual device: {actual}, proof status: {status}). Run setup smoke test on a CUDA runtime or choose CPU/MPS intentionally."
        )


def _resolved_runtime_contract_public(provider_id: str, runtime: dict[str, Any], *, device_requested: str) -> dict[str, Any]:
    verification = runtime.get("runtime_verification") if isinstance(runtime.get("runtime_verification"), dict) else {}
    model_cache = runtime.get("model_cache") if isinstance(runtime.get("model_cache"), dict) else {}
    default_runtime_kind = "transformers_sam3_tracker_direct" if provider_id == "sam3-local" else "transformers_mask_generation"
    accelerator_kind = str(verification.get("acceleratorKind") or _accelerator_kind_from_device(str(verification.get("deviceActual") or device_requested or "")))
    return {
        "providerId": provider_id,
        "modelId": _safe_public_runtime_model_id(str(model_cache.get("model") or runtime.get("selected_model") or "")),
        "modelPathStatus": "recorded_server_side" if model_cache.get("serverPathRecorded") else "resolved_server_side",
        "localPathDisplay": "[LOCAL_PATH_REDACTED]" if model_cache.get("localPathKnown") else "",
        "deviceRequested": str(verification.get("deviceRequested") or device_requested or ""),
        "deviceActual": str(verification.get("deviceActual") or device_requested or ""),
        "runtimeKind": str(verification.get("runtimeKind") or default_runtime_kind),
        "acceleratorKind": accelerator_kind,
        "runtimeProofStatus": str(verification.get("runtimeProofStatus") or ("verified" if verification.get("verified") else "not_verified")),
        "loadedOnCuda": bool(verification.get("loadedOnCuda")),
        "loadedOnMps": bool(verification.get("loadedOnMps")),
        "cudaAvailable": bool(verification.get("cudaAvailable")),
        "mpsAvailable": bool(verification.get("mpsAvailable")),
        "gpuMemoryBefore": verification.get("gpuMemoryBefore") if isinstance(verification.get("gpuMemoryBefore"), dict) else {},
        "gpuMemoryAfter": verification.get("gpuMemoryAfter") if isinstance(verification.get("gpuMemoryAfter"), dict) else {},
        "reasonCode": str(verification.get("reasonCode") or ""),
        "warmupStatus": str(verification.get("warmupStatus") or "not_verified"),
        "lastVerifiedAt": verification.get("lastVerifiedAt") or "",
        "runtimeModelSource": str(runtime.get("runtime_model_source") or "saved_cache"),
    }


def _runtime_environment_proof_for_job(
    provider_name: str,
    *,
    discovery_mode: str | None,
    discovery_config: dict[str, Any],
    run_config: ExtractionRunConfig | None,
) -> dict[str, Any]:
    provider_id = str(provider_name or "")
    if discovery_config.get("mock"):
        return {}
    if provider_id.endswith("-hosted"):
        return {
            "providerId": provider_id,
            "displayProvider": _runtime_display_provider(provider_id, discovery_mode),
            "acceleratorKind": "hosted",
            "runtimeProofStatus": "hosted",
            "deviceRequested": "hosted",
            "deviceActual": "hosted",
            "loadedOnCuda": False,
            "loadedOnMps": False,
            "cudaAvailable": False,
            "mpsAvailable": False,
            "gpuMemoryBefore": {},
            "gpuMemoryAfter": {},
            "reasonCode": "",
            "runtimeKind": "hosted_provider",
        }
    if not _should_probe_runtime(provider_id, discovery_mode):
        return {}

    device_requested = _requested_device_for_runtime(provider_id, discovery_mode, discovery_config, run_config)
    torch_status = cuda_status()
    devices = [device for device in torch_status.get("devices", []) if isinstance(device, dict)]
    cuda_available = bool(torch_status.get("available"))
    mps_available = any(str(device.get("name") or "").lower() == "mps" and bool(device.get("available")) for device in devices)
    requested_lower = device_requested.lower()
    cuda_requested = requested_lower.startswith("cuda")
    mps_requested = requested_lower.startswith("mps")
    device_actual = _environment_device_actual(device_requested, cuda_available=cuda_available, mps_available=mps_available)
    accelerator_kind = _accelerator_kind_from_device(device_actual)
    if cuda_requested and not cuda_available:
        runtime_status = "gpu_device_mismatch"
        reason_code = "gpu_device_mismatch"
        message = "CUDA was requested, but PyTorch in the extraction worker cannot see CUDA."
    elif mps_requested and not mps_available:
        runtime_status = "gpu_device_mismatch"
        reason_code = "gpu_device_mismatch"
        message = "MPS was requested, but PyTorch in the extraction worker cannot see MPS."
    elif bool(torch_status.get("torchInstalled")):
        runtime_status = "environment_verified"
        reason_code = ""
        message = f"Extraction worker runtime can see {accelerator_kind.upper() if accelerator_kind in {'cuda', 'mps'} else accelerator_kind}."
    else:
        runtime_status = "not_verified"
        reason_code = "torch_unavailable"
        message = "PyTorch is not importable in the extraction worker, so accelerator proof is unavailable."
    return {
        "providerId": provider_id,
        "displayProvider": _runtime_display_provider(provider_id, discovery_mode),
        "acceleratorKind": accelerator_kind,
        "runtimeProofStatus": runtime_status,
        "deviceRequested": device_requested,
        "deviceActual": device_actual,
        "loadedOnCuda": False,
        "loadedOnMps": False,
        "cudaAvailable": cuda_available,
        "mpsAvailable": mps_available,
        "gpuMemoryBefore": _worker_cuda_memory_snapshot(device_actual) if device_actual.startswith("cuda") and cuda_available else {},
        "gpuMemoryAfter": {},
        "reasonCode": reason_code,
        "runtimeKind": "worker_environment_probe",
        "message": message,
        "torchInstalled": bool(torch_status.get("torchInstalled")),
        "torchVersion": torch_status.get("torchVersion"),
    }


def _merge_runtime_proof(base: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    if not base:
        return dict(candidate)
    if not candidate:
        return dict(base)
    merged = dict(base)
    for key, value in candidate.items():
        if value not in (None, "", {}, []):
            merged[key] = value
    for key in ("cudaAvailable", "mpsAvailable"):
        if key in base and key not in candidate:
            merged[key] = base[key]
    return merged


def _should_probe_runtime(provider_id: str, discovery_mode: str | None) -> bool:
    mode = str(discovery_mode or "")
    if provider_id in {"sam3-local", "sam2-local", "sam2-hf-auto-masks"}:
        return True
    return mode.startswith("sam3") or mode in {"sam_auto_masks"}


def _requested_device_for_runtime(
    provider_id: str,
    discovery_mode: str | None,
    discovery_config: dict[str, Any],
    run_config: ExtractionRunConfig | None,
) -> str:
    if provider_id == "sam3-local" or str(discovery_mode or "").startswith("sam3"):
        return str(
            discovery_config.get("sam3Device")
            or discovery_config.get("sam3_device")
            or (run_config.provider.sam3.device if run_config is not None else None)
            or os.environ.get("SAM3_LOCAL_DEVICE")
            or "cuda"
        )
    if provider_id == "sam2-hf-auto-masks":
        return str(
            discovery_config.get("sam2HfDevice")
            or discovery_config.get("sam2_hf_device")
            or os.environ.get("SAM2_HF_DEVICE")
            or "cpu"
        )
    if provider_id == "sam2-local":
        return str((run_config.provider.sam2.device if run_config is not None else None) or os.environ.get("SAM2_DEVICE") or "cpu")
    return "cpu"


def _environment_device_actual(device_requested: str, *, cuda_available: bool, mps_available: bool) -> str:
    requested = str(device_requested or "").strip().lower()
    if requested.startswith("cuda"):
        return requested if ":" in requested else "cuda:0" if cuda_available else "cpu"
    if requested.startswith("mps"):
        return "mps" if mps_available else "cpu"
    if requested.startswith("cpu") or requested == "-1":
        return "cpu"
    if cuda_available:
        return "cuda:0"
    if mps_available:
        return "mps"
    return "cpu"


def _runtime_display_provider(provider_id: str, discovery_mode: str | None) -> str:
    mode = str(discovery_mode or "")
    if provider_id == "sam3-local" or mode.startswith("sam3"):
        return "SAM3 Scene Sweep runtime"
    if provider_id == "sam2-hf-auto-masks":
        return "SAM2 HF automatic-mask runtime"
    if provider_id == "sam2-local":
        return "SAM2 prompt tracking runtime"
    if provider_id.endswith("-hosted"):
        return "Hosted SAM runtime"
    return provider_id or "SAM runtime"


def _worker_cuda_memory_snapshot(device_actual: str) -> dict[str, Any]:
    if not str(device_actual or "").startswith("cuda"):
        return {}
    try:
        import torch  # type: ignore
    except Exception:
        return {}
    cuda = getattr(torch, "cuda", None)
    if cuda is None:
        return {}
    try:
        index = int(str(device_actual).split(":", 1)[1]) if ":" in str(device_actual) else 0
    except (TypeError, ValueError):
        index = 0
    snapshot: dict[str, Any] = {}
    try:
        free_bytes, total_bytes = cuda.mem_get_info(index)
        snapshot["freeBytes"] = int(free_bytes)
        snapshot["totalBytes"] = int(total_bytes)
        snapshot["usedBytes"] = int(total_bytes) - int(free_bytes)
    except Exception:
        pass
    try:
        snapshot["allocatedBytes"] = int(cuda.memory_allocated(index))
        snapshot["reservedBytes"] = int(cuda.memory_reserved(index))
    except Exception:
        pass
    return snapshot


def _raise_if_environment_device_mismatch(proof: dict[str, Any], *, discovery_config: dict[str, Any]) -> None:
    if not proof or discovery_config.get("mock"):
        return
    if str(proof.get("providerId") or "") != "sam3-local":
        return
    if str(proof.get("deviceRequested") or "").lower().startswith("cuda") and proof.get("cudaAvailable") is not True:
        raise ProviderConfigError(
            "gpu_device_mismatch: SAM3 Scene Sweep requested CUDA, but PyTorch in this extraction worker cannot see CUDA. "
            "In Colab, switch to a GPU runtime, reinstall a CUDA-enabled torch build if needed, restart the runtime, then rerun setup."
        )


def _accelerator_kind_from_device(device: str) -> str:
    text = str(device or "").strip().lower()
    if text.startswith("cuda"):
        return "cuda"
    if text.startswith("mps"):
        return "mps"
    if text.startswith("cpu") or text == "-1":
        return "cpu"
    return "unknown"


def _safe_public_runtime_model_id(value: str) -> str:
    text = str(value or "").strip()
    if text.startswith(("/", "~", "./", "../")) or "\\" in text or text.lower().startswith("file://"):
        return "[LOCAL_PATH_REDACTED]"
    return text


def _sam3_extraction_timeout_seconds(config: dict[str, Any]) -> float:
    default = 1800.0
    env_value = os.environ.get("MOTIONJSON_SAM3_EXTRACTION_TIMEOUT_SECONDS")
    if env_value:
        try:
            default = float(env_value)
        except (TypeError, ValueError):
            default = 1800.0
    value = config.get("sam3ExtractionTimeoutSeconds", config.get("sam3_extraction_timeout_seconds", default))
    try:
        timeout = float(value)
    except (TypeError, ValueError):
        timeout = default
    return min(max(timeout, 30.0), 7200.0)


def _ui_discovery_provider(mode: str, config: dict[str, Any] | None = None) -> tuple[Any, str, bool] | None:
    discovery_config = dict(config or {})
    if mode == "auto_object_proposals":
        provider_preference = str(discovery_config.get("providerPreference") or discovery_config.get("provider_preference") or "auto")
        if discovery_config.get("mock") or provider_preference == "mock":
            return MockObjectDiscoveryProvider(), "automatic object proposal mock discovery configured", True
        if provider_preference == "sam2-hf-auto-masks":
            return SAM2HFAutomaticMasksDiscoveryProvider(), "SAM2 HF automatic masks configured", False
        return SAM2AutomaticProposalDiscoveryProvider(), "SAM2 automatic object proposals configured", False
    if mode == "sam2_hf_auto_masks":
        if discovery_config.get("mock"):
            return SAM2HFAutomaticMasksDiscoveryProvider(), "SAM2 HF automatic-mask mock discovery configured", True
        return SAM2HFAutomaticMasksDiscoveryProvider(), "SAM2 HF automatic masks configured", False
    if mode == "text_detector":
        return TextDetectorDiscoveryProvider(), "text detector mock discovery configured", True
    if mode == "sam_auto_masks":
        if discovery_config.get("mock"):
            return SamAutoMasksDiscoveryProvider(), "automatic mask mock proposals configured", True
        return SamAutoMasksDiscoveryProvider(), "SAM2 automatic mask proposals configured", False
    if mode == "sam3_concept":
        if discovery_config.get("mock"):
            return SAM3ConceptDiscoveryProvider(), "SAM3 concept mock discovery configured", True
        return SAM3ConceptDiscoveryProvider(), "SAM3 concept runtime configured", False
    if mode == "sam3_exemplar":
        if discovery_config.get("mock"):
            return SAM3ExemplarDiscoveryProvider(), "SAM3 exemplar mock discovery configured", True
        return SAM3ExemplarDiscoveryProvider(), "SAM3 exemplar runtime configured", False
    if mode == "sam3_auto_masks":
        if discovery_config.get("mock"):
            return SAM3AutoMasksDiscoveryProvider(), "SAM3 auto-mask mock discovery configured", True
        return SAM3AutoMasksDiscoveryProvider(), "SAM3 Scene Sweep runtime configured", False
    if mode == "class_detector":
        return ClassDetectorDiscoveryProvider(), "class detector mock discovery configured", True
    if mode == "motion_foreground":
        return MotionForegroundDiscoveryProvider(), "motion foreground CPU discovery configured", False
    return None


def _raster_device_for_run(run_config: ExtractionRunConfig | None, runtime_proof: Mapping[str, Any] | None = None) -> str | None:
    runtime = runtime_proof if isinstance(runtime_proof, Mapping) else {}
    actual = str(runtime.get("deviceActual") or "").strip()
    if actual:
        return actual
    if run_config is None:
        return None
    provider_name = str(run_config.provider.name or "")
    if provider_name == "sam3-local":
        return str(run_config.provider.sam3.device or "").strip() or None
    if provider_name in {"sam2-local", "sam2-hf-auto-masks", "sam2-hosted"}:
        return str(run_config.provider.sam2.device or "").strip() or None
    return None


def _selected_tracking_mode(payload: dict[str, Any]) -> str:
    return str(payload.get("mode") or "").strip().lower()


def _scan_mask_path(mask_dir: Path, frame_index: int) -> Path:
    preferred = mask_dir / f"mask_{int(frame_index) + 1:06d}.png"
    if preferred.exists():
        return preferred
    matches = sorted(mask_dir.glob("mask_*.png"))
    if not matches:
        raise FileNotFoundError(f"no scan mask exists in {mask_dir}")
    return matches[0]


def _load_binary_mask(path: Path) -> np.ndarray:
    image = Image.open(path).convert("L")
    return np.where(np.asarray(image, dtype=np.uint8) > 127, 255, 0).astype(np.uint8)


def _candidate_box(candidate: Mapping[str, Any], width: int, height: int) -> Box:
    raw_box = candidate.get("box") or candidate.get("bbox") or {}
    if isinstance(raw_box, Mapping):
        x = int(raw_box.get("x", 0))
        y = int(raw_box.get("y", 0))
        w = int(raw_box.get("w", raw_box.get("width", width)))
        h = int(raw_box.get("h", raw_box.get("height", height)))
        x = max(0, min(max(0, width - 1), x))
        y = max(0, min(max(0, height - 1), y))
        w = max(1, min(max(1, width - x), w))
        h = max(1, min(max(1, height - y), h))
        return Box(x, y, w, h)
    return Box(0, 0, max(1, width), max(1, height))


def _write_mask_sequence_dir(mask_dir: Path, masks: list[np.ndarray]) -> None:
    mask_dir.mkdir(parents=True, exist_ok=True)
    for stale in mask_dir.glob("mask_*.png"):
        stale.unlink()
    for index, mask in enumerate(masks, start=1):
        Image.fromarray(np.where(mask > 127, 255, 0).astype(np.uint8)).save(mask_dir / f"mask_{index:06d}.png")


def _constant_box_mask_sequence(video_source: VideoSource, box: Box) -> list[np.ndarray]:
    masks: list[np.ndarray] = []
    width = int(getattr(video_source.info, "width", 0))
    height = int(getattr(video_source.info, "height", 0))
    for _frame in video_source.frames:
        mask = np.zeros((height, width), dtype=np.uint8)
        mask[box.y : box.y + box.h, box.x : box.x + box.w] = 255
        masks.append(mask)
    return masks


def _selected_tracking_masks_for_candidate(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    candidate: Mapping[str, Any],
    video_source: VideoSource,
    scan_mask: np.ndarray,
    box: Box,
) -> tuple[list[np.ndarray], str]:
    metadata = candidate.get("metadata") if isinstance(candidate.get("metadata"), Mapping) else {}
    provider_name = str(candidate.get("providerName") or metadata.get("providerName") or "").strip()
    source = str(candidate.get("source") or "").strip()
    frame_index = int(candidate.get("frameIndex", candidate.get("frame_index", metadata.get("scanFrameIndex", 0))) or 0)
    object_id = str(candidate.get("candidateId") or candidate.get("id") or candidate.get("objectId") or "candidate").strip() or "candidate"

    if provider_name == "sam3-local" or source == "sam3_auto_masks":
        runtime = provider_runtime_settings(conn, user_id=user_id, provider_id="sam3-local")
        backend = LocalSAM3DiscoveryBackend(
            model_path=str(runtime.get("runtime_model") or runtime.get("selected_model") or ""),
            device=str(runtime.get("sam3_device") or "cuda"),
        )
        try:
            masks = list(
                backend.track_candidate(
                    video_source,
                    frame_index=frame_index,
                    object_id=object_id,
                    box=(box.x, box.y, box.w, box.h),
                    mask=scan_mask,
                    config={"sam3Device": str(runtime.get("sam3_device") or "cuda"), "useTransformersTracker": True},
                )
            )
            return [np.where(np.asarray(mask) > 127, 255, 0).astype(np.uint8) for mask in masks], "sam3-local"
        except Exception:
            fallback = _template_match_mask_sequence(
                video_source,
                frame_index=frame_index,
                mask=scan_mask,
                box=box,
                config={"templateTrackPadding": max(4, int(max(box.w, box.h) * 0.75))},
            )
            return fallback or _constant_box_mask_sequence(video_source, box), "template_match_fallback"

    if provider_name == "sam2-hf-auto-masks":
        runtime = provider_runtime_settings(conn, user_id=user_id, provider_id="sam2-hf-auto-masks")
        backend = LocalSAM2HFAutomaticMaskProposalBackend(
            model=str(runtime.get("runtime_model") or runtime.get("selected_model") or ""),
            device=str(runtime.get("sam2_hf_device") or "cpu"),
        )
        masks = list(
            backend.track_candidate(
                video_source,
                frame_index=frame_index,
                object_id=object_id,
                box=(box.x, box.y, box.w, box.h),
                mask=scan_mask,
                config={"sam2HfDevice": str(runtime.get("sam2_hf_device") or "cpu")},
            )
        )
        return [np.where(np.asarray(mask) > 127, 255, 0).astype(np.uint8) for mask in masks], "sam2-hf-auto-masks"

    if provider_name == "sam2-local" or source == "sam_auto_masks":
        runtime = provider_runtime_settings(conn, user_id=user_id, provider_id="sam2-local")
        backend = LocalSAM2AutomaticMaskProposalBackend(
            checkpoint=str(runtime.get("sam2_checkpoint_path") or ""),
            model_config=str(runtime.get("sam2_model_config_path") or ""),
            device=str(runtime.get("sam2_device") or "cpu"),
        )
        masks = list(
            backend.track_candidate(
                video_source,
                frame_index=frame_index,
                object_id=object_id,
                box=(box.x, box.y, box.w, box.h),
                mask=scan_mask,
                config={"sam2Device": str(runtime.get("sam2_device") or "cpu")},
            )
        )
        return [np.where(np.asarray(mask) > 127, 255, 0).astype(np.uint8) for mask in masks], "sam2-local"

    return _constant_box_mask_sequence(video_source, box), "box_seed_sequence"


def _run_selected_tracking_extract(
    conn: sqlite3.Connection,
    *,
    storage: StorageProvider,
    job: dict[str, Any],
    payload: dict[str, Any],
    video_path: Path,
    out_dir: Path,
    source_asset: Mapping[str, Any],
    rights_context: dict[str, Any],
    job_run: LocalJobRun,
) -> dict[str, Any]:
    source_job_id = str(payload.get("source_job_id") or payload.get("parent_job_id") or "").strip()
    if not source_job_id:
        raise ValueError("selected_tracking extract payload requires source_job_id")
    candidate_ids = [str(item).strip() for item in payload.get("candidate_ids", []) if str(item).strip()]
    if not candidate_ids:
        raise ValueError("selected_tracking extract payload requires candidate_ids")
    track_mode = str(payload.get("track_mode") or "selected_only")
    export_review_required = bool(payload.get("export_review_required", True))
    label_overrides = _candidate_label_overrides(payload)
    source_job = get_job(conn, user_id=job["created_by_user_id"], job_id=source_job_id)

    with tempfile.TemporaryDirectory(prefix="motionjson_selected_tracking_source_") as temp_name:
        source_dir = Path(temp_name)
        _materialize_job_assets(conn, storage=storage, project_id=job["project_id"], source_job_id=source_job_id, out_dir=source_dir)
        candidate_asset, candidate_doc = _latest_candidate_document(conn, storage=storage, project_id=job["project_id"], job_id=source_job_id)
        candidates_by_id = {_candidate_id(candidate): candidate for candidate in _candidate_documents(candidate_doc)}
        missing = [candidate_id for candidate_id in candidate_ids if candidate_id not in candidates_by_id]
        if missing:
            raise ValueError(f"candidateIds do not belong to source job: {', '.join(missing)}")

        selected_objects = _selected_external_mask_objects(
            candidates_by_id,
            candidate_ids,
            source_dir=source_dir,
            label_overrides=label_overrides,
        )

        run_config = _stored_run_config(payload) or _stored_run_config(json.loads(source_job.get("payload_json") or "{}"))
        sample_fps = run_config.sampling.sample_fps if run_config is not None else float(payload.get("sample_fps") or 12.0)
        max_frames = run_config.sampling.max_frames if run_config is not None else payload.get("max_frames")
        info, frame_iter = iter_sampled_frames(video_path, sample_fps=sample_fps, max_frames=max_frames)
        frames = list(frame_iter)
        video_source = VideoSource(path=video_path, info=info, frames=frames)

        selected_tracking_root = out_dir / "selected_tracking"
        selected_tracking_root.mkdir(parents=True, exist_ok=True)
        object_specs = []
        for index, selected in enumerate(selected_objects):
            candidate_id = str(selected["object_id"])
            candidate = candidates_by_id[candidate_id]
            metadata = candidate.get("metadata") if isinstance(candidate.get("metadata"), Mapping) else {}
            relative_mask_dir = Path(str(metadata.get("maskDir") or metadata.get("mask_dir") or ""))
            absolute_mask_dir = source_dir / relative_mask_dir
            scan_frame_index = int(candidate.get("frameIndex", candidate.get("frame_index", metadata.get("scanFrameIndex", 0))) or 0)
            scan_mask = _load_binary_mask(_scan_mask_path(absolute_mask_dir, scan_frame_index))
            box = _candidate_box(candidate, int(getattr(info, "width", 0)), int(getattr(info, "height", 0)))
            job_run.emit(
                "selected_tracking",
                "running",
                f"tracking selected object {candidate_id}",
                progress={"overallRatio": round(0.22 + (index / max(1, len(selected_objects))) * 0.08, 4)},
                metadata={"objectId": candidate_id, "scanFrameIndex": scan_frame_index, "trackMode": track_mode},
            )
            masks, tracking_provider = _selected_tracking_masks_for_candidate(
                conn,
                user_id=job["created_by_user_id"],
                candidate=candidate,
                video_source=video_source,
                scan_mask=scan_mask,
                box=box,
            )
            runtime_mask_dir = selected_tracking_root / candidate_id / "masks"
            _write_mask_sequence_dir(runtime_mask_dir, masks)
            object_specs.append(
                ObjectExtractionSpec(
                    object_id=candidate_id,
                    label=str(label_overrides.get(candidate_id) or selected["label"] or candidate_id),
                    mask_provider=ExternalMaskProvider(runtime_mask_dir),
                    z_index=int(selected.get("z_index") or 10 + index * 10),
                    metadata={
                        "candidateId": candidate_id,
                        "candidateMetadata": {
                            **dict(metadata),
                            "source": str(candidate.get("source") or metadata.get("source") or "track_selected"),
                            "providerName": str(candidate.get("providerName") or metadata.get("providerName") or tracking_provider),
                            "reviewStatus": "selected",
                            "selectedForTracking": True,
                            "defaultSelected": True,
                            "trackingProvider": tracking_provider,
                            "labelSource": "user" if candidate_id in label_overrides else metadata.get("labelSource") or metadata.get("label_source") or "provider",
                        },
                        "source": str(candidate.get("source") or metadata.get("source") or "track_selected"),
                    },
                )
            )
            job_run.emit(
                "selected_tracking",
                "running",
                f"tracked selected object {candidate_id}",
                progress={"overallRatio": round(0.24 + ((index + 1) / max(1, len(selected_objects))) * 0.08, 4)},
                metadata={"objectId": candidate_id, "trackingProvider": tracking_provider, "maskFrames": len(masks)},
            )

        scene = run_multi_object_pipeline(
            video_path=video_path,
            out_dir=out_dir,
            object_specs=object_specs,
            sample_fps=sample_fps,
            max_frames=max_frames,
            min_area=run_config.filters.min_area if run_config is not None else 100.0,
            simplify_ratio=run_config.filters.simplify_ratio if run_config is not None else 0.006,
            feather=run_config.export.feather if run_config is not None else 0,
            layer_padding=run_config.export.layer_padding if run_config is not None else 4,
            sprite_format=run_config.export.sprite_format if run_config is not None else "webp",
            output_mode=run_config.export.output_mode if run_config is not None else "authoring",
            production_avif=run_config.export.production_avif if run_config is not None else False,
            rights_context=rights_context,
            raster_device=_raster_device_for_run(run_config),
            job_context=job_run,
        )
        _write_selection_review(
            out_dir,
            source_candidate_doc=candidate_doc,
            selected_ids=set(candidate_ids),
            track_mode=track_mode,
            export_review_required=export_review_required,
            label_overrides=label_overrides,
        )
        if export_review_required:
            _mark_export_review_pending(out_dir, selected_ids=set(candidate_ids))
        _write_selection_manifest(
            out_dir,
            candidate_asset_id=candidate_asset["id"],
            selected_ids=candidate_ids,
            track_mode=track_mode,
            export_review_required=export_review_required,
            scene=scene,
        )
        return scene


def _run_extract(conn: sqlite3.Connection, *, storage: StorageProvider, job: dict[str, Any]) -> dict[str, Any]:
    payload = _json(job, "payload_json")
    selected_tracking_job = _selected_tracking_mode(payload) == "selected_tracking"
    run_config = _stored_run_config(payload)
    requested_provider = run_config.provider.name if run_config is not None else payload.get("mask_provider") or "threshold"
    provider_name = validate_extract_provider_policy(str(requested_provider))
    source_asset = _asset_row(conn, str(payload["asset_id"]))
    source_bytes = storage.load_bytes(source_asset["storage_key"])
    source_metadata = json.loads(source_asset["metadata_json"] or "{}")
    source_rights_context = source_metadata.get("rights_context") if isinstance(source_metadata.get("rights_context"), dict) else {}
    config_rights_context = run_config.rights.to_dict() if run_config is not None else {}
    rights_context = {**source_rights_context, **config_rights_context, **dict(payload.get("rights_context") or {})}
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
        try:
            if run_config is not None:
                run_config_payload = _runtime_run_config_payload(run_config, video_path=video_path, out_dir=out_dir)
            else:
                run_config_payload = _run_config_from_backend_payload(video_path=video_path, out_dir=out_dir, provider_name=provider_name, payload=payload).to_dict()
        except Exception:
            run_config_payload = {
                "schema": "motionjson.extraction_run_config.v0.1",
                "input": {"path": str(video_path)},
                "output": {"directory": str(out_dir)},
                "provider": {"name": provider_name, "payload": payload},
                "error": "backend payload could not be normalized into a validated run config",
            }
        job_run = LocalJobRun(
            run_dir=out_dir,
            run_config=run_config_payload,
            job_id=job["id"],
            event_callback=_event_mirror(conn, job["id"]),
            heartbeat_callback=(
                _event_mirror_for_db_path(db_path, job["id"])
                if (db_path := _connection_database_path(conn))
                else None
            ),
            cancel_check=lambda: _backend_cancel_requested(conn, job["id"]),
        )
        def checkpoint_object_outputs(object_id: str, *, status: str = "finished") -> dict[str, Any]:
            assets = _register_output_tree(
                conn,
                storage=storage,
                project_id=job["project_id"],
                job_id=job["id"],
                out_dir=out_dir,
                source_asset_id=source_asset["id"],
                object_id_filter=object_id,
            )
            record_job_event(
                conn,
                job_id=job["id"],
                event_type="object_artifacts_registered",
                message=f"registered {len(assets)} {status} object artifacts for {object_id}",
                metadata={"objectId": object_id, "status": status, "assetCount": len(assets)},
            )
            return {"objectId": object_id, "status": status, "assetCount": len(assets)}

        job_run.checkpoint_object_outputs = checkpoint_object_outputs  # type: ignore[attr-defined]
        job_run.initialize(video_path=video_path, output_dir=out_dir)
        job_run.start()
        job_run.emit("validating_config", "succeeded", "backend extraction payload validated", progress={"overallRatio": 0.03}, metadata={"provider": provider_name})

        runtime_proof: dict[str, Any] = {}
        try:
            discovery_mode = run_config.discovery.mode if run_config is not None else None
            discovery_config = dict(run_config.discovery.config) if run_config is not None else {}
            hosted_sam3_backend = None
            cached_runtime_discovery_provider = None
            if run_config is not None:
                sam2_config = run_config.provider.sam2
                if sam2_config.checkpoint and not any(key in discovery_config for key in ("sam2Checkpoint", "sam2_checkpoint", "checkpoint")):
                    discovery_config["sam2Checkpoint"] = sam2_config.checkpoint
                if sam2_config.model_config and not any(key in discovery_config for key in ("sam2ModelConfig", "sam2_model_config", "model_config")):
                    discovery_config["sam2ModelConfig"] = sam2_config.model_config
                if sam2_config.device and not any(key in discovery_config for key in ("sam2Device", "sam2_device", "device")):
                    discovery_config["sam2Device"] = sam2_config.device
                discovery_config = _apply_sam3_provider_runtime(run_config, discovery_config)
                runtime_proof = _runtime_environment_proof_for_job(
                    provider_name,
                    discovery_mode=discovery_mode,
                    discovery_config=discovery_config,
                    run_config=run_config,
                )
                if runtime_proof:
                    job_run.emit(
                        "provider_preflight",
                        "succeeded" if runtime_proof.get("runtimeProofStatus") != "gpu_device_mismatch" else "failed",
                        runtime_proof.get("message") or "runtime environment proof recorded",
                        event_type="runtime_environment_proof_recorded",
                        progress={"overallRatio": 0.055},
                        metadata={"provider": provider_name, "discoveryMode": discovery_mode, "runtimeProof": runtime_proof},
                    )
                    _raise_if_environment_device_mismatch(runtime_proof, discovery_config=discovery_config)
                if discovery_mode in {"sam3_concept", "sam3_exemplar", "sam3_auto_masks"}:
                    discovery_config, hosted_sam3_backend = _hosted_sam3_discovery_runtime(
                        conn,
                        user_id=job["created_by_user_id"],
                        discovery_config=discovery_config,
                    )
                if hosted_sam3_backend is None:
                    cached_runtime_discovery_provider, discovery_config = _cached_local_runtime_discovery_provider(
                        conn,
                        user_id=job["created_by_user_id"],
                        discovery_mode=discovery_mode,
                        discovery_config=discovery_config,
                    )
            if selected_tracking_job:
                scene = _run_selected_tracking_extract(
                    conn,
                    storage=storage,
                    job=job,
                    payload=payload,
                    video_path=video_path,
                    out_dir=out_dir,
                    source_asset=source_asset,
                    rights_context=rights_context,
                    job_run=job_run,
                )
            elif hosted_sam3_backend is not None and discovery_mode == "sam3_concept":
                discovery_provider = (
                    SAM3ConceptDiscoveryProvider(backend=hosted_sam3_backend),
                    "SAM3 hosted concept discovery configured",
                    False,
                )
            elif hosted_sam3_backend is not None and discovery_mode == "sam3_exemplar":
                discovery_provider = (
                    SAM3ExemplarDiscoveryProvider(backend=hosted_sam3_backend),
                    "SAM3 hosted exemplar discovery configured",
                    False,
                )
            elif hosted_sam3_backend is not None and discovery_mode == "sam3_auto_masks":
                discovery_provider = (
                    SAM3AutoMasksDiscoveryProvider(backend=hosted_sam3_backend),
                    "SAM3 hosted auto-mask discovery configured",
                    False,
                )
            elif cached_runtime_discovery_provider is not None:
                discovery_provider = cached_runtime_discovery_provider
            else:
                discovery_provider = _ui_discovery_provider(discovery_mode or "", discovery_config)
            if not selected_tracking_job and discovery_provider is not None:
                provider, message, requires_mock = discovery_provider[:3]
                provider_metadata = dict(discovery_provider[3]) if len(discovery_provider) > 3 and isinstance(discovery_provider[3], dict) else {}
                runtime_proof = _merge_runtime_proof(
                    runtime_proof,
                    dict(provider_metadata.get("runtimeContract") or discovery_config.get("runtimeContractPublic") or {}),
                )
                if runtime_proof and provider_name == "sam3-local":
                    runtime_proof.setdefault("displayProvider", "SAM3 Scene Sweep runtime")
                if requires_mock and not discovery_config.get("mock"):
                    raise RuntimeError(
                        f"workspace {discovery_mode} jobs require discovery.config.mock=true; real discovery adapters remain capability-gated"
                    )
                job_run.emit(
                    "provider_preflight",
                    "succeeded",
                    message,
                    progress={"overallRatio": 0.06},
                    metadata={"provider": provider_name, "discoveryMode": discovery_mode, **provider_metadata},
                )
                if runtime_proof:
                    job_run.emit(
                        "provider_preflight",
                        "succeeded",
                        "runtime proof recorded",
                        event_type="runtime_proof_recorded",
                        progress={"overallRatio": 0.061},
                        metadata={"provider": provider_name, "discoveryMode": discovery_mode, "runtimeProof": runtime_proof},
                    )
                scene = run_multi_object_pipeline(
                    video_path=video_path,
                    out_dir=out_dir,
                    object_specs=[],
                    candidate_provider=provider,
                    candidate_config=discovery_config,
                    candidate_to_specs=lambda candidates: object_specs_from_candidates(candidates, base_dir=out_dir),
                    sample_fps=run_config.sampling.sample_fps,
                    max_frames=run_config.sampling.max_frames,
                    min_area=run_config.filters.min_area,
                    simplify_ratio=run_config.filters.simplify_ratio,
                    feather=run_config.export.feather,
                    layer_padding=run_config.export.layer_padding,
                    sprite_format=run_config.export.sprite_format,
                    output_mode=run_config.export.output_mode,
                    production_avif=run_config.export.production_avif,
                    rights_context=rights_context,
                    raster_device=_raster_device_for_run(run_config, runtime_proof),
                    scan_only=bool(discovery_config.get("fastFramePick") or discovery_config.get("fast_frame_pick")),
                    job_context=job_run,
                )
            elif not selected_tracking_job and discovery_mode not in {None, "manual_prompt"}:
                raise RuntimeError(
                    f"workspace worker does not support discovery mode {discovery_mode!r} yet; use the CLI or a mock text-detector run"
                )
            elif not selected_tracking_job and provider_name == "external":
                mask_dir = payload.get("mask_dir")
                if not mask_dir:
                    raise ValueError("mask_dir is required for external mask provider")
                mask_provider = ExternalMaskProvider(mask_dir)
                job_run.emit("provider_preflight", "succeeded", "mask provider constructed", progress={"overallRatio": 0.06}, metadata={"provider": provider_name})
                scene = run_pipeline(
                    video_path=video_path,
                    out_dir=out_dir,
                    mask_provider=mask_provider,
                    **_single_object_pipeline_options(run_config, payload),
                    rights_context=rights_context,
                    raster_device=_raster_device_for_run(run_config, runtime_proof),
                    job_context=job_run,
                )
            elif not selected_tracking_job:
                if provider_name == "mock":
                    mask_provider = SegmentationMaskProvider(MockSegmentationProvider())
                elif provider_name == "sam2-local" and run_config is not None:
                    runtime = provider_runtime_settings(
                        conn,
                        user_id=job["created_by_user_id"],
                        provider_id="sam2-local",
                    )
                    point, box = _prompt_point_and_box(run_config)
                    mask_provider = SegmentationMaskProvider(
                        LocalSAM2SegmentationProvider(
                            source_video=video_path,
                            checkpoint=_server_runtime_value(
                                run_config.provider.sam2.checkpoint,
                                runtime.get("sam2_checkpoint_path"),
                            ),
                            model_config=_server_runtime_value(
                                run_config.provider.sam2.model_config,
                                runtime.get("sam2_model_config_path"),
                            ),
                            device=(
                                _server_runtime_value(run_config.provider.sam2.device, runtime.get("sam2_device"))
                                or "cpu"
                            ),
                            prompt_frame_index=run_config.provider.sam2.prompt_frame,
                            object_id=run_config.object_id,
                            prompt_point=point,
                            prompt_box=box,
                        ),
                        prompt_point=point,
                        prompt_box=box,
                    )
                elif provider_name == "sam2-hosted" and run_config is not None:
                    runtime = provider_runtime_settings(
                        conn,
                        user_id=job["created_by_user_id"],
                        provider_id="sam2-hosted",
                    )
                    point, box = _prompt_point_and_box(run_config)
                    hosted_allowed = bool(run_config.provider.sam2.hosted_allow_network and runtime.get("allow_hosted"))
                    hosted_config = {
                        **dict(run_config.provider.sam2.hosted_config or {}),
                        "profile": runtime.get("hosted_profile_id"),
                        "hostedProfile": runtime.get("hosted_profile_id"),
                        "apiKey": runtime.get("api_key"),
                        "endpoint": runtime.get("endpoint"),
                        "model": runtime.get("selected_model"),
                        "allowNetwork": hosted_allowed,
                        "acknowledgeCostPrivacy": hosted_allowed,
                    }
                    mask_provider = SegmentationMaskProvider(
                        HostedSAM2SegmentationProvider(
                            source_video=video_path,
                            endpoint=str(runtime.get("endpoint") or run_config.provider.sam2.endpoint or "") or None,
                            api_key=str(runtime.get("api_key") or "") or None,
                            config=hosted_config,
                            auth_env=run_config.provider.sam2.auth_env,
                            endpoint_env=run_config.provider.sam2.endpoint_env,
                            prompt_frame_index=run_config.provider.sam2.prompt_frame,
                            object_id=run_config.object_id,
                            prompt_point=point,
                            prompt_box=box,
                            allow_network=hosted_allowed,
                        ),
                        prompt_point=point,
                        prompt_box=box,
                    )
                elif provider_name == "motion":
                    motion_config = dict(run_config.discovery.config) if run_config is not None and run_config.discovery.mode == "motion_foreground" else {}
                    mask_provider = MotionMaskProvider(var_threshold=float(motion_config.get("threshold", 25.0) or 25.0))
                elif provider_name in {"sam3-local", "sam3-hosted"}:
                    raise RuntimeError(
                        f"{provider_name} local UI runs must use sam3_concept, sam3_exemplar, or sam3_auto_masks discovery modes."
                    )
                else:
                    lower = tuple(int(v) for v in payload.get("lower_hsv", [0, 80, 80]))
                    upper = tuple(int(v) for v in payload.get("upper_hsv", [12, 255, 255]))
                    if run_config is not None:
                        lower = run_config.provider.threshold.lower_hsv
                        upper = run_config.provider.threshold.upper_hsv
                    mask_provider = ThresholdMaskProvider(lower, upper)
                job_run.emit("provider_preflight", "succeeded", "mask provider constructed", progress={"overallRatio": 0.06}, metadata={"provider": provider_name})
                scene = run_pipeline(
                    video_path=video_path,
                    out_dir=out_dir,
                    mask_provider=mask_provider,
                    **_single_object_pipeline_options(run_config, payload),
                    rights_context=rights_context,
                    raster_device=_raster_device_for_run(run_config, runtime_proof),
                    job_context=job_run,
                )
        except JobCanceled as exc:
            job_run.cancel(str(exc))
            _register_output_tree(conn, storage=storage, project_id=job["project_id"], job_id=job["id"], out_dir=out_dir, source_asset_id=source_asset["id"])
            raise
        except ProviderConfigError as exc:
            provider_reason = "gpu_device_mismatch" if "gpu_device_mismatch" in str(exc) else "provider_unavailable"
            _try_synthesize_partial_review_for_failure(
                job_run,
                out_dir=out_dir,
                video_path=video_path,
                job_id=job["id"],
                exc=exc,
                reason_code=provider_reason,
                runtime_proof=runtime_proof,
            )
            job_run.fail(exc, reason_code=provider_reason, user_message=str(exc))
            _register_output_tree(conn, storage=storage, project_id=job["project_id"], job_id=job["id"], out_dir=out_dir, source_asset_id=source_asset["id"])
            raise
        except Exception as exc:
            _try_synthesize_partial_review_for_failure(
                job_run,
                out_dir=out_dir,
                video_path=video_path,
                job_id=job["id"],
                exc=exc,
                reason_code="extraction_failed",
                runtime_proof=runtime_proof,
            )
            job_run.fail(exc)
            _register_output_tree(conn, storage=storage, project_id=job["project_id"], job_id=job["id"], out_dir=out_dir, source_asset_id=source_asset["id"])
            raise

        try:
            job_run.check_cancel("finalize")
        except JobCanceled as exc:
            job_run.cancel(str(exc))
            _register_output_tree(conn, storage=storage, project_id=job["project_id"], job_id=job["id"], out_dir=out_dir, source_asset_id=source_asset["id"])
            raise
        job_run.emit(
            "finalize",
            "succeeded",
            "worker extraction complete",
            event_type="worker_complete",
            progress={"overallRatio": 0.95},
            metadata={"frames": int(scene.get("source", {}).get("sampledFrameCount") or 0), "objects": len(scene.get("objects", []))},
        )
        assets = _register_output_tree(conn, storage=storage, project_id=job["project_id"], job_id=job["id"], out_dir=out_dir, source_asset_id=source_asset["id"])
        readiness = job_readiness(
            rel_paths=[_asset_rel_path(asset) for asset in assets],
            worker_complete=True,
            artifacts_registered=True,
            job_active=False,
            review_summary={},
        )
        job_run.emit(
            "finalize",
            "succeeded",
            "artifacts registered",
            event_type="artifacts_registered",
            progress={"overallRatio": 0.97},
            metadata={"assetCount": len(assets), "readiness": readiness},
        )
        if readiness["reviewPayloadReady"]:
            job_run.emit(
                "finalize",
                "succeeded",
                "review payload ready",
                event_type="review_payload_ready",
                progress={"overallRatio": 0.98},
                metadata={"readiness": readiness},
            )
        if readiness["previewToolsReady"]:
            job_run.emit(
                "finalize",
                "succeeded",
                "preview tools ready",
                event_type="preview_tools_ready",
                progress={"overallRatio": 0.99},
                metadata={"readiness": readiness},
            )
            job_run.emit(
                "finalize",
                "succeeded",
                "ready for review",
                event_type="ready_for_review",
                progress={"overallRatio": 1.0},
                metadata={"readiness": readiness},
            )
        else:
            job_run.emit(
                "finalize",
                "blocked",
                readiness["blockedReason"] or "Review assets are incomplete.",
                event_type="readiness_blocked",
                progress={"overallRatio": 0.99},
                metadata={"readiness": readiness},
            )
        job_run.succeed(
            scene=scene,
            result={
                "frames": int(scene.get("source", {}).get("sampledFrameCount") or 0),
                "objects": len(scene.get("objects", [])),
                "sceneGraph": "scene_graph.json",
                "readiness": readiness,
                "runtimeProof": runtime_proof,
            },
            progress_ratio=1.0 if readiness.get("readyForReview") else 0.99,
        )
        _register_output_tree(
            conn,
            storage=storage,
            project_id=job["project_id"],
            job_id=job["id"],
            out_dir=out_dir,
            source_asset_id=source_asset["id"],
            rel_path_filter={
                "run_config.json",
                "provider_diagnostics.json",
                "job.json",
                "events.jsonl",
                "logs.txt",
                "metrics.json",
                "artifacts.json",
            },
            replace_existing=True,
        )
        assets = list_assets_for_job(conn, project_id=job["project_id"], source_job_id=job["id"])

    frames = int(scene.get("source", {}).get("sampledFrameCount") or 0)
    objects = len(scene.get("objects", []))
    resource_profile = scene.get("resource_profile") if isinstance(scene.get("resource_profile"), dict) else {}
    latency_metrics = resource_profile.get("latencyMetrics") if isinstance(resource_profile.get("latencyMetrics"), dict) else scene.get("latencyMetrics", {})
    provider_performance = resource_profile.get("providerPerformance") if isinstance(resource_profile.get("providerPerformance"), dict) else scene.get("providerPerformance", {})
    cost_dashboard = resource_profile.get("costDashboard") if isinstance(resource_profile.get("costDashboard"), dict) else scene.get("costDashboard", {})
    record_usage_event(conn, user_id=job["created_by_user_id"], project_id=job["project_id"], job_id=job["id"], event_type="frames_processed", quantity=frames, unit="frame")
    record_usage_event(conn, user_id=job["created_by_user_id"], project_id=job["project_id"], job_id=job["id"], event_type="objects_extracted", quantity=objects, unit="object")
    if isinstance(latency_metrics, dict):
        total_ms = float(latency_metrics.get("totalElapsedMs") or 0.0)
        record_usage_event(
            conn,
            user_id=job["created_by_user_id"],
            project_id=job["project_id"],
            job_id=job["id"],
            event_type="latency_ms",
            quantity=total_ms,
            unit="ms",
            metadata={"phase": "extract_total"},
        )
        record_job_event(conn, job_id=job["id"], event_type="latency_metrics", message="extraction latency metrics recorded", metadata=latency_metrics)
    if isinstance(cost_dashboard, dict):
        for provider in cost_dashboard.get("providers", []):
            if not isinstance(provider, dict):
                continue
            record_usage_event(
                conn,
                user_id=job["created_by_user_id"],
                project_id=job["project_id"],
                job_id=job["id"],
                event_type="provider_attempts",
                quantity=float(provider.get("attempts") or 0),
                unit="attempt",
                metadata={
                    "provider": provider.get("provider"),
                    "estimatedCostUnits": provider.get("estimatedCostUnits"),
                    "costStatus": provider.get("costStatus"),
                },
            )
        cache = cost_dashboard.get("cache") if isinstance(cost_dashboard.get("cache"), dict) else {}
        record_usage_event(
            conn,
            user_id=job["created_by_user_id"],
            project_id=job["project_id"],
            job_id=job["id"],
            event_type="cache_hits",
            quantity=float(cache.get("hits") or 0),
            unit="hit",
            metadata={"readBytes": cache.get("readBytes", 0)},
        )
        record_usage_event(
            conn,
            user_id=job["created_by_user_id"],
            project_id=job["project_id"],
            job_id=job["id"],
            event_type="cache_misses",
            quantity=float(cache.get("misses") or 0),
            unit="miss",
            metadata={"writtenBytes": cache.get("writtenBytes", 0)},
        )
        record_job_event(conn, job_id=job["id"], event_type="cost_dashboard", message="provider cost dashboard recorded", metadata=cost_dashboard)
    record_audit_event(
        conn,
        user_id=job["created_by_user_id"],
        project_id=job["project_id"],
        job_id=job["id"],
        asset_id=source_asset["id"],
        event_type="extract_completed",
        metadata={"frames": frames, "objects": objects, "maskProvider": provider_name, "latencyMetrics": latency_metrics, "providerPerformance": provider_performance},
    )
    return {
        "scene": {"frames": frames, "objects": objects},
        "assetIds": [asset["id"] for asset in assets],
        "latencyMetrics": latency_metrics,
        "costDashboard": cost_dashboard,
        "readiness": readiness,
        "runtimeProof": runtime_proof,
    }


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
    object_ids = [str(item) for item in payload.get("object_ids", [])] if isinstance(payload.get("object_ids"), list) else None
    with tempfile.TemporaryDirectory(prefix="motionjson_backend_export_") as tmp:
        tmp_dir = Path(tmp)
        extraction_dir = tmp_dir / "extraction"
        extraction_dir.mkdir()
        _materialize_job_assets(conn, storage=storage, project_id=job["project_id"], source_job_id=source_job_id, out_dir=extraction_dir)
        output_path = tmp_dir / "website_package.zip"
        entry = export_website_package(out_dir=extraction_dir, output_path=output_path, object_ids=object_ids)
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
            metadata={"aiUsage": "none", "exportEntry": entry, "selectedObjectIds": entry.get("selectedObjectIds", [])},
        )
        record_asset_lineage(
            conn,
            project_id=job["project_id"],
            source_asset_id=source_asset_id,
            derived_asset_id=asset["id"],
            job_id=job["id"],
            operation="export_website_package",
            metadata={"format": "website-zip", "sourceJobId": source_job_id, "selectedObjectIds": entry.get("selectedObjectIds", [])},
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
            metadata={"format": "website-zip", "aiUsage": "none", "selectedObjectIds": entry.get("selectedObjectIds", [])},
        )
    record_usage_event(conn, user_id=job["created_by_user_id"], project_id=job["project_id"], job_id=job["id"], event_type="exports_produced", quantity=1, unit="export", metadata={"format": "website-zip", "assetId": asset["id"], "selectedObjectIds": entry.get("selectedObjectIds", [])})
    return {"assetId": asset["id"], "format": "website-zip", "selectedObjectIds": entry.get("selectedObjectIds", []), "aiUsage": "none"}


def _first_scene_object(scene: dict[str, Any], object_id: str | None = None) -> dict[str, Any]:
    objects = scene.get("objects") or []
    if object_id:
        for obj in objects:
            if obj.get("id") == object_id:
                return obj
        raise ValueError(f"object {object_id!r} not found in scene graph")
    if not objects:
        raise ValueError("scene graph does not contain objects")
    first = objects[0]
    if not isinstance(first, dict):
        raise ValueError("scene object must be a JSON object")
    return first


def _canvas(scene: dict[str, Any]) -> dict[str, Any]:
    source = scene.get("source", {})
    canvas = scene.get("canvas", {})
    return {
        "width": int(source.get("width") or canvas.get("width") or 1),
        "height": int(source.get("height") or canvas.get("height") or 1),
        "fps": float(source.get("sampleFps") or canvas.get("fps") or 12),
        "frameCount": int(source.get("sampledFrameCount") or canvas.get("frame_count") or 0),
    }


def _render_webm_alpha(*, extraction_dir: Path, output_path: Path, object_id: str | None) -> dict[str, Any]:
    scene = load_scene(extraction_dir)
    obj = _first_scene_object(scene, object_id)
    selected_object_id = str(obj.get("id"))
    canvas = _canvas(scene)
    webm = export_transparent_webm_object(
        out_dir=extraction_dir,
        output_path=output_path,
        motion=obj.get("motion", []),
        width=canvas["width"],
        height=canvas["height"],
        fps=canvas["fps"],
    )
    return final_export_entry(
        export_type="transparent_webm_object",
        format_name="webm-alpha",
        output_path=output_path,
        out_dir=extraction_dir,
        status=webm.get("status", "error"),
        mime_type=webm.get("mimeType", "video/webm"),
        width=canvas["width"],
        height=canvas["height"],
        fps=canvas["fps"],
        frame_count=canvas["frameCount"],
        reason=webm.get("reason"),
        extra={
            "objectId": selected_object_id,
            "encoder": webm.get("encoder", "ffmpeg"),
            "pixelFormat": "yuva420p",
            "cachedSource": webm.get("cachedSource", "cached_rgba_cutout_png_sequence"),
            "cachedSources": ["scene_graph.json", f"objects/{selected_object_id}/cutouts/*.png"],
            "source": webm.get("source", "cached_rgba_cutout_png_sequence_and_json_transforms"),
            "aiUsage": "none",
        },
    )


def _render_asset_kind(entry: dict[str, Any]) -> str:
    if entry.get("format") == "mp4":
        return "final_render_mp4"
    if entry.get("format") == "webm-alpha":
        return "transparent_webm"
    if entry.get("type") == "remotion_plan":
        return "remotion_plan"
    return "render_output"


def _register_render_entry(
    conn: sqlite3.Connection,
    *,
    storage: StorageProvider,
    job: dict[str, Any],
    extraction_dir: Path,
    entry: dict[str, Any],
    source_asset_id: str | None,
) -> dict[str, Any] | None:
    rel_path = entry.get("path")
    if not isinstance(rel_path, str) or entry.get("status") not in {"ready", "plan_ready"}:
        return None
    path = extraction_dir / rel_path
    if not path.exists() or not path.is_file():
        return None
    asset = register_generated_asset(
        conn,
        storage=storage,
        project_id=job["project_id"],
        kind=_render_asset_kind(entry),
        source_job_id=job["id"],
        path=path,
        rel_path=rel_path,
        content_type=entry.get("mimeType") or mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        metadata={"aiUsage": "none", "renderEntry": entry},
    )
    record_asset_lineage(
        conn,
        project_id=job["project_id"],
        source_asset_id=source_asset_id,
        derived_asset_id=asset["id"],
        job_id=job["id"],
        operation="render_cached_assets",
        object_id=entry.get("objectId"),
        metadata={"format": entry.get("format"), "source": entry.get("source"), "aiUsage": "none"},
    )
    record_audit_event(
        conn,
        user_id=job["created_by_user_id"],
        project_id=job["project_id"],
        job_id=job["id"],
        asset_id=asset["id"],
        object_id=entry.get("objectId"),
        event_type="render_asset_registered",
        metadata={"format": entry.get("format"), "status": entry.get("status"), "aiUsage": "none"},
    )
    return asset


def _run_render(conn: sqlite3.Connection, *, storage: StorageProvider, job: dict[str, Any]) -> dict[str, Any]:
    payload = _json(job, "payload_json")
    source_job_id = str(payload["source_job_id"])
    format_name = str(payload.get("format") or "remotion-plan")
    with tempfile.TemporaryDirectory(prefix="motionjson_backend_render_") as tmp:
        tmp_dir = Path(tmp)
        extraction_dir = tmp_dir / "extraction"
        extraction_dir.mkdir()
        _materialize_job_assets(conn, storage=storage, project_id=job["project_id"], source_job_id=source_job_id, out_dir=extraction_dir)
        exports_dir = extraction_dir / "exports"
        exports_dir.mkdir(parents=True, exist_ok=True)
        scene = load_scene(extraction_dir)

        if format_name == "remotion-plan":
            entry = write_remotion_plan(out_dir=extraction_dir, output_path=exports_dir / "remotion_export_plan.json")
        elif format_name == "mp4":
            editor_state = payload.get("editor_state") if isinstance(payload.get("editor_state"), dict) and payload.get("editor_state") else None
            editor_state_path = None
            if editor_state:
                editor_state_path = exports_dir / "editor_state.json"
                editor_state_path.write_text(json.dumps(editor_state, sort_keys=True), encoding="utf-8")
            entry = export_mp4(
                out_dir=extraction_dir,
                output_path=exports_dir / "final.mp4",
                background_color=str(payload.get("background_color") or "#fbfaf6"),
                editor_state_path=editor_state_path,
            )
        elif format_name == "webm-alpha":
            entry = _render_webm_alpha(
                extraction_dir=extraction_dir,
                output_path=exports_dir / f"{payload.get('object_id') or 'object_0'}.webm",
                object_id=payload.get("object_id"),
            )
        else:
            raise ValueError("render format must be remotion-plan, mp4, or webm-alpha")

        manifest_path = exports_dir / "final_export_manifest.json"
        write_final_export_manifest(
            manifest_path=manifest_path,
            out_dir=extraction_dir,
            scene=scene,
            exports=[entry],
            object_id=payload.get("object_id"),
        )
        source_asset_id = _source_asset_for_extraction(conn, source_job_id=source_job_id)
        asset = _register_render_entry(conn, storage=storage, job=job, extraction_dir=extraction_dir, entry=entry, source_asset_id=source_asset_id)
        manifest_asset = register_generated_asset(
            conn,
            storage=storage,
            project_id=job["project_id"],
            kind="final_export_manifest",
            source_job_id=job["id"],
            path=manifest_path,
            rel_path="exports/final_export_manifest.json",
            content_type="application/json",
            metadata={"aiUsage": "none", "renderStatus": entry.get("status"), "renderFormat": format_name},
        )
        record_asset_lineage(
            conn,
            project_id=job["project_id"],
            source_asset_id=source_asset_id,
            derived_asset_id=manifest_asset["id"],
            job_id=job["id"],
            operation="render_manifest",
            object_id=payload.get("object_id"),
            metadata={"format": format_name, "aiUsage": "none"},
        )

    record_usage_event(
        conn,
        user_id=job["created_by_user_id"],
        project_id=job["project_id"],
        job_id=job["id"],
        event_type="renders_requested",
        quantity=1,
        unit="render",
        metadata={"format": format_name, "status": entry.get("status"), "assetId": asset["id"] if asset else None},
    )
    record_audit_event(
        conn,
        user_id=job["created_by_user_id"],
        project_id=job["project_id"],
        job_id=job["id"],
        asset_id=asset["id"] if asset else None,
        object_id=payload.get("object_id"),
        event_type="render_completed",
        metadata={"format": format_name, "status": entry.get("status"), "aiUsage": "none"},
    )
    return {
        "assetId": asset["id"] if asset else None,
        "manifestAssetId": manifest_asset["id"],
        "format": format_name,
        "status": entry.get("status"),
        "entry": entry,
        "aiUsage": "none",
    }


def process_job(conn: sqlite3.Connection, *, storage: StorageProvider, job: dict[str, Any]) -> dict[str, Any]:
    mark_running(conn, job_id=job["id"])
    record_job_event(conn, job_id=job["id"], event_type="worker_claimed", message="worker claimed job")
    fresh_job = dict(conn.execute("SELECT * FROM jobs WHERE id = ?", (job["id"],)).fetchone())
    if fresh_job["type"] == "extract":
        return _run_extract(conn, storage=storage, job=fresh_job)
    if fresh_job["type"] == "export":
        return _run_export(conn, storage=storage, job=fresh_job)
    if fresh_job["type"] == "render":
        return _run_render(conn, storage=storage, job=fresh_job)
    raise ValueError(f"unsupported job type: {fresh_job['type']}")


def _asset_ids_from_result(result: dict[str, Any]) -> list[str]:
    asset_ids: list[str] = []
    if isinstance(result.get("assetIds"), list):
        asset_ids.extend(str(asset_id) for asset_id in result["assetIds"] if asset_id)
    for key in ("assetId", "manifestAssetId"):
        value = result.get(key)
        if value:
            asset_ids.append(str(value))
    return list(dict.fromkeys(asset_ids))


def _deliver_success_events(
    conn: sqlite3.Connection,
    *,
    job: dict[str, Any],
    result: dict[str, Any],
    transport: WebhookTransport | None = None,
) -> None:
    deliver_event(
        conn,
        user_id=job["created_by_user_id"],
        event_type="job.succeeded",
        payload={"jobId": job["id"], "projectId": job["project_id"], "type": job["type"], "status": job["status"], "result": result},
        transport=transport,
    )
    for asset_id in _asset_ids_from_result(result):
        deliver_event(
            conn,
            user_id=job["created_by_user_id"],
            event_type="asset.created",
            payload={"assetId": asset_id, "jobId": job["id"], "projectId": job["project_id"], "jobType": job["type"]},
            transport=transport,
        )
    if job["type"] == "export" and result.get("assetId"):
        deliver_event(
            conn,
            user_id=job["created_by_user_id"],
            event_type="asset_package.ready",
            payload={"assetId": result["assetId"], "jobId": job["id"], "projectId": job["project_id"], "format": result.get("format"), "aiUsage": "none"},
            transport=transport,
        )
    if job["type"] == "render":
        deliver_event(
            conn,
            user_id=job["created_by_user_id"],
            event_type="render.ready",
            payload={
                "assetId": result.get("assetId"),
                "manifestAssetId": result.get("manifestAssetId"),
                "jobId": job["id"],
                "projectId": job["project_id"],
                "format": result.get("format"),
                "status": result.get("status"),
                "aiUsage": "none",
            },
            transport=transport,
        )


def worker_once(
    conn: sqlite3.Connection,
    *,
    storage: StorageProvider,
    worker_id: str | None = None,
    max_attempts: int = 1,
    webhook_transport: WebhookTransport | None = None,
) -> dict[str, Any] | None:
    claimed = claim_next(conn, worker_id=worker_id or f"worker-{uuid.uuid4().hex[:8]}")
    if claimed is None:
        return None
    try:
        result = process_job(conn, storage=storage, job=claimed)
    except JobCanceled as exc:
        canceled = mark_canceled(conn, job_id=claimed["id"], reason=str(exc))
        deliver_event(
            conn,
            user_id=canceled["created_by_user_id"],
            event_type="job.canceled",
            payload={"jobId": canceled["id"], "projectId": canceled["project_id"], "type": canceled["type"], "status": canceled["status"], "error": canceled["error"]},
            transport=webhook_transport,
        )
        return canceled
    except Exception as exc:
        failed = mark_failed(conn, job_id=claimed["id"], error=str(exc), max_attempts=max_attempts)
        if failed["status"] == "failed":
            deliver_event(
                conn,
                user_id=failed["created_by_user_id"],
                event_type="job.failed",
                payload={"jobId": failed["id"], "projectId": failed["project_id"], "type": failed["type"], "status": failed["status"], "error": failed["error"]},
                transport=webhook_transport,
        )
        return failed
    succeeded = mark_succeeded(conn, job_id=claimed["id"], result=result)
    _deliver_success_events(conn, job=succeeded, result=result, transport=webhook_transport)
    return succeeded
