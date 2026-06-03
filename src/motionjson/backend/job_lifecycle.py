from __future__ import annotations

from typing import Any, Mapping, Sequence


TERMINAL_JOB_STATUSES = {"succeeded", "failed", "canceled", "cancelled"}
QUEUED_JOB_STATUSES = {"pending", "queued"}
ACTIVE_JOB_STATUSES = {"running", "cancel_requested"}
NO_MODEL_PROVIDERS = {"mock", "threshold", "motion", "motion_foreground", "external", "external_masks"}
REVIEW_PENDING_STATUSES = {"pending", "review_pending", "needs_review", "awaiting_review"}
EXPORT_READY_STATUSES = {"accepted", "ready", "reviewed"}
EXPORT_BLOCKED_STATUSES = {"rejected", "deleted", "excluded", "fallback_raster"}


def job_lifecycle_summary(
    job: Mapping[str, Any],
    *,
    events: Sequence[Mapping[str, Any]] | None = None,
    review: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a normalized, UI-facing lifecycle summary for a public job row."""

    event_list = [event for event in events or [] if isinstance(event, Mapping)]
    review_summary = review_lifecycle_summary(review or {})
    latest_event = _latest_event(event_list)
    raw_status = _text(job.get("status")).lower()
    status = _lifecycle_status(raw_status, review_summary)
    phase = _phase(raw_status, status, latest_event, review_summary)
    failure = _failure_summary(job, event_list, review or {}, raw_status)
    actions = _actions(job, raw_status, status, review_summary, failure)
    return {
        "format": "motionjson.job_lifecycle.v0.1",
        "jobId": _text(job.get("id")),
        "projectId": _text(job.get("project_id") or job.get("projectId")),
        "type": _text(job.get("type") or "extract"),
        "workflow": _workflow(job),
        "provider": _provider_summary(job),
        "status": status,
        "rawStatus": raw_status,
        "phase": phase,
        "progress": _progress(event_list, raw_status, status, phase),
        "latestEvent": latest_event,
        "failure": failure,
        "review": review_summary,
        "actions": actions,
        "nextAction": _next_action(status, review_summary, failure, actions),
    }


def review_lifecycle_summary(review: Mapping[str, Any]) -> dict[str, Any]:
    candidates = _list(review.get("candidates"))
    candidate_summary = _mapping(review.get("candidateSummary"))
    tracks = _list(review.get("tracks"))
    fallback_diagnostics = _list(review.get("fallbackDiagnostics"))
    diagnostics = _list(review.get("diagnostics")) + _list(review.get("providerDiagnostics"))
    candidate_count = _int(candidate_summary.get("candidateCount"), len(candidates))
    selected_candidate_count = _int(
        candidate_summary.get("selectedCandidateCount"),
        _int(candidate_summary.get("defaultSelectedCount"), _int(candidate_summary.get("acceptedCandidateCount"), 0)),
    )
    track_count = len(tracks)
    exportable_track_count = sum(1 for track in tracks if _track_exportable(_mapping(track)))
    pending_track_count = sum(1 for track in tracks if _track_needs_review(_mapping(track)))
    diagnostic_count = len(fallback_diagnostics) + len(diagnostics)
    needs_review = bool(
        (candidate_count > 0 and track_count == 0)
        or pending_track_count
        or (track_count > 0 and exportable_track_count == 0)
    )
    return {
        "candidateCount": candidate_count,
        "selectedCandidateCount": selected_candidate_count,
        "trackCount": track_count,
        "exportableTrackCount": exportable_track_count,
        "pendingTrackCount": pending_track_count,
        "diagnosticCount": diagnostic_count,
        "needsReview": needs_review,
        "hasRasterFallback": bool(review.get("rasterFallback") or fallback_diagnostics),
        "vectorUnavailableReason": _text_or_none(review.get("vectorUnavailableReason") or review.get("rasterFallbackReason")),
    }


def _latest_event(events: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    if not events:
        return None
    metadata = _mapping(events[-1].get("metadata"))
    latest = events[-1]
    return {
        "type": _text(latest.get("type") or latest.get("event_type")),
        "message": _text(latest.get("message")),
        "stage": _text(latest.get("stage") or metadata.get("stage")),
        "createdAt": _text(latest.get("created_at") or latest.get("createdAt")),
    }


def _progress(events: Sequence[Mapping[str, Any]], raw_status: str, status: str, phase: str) -> dict[str, Any]:
    ratio: float | None = None
    label = _phase_label(phase)
    for event in events:
        metadata = _mapping(event.get("metadata"))
        progress = _mapping(metadata.get("progress"))
        candidate = progress.get("overallRatio", progress.get("ratio"))
        if isinstance(candidate, (int, float)):
            ratio = max(ratio or 0.0, min(float(candidate), 1.0))
        stage = _text(metadata.get("stage"))
        if stage:
            label = _stage_label(stage)
    if ratio is not None:
        return {"known": True, "percent": int(round(ratio * 100)), "label": label}
    if raw_status == "failed":
        percent = 0
    elif raw_status in TERMINAL_JOB_STATUSES or status == "waiting_review":
        percent = 100
    else:
        percent = 0
    return {"known": False, "percent": percent, "label": _status_label(status)}


def _lifecycle_status(raw_status: str, review: Mapping[str, Any]) -> str:
    if raw_status in {"failed"}:
        return "failed"
    if raw_status in {"canceled", "cancelled"}:
        return "canceled"
    if raw_status in QUEUED_JOB_STATUSES:
        return "queued"
    if raw_status in ACTIVE_JOB_STATUSES:
        return "running"
    if raw_status == "succeeded" and review.get("needsReview"):
        return "waiting_review"
    if raw_status == "succeeded":
        return "succeeded"
    return raw_status or "queued"


def _phase(raw_status: str, status: str, latest_event: Mapping[str, Any] | None, review: Mapping[str, Any]) -> str:
    if status == "failed":
        return "failed"
    if status == "canceled":
        return "complete"
    if status == "queued":
        return "queued"
    if status == "waiting_review":
        return "review_ready"
    if status == "succeeded":
        return "complete"
    event_type = _text((latest_event or {}).get("type")).lower()
    event_message = _text((latest_event or {}).get("message")).lower()
    event_stage = _text((latest_event or {}).get("stage")).lower()
    combined = f"{event_type} {event_stage} {event_message}"
    if "validat" in combined or "preflight" in combined:
        return "validating"
    if "discover" in combined or "candidate" in combined or "proposal" in combined:
        return "discovering"
    if "track" in combined or "link" in combined:
        return "tracking"
    if "artifact" in combined or "write" in combined or "manifest" in combined:
        return "writing_artifacts"
    if "export" in combined or raw_status == "export":
        return "exporting"
    if raw_status in ACTIVE_JOB_STATUSES:
        return "extracting"
    if review.get("needsReview"):
        return "review_ready"
    return "setup"


def _failure_summary(
    job: Mapping[str, Any],
    events: Sequence[Mapping[str, Any]],
    review: Mapping[str, Any],
    raw_status: str,
) -> dict[str, Any] | None:
    if raw_status not in {"failed", "canceled", "cancelled"} and not review.get("failure"):
        return None
    message = _text(job.get("error"))
    if not message:
        failure = _mapping(review.get("failure"))
        message = _text(failure.get("message") or failure.get("error") or failure.get("reason"))
    if not message:
        for event in reversed(events):
            if _text(event.get("event_type") or event.get("type")).lower() in {"failed", "worker_error", "canceled"}:
                message = _text(event.get("message"))
                break
    if raw_status in {"canceled", "cancelled"}:
        message = message or "The job was canceled."
        return {
            "headline": "Job canceled",
            "reasonCode": "user_canceled",
            "message": message,
            "suggestedAction": "Start a new run when you are ready.",
        }
    message = message or "The job failed before producing reviewable output."
    reason_code = _failure_reason_code(message)
    return {
        "headline": _failure_headline(message, reason_code),
        "reasonCode": reason_code,
        "message": message,
        "suggestedAction": _suggested_action(reason_code),
    }


def _failure_reason_code(message: str) -> str:
    normalized = message.lower()
    if "asset preparation stalled" in normalized or "raster asset preparation stalled" in normalized:
        return "asset_preparation_stalled"
    if any(token in normalized for token in ("sam2", "sam3", "cuda", "checkpoint", "model", "provider", "api key", "token", "credential", "not importable", "unavailable")):
        return "provider_unavailable"
    if any(token in normalized for token in ("config", "validation", "payload", "schema")):
        return "validation_failed"
    if any(token in normalized for token in ("video", "asset", "mask_dir", "file", "path")):
        return "input_unavailable"
    return "job_failed"


def _failure_headline(message: str, reason_code: str) -> str:
    if reason_code == "asset_preparation_stalled":
        return "Raster asset preparation stalled"
    if reason_code == "provider_unavailable":
        if "sam3" in message.lower():
            return "SAM3 is not ready"
        if "sam2" in message.lower():
            return "SAM2 is not ready"
        return "Provider is not ready"
    if reason_code == "validation_failed":
        return "Run configuration needs changes"
    if reason_code == "input_unavailable":
        return "Input could not be read"
    first_sentence = message.split(".", 1)[0].strip()
    return first_sentence[:96] or "Job failed"


def _suggested_action(reason_code: str) -> str:
    if reason_code == "asset_preparation_stalled":
        return "Retry asset preparation from the current setup, or return to Model setup before starting a new run."
    if reason_code == "provider_unavailable":
        return "Open Model Connections, fix the provider setup, or choose a no-model workflow."
    if reason_code == "validation_failed":
        return "Review the run plan and fix the blocked fields before retrying."
    if reason_code == "input_unavailable":
        return "Check the source video or mask path, then add the input again."
    return "Open logs/details, fix the cause, then start a new run."


def _actions(
    job: Mapping[str, Any],
    raw_status: str,
    status: str,
    review: Mapping[str, Any],
    failure: Mapping[str, Any] | None,
) -> dict[str, Any]:
    can_review = bool(
        review.get("candidateCount")
        or review.get("trackCount")
        or review.get("diagnosticCount")
        or failure
    )
    return {
        "canCancel": raw_status in {"pending", "queued", "running"},
        "canRetry": bool(failure and _text(failure.get("reasonCode")) == "asset_preparation_stalled"),
        "canRetryAssetPreparation": bool(failure and _text(failure.get("reasonCode")) == "asset_preparation_stalled"),
        "canReview": can_review,
        "canTrackSelected": status == "waiting_review" and int(review.get("candidateCount") or 0) > 0 and int(review.get("trackCount") or 0) == 0,
        "canExport": status in {"waiting_review", "succeeded"} and int(review.get("exportableTrackCount") or 0) > 0,
    }


def _next_action(
    status: str,
    review: Mapping[str, Any],
    failure: Mapping[str, Any] | None,
    actions: Mapping[str, Any],
) -> dict[str, str]:
    if status in {"queued", "running"}:
        return {"label": "Watch job", "reason": "The run is still in progress."}
    if failure and _text(failure.get("reasonCode")) == "asset_preparation_stalled":
        return {"label": "Retry asset prep", "reason": _text(failure.get("headline"))}
    if failure:
        return {"label": "Open logs", "reason": _text(failure.get("headline"))}
    if actions.get("canTrackSelected"):
        return {"label": "Track selected", "reason": "Candidates exist but no tracks have been created."}
    if review.get("pendingTrackCount"):
        return {"label": "Mark reviewed", "reason": "Tracks exist but still need review before export."}
    if actions.get("canExport"):
        return {"label": "Export reviewed objects", "reason": "Reviewed exportable tracks are available."}
    if review.get("diagnosticCount"):
        return {"label": "Review diagnostics", "reason": "The run produced diagnostics before exportable tracks."}
    return {"label": "Start run", "reason": "No active job output is ready yet."}


def _provider_summary(job: Mapping[str, Any]) -> dict[str, Any]:
    payload = _mapping(job.get("payload"))
    run_config = _mapping(payload.get("run_config"))
    provider = _mapping(run_config.get("provider"))
    discovery = _mapping(run_config.get("discovery"))
    discovery_config = _mapping(discovery.get("config"))
    provider_id = _text(provider.get("name") or payload.get("mask_provider") or payload.get("maskProvider") or "unknown")
    hosted_config = _mapping(_mapping(provider.get("sam2")).get("hosted_config") or _mapping(provider.get("sam3")).get("hosted_config"))
    profile = _text(hosted_config.get("profile") or discovery_config.get("hostedProfile") or discovery_config.get("hosted_profile"))
    connection_id = f"{provider_id}:{profile}" if profile and "hosted" in provider_id else provider_id
    return {
        "id": provider_id,
        "connectionId": connection_id,
        "label": _provider_label(provider_id, profile),
        "engine": _provider_engine(provider_id, discovery),
        "locality": _provider_locality(provider_id),
        "hostedCallsAllowed": _hosted_calls_allowed(provider, discovery_config),
    }


def _workflow(job: Mapping[str, Any]) -> str:
    payload = _mapping(job.get("payload"))
    run_config = _mapping(payload.get("run_config"))
    discovery = _mapping(run_config.get("discovery"))
    mode = _text(discovery.get("mode") or payload.get("workflow") or payload.get("discovery"))
    return {
        "manual_prompt": "trace_one_object",
        "sam3_concept": "find_by_description",
        "text_detector": "find_by_description",
        "motion_foreground": "motion_foreground",
        "external_masks": "external_masks",
        "auto_object_proposals": "auto_object_proposals",
        "sam_auto_masks": "trace_all_objects",
        "sam3_auto_masks": "trace_all_objects",
        "sam3_exemplar": "trace_one_object",
    }.get(mode, mode or _text(job.get("type") or "extract"))


def _provider_engine(provider_id: str, discovery: Mapping[str, Any]) -> str:
    mode = _text(discovery.get("mode")).lower()
    if "sam3" in provider_id or mode.startswith("sam3"):
        return "sam3"
    if "sam2" in provider_id or mode.startswith("sam2"):
        return "sam2"
    if provider_id in {"motion", "motion_foreground"}:
        return "motion"
    if provider_id in {"external", "external_masks"}:
        return "external_masks"
    if provider_id in {"mock", "threshold"}:
        return "no_model"
    return "unknown"


def _provider_locality(provider_id: str) -> str:
    if "hosted" in provider_id:
        return "hosted"
    if provider_id in NO_MODEL_PROVIDERS:
        return "no_model"
    return "local"


def _provider_label(provider_id: str, profile: str) -> str:
    if provider_id == "sam2-local":
        return "SAM2 local"
    if provider_id == "sam2-hosted" and profile == "replicate-sam2-video":
        return "Replicate SAM2 video"
    if provider_id == "sam2-hosted":
        return "Hosted SAM2"
    if provider_id == "sam3-local":
        return "SAM3 local"
    if provider_id == "sam3-hosted" and profile == "roboflow-sam3-pcs":
        return "Roboflow SAM3"
    if provider_id == "sam3-hosted" and profile == "fal-sam3-image":
        return "Fal SAM3 image"
    if provider_id == "sam3-hosted" and profile:
        return "Custom SAM3 endpoint"
    return {
        "mock": "Mock no-model",
        "threshold": "Color threshold",
        "motion": "Motion foreground",
        "motion_foreground": "Motion foreground",
        "external": "Imported masks",
        "external_masks": "Imported masks",
    }.get(provider_id, provider_id or "Unknown provider")


def _hosted_calls_allowed(provider: Mapping[str, Any], discovery_config: Mapping[str, Any]) -> bool:
    sam2 = _mapping(provider.get("sam2"))
    sam3 = _mapping(provider.get("sam3"))
    return bool(
        provider.get("hostedCallsAllowed")
        or sam2.get("hosted_allow_network")
        or sam2.get("hostedAllowNetwork")
        or sam3.get("hosted_allow_network")
        or sam3.get("hostedAllowNetwork")
        or discovery_config.get("allowNetwork")
        or discovery_config.get("allow_network")
        or discovery_config.get("hostedCallsAllowed")
    )


def _track_exportable(track: Mapping[str, Any]) -> bool:
    status = _text(track.get("exportStatus") or track.get("export_status") or "accepted").lower()
    included = track.get("exportIncluded", track.get("export_included", True))
    return included is not False and status in EXPORT_READY_STATUSES and status not in EXPORT_BLOCKED_STATUSES


def _track_needs_review(track: Mapping[str, Any]) -> bool:
    status = _text(track.get("exportStatus") or track.get("export_status")).lower()
    return status in REVIEW_PENDING_STATUSES


def _phase_label(phase: str) -> str:
    return {
        "setup": "Setting up",
        "validating": "Validating run",
        "queued": "Queued",
        "extracting": "Extracting objects",
        "discovering": "Finding candidates",
        "tracking": "Tracking objects",
        "writing_artifacts": "Writing artifacts",
        "review_ready": "Ready for review",
        "exporting": "Exporting",
        "complete": "Complete",
        "failed": "Failed",
    }.get(phase, "Working")


def _stage_label(stage: str) -> str:
    normalized = stage.replace("_", " ").strip()
    return normalized[:1].upper() + normalized[1:] if normalized else "Working"


def _status_label(status: str) -> str:
    return {
        "queued": "Queued",
        "running": "Working",
        "waiting_review": "Ready for review",
        "succeeded": "Complete",
        "failed": "Failed",
        "canceled": "Canceled",
    }.get(status, "Working")


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _text_or_none(value: Any) -> str | None:
    text = _text(value)
    return text or None


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)
