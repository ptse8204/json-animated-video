from __future__ import annotations

import json
import mimetypes
import shutil
import sqlite3
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any

from motionjson.providers.base import StorageProvider

from .assets import _insert_asset, get_asset, update_asset_metadata


BROWSER_PREVIEW_FORMAT = "motionjson.browser_preview.v0.1"
BROWSER_PREVIEW_KIND = "browser_preview"
BROWSER_POSTER_KIND = "browser_poster"
SAFE_MP4_CODECS = {"h264", "av1"}
SAFE_WEBM_CODECS = {"vp8", "vp9", "av1"}
SAFE_OGG_CODECS = {"theora"}


def _sanitize_text(value: str) -> str:
    return value.replace("\r", " ").replace("\n", " ").strip()


def _metadata_json(asset: dict[str, Any]) -> dict[str, Any]:
    value = asset.get("metadata_json", asset.get("metadata"))
    if isinstance(value, dict):
        return dict(value)
    try:
        parsed = json.loads(value or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _safe_name(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {".", "_", "-"} else "_" for ch in name).strip("._-") or "asset"


def _parse_rational(value: Any) -> float:
    text = str(value or "").strip()
    if not text or text in {"0/0", "N/A"}:
        return 0.0
    if "/" in text:
        numerator, denominator = text.split("/", 1)
        try:
            denominator_value = float(denominator)
            if denominator_value == 0:
                return 0.0
            return float(numerator) / denominator_value
        except (TypeError, ValueError, ZeroDivisionError):
            return 0.0
    try:
        return float(text)
    except (TypeError, ValueError):
        return 0.0


def _parse_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _register_preview_asset(
    conn: sqlite3.Connection,
    *,
    storage: StorageProvider,
    project_id: str,
    kind: str,
    filename: str,
    data: bytes,
    content_type: str,
    metadata: dict[str, Any],
) -> dict:
    key = f"projects/{project_id}/browser_preview/{uuid.uuid4().hex}_{_safe_name(filename)}"
    uri = storage.save_bytes(key, data, content_type=content_type)
    return _insert_asset(
        conn,
        project_id=project_id,
        kind=kind,
        storage_key=key,
        uri=uri,
        content_type=content_type,
        byte_size=len(data),
        source_job_id=None,
        metadata=metadata,
    )


def ffprobe_status() -> dict[str, Any]:
    path = shutil.which("ffprobe")
    return {
        "available": bool(path),
        "path": path or "",
    }


def ffmpeg_status() -> dict[str, Any]:
    path = shutil.which("ffmpeg")
    return {
        "available": bool(path),
        "path": path or "",
    }


def probe_video_file(path: str | Path) -> dict[str, Any]:
    video_path = Path(path)
    probe = ffprobe_status()
    base: dict[str, Any] = {
        "format": BROWSER_PREVIEW_FORMAT,
        "status": "blocked",
        "path": str(video_path),
        "codec": "",
        "codecTag": "",
        "contentType": mimetypes.guess_type(video_path.name)[0] or "application/octet-stream",
        "container": "",
        "width": 0,
        "height": 0,
        "duration": 0.0,
        "fps": 0.0,
        "sourceFps": 0.0,
        "frameCount": 0,
        "bitrate": 0,
        "byteSize": video_path.stat().st_size if video_path.exists() else 0,
        "browserSafe": False,
        "reason": "",
    }
    if not probe["available"]:
        return {**base, "status": "blocked", "reason": "ffprobe executable was not found"}
    result = subprocess.run(
        [
            probe["path"],
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return {**base, "status": "failed", "reason": _sanitize_text(result.stderr or result.stdout or "ffprobe failed")}
    try:
        parsed = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return {**base, "status": "failed", "reason": "ffprobe returned invalid JSON"}
    streams = parsed.get("streams") if isinstance(parsed.get("streams"), list) else []
    video_stream = next((item for item in streams if isinstance(item, dict) and item.get("codec_type") == "video"), {})
    format_info = parsed.get("format") if isinstance(parsed.get("format"), dict) else {}
    codec = str(video_stream.get("codec_name") or "").lower()
    content_type = base["contentType"]
    if content_type == "application/octet-stream":
        format_name = str(format_info.get("format_name") or "")
        if "webm" in format_name:
            content_type = "video/webm"
        elif "ogg" in format_name:
            content_type = "video/ogg"
        else:
            content_type = "video/mp4"
    fps = _parse_rational(video_stream.get("avg_frame_rate")) or _parse_rational(video_stream.get("r_frame_rate"))
    duration = float(format_info.get("duration") or video_stream.get("duration") or 0.0)
    frame_count = _parse_int(video_stream.get("nb_frames"))
    if frame_count <= 0 and duration > 0 and fps > 0:
        frame_count = max(1, round(duration * fps))
    bitrate = _parse_int(format_info.get("bit_rate") or video_stream.get("bit_rate"))
    browser_safe = False
    if content_type == "video/mp4":
        browser_safe = codec in SAFE_MP4_CODECS
    elif content_type == "video/webm":
        browser_safe = codec in SAFE_WEBM_CODECS
    elif content_type == "video/ogg":
        browser_safe = codec in SAFE_OGG_CODECS
    return {
        **base,
        "status": "ready",
        "codec": codec,
        "codecTag": str(video_stream.get("codec_tag_string") or ""),
        "contentType": content_type,
        "container": str(format_info.get("format_name") or ""),
        "width": int(video_stream.get("width") or 0),
        "height": int(video_stream.get("height") or 0),
        "duration": duration,
        "fps": fps,
        "sourceFps": fps,
        "frameCount": frame_count,
        "bitrate": bitrate,
        "byteSize": video_path.stat().st_size if video_path.exists() else 0,
        "browserSafe": browser_safe,
        "reason": "" if browser_safe else f"{codec or 'unknown codec'} is not a browser-safe preview codec",
    }


def _preview_quality_fields(probe: dict[str, Any], *, source_probe: dict[str, Any] | None = None) -> dict[str, Any]:
    source = source_probe or probe
    return {
        "fps": probe.get("fps") or probe.get("sourceFps") or 0.0,
        "sourceFps": source.get("sourceFps") or source.get("fps") or probe.get("sourceFps") or probe.get("fps") or 0.0,
        "frameCount": source.get("frameCount") or probe.get("frameCount") or 0,
        "bitrate": source.get("bitrate") or probe.get("bitrate") or 0,
        "byteSize": source.get("byteSize") or probe.get("byteSize") or 0,
        "qualitySource": "ffprobe",
    }


def _generate_poster(video_path: Path, poster_path: Path) -> tuple[bool, str]:
    ffmpeg = ffmpeg_status()
    if ffmpeg["available"]:
        result = subprocess.run(
            [
                ffmpeg["path"],
                "-y",
                "-i",
                str(video_path),
                "-frames:v",
                "1",
                str(poster_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and poster_path.exists() and poster_path.stat().st_size:
            return True, ""
        return False, _sanitize_text(result.stderr or result.stdout or "ffmpeg poster generation failed")
    try:
        import cv2  # type: ignore
    except ImportError:
        return False, "Neither ffmpeg nor OpenCV is available for poster generation"
    capture = cv2.VideoCapture(str(video_path))
    try:
        ok, frame = capture.read()
        if not ok or frame is None:
            return False, "OpenCV could not read the first video frame"
        success, encoded = cv2.imencode(".jpg", frame)
        if not success:
            return False, "OpenCV could not encode the poster image"
        poster_path.write_bytes(encoded.tobytes())
        return True, ""
    finally:
        capture.release()


def _transcode_preview(source_path: Path, output_path: Path) -> tuple[bool, str]:
    ffmpeg = ffmpeg_status()
    if not ffmpeg["available"]:
        return False, "ffmpeg executable was not found"
    result = subprocess.run(
        [
            ffmpeg["path"],
            "-y",
            "-i",
            str(source_path),
            "-map",
            "0:v:0",
            "-an",
            "-vf",
            "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return False, _sanitize_text(result.stderr or result.stdout or "ffmpeg preview transcode failed")
    if not output_path.exists() or output_path.stat().st_size <= 0:
        return False, "ffmpeg completed but produced no preview output bytes"
    return True, ""


def prepare_browser_preview(
    conn: sqlite3.Connection,
    *,
    storage: StorageProvider,
    user_id: str,
    source_asset_id: str,
    force: bool = False,
) -> dict[str, Any]:
    source_asset = get_asset(conn, user_id=user_id, asset_id=source_asset_id)
    if source_asset["kind"] != "source_video":
        raise ValueError("browser preview can only be prepared for source_video assets")
    source_metadata = _metadata_json(source_asset)
    existing = source_metadata.get("browser_preview")
    if isinstance(existing, dict) and existing.get("status") == "ready" and not force:
        return existing

    filename = str(source_metadata.get("filename") or source_asset_id)
    suffix = Path(filename).suffix or ".mp4"
    project_id = str(source_asset["project_id"])
    with tempfile.TemporaryDirectory(prefix="motionjson_browser_preview_") as tmp:
        tmp_dir = Path(tmp)
        source_path = tmp_dir / f"source{suffix}"
        source_path.write_bytes(storage.load_bytes(source_asset["storage_key"]))
        probe = probe_video_file(source_path)
        poster_path = tmp_dir / "poster.jpg"
        poster_ok, poster_reason = _generate_poster(source_path, poster_path)
        poster_asset = None
        if poster_ok:
            poster_asset = _register_preview_asset(
                conn,
                storage=storage,
                project_id=project_id,
                kind=BROWSER_POSTER_KIND,
                filename=f"{Path(filename).stem}_poster.jpg",
                data=poster_path.read_bytes(),
                content_type="image/jpeg",
                metadata={
                    "sourceVideoAssetId": source_asset_id,
                    "previewRole": "poster",
                },
            )

        if probe["status"] != "ready":
            payload = {
                "status": "failed",
                "kind": "source",
                "contentAssetId": source_asset_id,
                "posterAssetId": poster_asset["id"] if poster_asset else "",
                "width": 0,
                "height": 0,
                "duration": 0.0,
                "codec": "",
                **_preview_quality_fields(probe),
                "reason": probe["reason"] or "video probe failed",
                "errorMessage": probe["reason"] or "video probe failed",
                "contentType": source_asset.get("content_type") or probe["contentType"],
            }
            update_asset_metadata(conn, asset_id=source_asset_id, metadata={"browser_preview": payload})
            return payload

        if probe["browserSafe"]:
            payload = {
                "status": "ready",
                "kind": "source",
                "contentAssetId": source_asset_id,
                "posterAssetId": poster_asset["id"] if poster_asset else "",
                "width": probe["width"],
                "height": probe["height"],
                "duration": probe["duration"],
                "codec": probe["codec"],
                **_preview_quality_fields(probe),
                "reason": "" if poster_ok else poster_reason,
                "errorMessage": "" if poster_ok else poster_reason,
                "contentType": probe["contentType"],
            }
            update_asset_metadata(conn, asset_id=source_asset_id, metadata={"browser_preview": payload})
            return payload

        preview_path = tmp_dir / f"{Path(filename).stem}_browser_preview.mp4"
        transcoded, transcode_reason = _transcode_preview(source_path, preview_path)
        if not transcoded:
            payload = {
                "status": "failed",
                "kind": "transcoded",
                "contentAssetId": "",
                "posterAssetId": poster_asset["id"] if poster_asset else "",
                "width": probe["width"],
                "height": probe["height"],
                "duration": probe["duration"],
                "codec": probe["codec"],
                **_preview_quality_fields(probe),
                "reason": transcode_reason,
                "errorMessage": transcode_reason,
                "contentType": "video/mp4",
            }
            update_asset_metadata(conn, asset_id=source_asset_id, metadata={"browser_preview": payload})
            return payload

        preview_probe = probe_video_file(preview_path)
        preview_asset = _register_preview_asset(
            conn,
            storage=storage,
            project_id=project_id,
            kind=BROWSER_PREVIEW_KIND,
            filename=preview_path.name,
            data=preview_path.read_bytes(),
            content_type="video/mp4",
            metadata={
                "sourceVideoAssetId": source_asset_id,
                "previewRole": "browser_preview",
                "codec": preview_probe["codec"] or "h264",
                "width": preview_probe["width"],
                "height": preview_probe["height"],
                "duration": preview_probe["duration"],
                **_preview_quality_fields(preview_probe, source_probe=probe),
            },
        )
        payload = {
            "status": "ready",
            "kind": "transcoded",
            "contentAssetId": preview_asset["id"],
            "posterAssetId": poster_asset["id"] if poster_asset else "",
            "width": preview_probe["width"] or probe["width"],
            "height": preview_probe["height"] or probe["height"],
            "duration": preview_probe["duration"] or probe["duration"],
            "codec": preview_probe["codec"] or "h264",
            **_preview_quality_fields(preview_probe, source_probe=probe),
            "reason": "",
            "errorMessage": "" if poster_ok else poster_reason,
            "contentType": "video/mp4",
        }
        update_asset_metadata(conn, asset_id=source_asset_id, metadata={"browser_preview": payload})
        return payload
