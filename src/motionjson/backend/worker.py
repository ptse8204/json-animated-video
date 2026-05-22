from __future__ import annotations

import json
import mimetypes
import sqlite3
import tempfile
import uuid
import zipfile
from pathlib import Path
from typing import Any

from motionjson.config import (
    ExtractionRunConfig,
    ExternalMaskProviderConfig,
    OutputConfig,
    ProviderConfig,
    SamplingConfig,
    ThresholdProviderConfig,
    VideoInputConfig,
)
from motionjson.exporters.final_render import export_mp4, final_export_entry, load_scene, write_final_export_manifest
from motionjson.exporters.production_assets import export_transparent_webm_object
from motionjson.exporters.remotion import write_remotion_plan
from motionjson.exporters.website_package import export_website_package
from motionjson.job_artifacts import JobCanceled, LocalJobRun, artifact_kind_for_rel_path
from motionjson.masks import ExternalMaskProvider, MotionMaskProvider, ThresholdMaskProvider
from motionjson.pipeline import run_multi_object_pipeline, run_pipeline
from motionjson.provider_settings import provider_runtime_settings
from motionjson.providers.base import ProviderConfigError, StorageProvider
from motionjson.providers.discovery import (
    ClassDetectorDiscoveryProvider,
    MockObjectDiscoveryProvider,
    MotionForegroundDiscoveryProvider,
    SAM2AutomaticProposalDiscoveryProvider,
    SAM3AutoMasksDiscoveryProvider,
    SAM3ConceptDiscoveryProvider,
    SAM3ExemplarDiscoveryProvider,
    SamAutoMasksDiscoveryProvider,
    TextDetectorDiscoveryProvider,
    object_specs_from_candidates,
)
from motionjson.providers.mocks import MockSegmentationProvider
from motionjson.providers.sam2 import HostedSAM2SegmentationProvider
from motionjson.providers.segmentation import SegmentationMaskProvider

from .assets import _asset_row, list_assets_for_job, register_generated_asset
from .jobs import record_job_event
from .models import validate_extract_provider_policy
from .queue import claim_next, mark_canceled, mark_failed, mark_running, mark_succeeded
from .rights import record_asset_lineage, record_audit_event, record_rights_metadata
from .usage import record_usage_event
from .webhooks import WebhookTransport, deliver_event


def _json(row: dict[str, Any], field: str) -> dict[str, Any]:
    parsed = json.loads(row[field] or "{}")
    if not isinstance(parsed, dict):
        raise ValueError(f"{field} must contain a JSON object")
    return parsed


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


def _event_mirror(conn: sqlite3.Connection, job_id: str):
    def mirror(event: dict[str, Any]) -> None:
        event_type = "progress" if event.get("type") == "progress" else f"job_{event.get('status', 'event')}"
        record_job_event(
            conn,
            job_id=job_id,
            event_type=event_type,
            message=str(event.get("message") or event.get("stage") or "job event"),
            metadata=event,
        )

    return mirror


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


def _ui_discovery_provider(mode: str, config: dict[str, Any] | None = None) -> tuple[Any, str, bool] | None:
    discovery_config = dict(config or {})
    if mode == "auto_object_proposals":
        provider_preference = str(discovery_config.get("providerPreference") or discovery_config.get("provider_preference") or "auto")
        if discovery_config.get("mock") or provider_preference == "mock":
            return MockObjectDiscoveryProvider(), "automatic object proposal mock discovery configured", True
        return SAM2AutomaticProposalDiscoveryProvider(), "SAM2 automatic object proposals configured", False
    if mode == "text_detector":
        return TextDetectorDiscoveryProvider(), "text detector mock discovery configured", True
    if mode == "sam_auto_masks":
        if discovery_config.get("mock"):
            return SamAutoMasksDiscoveryProvider(), "automatic mask mock proposals configured", True
        return SamAutoMasksDiscoveryProvider(), "SAM2 automatic mask proposals configured", False
    if mode == "sam3_concept":
        if discovery_config.get("mock"):
            return SAM3ConceptDiscoveryProvider(), "SAM3 concept mock discovery configured", True
        return SAM3ConceptDiscoveryProvider(), "SAM3 local concept discovery configured", False
    if mode == "sam3_exemplar":
        if discovery_config.get("mock"):
            return SAM3ExemplarDiscoveryProvider(), "SAM3 exemplar mock discovery configured", True
        return SAM3ExemplarDiscoveryProvider(), "SAM3 local exemplar discovery configured", False
    if mode == "sam3_auto_masks":
        if discovery_config.get("mock"):
            return SAM3AutoMasksDiscoveryProvider(), "SAM3 auto-mask mock discovery configured", True
        return SAM3AutoMasksDiscoveryProvider(), "SAM3 local auto-mask discovery configured", False
    if mode == "class_detector":
        return ClassDetectorDiscoveryProvider(), "class detector mock discovery configured", True
    if mode == "motion_foreground":
        return MotionForegroundDiscoveryProvider(), "motion foreground CPU discovery configured", False
    return None


def _run_extract(conn: sqlite3.Connection, *, storage: StorageProvider, job: dict[str, Any]) -> dict[str, Any]:
    payload = _json(job, "payload_json")
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
            cancel_check=lambda: _backend_cancel_requested(conn, job["id"]),
        )
        job_run.initialize(video_path=video_path, output_dir=out_dir)
        job_run.start()
        job_run.emit("validating_config", "succeeded", "backend extraction payload validated", progress={"overallRatio": 0.03}, metadata={"provider": provider_name})

        try:
            discovery_mode = run_config.discovery.mode if run_config is not None else None
            discovery_config = dict(run_config.discovery.config) if run_config is not None else {}
            hosted_sam3_backend = None
            if run_config is not None:
                sam2_config = run_config.provider.sam2
                if sam2_config.checkpoint and not any(key in discovery_config for key in ("sam2Checkpoint", "sam2_checkpoint", "checkpoint")):
                    discovery_config["sam2Checkpoint"] = sam2_config.checkpoint
                if sam2_config.model_config and not any(key in discovery_config for key in ("sam2ModelConfig", "sam2_model_config", "model_config")):
                    discovery_config["sam2ModelConfig"] = sam2_config.model_config
                if sam2_config.device and not any(key in discovery_config for key in ("sam2Device", "sam2_device", "device")):
                    discovery_config["sam2Device"] = sam2_config.device
                if discovery_mode in {"sam3_concept", "sam3_exemplar", "sam3_auto_masks"}:
                    discovery_config, hosted_sam3_backend = _hosted_sam3_discovery_runtime(
                        conn,
                        user_id=job["created_by_user_id"],
                        discovery_config=discovery_config,
                    )
            if hosted_sam3_backend is not None and discovery_mode == "sam3_concept":
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
            else:
                discovery_provider = _ui_discovery_provider(discovery_mode or "", discovery_config)
            if discovery_provider is not None:
                provider, message, requires_mock = discovery_provider
                if requires_mock and not discovery_config.get("mock"):
                    raise RuntimeError(
                        f"local UI {discovery_mode} jobs require discovery.config.mock=true; real discovery adapters remain capability-gated"
                    )
                job_run.emit(
                    "provider_preflight",
                    "succeeded",
                    message,
                    progress={"overallRatio": 0.06},
                    metadata={"provider": provider_name, "discoveryMode": discovery_mode},
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
                    job_context=job_run,
                )
            elif discovery_mode not in {None, "manual_prompt"}:
                raise RuntimeError(
                    f"local UI worker does not support discovery mode {discovery_mode!r} yet; use the CLI or a mock text-detector run"
                )
            elif provider_name == "external":
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
                    job_context=job_run,
                )
            else:
                if provider_name == "mock":
                    mask_provider = SegmentationMaskProvider(MockSegmentationProvider())
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
                    job_context=job_run,
                )
        except JobCanceled as exc:
            job_run.cancel(str(exc))
            _register_output_tree(conn, storage=storage, project_id=job["project_id"], job_id=job["id"], out_dir=out_dir, source_asset_id=source_asset["id"])
            raise
        except ProviderConfigError as exc:
            job_run.fail(exc, reason_code="provider_unavailable", user_message=str(exc))
            _register_output_tree(conn, storage=storage, project_id=job["project_id"], job_id=job["id"], out_dir=out_dir, source_asset_id=source_asset["id"])
            raise
        except Exception as exc:
            job_run.fail(exc)
            _register_output_tree(conn, storage=storage, project_id=job["project_id"], job_id=job["id"], out_dir=out_dir, source_asset_id=source_asset["id"])
            raise

        try:
            job_run.check_cancel("finalize")
        except JobCanceled as exc:
            job_run.cancel(str(exc))
            _register_output_tree(conn, storage=storage, project_id=job["project_id"], job_id=job["id"], out_dir=out_dir, source_asset_id=source_asset["id"])
            raise
        job_run.succeed(
            scene=scene,
            result={
                "frames": int(scene.get("source", {}).get("sampledFrameCount") or 0),
                "objects": len(scene.get("objects", [])),
                "sceneGraph": "scene_graph.json",
            },
        )
        assets = _register_output_tree(conn, storage=storage, project_id=job["project_id"], job_id=job["id"], out_dir=out_dir, source_asset_id=source_asset["id"])

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
    return {"scene": {"frames": frames, "objects": objects}, "assetIds": [asset["id"] for asset in assets], "latencyMetrics": latency_metrics, "costDashboard": cost_dashboard}


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
