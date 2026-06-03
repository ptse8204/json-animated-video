from __future__ import annotations

import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from PIL import Image
from tqdm import tqdm

from .exporters.lottie import write_silhouette_lottie
from .exporters.production_assets import export_production_assets
from .exporters.scene_graph import write_json
from .exporters.web_manifest import write_web_asset_manifest
from .layers import crop_rgba_layer, write_spritesheet
from .masks import MaskProvider as LegacyMaskProvider
from .metrics import build_cost_dashboard, build_resource_profile
from .providers.pipeline_adapters import (
    ContourVectorizer,
    IdentityTrackLinker,
    ObjectSpecCandidateProvider,
    ObjectSpecInitialMaskProvider,
    PerFrameMaskVideoTracker,
)
from .rights import build_object_rights, build_rights_manifest, normalize_rights_context, write_rights_manifest
from .track_filters import TrackFilterConfig, build_raster_fallback, evaluate_track, filter_and_dedupe_tracks
from .tracks import InitialMask, ObjectCandidate, ObjectTrack, RunContext, VideoSource
from .vectorize import build_quality_scores, recommended_output
from .video import iter_sampled_frames
from .providers.base import ObjectCandidateProvider, PhaseTiming, ProviderConfigError


SAFE_OBJECT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


@dataclass(frozen=True)
class ObjectExtractionSpec:
    object_id: str
    label: str
    mask_provider: LegacyMaskProvider
    z_index: int = 10
    metadata: dict[str, Any] = field(default_factory=dict)


def _validate_object_id(object_id: str) -> None:
    if not SAFE_OBJECT_ID_PATTERN.match(object_id):
        raise ValueError("Object IDs must be safe path segments using letters, numbers, underscores, or hyphens")


def _validate_object_specs(object_specs: Sequence[ObjectExtractionSpec]) -> None:
    object_ids = [spec.object_id for spec in object_specs]
    for object_id in object_ids:
        _validate_object_id(object_id)
    if len(set(object_ids)) != len(object_ids):
        raise ValueError("Object extraction specs must use unique object IDs")


def _candidate_provider_name(provider: ObjectCandidateProvider) -> str:
    name = getattr(provider, "name", None)
    if not isinstance(name, str) or not name.strip():
        raise ProviderConfigError(
            f"Discovery provider {type(provider).__name__} must define a non-empty name before it can run in the extraction pipeline."
        )
    return name.strip()


def _candidate_payload(
    *,
    provider_name: str,
    config: dict[str, Any],
    video_source: VideoSource,
    candidates: Sequence[ObjectCandidate],
) -> dict[str, Any]:
    return {
        "format": "motionjson.candidates.v0.1",
        "provider": provider_name,
        "config": config,
        "video": video_source.to_summary(),
        "candidates": [candidate.to_dict() for candidate in candidates],
    }


def _candidate_rejection_counts(candidates: Sequence[ObjectCandidate]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for candidate in candidates:
        reason = str(candidate.metadata.get("rejectionReason") or "").strip()
        review_status = str(candidate.metadata.get("reviewStatus") or "").strip().lower()
        if not reason and review_status in {"rejected", "ignored", "excluded"}:
            reason = review_status
        if reason:
            counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items()))


def _candidate_rejection_summary(counts: Mapping[str, int]) -> str:
    if not counts:
        return ""
    details = ", ".join(f"{reason}={count}" for reason, count in counts.items())
    return f" Rejection reasons: {details}."


def _clear_generated_frames(*directories: Path) -> None:
    for directory in directories:
        if not directory.exists():
            continue
        for pattern in ("frame_*.png", "mask_*.png", "cutout_*.png", "layer_*.webp", "layer_*.png"):
            for file in directory.glob(pattern):
                file.unlink()


def _preview_copy(out_dir: Path) -> None:
    preview_dir = out_dir / "preview"
    preview_dir.mkdir(parents=True, exist_ok=True)
    repo_root = Path(__file__).resolve().parents[2]
    for name in (
        "canvas_player.html",
        "pixi_player.html",
        "plain_js_embed.html",
        "website_graphics_hero.html",
        "object_selection_workflow.html",
        "object_selection_workflow.js",
        "timeline_editor.html",
        "timeline_editor.js",
    ):
        src = repo_root / "examples" / name
        if src.exists():
            shutil.copyfile(src, preview_dir / name)
    for directory_name in ("website_templates", "website_snippets"):
        src_dir = repo_root / "examples" / directory_name
        dest_dir = preview_dir / directory_name
        if src_dir.exists():
            if dest_dir.exists():
                shutil.rmtree(dest_dir)
            shutil.copytree(src_dir, dest_dir)
    runtime_src = repo_root / "packages" / "motionjson-runtime" / "src"
    runtime_dest = preview_dir / "runtime"
    if runtime_src.exists():
        if runtime_dest.exists():
            shutil.rmtree(runtime_dest)
        shutil.copytree(runtime_src, runtime_dest)


def _rel(path: Path, root: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def _elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 3)


def _fallback_payload(*, diagnostics: list[dict[str, Any]], summary: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "format": "motionjson.raster_fallback_diagnostics.v0.1",
        "diagnostics": diagnostics,
        "summary": dict(summary or {}),
    }


AUTO_REVIEW_DISCOVERY_SOURCES = {
    "auto_object_proposals",
    "sam_auto_masks",
    "sam3_concept",
    "sam3_exemplar",
    "sam3_auto_masks",
    "text_detector",
    "class_detector",
    "motion_foreground",
}


def _text_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _number_or_none(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in {float("inf"), float("-inf")}:
        return None
    return number


def _score_or_none(value: Any) -> float | None:
    number = _number_or_none(value)
    if number is None:
        return None
    return round(max(0.0, min(1.0, number)), 4)


def _bool_or_default(value: Any, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _motion_coverage(track: ObjectTrack, quality: Mapping[str, Any]) -> float:
    explicit = _score_or_none(quality.get("visibleFrameRatio"))
    if explicit is not None:
        return explicit
    if not track.frames:
        return 0.0
    visible = sum(1 for frame in track.frames if frame.visible)
    return round(visible / len(track.frames), 4)


def _discovery_artifacts(metadata: Mapping[str, Any]) -> dict[str, Any]:
    artifacts: dict[str, Any] = {}
    for key in (
        "maskDir",
        "thumbnailArtifactPath",
        "maskPreviewArtifactPath",
        "thumbnailArtifactId",
        "maskPreviewArtifactId",
    ):
        value = _text_or_none(metadata.get(key))
        if value is not None:
            artifacts[key] = value
    return artifacts


def _discovery_lineage(object_id: str, rights_context: Mapping[str, Any] | None) -> dict[str, Any]:
    rights = _mapping_or_empty(rights_context)
    return {
        "objectId": object_id,
        "rightsManifest": "rights_manifest.json",
        "sourceType": _text_or_none(rights.get("source_type")),
        "sourceAssetId": _text_or_none(rights.get("source_asset_id")),
        "sourceUri": _text_or_none(rights.get("source_uri")),
        "license": _text_or_none(rights.get("license")),
        "assetLineage": {
            "origin": "source_video",
            "operations": ["object_discovery", "mask_tracking", "motionjson_export"],
        },
    }


def _build_discovery_metadata(
    *,
    spec: ObjectExtractionSpec,
    initial: InitialMask | None,
    track: ObjectTrack,
    quality: Mapping[str, Any],
    rights_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    candidate = initial.candidate if initial is not None else None
    candidate_doc = candidate.to_dict() if candidate is not None else {}
    spec_metadata = _mapping_or_empty(spec.metadata)
    candidate_metadata = {
        **_mapping_or_empty(spec_metadata.get("candidateMetadata")),
        **_mapping_or_empty(candidate.metadata if candidate is not None else None),
    }
    candidate_id = _text_or_none(
        candidate_doc.get("candidateId")
        or candidate_doc.get("id")
        or candidate_metadata.get("candidateId")
        or candidate_metadata.get("candidate_id")
        or spec_metadata.get("candidateId")
        or spec.object_id
    )
    source = _text_or_none(candidate_doc.get("source") or candidate_metadata.get("source") or spec_metadata.get("source")) or "manual_object_spec"
    provider_name = _text_or_none(
        candidate_metadata.get("providerName")
        or candidate_metadata.get("provider_name")
        or (initial.provider_name if initial is not None else None)
        or track.provider_name
    )
    review_status = _text_or_none(candidate_metadata.get("reviewStatus") or candidate_metadata.get("review_status"))
    rejection_reason = _text_or_none(candidate_metadata.get("rejectionReason") or candidate_metadata.get("rejection_reason"))
    selected_for_tracking = _bool_or_default(
        candidate_metadata.get("selectedForTracking"),
        default=_bool_or_default(candidate_metadata.get("defaultSelected"), default=rejection_reason is None),
    )
    if review_status is None:
        if rejection_reason is not None:
            review_status = "rejected"
        elif selected_for_tracking and source in AUTO_REVIEW_DISCOVERY_SOURCES:
            review_status = "pending"
        else:
            review_status = "accepted"
    review_status = review_status.strip().lower()
    review_required = _bool_or_default(
        candidate_metadata.get("reviewRequired"),
        default=source in AUTO_REVIEW_DISCOVERY_SOURCES and review_status in {"pending", "selected", "review_pending"},
    )
    export_status = _text_or_none(track.export_status) or ("review_pending" if review_required else "accepted")
    if review_required and export_status == "accepted":
        export_status = "review_pending"
    motion_coverage = _motion_coverage(track, quality)
    candidate_score = _score_or_none(
        candidate_doc.get("score")
        if candidate_doc.get("score") is not None
        else candidate_metadata.get("confidence", candidate_metadata.get("score"))
    )
    track_confidence = _score_or_none(track.confidence if track.confidence is not None else candidate_score)
    warnings = candidate_metadata.get("warnings")
    if not isinstance(warnings, list):
        warnings = []
    return {
        "candidateId": candidate_id,
        "source": source,
        "providerName": provider_name,
        "providerModel": _text_or_none(
            candidate_metadata.get("providerModel")
            or candidate_metadata.get("provider_model")
            or candidate_metadata.get("modelName")
            or candidate_metadata.get("model")
        ),
        "qualityPreset": _text_or_none(candidate_metadata.get("qualityPreset") or candidate_metadata.get("quality_preset")),
        "candidateScore": candidate_score,
        "stabilityScore": _score_or_none(candidate_metadata.get("stabilityScore") or candidate_metadata.get("stability_score")),
        "motionScore": _score_or_none(candidate_metadata.get("motionScore") or candidate_metadata.get("motion_score")),
        "frameCoverageEstimate": _score_or_none(
            candidate_metadata.get("frameCoverageEstimate") or candidate_metadata.get("frame_coverage_estimate")
        ),
        "reviewStatus": review_status,
        "rejectionReason": rejection_reason,
        "selectedForTracking": selected_for_tracking,
        "defaultSelected": _bool_or_default(candidate_metadata.get("defaultSelected"), default=selected_for_tracking),
        "trackConfidence": track_confidence,
        "motionCoverage": motion_coverage,
        "reviewRequired": review_required,
        "exportStatus": export_status,
        "trackingProvider": _text_or_none(candidate_metadata.get("trackingProvider") or candidate_metadata.get("tracking_provider")),
        "correctionHistoryRef": _text_or_none(
            candidate_metadata.get("correctionHistoryRef") or spec_metadata.get("correctionHistoryRef")
        ),
        "warnings": [str(item) for item in warnings],
        "filters": _mapping_or_empty(candidate_metadata.get("filters")),
        "artifacts": _discovery_artifacts(candidate_metadata),
        "lineage": _discovery_lineage(spec.object_id, rights_context),
    }


def _trace_everything_export_gate(provider_name: str, config: dict[str, Any]) -> dict[str, Any] | None:
    if provider_name != "auto_object_proposals":
        return None
    if str(config.get("qualityPreset") or config.get("quality_preset") or "") != "trace_everything":
        return None
    return {
        "reason": "trace_everything_requires_review",
        "qualityPreset": "trace_everything",
        "reviewRequired": True,
    }


def _mark_trace_everything_review_pending(
    *,
    objects: list[dict[str, Any]],
    layers: list[dict[str, Any]],
    tracks: list[ObjectTrack],
    gate: dict[str, Any],
) -> None:
    for obj in objects:
        quality = obj.get("quality") if isinstance(obj.get("quality"), dict) else {}
        obj["quality"] = {**quality, "reviewRequired": True, "exportReviewGate": dict(gate)}
    for layer in layers:
        controls = layer.get("controls") if isinstance(layer.get("controls"), dict) else {}
        layer["controls"] = {**controls, "reviewRequired": True, "exportReviewGate": dict(gate)}
    for track in tracks:
        if str(track.export_status or "accepted") == "accepted":
            track.export_status = "review_pending"
        track.metadata = {**track.metadata, "reviewRequired": True, "exportReviewGate": dict(gate)}


def _apply_track_filter_decisions(
    *,
    objects: list[dict[str, Any]],
    layers: list[dict[str, Any]],
    tracks: Sequence[ObjectTrack],
    filter_report: Mapping[str, Any],
) -> None:
    decisions = filter_report.get("decisions") if isinstance(filter_report.get("decisions"), list) else []
    decisions_by_id = {str(decision.get("objectId")): decision for decision in decisions if isinstance(decision, Mapping)}
    tracks_by_id = {track.object_id: track for track in tracks}
    for obj in objects:
        object_id = _text_or_none(obj.get("id") or obj.get("objectId"))
        if not object_id:
            continue
        decision = decisions_by_id.get(object_id)
        track = tracks_by_id.get(object_id)
        if not decision:
            continue
        status = str(decision.get("status") or "accepted")
        reason_codes = [str(reason) for reason in decision.get("reasonCodes", []) if reason]
        if status == "accepted":
            continue
        quality = obj.get("quality") if isinstance(obj.get("quality"), dict) else {}
        discovery = obj.get("discovery") if isinstance(obj.get("discovery"), dict) else {}
        obj["quality"] = {**quality, "trackFilter": dict(decision), "exportValidationStatus": status}
        obj["exportStatus"] = "rejected"
        obj["exportIncluded"] = False
        obj["discovery"] = {
            **discovery,
            "exportStatus": "rejected",
            "exportValidationReasonCodes": reason_codes,
            "reviewRequired": True,
        }
    for layer in layers:
        object_id = _text_or_none(layer.get("object_id") or layer.get("objectId"))
        decision = decisions_by_id.get(object_id or "")
        if decision and str(decision.get("status") or "accepted") != "accepted":
            controls = layer.get("controls") if isinstance(layer.get("controls"), dict) else {}
            layer["controls"] = {
                **controls,
                "exportStatus": "rejected",
                "exportIncluded": False,
                "exportValidationReasonCodes": [str(reason) for reason in decision.get("reasonCodes", []) if reason],
            }


def _job_emit(
    job_context: Any | None,
    stage: str,
    status: str,
    message: str,
    *,
    progress: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    emit = getattr(job_context, "emit", None)
    if callable(emit):
        emit(stage, status, message, progress=progress, metadata=metadata)


def _job_check_cancel(job_context: Any | None, stage: str) -> None:
    check = getattr(job_context, "check_cancel", None)
    if callable(check):
        check(stage)


ASSET_MATERIALIZATION_SKIP_REASONS = {"masks_too_large_whole_frame", "no_masks_accepted"}


def _should_skip_asset_materialization(reason_codes: Sequence[str]) -> bool:
    return any(reason in ASSET_MATERIALIZATION_SKIP_REASONS for reason in reason_codes)


def _object_dir(out_dir: Path, object_id: str) -> Path:
    return out_dir / "objects" / object_id


def _write_object_motion(out_dir: Path, object_id: str, object_motion: dict[str, Any], *, legacy: bool = False) -> None:
    write_json(_object_dir(out_dir, object_id) / "object_motion.json", object_motion)
    if legacy:
        write_json(out_dir / "object_motion.json", object_motion)


def _write_object_web_manifest(out_dir: Path, scene: dict[str, Any], object_id: str, *, legacy: bool = False) -> None:
    write_web_asset_manifest(
        _object_dir(out_dir, object_id) / "web_asset_manifest.json",
        scene,
        object_id=object_id,
        path_prefix="../../",
        source_scene_graph="../../scene_graph.json",
    )
    if legacy:
        write_web_asset_manifest(out_dir / "web_asset_manifest.json", scene, object_id=object_id)


def write_profiled_outputs(
    *,
    out_dir: Path,
    video_path: Path,
    object_id: str,
    scene: dict[str, Any],
    profile_updates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write profile-dependent outputs until self-reported JSON sizes stabilize."""
    profile: dict[str, Any] = {}
    seen_payloads: set[tuple[tuple[str, Any], ...]] = set()
    for _ in range(20):
        profile = build_resource_profile(video_path=video_path, out_dir=out_dir, object_id=object_id, scene=scene)
        if profile_updates:
            profile.update(profile_updates)
        scene["resource_profile"] = profile
        write_json(out_dir / "resource_profile.json", profile)
        write_json(out_dir / "scene_graph.json", scene)
        for index, obj in enumerate(scene.get("objects", [])):
            current_id = obj.get("id")
            if current_id:
                _write_object_web_manifest(out_dir, scene, current_id, legacy=index == 0 and current_id == object_id)
        payloads = profile.get("sizes", {}).get("payloads", {})
        actual_profile = build_resource_profile(video_path=video_path, out_dir=out_dir, object_id=object_id, scene=scene)
        if profile_updates:
            actual_profile.update(profile_updates)
        actual_payloads = actual_profile.get("sizes", {}).get("payloads", {})
        if actual_payloads == payloads:
            break
        payload_key = tuple(sorted(payloads.items()))
        if payload_key in seen_payloads:
            break
        seen_payloads.add(payload_key)
    return profile


def _build_layer_frames(object_id: str, fps: float, motion: list[dict[str, Any]], *, z_index: int = 10) -> dict[str, Any]:
    return {
        "id": f"{object_id}_raster_layer",
        "object_id": object_id,
        "type": "raster_alpha_sequence",
        "asset_type": "cropped_rgba_png_sequence",
        "fps": fps,
        "z_index": z_index,
        "blend_mode": "source-over",
        "frames": [
            {
                "frame": entry["frame"],
                "t": entry["t"],
                "visible": entry["visible"],
                "asset": entry["asset"],
                "mask": entry["mask"],
                "x": entry["x"],
                "y": entry["y"],
                "width": entry["w"],
                "height": entry["h"],
                "anchor": entry["anchor"],
                "opacity": entry["opacity"],
                "scale": entry["scale"],
                "rotation": entry["rotation"],
            }
            for entry in motion
        ],
        "controls": {
            "editable": ["x", "y", "scale", "rotation", "opacity", "visible", "z_index"],
            "json_edit_example": {
                "translate": [40, -20],
                "scale": 1.12,
                "rotation": 0.08,
                "opacity": 0.92,
            },
        },
    }


def _extract_object(
    *,
    out_dir: Path,
    frames_dir: Path,
    info: Any,
    frames: list[Any],
    video_source: VideoSource,
    initial_masks: list[InitialMask],
    run_context: RunContext,
    spec: ObjectExtractionSpec,
    min_area: float,
    simplify_ratio: float,
    feather: int,
    layer_padding: int,
    sprite_format: str,
    output_mode: str,
    production_avif: bool,
    rights_context: dict[str, Any] | None,
    job_context: Any | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, Any], ObjectTrack]:
    object_id = spec.object_id
    mask_dir = out_dir / "masks" / object_id
    object_dir = _object_dir(out_dir, object_id)
    cutout_dir = object_dir / "cutouts"
    for directory in (mask_dir, cutout_dir, object_dir):
        directory.mkdir(parents=True, exist_ok=True)
    _clear_generated_frames(mask_dir, cutout_dir)
    for stale_dir in (object_dir / "masks", object_dir / "layers", object_dir / "production"):
        if stale_dir.exists():
            shutil.rmtree(stale_dir)
    for stale in (object_dir / "spritesheet.webp", object_dir / "spritesheet.png"):
        if stale.exists():
            stale.unlink()

    detailed_frames: list[dict[str, Any]] = []
    motion: list[dict[str, Any]] = []
    cutout_paths: list[Path] = []

    object_initial_masks = [mask for mask in initial_masks if mask.object_id == object_id]
    initial = object_initial_masks[0] if object_initial_masks else None
    tracker = PerFrameMaskVideoTracker([spec])
    track = tracker.track(
        video_source,
        object_initial_masks,
        {},
        run_context,
    )[0]
    _job_emit(job_context, "propagation", "succeeded", f"tracking completed for {object_id}", progress={"stageRatio": 1.0, "overallRatio": 0.66}, metadata={"objectId": object_id})
    vectorizer = ContourVectorizer(min_area=min_area, simplify_ratio=simplify_ratio)
    track = vectorizer.vectorize(
        [track],
        {"min_area": min_area, "simplify_ratio": simplify_ratio},
        run_context,
    )[0]
    _job_emit(job_context, "vectorization", "succeeded", f"contours vectorized for {object_id}", progress={"stageRatio": 1.0, "overallRatio": 0.7}, metadata={"objectId": object_id})
    pre_export_decision = evaluate_track(
        track,
        width=info.width,
        height=info.height,
        config=TrackFilterConfig(min_area=min_area),
    )
    pre_export_payload = pre_export_decision.to_dict()
    pre_export_reason_codes = list(pre_export_decision.reason_codes)
    skip_asset_materialization = (
        pre_export_decision.status == "rejected"
        and _should_skip_asset_materialization(pre_export_reason_codes)
    )
    track.metadata["trackFilterPreflight"] = pre_export_payload
    if skip_asset_materialization:
        track.export_status = "rejected"
        track.warnings = list(dict.fromkeys([*track.warnings, *pre_export_reason_codes]))
        _job_emit(
            job_context,
            "asset_preparation",
            "skipped",
            f"skipped raster asset materialization for rejected track {object_id}",
            progress={"stageRatio": 1.0, "overallRatio": 0.73},
            metadata={
                "objectId": object_id,
                "reasonCodes": pre_export_reason_codes,
                "decision": pre_export_payload,
            },
        )
    else:
        _job_emit(
            job_context,
            "asset_preparation",
            "running",
            f"preparing raster assets for {object_id}",
            progress={"overallRatio": 0.705},
            metadata={"objectId": object_id, "frames": len(track.frames)},
        )
    provider_performance = dict(track.metadata.get("providerPerformance") or {})

    total_track_frames = len(track.frames)
    progress_stride = max(1, total_track_frames // 4)
    for position, track_frame in enumerate(tqdm(track.frames, desc=f"processing {object_id}"), start=1):
        _job_check_cancel(job_context, "export")
        frame_number = track_frame.frame
        frame_name = f"frame_{frame_number:06d}.png"
        mask_name = f"mask_{frame_number:06d}.png"
        cutout_name = f"cutout_{frame_number:06d}.png"

        frame_path = frames_dir / frame_name
        mask_path = mask_dir / mask_name
        cutout_path = cutout_dir / cutout_name

        if track_frame.rgb is None:
            raise RuntimeError(f"Track frame {frame_number} for {object_id} is missing RGB frame data")
        if track_frame.mask is None:
            raise RuntimeError(f"Track frame {frame_number} for {object_id} is missing mask data")
        if not frame_path.exists():
            Image.fromarray(track_frame.rgb).save(frame_path)
        Image.fromarray(track_frame.mask).save(mask_path)

        source_visible = bool(track_frame.visible and track_frame.bbox)
        visible = source_visible and not skip_asset_materialization
        x = y = w = h = 0
        anchor = [0.0, 0.0]
        cutout_rel: str | None = None
        if visible:
            layer_crop = crop_rgba_layer(
                track_frame.rgb,
                track_frame.mask,
                track_frame.bbox or [0, 0, 1, 1],
                centroid=track_frame.centroid,
                feather=feather,
                padding=layer_padding,
            )
            Image.fromarray(layer_crop.rgba, mode="RGBA").save(cutout_path)
            cutout_paths.append(cutout_path)
            x, y, w, h = layer_crop.bbox
            anchor = layer_crop.anchor
            cutout_rel = _rel(cutout_path, out_dir)
        track_frame.mask_ref = _rel(mask_path, out_dir)
        track_frame.asset_ref = cutout_rel
        track_frame.anchor = anchor

        frame_record = {
            "source_frame_index": track_frame.source_frame_index,
            "frame": frame_number,
            "out_index": track_frame.out_index,
            "t": round(track_frame.t, 6),
            "visible": visible,
            "area": track_frame.area,
            "bbox": [x, y, w, h] if visible else None,
            "centroid": track_frame.centroid,
            "polygon": track_frame.polygon,
            "contour_points": track_frame.contour_points,
            "framePath": _rel(frame_path, out_dir),
            "mask": _rel(mask_path, out_dir),
            "asset": cutout_rel,
            "anchor": anchor,
        }
        detailed_frames.append(frame_record)
        motion.append(
            {
                "frame": frame_number,
                "sourceFrameIndex": track_frame.source_frame_index,
                "t": round(track_frame.t, 6),
                "visible": visible,
                "x": x,
                "y": y,
                "w": w,
                "h": h,
                "scale": 1.0,
                "rotation": 0.0,
                "opacity": 1.0 if visible else 0.0,
                "anchor": anchor,
                "asset": cutout_rel,
                "mask": _rel(mask_path, out_dir),
                "centroid": track_frame.centroid,
            }
        )
        if (
            not skip_asset_materialization
            and (position == 1 or position == total_track_frames or position % progress_stride == 0)
        ):
            _job_emit(
                job_context,
                "asset_preparation",
                "running",
                f"prepared raster asset frame {position}/{total_track_frames} for {object_id}",
                progress={
                    "current": position,
                    "total": total_track_frames,
                    "stageRatio": round(position / total_track_frames, 4) if total_track_frames else 1.0,
                    "overallRatio": round(0.705 + ((position / total_track_frames) if total_track_frames else 1.0) * 0.02, 4),
                },
                metadata={"objectId": object_id},
            )

    quality = build_quality_scores(detailed_frames)
    route = recommended_output(quality)
    discovery = _build_discovery_metadata(
        spec=spec,
        initial=initial,
        track=track,
        quality=quality,
        rights_context=rights_context,
    )
    if skip_asset_materialization:
        discovery = {
            **discovery,
            "assetMaterialization": {
                "status": "skipped",
                "reasonCodes": pre_export_reason_codes,
                "trackFilterPreflight": pre_export_payload,
            },
            "exportStatus": "rejected",
            "exportValidationReasonCodes": pre_export_reason_codes,
            "reviewRequired": True,
        }
    sprite_path = object_dir / f"spritesheet.{sprite_format}"
    sprite_meta = None
    if not skip_asset_materialization:
        _job_emit(
            job_context,
            "asset_preparation",
            "running",
            f"writing spritesheet for {object_id}",
            progress={"overallRatio": 0.728},
            metadata={"objectId": object_id, "cutouts": len(cutout_paths)},
        )
        sprite_meta = write_spritesheet(
            cutout_paths=cutout_paths,
            output_path=sprite_path,
            format="WEBP" if sprite_format == "webp" else "PNG",
        )
    if sprite_meta:
        sprite_meta["path"] = _rel(sprite_path, out_dir)
        for entry, sprite_frame in zip((m for m in motion if m["asset"]), sprite_meta["frames"]):
            entry["sprite"] = sprite_frame
    if not skip_asset_materialization:
        _job_emit(
            job_context,
            "asset_preparation",
            "succeeded",
            f"raster assets prepared for {object_id}",
            progress={"stageRatio": 1.0, "overallRatio": 0.73},
            metadata={"objectId": object_id, "cutouts": len(cutout_paths), "spritesheet": bool(sprite_meta)},
        )

    rights = build_object_rights(object_id=object_id, context=rights_context, fallback_source_uri=rights_context.get("source_uri") if rights_context else None)
    obj = {
        "id": object_id,
        "label": spec.label,
        "renderMode": "raster_alpha_sequence",
        "asset": f"objects/{object_id}/cutouts/cutout_%06d.png",
        "mask": f"masks/{object_id}/mask_%06d.png",
        "assets": {
            "cutoutPattern": f"objects/{object_id}/cutouts/cutout_%06d.png",
            "spritesheet": sprite_meta,
        },
        "zIndex": spec.z_index,
        "motion": motion,
        "frames": detailed_frames,
        "interactions": {
            "idle": {"loop": True, "scale": 1.0, "opacity": 1.0},
            "hover": {"scale": 1.06, "outline": True},
            "click": {"action": "reuse_or_open_detail"},
        },
        "quality": quality,
        "recommendedOutput": route,
        "rights": rights,
        "discovery": discovery,
    }
    if skip_asset_materialization:
        obj["exportStatus"] = "rejected"
        obj["exportIncluded"] = False
    if output_mode in {"production", "both"} and not skip_asset_materialization:
        production_assets = export_production_assets(
            out_dir=out_dir,
            object_id=object_id,
            motion=motion,
            canvas_width=info.width,
            canvas_height=info.height,
            fps=info.sample_fps,
            include_avif=production_avif,
        )
        obj["assets"]["production"] = production_assets

    object_manifest = {
        "schema": "motionjson.object_manifest.v0.1",
        "objectId": object_id,
        "label": spec.label,
        "renderMode": obj["renderMode"],
        "cutouts": [entry["asset"] for entry in motion if entry["asset"]],
        "masks": [entry["mask"] for entry in motion],
        "spritesheet": sprite_meta,
        "motion": motion,
        "quality": quality,
        "recommendedOutput": route,
        "rights": rights,
        "discovery": discovery,
    }
    if "production" in obj["assets"]:
        object_manifest["production"] = obj["assets"]["production"]
    object_motion = {
        "schema": "motionjson.object_motion.v0.1",
        "objectId": object_id,
        "fps": info.sample_fps,
        "motion": motion,
        "quality": quality,
        "recommendedOutput": route,
        "discovery": discovery,
    }

    write_json(object_dir / "object_manifest.json", object_manifest)
    _write_object_motion(out_dir, object_id, object_motion)
    layer = _build_layer_frames(object_id, info.sample_fps, motion, z_index=spec.z_index)
    layer["discovery"] = discovery
    provider_performance.setdefault("objectId", object_id)
    provider_performance.setdefault("providerName", spec.mask_provider.__class__.__name__)
    provider_performance.setdefault("frames", len(frames))
    track.metadata["discovery"] = discovery
    track.metadata["quality"] = quality
    track.metadata["recommendedOutput"] = route
    return obj, layer, object_motion, detailed_frames, provider_performance, track


def run_multi_object_pipeline(
    *,
    video_path: str | Path,
    out_dir: str | Path,
    object_specs: list[ObjectExtractionSpec] | None,
    candidate_provider: ObjectCandidateProvider | None = None,
    candidate_config: dict[str, Any] | None = None,
    candidate_to_specs: Callable[[Sequence[ObjectCandidate]], list[ObjectExtractionSpec]] | None = None,
    sample_fps: float | None = None,
    max_frames: int | None = None,
    min_area: float = 100.0,
    simplify_ratio: float = 0.006,
    feather: int = 0,
    layer_padding: int = 4,
    sprite_format: str = "webp",
    output_mode: str = "authoring",
    production_avif: bool = False,
    rights_context: dict[str, Any] | None = None,
    job_context: Any | None = None,
) -> dict[str, Any]:
    if sprite_format not in {"webp", "png"}:
        raise ValueError("sprite_format must be 'webp' or 'png'")
    if output_mode not in {"authoring", "production", "both"}:
        raise ValueError("output_mode must be 'authoring', 'production', or 'both'")
    object_specs = list(object_specs or [])
    if not object_specs and candidate_provider is None:
        raise ValueError("At least one object extraction spec is required")
    _validate_object_specs(object_specs)

    video_path = Path(video_path)
    out_dir = Path(out_dir)
    normalized_rights = normalize_rights_context(rights_context, fallback_source_uri=video_path)
    rights_payload = {
        "source_type": normalized_rights.source_type,
        "source_asset_id": normalized_rights.source_asset_id,
        "source_uri": normalized_rights.source_uri,
        "display_text": normalized_rights.display_text,
        "attribution_required": normalized_rights.attribution_required,
        "license": normalized_rights.license,
        "license_name": normalized_rights.license_name,
        "license_url": normalized_rights.license_url,
        "license_scope": normalized_rights.license_scope,
        "creator_approved": normalized_rights.creator_approved,
        "creator_approval_status": normalized_rights.creator_approval_status,
        "creator_approval_evidence": list(normalized_rights.creator_approval_evidence),
        "commercial_use": normalized_rights.commercial_use,
        "commercial_use_status": normalized_rights.commercial_use_status,
        "audit_log": list(normalized_rights.audit_log),
    }
    frames_dir = out_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    _clear_generated_frames(frames_dir)
    for stale in (out_dir / "benchmark_report.json", out_dir / "silhouette_lottie.json"):
        if stale.exists():
            stale.unlink()

    total_start = time.perf_counter()
    sample_start = time.perf_counter()
    _job_check_cancel(job_context, "video_read")
    _job_emit(job_context, "video_read", "running", "reading source video metadata", progress={"overallRatio": 0.05}, metadata={"video": str(video_path)})
    info, frame_iter = iter_sampled_frames(video_path, sample_fps=sample_fps, max_frames=max_frames)
    frames = list(frame_iter)
    _job_emit(
        job_context,
        "video_read",
        "succeeded",
        "source video sampled",
        progress={"current": len(frames), "total": len(frames), "overallRatio": 0.2},
        metadata={"width": info.width, "height": info.height, "sourceFps": info.source_fps, "sampleFps": info.sample_fps},
    )
    _job_emit(job_context, "keyframe_selection", "succeeded", "sampled frames selected", progress={"overallRatio": 0.25}, metadata={"sampledFrames": len(frames)})
    phase_timings = [
        PhaseTiming(phase="sample_frames", elapsed_ms=_elapsed_ms(sample_start), count=len(frames)).to_dict()
    ]
    write_frames_start = time.perf_counter()
    for frame in frames:
        _job_check_cancel(job_context, "write_debug_frames")
        frame_number = frame.out_index + 1
        Image.fromarray(frame.rgb).save(frames_dir / f"frame_{frame_number:06d}.png")
    phase_timings.append(PhaseTiming(phase="write_debug_frames", elapsed_ms=_elapsed_ms(write_frames_start), count=len(frames)).to_dict())
    _job_emit(job_context, "debug_artifacts", "succeeded", "debug frames written", progress={"overallRatio": 0.3}, metadata={"frames": len(frames)})

    source = {
        "video": str(video_path),
        "width": info.width,
        "height": info.height,
        "fps": info.source_fps,
        "sampleFps": info.sample_fps,
        "totalSourceFrames": info.total_source_frames,
        "sampledFrameCount": len(frames),
    }
    video_source = VideoSource(path=video_path, info=info, frames=frames)
    run_context = RunContext(out_dir=out_dir, job_context=job_context)

    candidate_start = time.perf_counter()
    _job_check_cancel(job_context, "candidate_discovery")
    active_candidate_provider = candidate_provider or ObjectSpecCandidateProvider(object_specs)
    active_candidate_provider_name = _candidate_provider_name(active_candidate_provider)
    active_candidate_config = dict(candidate_config or {"frame_index": 0})
    _job_emit(
        job_context,
        "candidate_discovery",
        "running",
        "discovering object candidates",
        progress={"overallRatio": 0.31},
        metadata={"provider": active_candidate_provider_name},
    )
    candidates = list(active_candidate_provider.propose(video_source, active_candidate_config, run_context))
    write_json(
        out_dir / "candidates.json",
        _candidate_payload(
            provider_name=active_candidate_provider_name,
            config=active_candidate_config,
            video_source=video_source,
            candidates=candidates,
        ),
    )
    if candidate_provider is not None and not candidates:
        fallback = build_raster_fallback(
            "no_candidates",
            metadata={"provider": active_candidate_provider_name, "config": active_candidate_config},
            severity="error",
        )
        write_json(
            out_dir / "fallback_diagnostics.json",
            _fallback_payload(
                diagnostics=[fallback.to_dict()],
                summary={"fallbackReasonCounts": {"no_candidates": 1}, "acceptedTracks": 0, "rejectedTracks": 0},
            ),
        )
        raise ValueError(f"Discovery provider {active_candidate_provider_name!r} produced no candidates")
    if candidate_provider is not None and candidate_to_specs is not None:
        object_specs = candidate_to_specs(candidates)
        if not object_specs:
            rejection_counts = _candidate_rejection_counts(candidates)
            fallback = build_raster_fallback(
                "no_candidates",
                metadata={
                    "provider": active_candidate_provider_name,
                    "config": active_candidate_config,
                    "candidateCount": len(candidates),
                    "rejectionReasonCounts": rejection_counts,
                },
                severity="error",
            )
            write_json(
                out_dir / "fallback_diagnostics.json",
                _fallback_payload(
                    diagnostics=[fallback.to_dict()],
                    summary={
                        "fallbackReasonCounts": {"no_candidates": 1},
                        "acceptedTracks": 0,
                        "rejectedTracks": len(candidates),
                        "candidateRejectionReasonCounts": rejection_counts,
                    },
                ),
            )
            raise ValueError(
                f"Discovery provider {active_candidate_provider_name!r} produced no candidates usable for extraction."
                f"{_candidate_rejection_summary(rejection_counts)}"
            )
        _validate_object_specs(object_specs)
    elif candidate_provider is not None and not object_specs:
        raise ValueError("candidate_to_specs is required when discovery provides candidates without initial object_specs")
    phase_timings.append(PhaseTiming(phase="candidate_discovery", elapsed_ms=_elapsed_ms(candidate_start), count=len(candidates)).to_dict())
    _job_emit(
        job_context,
        "candidate_discovery",
        "succeeded",
        "object candidates discovered",
        progress={"stageRatio": 1.0, "overallRatio": 0.32},
        metadata={"provider": active_candidate_provider_name, "candidates": len(candidates), "objectSpecs": len(object_specs)},
    )

    initial_masks_start = time.perf_counter()
    _job_check_cancel(job_context, "initial_masks")
    _job_emit(job_context, "initial_masks", "running", "initializing candidate masks", progress={"overallRatio": 0.33}, metadata={"provider": "object-spec-initial-masks"})
    initial_mask_provider = ObjectSpecInitialMaskProvider(object_specs)
    initial_masks = list(initial_mask_provider.initialize_masks(video_source, candidates, run_context))
    phase_timings.append(PhaseTiming(phase="initial_masks", elapsed_ms=_elapsed_ms(initial_masks_start), count=len(initial_masks)).to_dict())
    _job_emit(job_context, "initial_masks", "succeeded", "candidate masks initialized", progress={"stageRatio": 1.0, "overallRatio": 0.34}, metadata={"masks": len(initial_masks)})

    objects: list[dict[str, Any]] = []
    layers: list[dict[str, Any]] = []
    object_motions: dict[str, dict[str, Any]] = {}
    first_detailed_frames: list[dict[str, Any]] = []
    provider_performance_objects: list[dict[str, Any]] = []
    object_tracks: list[ObjectTrack] = []
    extract_start = time.perf_counter()
    for index, spec in enumerate(object_specs):
        _job_check_cancel(job_context, "extract_objects")
        obj, layer, object_motion, detailed_frames, provider_performance, object_track = _extract_object(
            out_dir=out_dir,
            frames_dir=frames_dir,
            info=info,
            frames=frames,
            video_source=video_source,
            initial_masks=initial_masks,
            run_context=run_context,
            spec=spec,
            min_area=min_area,
            simplify_ratio=simplify_ratio,
            feather=feather,
            layer_padding=layer_padding,
            sprite_format=sprite_format,
            output_mode=output_mode,
            production_avif=production_avif,
            rights_context=rights_payload,
            job_context=job_context,
        )
        objects.append(obj)
        layers.append(layer)
        object_motions[spec.object_id] = object_motion
        provider_performance_objects.append(provider_performance)
        object_tracks.append(object_track)
        if index == 0:
            first_detailed_frames = detailed_frames
    phase_timings.append(PhaseTiming(phase="extract_objects", elapsed_ms=_elapsed_ms(extract_start), count=len(object_specs)).to_dict())
    link_start = time.perf_counter()
    _job_emit(
        job_context,
        "track_linking",
        "running",
        "linking object tracks",
        progress={"overallRatio": 0.74},
        metadata={"provider": "identity-track-linker", "tracks": len(object_tracks)},
    )
    linker = IdentityTrackLinker()
    linked_tracks = list(linker.link(object_tracks, {}, run_context))
    track_filter_report = filter_and_dedupe_tracks(
        linked_tracks,
        width=info.width,
        height=info.height,
        config=TrackFilterConfig(min_area=min_area),
    )
    track_filter_payload = track_filter_report.to_dict()
    _apply_track_filter_decisions(
        objects=objects,
        layers=layers,
        tracks=linked_tracks,
        filter_report=track_filter_payload,
    )
    trace_export_gate = _trace_everything_export_gate(active_candidate_provider_name, active_candidate_config)
    if trace_export_gate is not None:
        _mark_trace_everything_review_pending(
            objects=objects,
            layers=layers,
            tracks=linked_tracks,
            gate=trace_export_gate,
        )
        track_filter_payload["exportReviewGate"] = dict(trace_export_gate)
    fallback_diagnostics = [
        decision["fallback"]
        for decision in track_filter_payload["decisions"]
        if decision.get("fallback")
    ]
    write_json(
        out_dir / "fallback_diagnostics.json",
        _fallback_payload(
            diagnostics=fallback_diagnostics,
            summary=track_filter_payload["summary"],
        ),
    )
    write_json(
        out_dir / "tracks.json",
        {
            "format": "motionjson.tracks.v0.1",
            "provider": linker.name,
            "filterReport": track_filter_payload,
            "fallbackDiagnostics": fallback_diagnostics,
            "tracks": [track.to_summary() for track in linked_tracks],
        },
    )
    phase_timings.append(PhaseTiming(phase="track_linking", elapsed_ms=_elapsed_ms(link_start), count=len(linked_tracks)).to_dict())
    _job_emit(
        job_context,
        "track_linking",
        "succeeded",
        "object tracks linked",
        progress={"stageRatio": 1.0, "overallRatio": 0.75},
        metadata={"tracks": len(linked_tracks), "acceptedTracks": track_filter_payload["summary"]["acceptedTracks"], "rejectedTracks": track_filter_payload["summary"]["rejectedTracks"]},
    )

    latency_metrics = {
        "schema": "motionjson.latency_metrics.v0.1",
        "phaseTimings": phase_timings,
        "totalElapsedMs": _elapsed_ms(total_start),
        "sampledFrames": len(frames),
        "objects": len(object_specs),
    }
    provider_performance = {
        "schema": "motionjson.provider_performance.v0.1",
        "objects": provider_performance_objects,
        "trackFilter": track_filter_payload,
        "fallbackDiagnostics": fallback_diagnostics,
    }
    scene = {
        "schema": "motionjson.scene_graph.v0.1",
        "version": "0.1.0",
        "source": source,
        "objects": objects,
        "canvas": {
            "width": info.width,
            "height": info.height,
            "source_fps": info.source_fps,
            "fps": info.sample_fps,
            "frame_count": len(frames),
        },
        "layers": layers,
        "rendering": {
            "recommendedRuntime": "Canvas/WebGL/PixiJS",
            "defaultRenderMode": "raster_alpha_sequence",
            "outputMode": output_mode,
            "vectorPolicy": "Use SVG/Lottie only for simple silhouettes, outlines, labels, annotations, or clean flat graphics.",
        },
        "providerPerformance": provider_performance,
        "latencyMetrics": latency_metrics,
        "rightsManifest": "rights_manifest.json",
    }
    scene["costDashboard"] = build_cost_dashboard(
        provider_performance=provider_performance,
        latency_metrics=latency_metrics,
        production_assets=objects[0].get("assets", {}).get("production") if objects else None,
    )
    rights_manifest = build_rights_manifest(source=source, objects=objects, context=rights_payload)

    _job_check_cancel(job_context, "export")
    _job_emit(job_context, "export", "running", "writing MotionJSON artifacts", progress={"overallRatio": 0.78}, metadata={"objects": len(objects)})
    default_object_id = object_specs[0].object_id
    _write_object_motion(out_dir, default_object_id, object_motions[default_object_id], legacy=True)
    write_silhouette_lottie(
        out_dir / "silhouette_lottie.json",
        width=info.width,
        height=info.height,
        fps=info.sample_fps,
        frames=first_detailed_frames,
    )
    write_json(out_dir / "scene_graph.json", scene)
    write_rights_manifest(out_dir / "rights_manifest.json", rights_manifest)
    for index, spec in enumerate(object_specs):
        _write_object_web_manifest(out_dir, scene, spec.object_id, legacy=index == 0)
    _preview_copy(out_dir)
    scene["latencyMetrics"]["totalElapsedMs"] = _elapsed_ms(total_start)
    scene["costDashboard"] = build_cost_dashboard(
        provider_performance=provider_performance,
        latency_metrics=scene["latencyMetrics"],
        production_assets=objects[0].get("assets", {}).get("production") if objects else None,
    )
    write_profiled_outputs(out_dir=out_dir, video_path=video_path, object_id=default_object_id, scene=scene)
    _job_emit(job_context, "export", "succeeded", "MotionJSON artifacts written", progress={"overallRatio": 0.95}, metadata={"objects": len(objects), "frames": len(frames)})

    return scene


def run_pipeline(
    *,
    video_path: str | Path,
    out_dir: str | Path,
    mask_provider: LegacyMaskProvider,
    object_id: str = "object_0",
    object_label: str = "selected_object",
    sample_fps: float | None = None,
    max_frames: int | None = None,
    min_area: float = 100.0,
    simplify_ratio: float = 0.006,
    feather: int = 0,
    layer_padding: int = 4,
    sprite_format: str = "webp",
    output_mode: str = "authoring",
    production_avif: bool = False,
    rights_context: dict[str, Any] | None = None,
    job_context: Any | None = None,
) -> dict[str, Any]:
    return run_multi_object_pipeline(
        video_path=video_path,
        out_dir=out_dir,
        object_specs=[ObjectExtractionSpec(object_id=object_id, label=object_label, mask_provider=mask_provider)],
        sample_fps=sample_fps,
        max_frames=max_frames,
        min_area=min_area,
        simplify_ratio=simplify_ratio,
        feather=feather,
        layer_padding=layer_padding,
        sprite_format=sprite_format,
        output_mode=output_mode,
        production_avif=production_avif,
        rights_context=rights_context,
        job_context=job_context,
    )
