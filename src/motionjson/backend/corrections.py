from __future__ import annotations

import copy
import json
import re
import sqlite3
import uuid
from typing import Any

from motionjson.providers.base import StorageProvider

from .assets import list_assets_for_job, register_generated_asset
from .jobs import get_job, record_job_event
from .models import NotFoundError
from .rights import record_audit_event
from .usage import utc_now


TRACK_EDIT_OPERATIONS = {"relabel", "hide", "show", "set_export_inclusion", "delete", "merge", "split", "add_object", "repair"}
HOOK_OPERATIONS = {"add_object", "repair"}
UI_CORRECTION_STATE_FORMAT = "motionjson.local_ui_corrections.v0.1"
UI_REVIEW_STATE_MANIFEST_FORMAT = "motionjson.local_ui_review_state_manifest.v0.1"
UI_REVIEW_STATE_MANIFEST_KIND = "review_state_manifest"
UI_TRACK_ACTIONS = {
    "relabel_track",
    "set_track_visibility",
    "set_export_inclusion",
    "delete_track",
    "merge_tracks",
    "split_track",
    "add_object",
    "repair_track",
}
UI_TRACK_ACTION_ALIASES = {
    "relabel": "relabel_track",
    "rename_track": "relabel_track",
    "hide": "set_track_visibility",
    "hide_track": "set_track_visibility",
    "show": "set_track_visibility",
    "show_track": "set_track_visibility",
    "delete": "delete_track",
    "remove_track": "delete_track",
    "merge": "merge_tracks",
    "split": "split_track",
    "repair": "repair_track",
    "set_track_export": "set_export_inclusion",
    "include_in_export": "set_export_inclusion",
    "exclude_track": "set_export_inclusion",
}
SAFE_ID_RE = re.compile(r"[^A-Za-z0-9._-]+")
LOCAL_PATH_RE = re.compile(r"(?i)\bfile://[^\r\n]+|(?<![\w:])/(?:Users|private|var|tmp|Volumes|home)/[^\r\n]+")
WINDOWS_LOCAL_PATH_RE = re.compile(r"(?i)(?<![\w:])(?:[A-Z]:[\\/]|\\\\)[^\r\n\"'<>|]+")
STORAGE_KEY_RE = re.compile(r"\bprojects/[A-Za-z0-9._~!$&'()*+,;=:@%/-]+")


def _sanitize_public_text(value: str) -> str:
    return STORAGE_KEY_RE.sub(
        "[STORAGE_KEY_REDACTED]",
        WINDOWS_LOCAL_PATH_RE.sub(
            "[LOCAL_PATH_REDACTED]",
            LOCAL_PATH_RE.sub("[LOCAL_PATH_REDACTED]", value),
        ),
    )


def _sanitize_public_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _sanitize_public_value(item)
            for key, item in value.items()
            if re.sub(r"[^a-z0-9]", "", str(key).lower()) != "storagekey"
        }
    if isinstance(value, list):
        return [_sanitize_public_value(item) for item in value]
    if isinstance(value, str):
        return _sanitize_public_text(value)
    return value


def _json_bytes(document: dict[str, Any]) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _parse_json(value: str | bytes) -> dict[str, Any]:
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("stored correction artifact must be a JSON object")
    return parsed


def _json_field(row: dict[str, Any], field: str) -> Any:
    return json.loads(row.get(field) or "{}")


def public_correction_event(row: dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    data["payload"] = _json_field(data, "payload_json")
    data["result"] = _json_field(data, "result_json")
    data.pop("payload_json", None)
    data.pop("result_json", None)
    return data


def _normalize_operation(value: Any) -> str:
    operation = str(value or "").strip().lower().replace("-", "_")
    operation = {
        "relabel_track": "relabel",
        "set_track_visibility": "hide",
        "set_export_inclusion": "set_export_inclusion",
        "set_track_export": "set_export_inclusion",
        "include_in_export": "set_export_inclusion",
        "exclude_track": "set_export_inclusion",
        "delete_track": "delete",
        "merge_tracks": "merge",
        "split_track": "split",
        "repair_track": "repair",
    }.get(operation, operation)
    if operation not in TRACK_EDIT_OPERATIONS:
        raise ValueError(
            "operation must be relabel, hide, show, set_export_inclusion, delete, merge, split, add_object, or repair"
        )
    return operation


def _normalize_ui_action_type(value: Any) -> str:
    action_type = str(value or "").strip().lower().replace("-", "_")
    action_type = UI_TRACK_ACTION_ALIASES.get(action_type, action_type)
    if action_type not in UI_TRACK_ACTIONS:
        raise ValueError(
            "correction action type must be relabel_track, set_track_visibility, "
            "set_export_inclusion, delete_track, merge_tracks, split_track, add_object, or repair_track"
        )
    return action_type


def _action_track_id(action: dict[str, Any]) -> str:
    return str(action.get("trackId") or action.get("track_id") or action.get("objectId") or action.get("object_id") or "").strip()


def _action_object_id(action: dict[str, Any]) -> str:
    return str(action.get("objectId") or action.get("object_id") or action.get("trackId") or action.get("track_id") or "").strip()


def _bool_value(value: Any, fallback: bool) -> bool:
    if value is None:
        return fallback
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)


def _normalized_frame_range(value: Any) -> list[int] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    start = int(value[0])
    end = int(value[1])
    if start > end:
        start, end = end, start
    return [start, end]


def _coerce_track_edit_payload(payload: dict[str, Any]) -> dict[str, Any]:
    action = payload.get("action") if isinstance(payload.get("action"), dict) else None
    if action is None:
        return dict(payload)

    action_type = _normalize_ui_action_type(action.get("type"))
    operation = _normalize_operation(action_type)
    if action_type == "set_track_visibility":
        operation = "show" if _bool_value(action.get("visible"), True) else "hide"
    elif action_type == "set_export_inclusion":
        included = action.get("included", action.get("exportIncluded", action.get("includeInExport")))
        operation = "set_export_inclusion"

    normalized: dict[str, Any] = {"operation": operation, "action": dict(action)}
    track_id = _action_track_id(action)
    object_id = _action_object_id(action)
    if track_id:
        normalized["objectId"] = track_id
    if object_id:
        normalized["objectId"] = object_id
    if action.get("label") is not None:
        normalized["label"] = action.get("label")
    if action.get("frameRange") is not None:
        frame_range = _normalized_frame_range(action.get("frameRange"))
        normalized["frameRange"] = [max(1, int(frame) + 1) for frame in frame_range] if frame_range else action.get("frameRange")
    if action_type == "set_export_inclusion":
        included = action.get("included", action.get("exportIncluded", action.get("includeInExport")))
        normalized["included"] = _bool_value(included, True)
    if action.get("newTrackId") or action.get("newObjectId"):
        normalized["newObjectId"] = action.get("newTrackId") or action.get("newObjectId")
    if action.get("prompts") is not None:
        normalized["prompts"] = action.get("prompts")
    if action.get("prompt") is not None:
        normalized["prompt"] = action.get("prompt")
    if action.get("correctionRequest") is not None:
        normalized["correctionRequest"] = action.get("correctionRequest")
    if action.get("repairProvider") is not None:
        normalized["repairProvider"] = action.get("repairProvider")
    if action_type == "merge_tracks":
        track_ids = [str(item) for item in action.get("trackIds", [])] if isinstance(action.get("trackIds"), list) else []
        keep_id = str(action.get("keepTrackId") or (track_ids[0] if track_ids else ""))
        merge_id = next((item for item in track_ids if item != keep_id), "")
        if keep_id:
            normalized["keepObjectId"] = keep_id
        if merge_id:
            normalized["mergeObjectId"] = merge_id
    return normalized


def _safe_object_id(value: str) -> str:
    cleaned = SAFE_ID_RE.sub("_", value.strip()).strip("._-")
    return cleaned or "object"


def _asset_rel_path(asset: dict[str, Any]) -> str:
    metadata = json.loads(asset.get("metadata_json") or "{}")
    rel_path = metadata.get("rel_path")
    return rel_path if isinstance(rel_path, str) else ""


def _latest_asset_by_kind(assets: list[dict[str, Any]], kind: str) -> dict[str, Any] | None:
    matches = [asset for asset in assets if asset.get("kind") == kind]
    return matches[-1] if matches else None


def _object_id_from_manifest_rel_path(rel_path: str) -> str | None:
    parts = rel_path.replace("\\", "/").split("/")
    if len(parts) >= 3 and parts[0] == "objects" and parts[2] == "object_manifest.json":
        return parts[1]
    return None


def _load_json_asset(storage: StorageProvider, asset: dict[str, Any]) -> dict[str, Any]:
    return _parse_json(storage.load_bytes(asset["storage_key"]).decode("utf-8"))


def _write_json_asset(
    conn: sqlite3.Connection,
    *,
    storage: StorageProvider,
    asset: dict[str, Any],
    document: dict[str, Any],
) -> dict[str, Any]:
    data = _json_bytes(document)
    storage.save_bytes(asset["storage_key"], data, content_type=asset.get("content_type"))
    conn.execute("UPDATE assets SET byte_size = ? WHERE id = ?", (len(data), asset["id"]))
    conn.commit()
    updated = dict(asset)
    updated["byte_size"] = len(data)
    return updated


def _scene_object(scene: dict[str, Any], object_id: str) -> dict[str, Any] | None:
    for item in scene.get("objects", []):
        if isinstance(item, dict) and item.get("id") == object_id:
            return item
    return None


def _scene_layer(scene: dict[str, Any], object_id: str) -> dict[str, Any] | None:
    for item in scene.get("layers", []):
        if isinstance(item, dict) and item.get("object_id") == object_id:
            return item
    return None


def _track(tracks: dict[str, Any], object_id: str) -> dict[str, Any] | None:
    for item in tracks.get("tracks", []):
        if isinstance(item, dict) and item.get("objectId") == object_id:
            return item
    return None


def _ensure_object_exists(scene: dict[str, Any] | None, tracks: dict[str, Any] | None, object_id: str) -> None:
    if (scene and _scene_object(scene, object_id)) or (tracks and _track(tracks, object_id)):
        return
    raise ValueError(f"objectId {object_id!r} was not found in the job artifacts")


def _frames_visible_count(frames: list[Any]) -> int:
    return sum(1 for frame in frames if isinstance(frame, dict) and frame.get("visible"))


def _refresh_track_counts(track: dict[str, Any]) -> None:
    frames = track.get("frames") if isinstance(track.get("frames"), list) else []
    track["frameCount"] = len(frames)
    track["visibleFrameCount"] = _frames_visible_count(frames)


def _append_warning(track: dict[str, Any], warning: str) -> None:
    warnings = track.setdefault("warnings", [])
    if not isinstance(warnings, list):
        warnings = []
        track["warnings"] = warnings
    if warning not in warnings:
        warnings.append(warning)


def _metadata(item: dict[str, Any]) -> dict[str, Any]:
    metadata = item.setdefault("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
        item["metadata"] = metadata
    return metadata


def _snapshot_frames(container: dict[str, Any], key: str, snapshot_key: str) -> None:
    frames = container.get(key) if isinstance(container.get(key), list) else []
    corrections = container.setdefault("corrections", {})
    if not isinstance(corrections, dict):
        corrections = {}
        container["corrections"] = corrections
    if snapshot_key in corrections:
        return
    corrections[snapshot_key] = [
        {
            "index": index,
            "visible": frame.get("visible"),
            "opacity": frame.get("opacity"),
        }
        for index, frame in enumerate(frames)
        if isinstance(frame, dict)
    ]


def _restore_frames(container: dict[str, Any], key: str, snapshot_key: str) -> None:
    frames = container.get(key) if isinstance(container.get(key), list) else []
    corrections = container.get("corrections") if isinstance(container.get("corrections"), dict) else {}
    snapshot = corrections.pop(snapshot_key, None) if isinstance(corrections, dict) else None
    if not isinstance(snapshot, list):
        return
    by_index = {int(item["index"]): item for item in snapshot if isinstance(item, dict) and "index" in item}
    for index, frame in enumerate(frames):
        if not isinstance(frame, dict) or index not in by_index:
            continue
        item = by_index[index]
        if "visible" in item:
            frame["visible"] = bool(item["visible"])
        if "opacity" in item and item["opacity"] is not None:
            frame["opacity"] = item["opacity"]


def _set_frames_hidden(container: dict[str, Any], key: str) -> None:
    frames = container.get(key) if isinstance(container.get(key), list) else []
    for frame in frames:
        if not isinstance(frame, dict):
            continue
        frame["visible"] = False
        if "opacity" in frame:
            frame["opacity"] = 0.0


def _set_hidden(scene: dict[str, Any] | None, tracks: dict[str, Any] | None, object_id: str, hidden: bool) -> dict[str, Any]:
    if scene:
        obj = _scene_object(scene, object_id)
        if obj:
            if hidden:
                _snapshot_frames(obj, "motion", "preHideMotion")
                _snapshot_frames(obj, "frames", "preHideFrames")
                _set_frames_hidden(obj, "motion")
                _set_frames_hidden(obj, "frames")
                obj["hidden"] = True
                obj["exportStatus"] = "rejected"
            else:
                _restore_frames(obj, "motion", "preHideMotion")
                _restore_frames(obj, "frames", "preHideFrames")
                obj["hidden"] = False
                obj["exportStatus"] = "accepted"
        layer = _scene_layer(scene, object_id)
        if layer:
            if hidden:
                _snapshot_frames(layer, "frames", "preHideLayerFrames")
                _set_frames_hidden(layer, "frames")
                layer["hidden"] = True
            else:
                _restore_frames(layer, "frames", "preHideLayerFrames")
                layer["hidden"] = False

    changed_track = None
    if tracks:
        changed_track = _track(tracks, object_id)
        if changed_track:
            metadata = _metadata(changed_track)
            if hidden:
                _snapshot_frames(changed_track, "frames", "preHideTrackFrames")
                _set_frames_hidden(changed_track, "frames")
                metadata["hidden"] = True
                changed_track["exportStatus"] = "rejected"
                changed_track["visible"] = False
                changed_track["exportIncluded"] = False
                _append_warning(changed_track, "hidden_by_user")
            else:
                _restore_frames(changed_track, "frames", "preHideTrackFrames")
                metadata["hidden"] = False
                changed_track["exportStatus"] = "accepted"
                changed_track["visible"] = True
                changed_track["exportIncluded"] = True
                if isinstance(changed_track.get("warnings"), list):
                    changed_track["warnings"] = [item for item in changed_track["warnings"] if item != "hidden_by_user"]
            _refresh_track_counts(changed_track)
    return {
        "objectId": object_id,
        "hidden": hidden,
        "exportStatus": "rejected" if hidden else "accepted",
        "visibleFrameCount": changed_track.get("visibleFrameCount") if changed_track else None,
    }


def _set_export_inclusion(scene: dict[str, Any] | None, tracks: dict[str, Any] | None, object_id: str, included: bool) -> dict[str, Any]:
    export_status = "accepted" if included else "excluded"
    if scene:
        obj = _scene_object(scene, object_id)
        if obj:
            obj["exportIncluded"] = included
            obj["exportStatus"] = export_status
        layer = _scene_layer(scene, object_id)
        if layer:
            layer["exportIncluded"] = included
            layer["exportStatus"] = export_status

    changed_track = None
    if tracks:
        changed_track = _track(tracks, object_id)
        if changed_track:
            changed_track["exportIncluded"] = included
            changed_track["exportStatus"] = export_status
            metadata = _metadata(changed_track)
            metadata["exportIncluded"] = included
            if included and isinstance(changed_track.get("warnings"), list):
                changed_track["warnings"] = [item for item in changed_track["warnings"] if item != "excluded_from_export"]
            elif not included:
                _append_warning(changed_track, "excluded_from_export")
            _refresh_track_counts(changed_track)
    return {
        "objectId": object_id,
        "exportIncluded": included,
        "exportStatus": export_status,
        "visibleFrameCount": changed_track.get("visibleFrameCount") if changed_track else None,
    }


def _relabel(
    scene: dict[str, Any] | None,
    tracks: dict[str, Any] | None,
    manifests: dict[str, tuple[dict[str, Any], dict[str, Any]]],
    web_manifests: list[tuple[dict[str, Any], dict[str, Any]]],
    *,
    object_id: str,
    label: str,
) -> dict[str, Any]:
    if scene:
        obj = _scene_object(scene, object_id)
        if obj:
            obj["label"] = label
    if tracks:
        item = _track(tracks, object_id)
        if item:
            item["label"] = label
    manifest_pair = manifests.get(object_id)
    if manifest_pair:
        manifest_pair[1]["label"] = label
    for _asset, document in web_manifests:
        if document.get("assetId") == object_id or document.get("objectId") == object_id:
            document["label"] = label
    return {"objectId": object_id, "label": label}


def _remove_scene_object(scene: dict[str, Any], object_id: str) -> None:
    scene["objects"] = [
        item for item in scene.get("objects", []) if not (isinstance(item, dict) and item.get("id") == object_id)
    ]
    scene["layers"] = [
        item for item in scene.get("layers", []) if not (isinstance(item, dict) and item.get("object_id") == object_id)
    ]


def _delete(scene: dict[str, Any] | None, tracks: dict[str, Any] | None, object_id: str) -> dict[str, Any]:
    if scene:
        _remove_scene_object(scene, object_id)
    marked_track = False
    if tracks:
        item = _track(tracks, object_id)
        if item:
            marked_track = True
            item["deleted"] = True
            item["visible"] = False
            item["exportIncluded"] = False
            item["exportStatus"] = "deleted"
            _metadata(item)["deleted"] = True
            _append_warning(item, "deleted_by_user")
    return {"objectId": object_id, "deleted": True, "trackRemoved": False, "trackMarkedDeleted": marked_track, "exportStatus": "deleted"}


def _frame_key(frame: dict[str, Any]) -> int:
    return int(frame.get("frame") or frame.get("outIndex") or 0)


def _merge_frame_lists(keep_frames: list[Any], merge_frames: list[Any]) -> list[Any]:
    merged: dict[int, dict[str, Any]] = {}
    order = 0
    for frame in keep_frames:
        if not isinstance(frame, dict):
            continue
        key = _frame_key(frame)
        copied = copy.deepcopy(frame)
        copied["_order"] = order
        order += 1
        merged[key] = copied
    for frame in merge_frames:
        if not isinstance(frame, dict):
            continue
        key = _frame_key(frame)
        existing = merged.get(key)
        if existing is None or (not existing.get("visible") and frame.get("visible")):
            copied = copy.deepcopy(frame)
            copied["_order"] = order
            order += 1
            merged[key] = copied
    result = sorted(merged.values(), key=lambda item: (_frame_key(item), int(item.get("_order") or 0)))
    for item in result:
        item.pop("_order", None)
    return result


def _merge(scene: dict[str, Any] | None, tracks: dict[str, Any] | None, keep_id: str, merge_id: str) -> dict[str, Any]:
    if keep_id == merge_id:
        raise ValueError("merge requires two different object ids")
    if scene:
        keep_obj = _scene_object(scene, keep_id)
        merge_obj = _scene_object(scene, merge_id)
        if keep_obj and merge_obj:
            keep_obj["motion"] = _merge_frame_lists(
                keep_obj.get("motion") if isinstance(keep_obj.get("motion"), list) else [],
                merge_obj.get("motion") if isinstance(merge_obj.get("motion"), list) else [],
            )
            keep_obj["frames"] = _merge_frame_lists(
                keep_obj.get("frames") if isinstance(keep_obj.get("frames"), list) else [],
                merge_obj.get("frames") if isinstance(merge_obj.get("frames"), list) else [],
            )
            corrections = keep_obj.setdefault("corrections", {})
            if isinstance(corrections, dict):
                corrections.setdefault("mergedObjectIds", []).append(merge_id)
        keep_layer = _scene_layer(scene, keep_id)
        merge_layer = _scene_layer(scene, merge_id)
        if keep_layer and merge_layer:
            keep_layer["frames"] = _merge_frame_lists(
                keep_layer.get("frames") if isinstance(keep_layer.get("frames"), list) else [],
                merge_layer.get("frames") if isinstance(merge_layer.get("frames"), list) else [],
            )
        _remove_scene_object(scene, merge_id)

    if tracks:
        keep_track = _track(tracks, keep_id)
        merge_track = _track(tracks, merge_id)
        if keep_track and merge_track:
            keep_track["frames"] = _merge_frame_lists(
                keep_track.get("frames") if isinstance(keep_track.get("frames"), list) else [],
                merge_track.get("frames") if isinstance(merge_track.get("frames"), list) else [],
            )
            _refresh_track_counts(keep_track)
            metadata = _metadata(keep_track)
            metadata.setdefault("mergedObjectIds", []).append(merge_id)
            _append_warning(keep_track, "merged_duplicate_track")
            merge_track["mergedIntoObjectId"] = keep_id
            merge_track["visible"] = False
            merge_track["exportIncluded"] = False
            merge_track["exportStatus"] = "merged"
            _metadata(merge_track)["mergedIntoObjectId"] = keep_id
            _append_warning(merge_track, "merged_duplicate_track")
    return {"objectId": merge_id, "targetObjectId": keep_id, "merged": True, "exportStatus": "merged"}


def _in_frame_range(frame: dict[str, Any], start: int, end: int) -> bool:
    value = _frame_key(frame)
    return start <= value <= end


def _split_frames(frames: list[Any], start: int, end: int) -> tuple[list[Any], list[Any]]:
    kept: list[Any] = []
    moved: list[Any] = []
    for frame in frames:
        if not isinstance(frame, dict):
            continue
        target = moved if _in_frame_range(frame, start, end) else kept
        target.append(copy.deepcopy(frame))
    return kept, moved


def _split(scene: dict[str, Any] | None, tracks: dict[str, Any] | None, object_id: str, new_object_id: str, start: int, end: int, label: str | None) -> dict[str, Any]:
    moved_count = 0
    if scene:
        obj = _scene_object(scene, object_id)
        if obj:
            new_obj = copy.deepcopy(obj)
            new_obj["id"] = new_object_id
            new_obj["label"] = label or f"{obj.get('label') or object_id} split"
            obj["motion"], new_obj["motion"] = _split_frames(
                obj.get("motion") if isinstance(obj.get("motion"), list) else [],
                start,
                end,
            )
            obj["frames"], new_obj["frames"] = _split_frames(
                obj.get("frames") if isinstance(obj.get("frames"), list) else [],
                start,
                end,
            )
            moved_count = len(new_obj.get("motion") or new_obj.get("frames") or [])
            scene.setdefault("objects", []).append(new_obj)
        layer = _scene_layer(scene, object_id)
        if layer:
            new_layer = copy.deepcopy(layer)
            new_layer["id"] = f"{new_object_id}_raster_layer"
            new_layer["object_id"] = new_object_id
            layer["frames"], new_layer["frames"] = _split_frames(
                layer.get("frames") if isinstance(layer.get("frames"), list) else [],
                start,
                end,
            )
            scene.setdefault("layers", []).append(new_layer)

    if tracks:
        source_track = _track(tracks, object_id)
        if source_track:
            new_track = copy.deepcopy(source_track)
            new_track["objectId"] = new_object_id
            new_track["label"] = label or f"{source_track.get('label') or object_id} split"
            source_track["frames"], new_track["frames"] = _split_frames(
                source_track.get("frames") if isinstance(source_track.get("frames"), list) else [],
                start,
                end,
            )
            _refresh_track_counts(source_track)
            _refresh_track_counts(new_track)
            metadata = _metadata(new_track)
            metadata["splitFromObjectId"] = object_id
            metadata["splitFrameRange"] = [start, end]
            source_metadata = _metadata(source_track)
            source_metadata.setdefault("splitObjectIds", []).append(new_object_id)
            tracks.setdefault("tracks", []).append(new_track)
            moved_count = max(moved_count, len(new_track.get("frames") or []))
    return {
        "objectId": object_id,
        "newObjectId": new_object_id,
        "frameRange": [start, end],
        "movedFrameCount": moved_count,
    }


def _first_prompt(payload: dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload.get("prompt"), dict):
        return payload["prompt"]
    prompts = payload.get("prompts")
    if isinstance(prompts, list):
        for prompt in prompts:
            if isinstance(prompt, dict):
                return prompt
    action = payload.get("action") if isinstance(payload.get("action"), dict) else {}
    prompts = action.get("prompts") if isinstance(action.get("prompts"), list) else []
    for prompt in prompts:
        if isinstance(prompt, dict):
            return prompt
    return {}


def _prompt_frame(prompt: dict[str, Any], payload: dict[str, Any]) -> int:
    for key in ("frame", "frameIndex", "frame_index"):
        if prompt.get(key) is not None:
            value = int(prompt[key])
            return max(1, value + 1 if key == "frame_index" and value == 0 else value)
    frame_range = _normalized_frame_range(payload.get("frameRange") or payload.get("frame_range"))
    if frame_range:
        return max(1, int(frame_range[0]))
    return 1


def _prompt_bbox(prompt: dict[str, Any]) -> list[int]:
    data = prompt.get("data") if isinstance(prompt.get("data"), dict) else prompt
    if all(key in data for key in ("x", "y", "w", "h")):
        return [int(data["x"]), int(data["y"]), max(1, int(data["w"])), max(1, int(data["h"]))]
    if isinstance(data.get("box"), dict):
        box = data["box"]
        return [int(box.get("x", 0)), int(box.get("y", 0)), max(1, int(box.get("w", 1))), max(1, int(box.get("h", 1)))]
    x = int(data.get("x", 0))
    y = int(data.get("y", 0))
    return [max(0, x - 4), max(0, y - 4), 8, 8]


def _add_object(scene: dict[str, Any] | None, tracks: dict[str, Any] | None, payload: dict[str, Any], object_id: str) -> dict[str, Any]:
    label = str(payload.get("label") or object_id)
    prompt = _first_prompt(payload)
    frame = _prompt_frame(prompt, payload)
    bbox = _prompt_bbox(prompt)
    x, y, w, h = bbox
    frame_record = {
        "frame": frame,
        "sourceFrameIndex": max(0, frame - 1),
        "outIndex": max(0, frame - 1),
        "t": 0.0,
        "visible": True,
        "area": float(w * h),
        "bbox": bbox,
        "centroid": [round(x + w / 2, 3), round(y + h / 2, 3)],
        "contourPoints": 4,
    }
    motion_record = {
        "frame": frame,
        "sourceFrameIndex": max(0, frame - 1),
        "t": 0.0,
        "visible": True,
        "x": x,
        "y": y,
        "w": w,
        "h": h,
        "scale": 1.0,
        "rotation": 0.0,
        "opacity": 1.0,
        "asset": None,
        "mask": None,
        "centroid": frame_record["centroid"],
    }
    if scene and _scene_object(scene, object_id) is None:
        scene.setdefault("objects", []).append(
            {
                "id": object_id,
                "label": label,
                "renderMode": "manual_correction_placeholder",
                "recommendedOutput": "requires_repair",
                "exportStatus": "accepted",
                "motion": [copy.deepcopy(motion_record)],
                "frames": [copy.deepcopy(frame_record)],
                "corrections": {"source": "correction/add_object", "partialRerunRequired": True},
            }
        )
        scene.setdefault("layers", []).append(
            {
                "id": f"{object_id}_correction_layer",
                "object_id": object_id,
                "type": "manual_correction_placeholder",
                "fps": float(scene.get("source", {}).get("sampleFps") or scene.get("canvas", {}).get("fps") or 12.0),
                "z_index": 10 + len(scene.get("objects", [])),
                "frames": [copy.deepcopy(motion_record)],
            }
        )
    if tracks and _track(tracks, object_id) is None:
        tracks.setdefault("tracks", []).append(
            {
                "objectId": object_id,
                "label": label,
                "source": "correction/add_object",
                "providerName": "manual_correction",
                "zIndex": 10 + len(tracks.get("tracks", [])),
                "confidence": 1.0,
                "frameCount": 1,
                "visibleFrameCount": 1,
                "visible": True,
                "exportIncluded": True,
                "exportStatus": "accepted",
                "warnings": ["partial_rerun_required"],
                "metadata": {
                    "correctionHook": True,
                    "partialRerunRequired": True,
                    "prompts": payload.get("prompts") if isinstance(payload.get("prompts"), list) else ([payload["prompt"]] if isinstance(payload.get("prompt"), dict) else []),
                },
                "frames": [copy.deepcopy(frame_record)],
            }
        )
    return {"objectId": object_id, "label": label, "added": True, "source": "correction/add_object", "exportStatus": "accepted"}


def _hook_result(operation: str, payload: dict[str, Any]) -> dict[str, Any]:
    result = {
        "operation": operation,
        "hookRecorded": True,
        "aiUsage": "none",
        "mockSafe": True,
        "partialRerun": {
            "available": False,
            "status": "not_enqueued",
            "reason": "Partial rerun worker is not implemented in this backend slice; the request is persisted for a later repair worker.",
            "requestedFrameRange": payload.get("frameRange") or payload.get("frame_range"),
            "promptCount": len(payload.get("prompts") or []) if isinstance(payload.get("prompts"), list) else (1 if payload.get("prompt") else 0),
        },
    }
    if operation == "repair":
        result["repairDiagnostics"] = repair_unavailable_diagnostics(payload)
    return result


def _record_event(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    project_id: str,
    job_id: str,
    operation: str,
    object_id: str | None,
    target_object_id: str | None,
    payload: dict[str, Any],
    result: dict[str, Any],
    status: str,
) -> dict[str, Any]:
    now = utc_now()
    row = {
        "id": uuid.uuid4().hex,
        "project_id": project_id,
        "job_id": job_id,
        "created_by_user_id": user_id,
        "operation": operation,
        "object_id": object_id,
        "target_object_id": target_object_id,
        "payload_json": json.dumps(payload, sort_keys=True),
        "result_json": json.dumps(result, sort_keys=True),
        "status": status,
        "created_at": now,
    }
    conn.execute(
        """
        INSERT INTO correction_events
        (id, project_id, job_id, created_by_user_id, operation, object_id, target_object_id, payload_json, result_json, status, created_at)
        VALUES (:id, :project_id, :job_id, :created_by_user_id, :operation, :object_id, :target_object_id, :payload_json, :result_json, :status, :created_at)
        """,
        row,
    )
    conn.commit()
    return row


def list_track_corrections(conn: sqlite3.Connection, *, user_id: str, job_id: str) -> list[dict[str, Any]]:
    get_job(conn, user_id=user_id, job_id=job_id)
    rows = conn.execute(
        """
        SELECT *
        FROM correction_events
        WHERE job_id = ?
        ORDER BY created_at, id
        """,
        (job_id,),
    ).fetchall()
    return [public_correction_event(dict(row)) for row in rows]


def _frame_range(payload: dict[str, Any]) -> tuple[int, int]:
    value = payload.get("frameRange", payload.get("frame_range"))
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("split requires frameRange: [start, end]")
    start = int(value[0])
    end = int(value[1])
    if start > end:
        start, end = end, start
    if start < 1:
        raise ValueError("frameRange values must be positive")
    return start, end


def _operation_ids(operation: str, payload: dict[str, Any]) -> tuple[str | None, str | None]:
    object_id = payload.get("objectId") or payload.get("object_id")
    target_id = payload.get("targetObjectId") or payload.get("target_object_id")
    if operation == "merge":
        object_id = payload.get("mergeObjectId") or payload.get("sourceObjectId") or object_id
        target_id = payload.get("keepObjectId") or target_id
    if object_id is not None:
        object_id = str(object_id)
    if target_id is not None:
        target_id = str(target_id)
    return object_id, target_id


def apply_track_edit(
    conn: sqlite3.Connection,
    *,
    storage: StorageProvider,
    user_id: str,
    job_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    payload = _coerce_track_edit_payload(payload)
    operation = _normalize_operation(payload.get("operation") or payload.get("type"))
    job = get_job(conn, user_id=user_id, job_id=job_id)
    assets = list_assets_for_job(conn, project_id=job["project_id"], source_job_id=job_id)
    scene_asset = _latest_asset_by_kind(assets, "scene_graph")
    tracks_asset = _latest_asset_by_kind(assets, "track_summary")

    scene = _load_json_asset(storage, scene_asset) if scene_asset else None
    tracks = _load_json_asset(storage, tracks_asset) if tracks_asset else None
    object_id, target_object_id = _operation_ids(operation, payload)

    if operation not in HOOK_OPERATIONS:
        if not scene and not tracks:
            raise NotFoundError("job has no editable scene or track artifacts")
        if not object_id:
            raise ValueError("objectId is required")
        _ensure_object_exists(scene, tracks, object_id)

    manifests: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    web_manifests: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for asset in assets:
        rel_path = _asset_rel_path(asset)
        if asset.get("kind") == "object_manifest":
            manifest_object_id = _object_id_from_manifest_rel_path(rel_path)
            if manifest_object_id:
                manifests[manifest_object_id] = (asset, _load_json_asset(storage, asset))
        elif asset.get("kind") == "web_manifest":
            web_manifests.append((asset, _load_json_asset(storage, asset)))

    updated_docs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    partial_rerun: dict[str, Any] | None = None
    status = "applied"

    if operation == "relabel":
        label = str(payload.get("label") or "").strip()
        if not label:
            raise ValueError("label is required for relabel")
        result = _relabel(scene, tracks, manifests, web_manifests, object_id=str(object_id), label=label)
    elif operation == "hide":
        result = _set_hidden(scene, tracks, str(object_id), True)
    elif operation == "show":
        result = _set_hidden(scene, tracks, str(object_id), False)
    elif operation == "set_export_inclusion":
        included = _bool_value(payload.get("included", payload.get("exportIncluded", payload.get("includeInExport"))), True)
        result = _set_export_inclusion(scene, tracks, str(object_id), included)
    elif operation == "delete":
        result = _delete(scene, tracks, str(object_id))
    elif operation == "merge":
        if not target_object_id:
            raise ValueError("merge requires keepObjectId or targetObjectId")
        _ensure_object_exists(scene, tracks, target_object_id)
        result = _merge(scene, tracks, target_object_id, str(object_id))
    elif operation == "split":
        start, end = _frame_range(payload)
        new_object_id = _safe_object_id(str(payload.get("newObjectId") or payload.get("new_object_id") or f"{object_id}_split_{start}_{end}"))
        if scene and _scene_object(scene, new_object_id):
            raise ValueError(f"newObjectId {new_object_id!r} already exists")
        if tracks and _track(tracks, new_object_id):
            raise ValueError(f"newObjectId {new_object_id!r} already exists")
        result = _split(
            scene,
            tracks,
            str(object_id),
            new_object_id,
            start,
            end,
            str(payload.get("label") or payload.get("newLabel") or "").strip() or None,
        )
    elif operation in HOOK_OPERATIONS:
        status = "hook_recorded"
        result = _hook_result(operation, payload)
        object_id = object_id or payload.get("newObjectId") or payload.get("new_object_id")
        partial_rerun = result["partialRerun"]
        if operation == "repair" and object_id and tracks:
            item = _track(tracks, str(object_id))
            if item:
                _metadata(item).setdefault("repairRequests", []).append(
                    {
                        "frameRange": payload.get("frameRange") or payload.get("frame_range"),
                        "prompt": payload.get("prompt"),
                        "prompts": payload.get("prompts") if isinstance(payload.get("prompts"), list) else None,
                        "status": "hook_recorded",
                    }
                )
                _append_warning(item, "repair_requested")
                _refresh_track_counts(item)
    else:
        raise ValueError(f"unsupported operation: {operation}")

    if scene_asset and scene is not None and operation != "add_object":
        updated_docs.append((scene_asset, scene))
    if tracks_asset and tracks is not None:
        updated_docs.append((tracks_asset, tracks))
    if operation == "relabel":
        updated_docs.extend((asset, document) for asset, document in manifests.values())
        updated_docs.extend(web_manifests)

    updated_assets = []
    seen_asset_ids: set[str] = set()
    for asset, document in updated_docs:
        if asset["id"] in seen_asset_ids:
            continue
        seen_asset_ids.add(asset["id"])
        updated = _write_json_asset(conn, storage=storage, asset=asset, document=document)
        updated_assets.append({"id": updated["id"], "kind": updated["kind"], "byteSize": updated["byte_size"]})

    event = _record_event(
        conn,
        user_id=user_id,
        project_id=job["project_id"],
        job_id=job_id,
        operation=operation,
        object_id=str(object_id) if object_id else None,
        target_object_id=target_object_id,
        payload=payload,
        result=result,
        status=status,
    )
    record_job_event(
        conn,
        job_id=job_id,
        event_type="correction_applied" if status == "applied" else "correction_hook_recorded",
        message=f"{operation} correction {status}",
        metadata={"correctionId": event["id"], "operation": operation, "objectId": object_id, "targetObjectId": target_object_id, "status": status},
    )
    record_audit_event(
        conn,
        user_id=user_id,
        project_id=job["project_id"],
        job_id=job_id,
        object_id=str(object_id) if object_id else None,
        event_type="track_correction",
        metadata={"correctionId": event["id"], "operation": operation, "status": status, "result": result},
    )
    review_manifest = write_review_state_manifest(
        conn,
        storage=storage,
        user_id=user_id,
        job_id=job_id,
    )
    manifest_asset = review_manifest["asset"]
    if manifest_asset["id"] not in seen_asset_ids:
        updated_assets.append(
            {
                "id": manifest_asset["id"],
                "kind": manifest_asset["kind"],
                "byteSize": manifest_asset["byte_size"],
            }
        )
    response = {
        "correction": public_correction_event(event),
        "updatedAssets": updated_assets,
        "reviewStateManifest": {
            "assetId": manifest_asset["id"],
            "kind": manifest_asset["kind"],
            "format": review_manifest["document"]["format"],
            "correctionEventCount": review_manifest["document"]["correctionEventCount"],
        },
        "status": status,
        "result": result,
        "partialRerun": partial_rerun,
    }
    return response


def normalize_track_edit_action(action: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(action, dict):
        raise ValueError("correction action must be a JSON object")
    raw_action_type = str(action.get("type") or action.get("operation") or "").strip().lower().replace("-", "_")
    action_type = _normalize_ui_action_type(action.get("type") or action.get("operation"))
    normalized = copy.deepcopy(action)
    normalized["type"] = action_type

    if action_type == "relabel_track":
        track_id = _action_track_id(normalized)
        label = str(normalized.get("label") or "").strip()
        if not track_id:
            raise ValueError("trackId is required for relabel_track")
        if not label:
            raise ValueError("label is required for relabel_track")
        normalized["trackId"] = track_id
        normalized["label"] = label
    elif action_type == "set_track_visibility":
        track_id = _action_track_id(normalized)
        if not track_id:
            raise ValueError("trackId is required for set_track_visibility")
        if "visible" not in normalized and "hidden" in normalized:
            normalized["visible"] = not _bool_value(normalized.get("hidden"), False)
        elif "visible" not in normalized and raw_action_type in {"hide", "hide_track"}:
            normalized["visible"] = False
        elif "visible" not in normalized and raw_action_type in {"show", "show_track"}:
            normalized["visible"] = True
        else:
            normalized["visible"] = _bool_value(normalized.get("visible"), True)
        normalized["trackId"] = track_id
    elif action_type == "set_export_inclusion":
        track_id = _action_track_id(normalized)
        if not track_id:
            raise ValueError("trackId is required for set_export_inclusion")
        included = normalized.get("included", normalized.get("exportIncluded", normalized.get("includeInExport")))
        normalized["included"] = _bool_value(included, raw_action_type != "exclude_track")
        normalized["trackId"] = track_id
    elif action_type == "delete_track":
        track_id = _action_track_id(normalized)
        if not track_id:
            raise ValueError("trackId is required for delete_track")
        normalized["trackId"] = track_id
    elif action_type == "merge_tracks":
        track_ids = [str(item).strip() for item in normalized.get("trackIds", normalized.get("track_ids", [])) if str(item).strip()]
        if not track_ids and (normalized.get("mergeObjectId") or normalized.get("sourceObjectId")):
            track_ids = [
                str(normalized.get("keepObjectId") or normalized.get("targetObjectId") or "").strip(),
                str(normalized.get("mergeObjectId") or normalized.get("sourceObjectId") or "").strip(),
            ]
            track_ids = [item for item in track_ids if item]
        if len(dict.fromkeys(track_ids)) < 2:
            raise ValueError("merge_tracks requires at least two trackIds")
        keep_track_id = str(normalized.get("keepTrackId") or normalized.get("keep_track_id") or normalized.get("keepObjectId") or track_ids[0]).strip()
        if keep_track_id not in track_ids:
            raise ValueError("keepTrackId must be one of trackIds")
        normalized["trackIds"] = list(dict.fromkeys(track_ids))
        normalized["keepTrackId"] = keep_track_id
    elif action_type == "split_track":
        track_id = _action_track_id(normalized)
        frame_range = _normalized_frame_range(normalized.get("frameRange", normalized.get("frame_range")))
        if not track_id:
            raise ValueError("trackId is required for split_track")
        if frame_range is None:
            raise ValueError("split_track requires frameRange: [start, end]")
        normalized["trackId"] = track_id
        normalized["frameRange"] = frame_range
        normalized["newTrackId"] = _safe_object_id(
            str(
                normalized.get("newTrackId")
                or normalized.get("new_track_id")
                or normalized.get("newObjectId")
                or normalized.get("new_object_id")
                or f"{track_id}_split_{frame_range[0]}_{frame_range[1]}"
            )
        )
        if normalized.get("label") is not None:
            normalized["label"] = str(normalized["label"]).strip()
    elif action_type == "add_object":
        object_id = _action_object_id(normalized)
        if not object_id:
            raise ValueError("objectId is required for add_object")
        normalized["objectId"] = _safe_object_id(object_id)
        normalized["label"] = str(normalized.get("label") or normalized["objectId"]).strip() or normalized["objectId"]
        frame_range = _normalized_frame_range(normalized.get("frameRange", normalized.get("frame_range")))
        if frame_range is not None:
            normalized["frameRange"] = frame_range
        prompts = normalized.get("prompts")
        normalized["prompts"] = prompts if isinstance(prompts, list) else []
    elif action_type == "repair_track":
        track_id = _action_track_id(normalized)
        if not track_id:
            raise ValueError("trackId is required for repair_track")
        normalized["trackId"] = track_id
        frame_range = _normalized_frame_range(normalized.get("frameRange", normalized.get("frame_range")))
        if frame_range is not None:
            normalized["frameRange"] = frame_range
        prompts = normalized.get("prompts")
        normalized["prompts"] = prompts if isinstance(prompts, list) else []

    return normalized


def repair_unavailable_diagnostics(action: dict[str, Any]) -> dict[str, Any]:
    provider = str(action.get("repairProvider") or action.get("repair_provider") or "local-repair-worker")
    track_id = _action_track_id(action)
    return {
        "status": "unavailable",
        "aiUsage": "none",
        "trackId": track_id,
        "frameRange": action.get("frameRange") or action.get("frame_range"),
        "partialRerun": {
            "available": False,
            "status": "not_enqueued",
            "reason": "Partial rerun repair is not available in this local UI slice; the correction request was saved for review.",
        },
        "diagnostics": [
            {
                "code": "repair_provider_unavailable",
                "provider": provider,
                "message": f"{provider} is not available for partial track repair in the local UI backend.",
                "suggestedFixes": [
                    "Use the deterministic prompt tools to record the requested repair.",
                    "Install and enable the requested repair provider before running model-assisted repair.",
                    "Export only accepted tracks until a repair worker is available.",
                ],
            }
        ],
    }


def record_track_edit_action(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    job_id: str,
    action: dict[str, Any],
) -> dict[str, Any]:
    normalized = normalize_track_edit_action(action)
    job = get_job(conn, user_id=user_id, job_id=job_id)
    action_type = normalized["type"]
    object_id: str | None
    target_object_id: str | None = None
    if action_type == "merge_tracks":
        keep_id = normalized["keepTrackId"]
        merge_ids = [item for item in normalized["trackIds"] if item != keep_id]
        object_id = merge_ids[0] if merge_ids else keep_id
        target_object_id = keep_id
    elif action_type == "add_object":
        object_id = normalized["objectId"]
    else:
        object_id = normalized.get("trackId") or normalized.get("objectId")

    result: dict[str, Any] = {
        "aiUsage": "none",
        "mockSafe": True,
        "operation": action_type,
    }
    status = "applied"
    if action_type == "repair_track":
        status = "unavailable"
        result["repairDiagnostics"] = repair_unavailable_diagnostics(normalized)
    elif action_type == "add_object":
        status = "hook_recorded"
        result["partialRerun"] = {
            "available": False,
            "status": "not_enqueued",
            "reason": "Manual add-object prompts were saved; automatic partial extraction is not run by this local UI endpoint.",
        }

    event = _record_event(
        conn,
        user_id=user_id,
        project_id=job["project_id"],
        job_id=job_id,
        operation=action_type,
        object_id=str(object_id) if object_id else None,
        target_object_id=target_object_id,
        payload=normalized,
        result=result,
        status=status,
    )
    record_job_event(
        conn,
        job_id=job_id,
        event_type="track_correction_saved",
        message=f"{action_type} correction saved",
        metadata={
            "correctionId": event["id"],
            "operation": action_type,
            "objectId": object_id,
            "targetObjectId": target_object_id,
            "status": status,
            "aiUsage": "none",
        },
    )
    record_audit_event(
        conn,
        user_id=user_id,
        project_id=job["project_id"],
        job_id=job_id,
        object_id=str(object_id) if object_id else None,
        event_type="track_correction_saved",
        metadata={"correctionId": event["id"], "operation": action_type, "status": status},
    )
    return public_correction_event(event)


def _history_entry(event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    result = event.get("result") if isinstance(event.get("result"), dict) else {}
    raw_type = str(payload.get("type") or event.get("operation") or "")
    try:
        action_type = _normalize_ui_action_type(raw_type)
    except ValueError:
        action_type = raw_type
    entry = {
        **copy.deepcopy(payload),
        "id": event.get("id"),
        "type": action_type,
        "operation": action_type,
        "status": event.get("status"),
        "createdAt": event.get("created_at"),
        "actor": "local_ui",
        "persistenceStatus": "saved",
        "aiUsage": result.get("aiUsage", "none"),
    }
    if raw_type == "hide":
        entry["visible"] = False
    elif raw_type == "show":
        entry["visible"] = True
    if action_type == "merge_tracks":
        keep_id = str(payload.get("keepTrackId") or payload.get("keepObjectId") or payload.get("targetObjectId") or event.get("target_object_id") or "")
        merge_id = str(payload.get("mergeObjectId") or payload.get("sourceObjectId") or event.get("object_id") or "")
        track_ids = [str(item) for item in payload.get("trackIds", [])] if isinstance(payload.get("trackIds"), list) else []
        if keep_id and keep_id not in track_ids:
            track_ids.insert(0, keep_id)
        if merge_id and merge_id not in track_ids:
            track_ids.append(merge_id)
        if keep_id:
            entry["keepTrackId"] = keep_id
        if track_ids:
            entry["trackIds"] = track_ids
    if action_type == "split_track" and payload.get("newObjectId") and not entry.get("newTrackId"):
        entry["newTrackId"] = payload["newObjectId"]
    if event.get("object_id") and not entry.get("trackId") and entry.get("type") != "add_object":
        entry["trackId"] = event["object_id"]
    if event.get("object_id") and not entry.get("objectId") and entry.get("type") == "add_object":
        entry["objectId"] = event["object_id"]
    if event.get("target_object_id"):
        entry["targetObjectId"] = event["target_object_id"]
    if "repairDiagnostics" in result:
        entry["repairDiagnostics"] = result["repairDiagnostics"]
    if "partialRerun" in result:
        entry["partialRerun"] = result["partialRerun"]
    return entry


def _ensure_track_edit(track_edits: dict[str, dict[str, Any]], track_id: str) -> dict[str, Any]:
    edit = track_edits.setdefault(track_id, {"trackId": track_id})
    edit["trackId"] = track_id
    return edit


def _apply_history_to_state(state: dict[str, Any], entry: dict[str, Any]) -> None:
    action_type = str(entry.get("type") or "")
    track_edits = state["trackEdits"]
    if action_type == "relabel_track":
        edit = _ensure_track_edit(track_edits, str(entry.get("trackId") or ""))
        edit["label"] = str(entry.get("label") or "")
    elif action_type == "set_track_visibility":
        edit = _ensure_track_edit(track_edits, str(entry.get("trackId") or ""))
        edit["visible"] = bool(entry.get("visible"))
    elif action_type == "set_export_inclusion":
        edit = _ensure_track_edit(track_edits, str(entry.get("trackId") or ""))
        edit["exportIncluded"] = bool(entry.get("included", entry.get("exportIncluded", True)))
    elif action_type == "delete_track":
        edit = _ensure_track_edit(track_edits, str(entry.get("trackId") or ""))
        edit.update({"deleted": True, "visible": False, "exportIncluded": False, "exportStatus": "deleted"})
    elif action_type == "merge_tracks":
        keep_id = str(entry.get("keepTrackId") or "")
        for track_id in entry.get("trackIds") or []:
            track_id = str(track_id)
            if not track_id or track_id == keep_id:
                continue
            edit = _ensure_track_edit(track_edits, track_id)
            edit.update({"visible": False, "exportIncluded": False, "mergedInto": keep_id, "exportStatus": "merged"})
    elif action_type == "repair_track":
        edit = _ensure_track_edit(track_edits, str(entry.get("trackId") or ""))
        edit["repairRequested"] = True


def build_track_correction_state(events: list[dict[str, Any]], *, job_id: str) -> dict[str, Any]:
    state: dict[str, Any] = {
        "format": UI_CORRECTION_STATE_FORMAT,
        "jobId": job_id,
        "trackEdits": {},
        "syntheticTracks": [],
        "history": [],
        "mergeSuggestions": [],
        "loaded": True,
        "persistenceStatus": "loaded",
        "persistenceMessage": "Correction history loaded from the local backend.",
        "aiUsage": "none",
    }
    for event in events:
        entry = _history_entry(event)
        state["history"].append(entry)
        _apply_history_to_state(state, entry)
    return state


def _compact_review_track(track: dict[str, Any]) -> dict[str, Any]:
    return {
        "objectId": _track_id(track),
        "label": track.get("label"),
        "source": track.get("source"),
        "providerName": track.get("providerName"),
        "confidence": track.get("confidence"),
        "frameCount": track.get("frameCount"),
        "visibleFrameCount": track.get("visibleFrameCount"),
        "visible": track.get("visible", True),
        "exportIncluded": _export_included(track),
        "exportStatus": track.get("exportStatus"),
        "deleted": bool(track.get("deleted")),
        "mergedInto": track.get("mergedInto") or track.get("mergedIntoObjectId"),
        "repairRequested": bool(track.get("repairRequested")),
        "warnings": list(track.get("warnings") if isinstance(track.get("warnings"), list) else []),
        "reviewSource": track.get("reviewSource"),
    }


def _review_export_summary(review: dict[str, Any] | None, tracks: list[dict[str, Any]]) -> dict[str, Any]:
    export = review.get("export") if isinstance(review, dict) and isinstance(review.get("export"), dict) else {}
    included = export.get("includedObjectIds") if isinstance(export.get("includedObjectIds"), list) else None
    excluded = export.get("excludedObjectIds") if isinstance(export.get("excludedObjectIds"), list) else None
    if included is None:
        included = [_track_id(track) for track in tracks if _export_included(track)]
    if excluded is None:
        excluded = [_track_id(track) for track in tracks if not _export_included(track)]
    return {
        "source": export.get("source") or ("edited_project_state" if tracks else "review_artifacts"),
        "includedObjectIds": [item for item in included if item],
        "excludedObjectIds": [item for item in excluded if item],
        "includedCount": len([item for item in included if item]),
        "excludedCount": len([item for item in excluded if item]),
    }


def build_review_state_manifest(
    corrections: list[dict[str, Any]],
    *,
    job_id: str,
    review: dict[str, Any] | None = None,
) -> dict[str, Any]:
    correction_state = build_track_correction_state(corrections, job_id=job_id)
    review_tracks = [
        _compact_review_track(track)
        for track in (review.get("tracks") if isinstance(review, dict) and isinstance(review.get("tracks"), list) else [])
        if isinstance(track, dict)
    ]
    manifest: dict[str, Any] = {
        "format": UI_REVIEW_STATE_MANIFEST_FORMAT,
        "jobId": job_id,
        "generatedAt": utc_now(),
        "aiUsage": "none",
        "correctionEventCount": len(corrections),
        "correctionState": correction_state,
    }
    if isinstance(review, dict):
        manifest["review"] = {
            "format": review.get("format"),
            "trackCount": len(review_tracks),
            "tracks": review_tracks,
            "export": _review_export_summary(review, review_tracks),
            "rasterFallback": bool(review.get("rasterFallback")),
            "rasterFallbackReason": review.get("rasterFallbackReason"),
            "vectorUnavailableReason": review.get("vectorUnavailableReason"),
            "fallbackDiagnostics": copy.deepcopy(review.get("fallbackDiagnostics") if isinstance(review.get("fallbackDiagnostics"), list) else []),
        }
    return _sanitize_public_value(manifest)


def write_review_state_manifest(
    conn: sqlite3.Connection,
    *,
    storage: StorageProvider,
    user_id: str,
    job_id: str,
    review: dict[str, Any] | None = None,
) -> dict[str, Any]:
    job = get_job(conn, user_id=user_id, job_id=job_id)
    corrections = list_track_corrections(conn, user_id=user_id, job_id=job_id)
    document = build_review_state_manifest(corrections, job_id=job_id, review=review)
    assets = list_assets_for_job(conn, project_id=job["project_id"], source_job_id=job_id)
    existing = _latest_asset_by_kind(assets, UI_REVIEW_STATE_MANIFEST_KIND)
    if existing:
        asset = _write_json_asset(conn, storage=storage, asset=existing, document=document)
    else:
        asset = register_generated_asset(
            conn,
            storage=storage,
            project_id=job["project_id"],
            source_job_id=job_id,
            kind=UI_REVIEW_STATE_MANIFEST_KIND,
            data=_json_bytes(document),
            rel_path="review/review_state_manifest.json",
            content_type="application/json",
            metadata={"aiUsage": "none", "format": UI_REVIEW_STATE_MANIFEST_FORMAT},
        )
    return {"asset": asset, "document": document}


def _track_id(track: dict[str, Any]) -> str:
    return str(track.get("objectId") or track.get("object_id") or track.get("id") or "")


def _export_included(track: dict[str, Any]) -> bool:
    if track.get("deleted") or track.get("exportIncluded") is False:
        return False
    return not re.search(r"deleted|excluded|rejected|failed|fallback_raster|review_pending", str(track.get("exportStatus") or "accepted"))


def _append_track_warning(track: dict[str, Any], warning: str) -> None:
    warnings = track.setdefault("warnings", [])
    if not isinstance(warnings, list):
        warnings = []
        track["warnings"] = warnings
    if warning not in warnings:
        warnings.append(warning)


def _apply_review_track_edit(track: dict[str, Any], edit: dict[str, Any]) -> None:
    if edit.get("label"):
        track["label"] = edit["label"]
    if "visible" in edit:
        track["visible"] = bool(edit["visible"])
    else:
        track.setdefault("visible", True)
    if "exportIncluded" in edit:
        track["exportIncluded"] = bool(edit["exportIncluded"])
    else:
        track["exportIncluded"] = _export_included(track)
    if edit.get("mergedInto"):
        track["mergedInto"] = edit["mergedInto"]
        _append_track_warning(track, f"merged_into_{edit['mergedInto']}")
    if edit.get("repairRequested"):
        track["repairRequested"] = True
        _append_track_warning(track, "repair_requested")
    if edit.get("deleted"):
        track["deleted"] = True
        track["visible"] = False
        track["exportIncluded"] = False
        track["exportStatus"] = "deleted"
        _append_track_warning(track, "deleted_by_user")
    elif track.get("exportIncluded") is False:
        track["exportStatus"] = edit.get("exportStatus") or "excluded"
        _append_track_warning(track, "excluded_from_export")
    if track.get("visible") is False:
        _append_track_warning(track, "hidden_by_user")


def _filter_frames(track: dict[str, Any], frame_range: list[int] | None) -> list[dict[str, Any]]:
    frames = [copy.deepcopy(frame) for frame in track.get("frames", []) if isinstance(frame, dict)]
    if not frame_range:
        return frames
    start, end = frame_range
    selected = []
    for frame in frames:
        frame_number = int(frame.get("frame") if frame.get("frame") is not None else frame.get("outIndex", 0))
        if start <= frame_number <= end:
            selected.append(frame)
    return selected


def _default_prompt_box(action: dict[str, Any], index: int) -> list[int]:
    prompt = next((item for item in action.get("prompts", []) if isinstance(item, dict)), {})
    data = prompt.get("data") if isinstance(prompt.get("data"), dict) else {}
    if prompt.get("kind") == "box":
        return [int(data.get("x", 10)), int(data.get("y", 10)), max(1, int(data.get("w", 16))), max(1, int(data.get("h", 16)))]
    x = int(data.get("x", 12 + index * 8))
    y = int(data.get("y", 12 + index * 6))
    return [max(0, x - 8), max(0, y - 8), 16, 16]


def _synthetic_split_track(source: dict[str, Any], action: dict[str, Any], index: int) -> dict[str, Any]:
    frame_range = action.get("frameRange") if isinstance(action.get("frameRange"), list) else None
    frames = _filter_frames(source, frame_range)
    if not frames:
        frames = _filter_frames(source, None)[:1]
    object_id = _safe_object_id(str(action.get("newTrackId") or f"{_track_id(source)}_split"))
    visible_count = _frames_visible_count(frames)
    return {
        **copy.deepcopy(source),
        "id": object_id,
        "objectId": object_id,
        "label": action.get("label") or f"{source.get('label') or _track_id(source)} split",
        "source": f"{source.get('source') or 'track'}/split",
        "frames": frames,
        "frameCount": len(frames),
        "visibleFrameCount": visible_count,
        "frameStart": frame_range[0] if frame_range else None,
        "frameEnd": frame_range[1] if frame_range else None,
        "exportStatus": "accepted",
        "exportIncluded": True,
        "visible": True,
        "reviewSource": "correction-history",
        "color": source.get("color") or None,
        "zIndex": int(source.get("zIndex") or index),
    }


def _synthetic_added_track(action: dict[str, Any], index: int) -> dict[str, Any]:
    frame_range = action.get("frameRange") if isinstance(action.get("frameRange"), list) else [0, 0]
    start, end = frame_range if len(frame_range) == 2 else [0, 0]
    box = _default_prompt_box(action, index)
    frames = [
        {
            "frame": frame,
            "outIndex": frame,
            "sourceFrameIndex": frame,
            "visible": True,
            "area": float(box[2] * box[3]),
            "bbox": box,
            "centroid": [box[0] + box[2] / 2, box[1] + box[3] / 2],
            "contourPoints": 4,
        }
        for frame in range(int(start), int(end) + 1)
    ]
    object_id = _safe_object_id(str(action.get("objectId") or f"added_object_{index}"))
    return {
        "id": object_id,
        "objectId": object_id,
        "label": action.get("label") or object_id,
        "source": "correction/add_object",
        "providerName": "manual_correction",
        "confidence": None,
        "zIndex": 1000 + index,
        "frameCount": len(frames),
        "visibleFrameCount": len(frames),
        "frameStart": start,
        "frameEnd": end,
        "exportStatus": "accepted",
        "exportIncluded": True,
        "visible": True,
        "warnings": ["manual_object_pending_extraction"],
        "frames": frames,
        "reviewSource": "correction-history",
    }


def apply_track_correction_state(review: dict[str, Any], correction_state: dict[str, Any]) -> dict[str, Any]:
    edited = copy.deepcopy(review)
    tracks = [copy.deepcopy(track) for track in edited.get("tracks", []) if isinstance(track, dict)]
    track_edits = correction_state.get("trackEdits") if isinstance(correction_state.get("trackEdits"), dict) else {}
    history = correction_state.get("history") if isinstance(correction_state.get("history"), list) else []

    for index, track in enumerate(tracks):
        object_id = _track_id(track) or f"object_{index}"
        track["objectId"] = object_id
        edit = track_edits.get(object_id) or track_edits.get(str(track.get("id") or "")) or {}
        _apply_review_track_edit(track, edit)

    existing_ids = {_track_id(track) for track in tracks}
    for entry in history:
        action_type = entry.get("type")
        if action_type == "split_track":
            source_id = str(entry.get("trackId") or "")
            source = next((track for track in tracks if _track_id(track) == source_id), None)
            if source is None:
                continue
            split = _synthetic_split_track(source, entry, len(tracks))
            if split["objectId"] not in existing_ids:
                tracks.append(split)
                existing_ids.add(split["objectId"])
        elif action_type == "add_object":
            added = _synthetic_added_track(entry, len(tracks))
            if added["objectId"] not in existing_ids:
                tracks.append(added)
                existing_ids.add(added["objectId"])

    for track in tracks:
        object_id = _track_id(track)
        edit = track_edits.get(object_id) or track_edits.get(str(track.get("id") or "")) or {}
        _apply_review_track_edit(track, edit)

    included = [_track_id(track) for track in tracks if _export_included(track)]
    excluded = [_track_id(track) for track in tracks if not _export_included(track)]
    edited["tracks"] = tracks
    edited["correctionHistory"] = copy.deepcopy(history)
    edited["correctionState"] = copy.deepcopy(correction_state)
    edited["export"] = {
        "source": "edited_project_state" if history else "review_artifacts",
        "includedObjectIds": [item for item in included if item],
        "excludedObjectIds": [item for item in excluded if item],
        "includedCount": len([item for item in included if item]),
        "excludedCount": len([item for item in excluded if item]),
    }
    return edited
