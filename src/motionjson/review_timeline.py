from __future__ import annotations

from typing import Any, Mapping, Sequence


REVIEW_TIMELINE_FORMAT = "motionjson.review_timeline.v0.1"


def review_timeline_payload(
    *,
    candidates: Sequence[Mapping[str, Any]] | None = None,
    tracks: Sequence[Mapping[str, Any]] | None = None,
    source: Mapping[str, Any] | None = None,
    candidate_summary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a public, API-owned timeline summary for review UIs."""

    candidate_records = [candidate for candidate in candidates or [] if isinstance(candidate, Mapping)]
    track_records = [track for track in tracks or [] if isinstance(track, Mapping)]
    source_data = source if isinstance(source, Mapping) else {}
    candidate_summary_data = candidate_summary if isinstance(candidate_summary, Mapping) else {}
    markers: list[dict[str, Any]] = []

    for candidate in candidate_records:
        frame_index = _int_any(candidate, ("frameIndex", "frame_index"), default=0)
        candidate_id = _text(candidate.get("candidateId") or candidate.get("candidate_id") or candidate.get("id"))
        marker = {
            "id": f"candidate:{candidate_id or len(markers) + 1}:{frame_index}",
            "kind": "candidate",
            "frameIndex": frame_index,
            "label": _text(candidate.get("label")) or "candidate",
            "candidateId": candidate_id or None,
            "objectId": _text(candidate.get("objectId") or candidate.get("object_id")) or None,
            "status": _candidate_status(candidate),
            "source": _text(candidate.get("source")) or "candidate",
            "confidence": _number(candidate.get("confidence")),
        }
        markers.append(_clean(marker))

    for track in track_records:
        object_id = _text(track.get("objectId") or track.get("object_id") or track.get("id"))
        label = _text(track.get("label")) or object_id or "track"
        frames = _visible_frame_indexes(track)
        if not frames:
            continue
        first = frames[0]
        last = frames[-1]
        markers.append(
            _clean(
                {
                    "id": f"track:{object_id}:start:{first}",
                    "kind": "track_start",
                    "frameIndex": first,
                    "label": f"{label} appears",
                    "objectId": object_id or None,
                    "status": _text(track.get("exportStatus") or track.get("export_status")) or "tracked",
                    "source": _text(track.get("source") or track.get("providerName") or track.get("provider_name")) or "track",
                    "confidence": _number(track.get("confidence")),
                }
            )
        )
        if last != first:
            markers.append(
                _clean(
                    {
                        "id": f"track:{object_id}:end:{last}",
                        "kind": "track_end",
                        "frameIndex": last,
                        "label": f"{label} last visible",
                        "objectId": object_id or None,
                        "status": _text(track.get("exportStatus") or track.get("export_status")) or "tracked",
                        "source": _text(track.get("source") or track.get("providerName") or track.get("provider_name")) or "track",
                        "confidence": _number(track.get("confidence")),
                    }
                )
            )
        for previous, current in zip(frames, frames[1:]):
            if current - previous > 1:
                markers.append(
                    _clean(
                        {
                            "id": f"track:{object_id}:gap:{previous + 1}",
                            "kind": "track_lost",
                            "frameIndex": previous + 1,
                            "label": f"{label} gap",
                            "objectId": object_id or None,
                            "status": "gap",
                            "source": "track_review",
                        }
                    )
                )

    markers = sorted(markers, key=lambda item: (int(item.get("frameIndex") or 0), str(item.get("kind") or ""), str(item.get("id") or "")))
    frame_count = _frame_count(source_data, candidate_summary_data, candidate_records, track_records, markers)
    suggested_keyframes = _suggested_keyframes(
        markers=markers,
        candidate_summary=candidate_summary_data,
        frame_count=frame_count,
    )
    return {
        "format": REVIEW_TIMELINE_FORMAT,
        "frameCount": frame_count,
        "fps": _number(source_data.get("fps") or source_data.get("sampleFps") or _mapping(candidate_summary_data.get("video")).get("fps")),
        "markers": markers,
        "suggestedKeyframes": suggested_keyframes,
        "markerCountsByKind": _counts(marker.get("kind") for marker in markers),
        "suggestionSource": "api_review_artifacts",
    }


def _suggested_keyframes(
    *,
    markers: Sequence[Mapping[str, Any]],
    candidate_summary: Mapping[str, Any],
    frame_count: int,
) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    config = _mapping(candidate_summary.get("config"))
    keyframe_policy = _text(config.get("keyframePolicy") or config.get("keyframe_policy"))
    configured = _frame_indexes(config.get("keyframes"))
    for frame_index in configured:
        suggestions.append(
            {
                "frameIndex": _clamp_frame(frame_index, frame_count),
                "reason": "configured_keyframe",
                "source": "discovery.config.keyframes",
            }
        )
    if not suggestions and keyframe_policy == "scene_changes":
        for marker in markers:
            if marker.get("kind") not in {"candidate", "track_start", "track_end", "track_lost"}:
                continue
            suggestions.append(
                {
                    "frameIndex": _clamp_frame(_int_any(marker, ("frameIndex", "frame_index"), default=0), frame_count),
                    "reason": "scene_change_policy_review_marker",
                    "source": "review.timeline",
                }
            )
    if not suggestions:
        for marker in markers:
            if marker.get("kind") in {"candidate", "track_start", "track_end"}:
                suggestions.append(
                    {
                        "frameIndex": _clamp_frame(_int_any(marker, ("frameIndex", "frame_index"), default=0), frame_count),
                        "reason": "review_marker",
                        "source": "review.timeline",
                    }
                )

    unique: dict[int, dict[str, Any]] = {}
    for suggestion in suggestions:
        frame_index = int(suggestion["frameIndex"])
        if frame_index not in unique:
            unique[frame_index] = suggestion
    return [unique[key] for key in sorted(unique)[:12]]


def _visible_frame_indexes(track: Mapping[str, Any]) -> list[int]:
    frames = track.get("frames") if isinstance(track.get("frames"), list) else []
    indexes: list[int] = []
    for frame in frames:
        if not isinstance(frame, Mapping) or frame.get("visible") is False:
            continue
        frame_index = _int_any(frame, ("frame", "frameIndex", "frame_index", "outIndex", "out_index"), default=None)
        if frame_index is not None:
            indexes.append(frame_index)
    if not indexes:
        first = _int_any(track, ("firstVisibleFrame", "first_visible_frame", "frameStart", "frame_start"), default=None)
        last = _int_any(track, ("lastVisibleFrame", "last_visible_frame", "frameEnd", "frame_end"), default=None)
        if first is not None:
            indexes.append(first)
        if last is not None and last != first:
            indexes.append(last)
    return sorted(dict.fromkeys(index for index in indexes if index >= 0))


def _frame_count(
    source: Mapping[str, Any],
    candidate_summary: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    tracks: Sequence[Mapping[str, Any]],
    markers: Sequence[Mapping[str, Any]],
) -> int:
    video = _mapping(candidate_summary.get("video"))
    explicit = _int_any(
        {**dict(video), **dict(source)},
        ("frameCount", "frame_count", "sampledFrameCount", "sampled_frame_count"),
        default=None,
    )
    max_frame = -1
    for marker in markers:
        frame_index = _int_any(marker, ("frameIndex", "frame_index"), default=None)
        if frame_index is not None:
            max_frame = max(max_frame, frame_index)
    for candidate in candidates:
        frame_index = _int_any(candidate, ("frameIndex", "frame_index"), default=None)
        if frame_index is not None:
            max_frame = max(max_frame, frame_index)
    for track in tracks:
        frames = _visible_frame_indexes(track)
        if frames:
            max_frame = max(max_frame, frames[-1])
    if explicit is not None:
        return max(1, max(explicit, max_frame + 1))
    return max(1, max_frame + 1)


def _candidate_status(candidate: Mapping[str, Any]) -> str:
    if candidate.get("rejectionReason") or candidate.get("rejection_reason"):
        return "rejected"
    status = _text(candidate.get("reviewStatus") or candidate.get("review_status"))
    return status or "pending"


def _frame_indexes(value: Any) -> list[int]:
    if isinstance(value, str):
        raw = value.replace(",", " ").split()
    elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        raw = value
    else:
        raw = []
    indexes: list[int] = []
    for item in raw:
        try:
            frame_index = int(item)
        except (TypeError, ValueError):
            continue
        if frame_index >= 0 and frame_index not in indexes:
            indexes.append(frame_index)
    return sorted(indexes)


def _counts(values: Sequence[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = _text(value) or "unknown"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _int_any(mapping: Mapping[str, Any], keys: tuple[str, ...], *, default: int | None) -> int | None:
    for key in keys:
        if key not in mapping or mapping[key] is None or mapping[key] == "":
            continue
        try:
            return int(mapping[key])
        except (TypeError, ValueError):
            continue
    return default


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return round(float(value), 6)
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str:
    return str(value or "").strip()


def _clean(value: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): item for key, item in value.items() if item is not None and item != ""}


def _clamp_frame(frame_index: int, frame_count: int) -> int:
    return max(0, min(int(frame_index), max(0, int(frame_count) - 1)))
