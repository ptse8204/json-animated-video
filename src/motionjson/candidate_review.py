from __future__ import annotations

import re
from collections import Counter
from typing import Any, Mapping

from motionjson.provider_settings import redact_secret_text


CANDIDATE_REVIEW_FORMAT = "motionjson.candidate_review.v0.1"
CANDIDATE_SUMMARY_FORMAT = "motionjson.candidate_summary.v0.2"
REVIEW_STATUS_REJECTED = {"rejected", "ignored", "excluded"}

_STORAGE_KEY_RE = re.compile(r"\bprojects/[A-Za-z0-9._~!$&'()*+,;=:@%/-]+")
_LOCAL_FILE_URI_RE = re.compile(r"(?i)\bfile://[^\r\n]+")
_LOCAL_ABSOLUTE_PATH_RE = re.compile(r"(?<![\w:])/(?:Users|private|var|tmp|Volumes|home)/[^\r\n]+")
_WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"(?i)(?<![\w:])(?:[A-Z]:[\\/]|\\\\)[^\r\n\"'<>|]+")


def candidate_review_payload(
    document: Mapping[str, Any],
    *,
    artifact_ids_by_rel_path: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Return the public API-first candidate records and aggregate summary."""

    artifact_ids = artifact_ids_by_rel_path or {}
    candidates = [
        _candidate_review_record(candidate, index, document, artifact_ids)
        for index, candidate in enumerate(_candidate_documents(document))
    ]
    summary = _candidate_summary(document, candidates)
    return {"candidates": candidates, "candidateSummary": summary}


def _candidate_documents(document: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    candidates = document.get("candidates")
    if not isinstance(candidates, list):
        return []
    return [candidate for candidate in candidates if isinstance(candidate, Mapping)]


def _candidate_review_record(
    candidate: Mapping[str, Any],
    index: int,
    document: Mapping[str, Any],
    artifact_ids_by_rel_path: Mapping[str, str],
) -> dict[str, Any]:
    metadata = _mapping(candidate.get("metadata"))
    provider_name = _text(
        _first_present(
            candidate,
            metadata,
            ("providerName", "provider_name"),
            default=document.get("provider") or candidate.get("source") or "unknown",
        )
    )
    source = _text(candidate.get("source") or document.get("provider") or provider_name or "unknown")
    box = _box(candidate.get("box") or candidate.get("bbox"))
    rejection_reason = _text_or_none(_first_present(candidate, metadata, ("rejectionReason", "rejection_reason")))
    review_status = _text(
        _first_present(candidate, metadata, ("reviewStatus", "review_status"), default="rejected" if rejection_reason else "pending")
    )
    confidence = _score(candidate, metadata, ("confidence", "score"), default=None)
    if confidence is None:
        confidence = _score(candidate, metadata, ("stabilityScore", "stability_score", "motionScore", "motion_score"), default=None)
    default_selected = _bool_or_default(
        _first_present(candidate, metadata, ("defaultSelected", "default_selected")),
        default=rejection_reason is None and not _is_rejected_status(review_status),
    )
    record = {
        "candidateId": _text(candidate.get("candidateId") or candidate.get("candidate_id") or candidate.get("id") or f"cand_{index + 1:03d}"),
        "objectId": _text_or_none(candidate.get("objectId") or candidate.get("object_id")),
        "label": _text(candidate.get("label") or "unlabeled object"),
        "source": source,
        "providerName": provider_name,
        "frameIndex": _int(candidate.get("frameIndex", candidate.get("frame_index")), default=0),
        "thumbnailArtifactId": _artifact_id_from_record(
            candidate,
            metadata,
            ("thumbnailArtifactId", "thumbnail_artifact_id"),
            ("thumbnailArtifactPath", "thumbnail_artifact_path"),
            artifact_ids_by_rel_path,
        ),
        "maskPreviewArtifactId": _artifact_id_from_record(
            candidate,
            metadata,
            ("maskPreviewArtifactId", "mask_preview_artifact_id"),
            ("maskPreviewArtifactPath", "mask_preview_artifact_path"),
            artifact_ids_by_rel_path,
        ),
        "box": box,
        "areaRatio": _area_ratio(candidate, metadata, box, _mapping(document.get("video"))),
        "stabilityScore": _score(candidate, metadata, ("stabilityScore", "stability_score"), default=confidence),
        "motionScore": _score(candidate, metadata, ("motionScore", "motion_score"), default=None),
        "confidence": confidence,
        "frameCoverageEstimate": _frame_coverage(candidate, metadata, _mapping(document.get("video"))),
        "warnings": _warnings(candidate, metadata),
        "rejectionReason": rejection_reason,
        "defaultSelected": default_selected,
        "reviewStatus": review_status,
    }
    return _public_value(record)


def _candidate_summary(document: Mapping[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    config = _mapping(document.get("config"))
    first_candidate_provider = candidates[0].get("providerName") if candidates else None
    rejection_reasons = Counter(
        _candidate_rejection_reason(candidate)
        for candidate in candidates
        if _is_rejected_candidate(candidate)
    )
    rejected_count = sum(rejection_reasons.values())
    candidate_count = len(candidates)
    return _public_value(
        {
            "format": CANDIDATE_SUMMARY_FORMAT,
            "candidateCount": candidate_count,
            "acceptedCandidateCount": candidate_count - rejected_count,
            "rejectedCandidateCount": rejected_count,
            "defaultSelectedCount": sum(1 for candidate in candidates if candidate.get("defaultSelected") is True),
            "rejectionReasons": dict(sorted(rejection_reasons.items())),
            "qualityPreset": _text(config.get("qualityPreset") or config.get("quality_preset") or "unknown"),
            "providerName": _text(config.get("providerName") or config.get("provider_name") or first_candidate_provider or document.get("provider") or "unknown"),
            "requiresReview": _bool_or_default(config.get("requireReview", config.get("require_review")), default=True),
        }
    )


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def public_review_value(value: Any) -> Any:
    return _public_value(value)


def _is_rejected_candidate(candidate: Mapping[str, Any]) -> bool:
    return bool(candidate.get("rejectionReason")) or _is_rejected_status(candidate.get("reviewStatus"))


def _candidate_rejection_reason(candidate: Mapping[str, Any]) -> str:
    reason = str(candidate.get("rejectionReason") or "").strip()
    return reason or "review_rejected"


def _is_rejected_status(value: Any) -> bool:
    return str(value or "").strip().lower() in REVIEW_STATUS_REJECTED


def _first_present(
    primary: Mapping[str, Any],
    secondary: Mapping[str, Any],
    keys: tuple[str, ...],
    *,
    default: Any = None,
) -> Any:
    for source in (primary, secondary):
        for key in keys:
            if key in source and source[key] is not None:
                return source[key]
    return default


def _text(value: Any) -> str:
    text = str(value or "").strip()
    return _public_text(text) if text else ""


def _text_or_none(value: Any) -> str | None:
    text = _text(value)
    return text or None


def _int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _rounded(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 6)


def _score(candidate: Mapping[str, Any], metadata: Mapping[str, Any], keys: tuple[str, ...], *, default: float | None) -> float | None:
    value = _first_present(candidate, metadata, keys)
    parsed = _number(value)
    return _rounded(default if parsed is None else parsed)


def _bool_or_default(value: Any, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return bool(default)


def _box(value: Any) -> dict[str, int] | None:
    if isinstance(value, Mapping):
        return {
            "x": _int(value.get("x"), default=0),
            "y": _int(value.get("y"), default=0),
            "w": _int(value.get("w", value.get("width")), default=0),
            "h": _int(value.get("h", value.get("height")), default=0),
        }
    if isinstance(value, (list, tuple)) and len(value) == 4:
        return {
            "x": _int(value[0], default=0),
            "y": _int(value[1], default=0),
            "w": _int(value[2], default=0),
            "h": _int(value[3], default=0),
        }
    return None


def _area_ratio(candidate: Mapping[str, Any], metadata: Mapping[str, Any], box: dict[str, int] | None, video: Mapping[str, Any]) -> float | None:
    explicit = _number(_first_present(candidate, metadata, ("areaRatio", "area_ratio", "maskAreaRatio", "mask_area_ratio")))
    if explicit is not None:
        return _rounded(explicit)
    if not box:
        return None
    width = _number(video.get("width"))
    height = _number(video.get("height"))
    if not width or not height:
        return None
    return _rounded(max(0, box["w"]) * max(0, box["h"]) / max(1.0, width * height))


def _frame_coverage(candidate: Mapping[str, Any], metadata: Mapping[str, Any], video: Mapping[str, Any]) -> float | None:
    explicit = _number(_first_present(candidate, metadata, ("frameCoverageEstimate", "frame_coverage_estimate", "frameCoverage", "frame_coverage")))
    if explicit is not None:
        return _rounded(explicit)
    mask_files = _number(metadata.get("maskFiles") or metadata.get("mask_files"))
    sampled_frames = _number(video.get("sampledFrameCount") or video.get("frameCount"))
    if mask_files is not None and sampled_frames:
        return _rounded(min(1.0, max(0.0, mask_files / sampled_frames)))
    return None


def _warnings(candidate: Mapping[str, Any], metadata: Mapping[str, Any]) -> list[Any]:
    value = candidate.get("warnings", metadata.get("warnings", []))
    if not isinstance(value, list):
        return [_public_value(value)] if value else []
    return [_public_value(item) for item in value]


def _artifact_id(value: Any) -> str | None:
    text = _text(value)
    if not text or "/" in text or "\\" in text or text.lower().startswith("file:"):
        return None
    return text


def _artifact_id_from_record(
    candidate: Mapping[str, Any],
    metadata: Mapping[str, Any],
    id_keys: tuple[str, ...],
    path_keys: tuple[str, ...],
    artifact_ids_by_rel_path: Mapping[str, str],
) -> str | None:
    direct = _artifact_id(_first_present(candidate, metadata, id_keys))
    if direct:
        return direct
    rel_path = _first_present(candidate, metadata, path_keys)
    if isinstance(rel_path, str):
        artifact_id = artifact_ids_by_rel_path.get(rel_path.replace("\\", "/"))
        if artifact_id:
            return _artifact_id(artifact_id)
    return None


def _public_text(value: str) -> str:
    return redact_secret_text(
        _WINDOWS_ABSOLUTE_PATH_RE.sub(
            "[LOCAL_PATH_REDACTED]",
            _LOCAL_ABSOLUTE_PATH_RE.sub(
                "[LOCAL_PATH_REDACTED]",
                _LOCAL_FILE_URI_RE.sub(
                    "[LOCAL_FILE_URI_REDACTED]",
                    _STORAGE_KEY_RE.sub("[STORAGE_KEY_REDACTED]", value),
                ),
            ),
        )
    )


def _public_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _public_value(item)
            for key, item in value.items()
            if re.sub(r"[^a-z0-9]", "", str(key).lower()) != "storagekey"
        }
    if isinstance(value, list):
        return [_public_value(item) for item in value]
    if isinstance(value, str):
        return _public_text(value)
    return value
