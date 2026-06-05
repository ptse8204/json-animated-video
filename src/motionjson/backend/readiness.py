from __future__ import annotations

from typing import Any, Mapping, Sequence


REVIEW_PAYLOAD_REQUIRED_ARTIFACTS = ("scene_graph.json", "web_asset_manifest.json")

REVIEW_TOOLS: tuple[dict[str, Any], ...] = (
    {
        "toolId": "canvas_player",
        "label": "Canvas player",
        "path": "preview/canvas_player.html",
        "requiredArtifacts": ("scene_graph.json", "web_asset_manifest.json", "preview/canvas_player.html"),
    },
    {
        "toolId": "object_selection",
        "label": "Object selection",
        "path": "preview/object_selection_workflow.html",
        "requiredArtifacts": (
            "scene_graph.json",
            "web_asset_manifest.json",
            "preview/object_selection_workflow.html",
            "preview/object_selection_workflow.js",
        ),
    },
    {
        "toolId": "timeline_editor",
        "label": "Timeline editor",
        "path": "preview/timeline_editor.html",
        "requiredArtifacts": ("scene_graph.json", "web_asset_manifest.json", "preview/timeline_editor.html", "preview/timeline_editor.js"),
    },
)


def normalize_rel_paths(paths: Sequence[Any]) -> set[str]:
    return {str(path).replace("\\", "/").lstrip("/") for path in paths if str(path or "").strip()}


def review_tool_statuses(
    *,
    job_id: str,
    rel_paths: Sequence[Any],
    job_active: bool = False,
) -> list[dict[str, Any]]:
    available = normalize_rel_paths(rel_paths)
    tools: list[dict[str, Any]] = []
    for tool in REVIEW_TOOLS:
        required = [str(item) for item in tool["requiredArtifacts"]]
        missing = [path for path in required if path not in available]
        if missing:
            status = "waiting" if job_active else "missing_artifacts"
        else:
            status = "ready"
        path = str(tool["path"])
        tools.append(
            {
                "toolId": tool["toolId"],
                "label": tool["label"],
                "status": status,
                "path": path,
                "url": _tool_url(job_id=job_id, path=path) if status == "ready" else "",
                "requiredArtifacts": required,
                "missingArtifacts": missing,
            }
        )
    return tools


def job_readiness(
    *,
    rel_paths: Sequence[Any],
    worker_complete: bool,
    artifacts_registered: bool,
    job_active: bool = False,
    review_summary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    available = normalize_rel_paths(rel_paths)
    missing_review = [path for path in REVIEW_PAYLOAD_REQUIRED_ARTIFACTS if path not in available]
    tools = review_tool_statuses(job_id="", rel_paths=available, job_active=job_active)
    missing_tool_artifacts = sorted({path for tool in tools for path in tool["missingArtifacts"]})
    review_payload_ready = not missing_review
    preview_tools_ready = not missing_tool_artifacts
    review = review_summary or {}
    export_eligible = int(review.get("exportableTrackCount") or 0) > 0
    export_ready = bool(export_eligible and int(review.get("pendingTrackCount") or 0) == 0)
    ready_for_review = bool(worker_complete and artifacts_registered and review_payload_ready and preview_tools_ready)
    missing_artifacts = sorted(set(missing_review + missing_tool_artifacts))

    blocked_reason_code = ""
    blocked_reason = ""
    if not worker_complete:
        blocked_reason_code = "worker_incomplete"
        blocked_reason = "The worker has not finished extraction yet."
    elif not artifacts_registered:
        blocked_reason_code = "artifacts_registering"
        blocked_reason = "Finalizing review assets."
    elif not review_payload_ready:
        blocked_reason_code = "review_payload_missing"
        blocked_reason = f"Review payload is missing: {', '.join(missing_review)}."
    elif not preview_tools_ready:
        blocked_reason_code = "preview_tools_missing"
        blocked_reason = f"Preview tools are missing: {', '.join(missing_tool_artifacts)}."
    elif not export_ready:
        blocked_reason_code = str(review.get("blockedReasonCode") or "needs_reviewed_track")
        blocked_reason = str(review.get("blockedReason") or "Mark at least one moving track for export.")

    return {
        "format": "motionjson.job_readiness.v0.1",
        "workerComplete": bool(worker_complete),
        "artifactsRegistered": bool(artifacts_registered),
        "reviewPayloadReady": review_payload_ready,
        "previewToolsReady": preview_tools_ready,
        "exportEligible": export_eligible,
        "exportReady": export_ready,
        "readyForReview": ready_for_review,
        "missingArtifacts": missing_artifacts,
        "blockedReasonCode": blocked_reason_code,
        "blockedReason": blocked_reason,
    }


def _tool_url(*, job_id: str, path: str) -> str:
    if not job_id:
        return ""
    encoded_scene = f"/api/jobs/{job_id}/preview-files/scene_graph.json"
    encoded_manifest = f"/api/jobs/{job_id}/preview-files/web_asset_manifest.json"
    return (
        f"/api/jobs/{job_id}/preview-files/{path}"
        f"?scene={encoded_scene}&manifest={encoded_manifest}&review=/api/jobs/{job_id}/review"
        f"&export=/api/jobs/{job_id}/exports/motionjson&jobId={job_id}"
    )
