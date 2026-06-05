from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from motionjson.providers.discovery import SAM3AutoMasksDiscoveryProvider
from motionjson.providers.sam3 import LocalSAM3DiscoveryBackend
from motionjson.tracks import RunContext, VideoSource
from motionjson.video import Frame, VideoInfo


LOCAL_PATH_REDACTION = "[LOCAL_PATH_REDACTED]"


class _EventBridge:
    def __init__(self, *, model_path: str) -> None:
        self.model_path = model_path

    def emit(self, stage: str, status: str, message: str, *, progress: Mapping[str, Any] | None = None, metadata: Mapping[str, Any] | None = None) -> None:
        _emit(
            {
                "type": "event",
                "stage": stage,
                "status": status,
                "message": _redact_runtime_text(message, self.model_path),
                "progress": dict(progress or {}),
                "metadata": _redact_runtime_payload(dict(metadata or {}), self.model_path),
            }
        )

    def check_cancel(self, _stage: str) -> None:
        return None


def main() -> int:
    try:
        request = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        _emit({"type": "error", "errorType": type(exc).__name__, "message": "Invalid SAM3 discovery worker request."})
        return 2
    model_path = str(request.get("modelId") or request.get("model") or "")
    try:
        video = _load_video(request)
        config = request.get("config") if isinstance(request.get("config"), Mapping) else {}
        out_dir = Path(str(request.get("outDir") or "")).expanduser()
        bridge = _EventBridge(model_path=model_path)
        ctx = RunContext(out_dir=out_dir, job_context=bridge)
        backend = LocalSAM3DiscoveryBackend(model_path=model_path, device=str(request.get("device") or "cuda"))
        provider = SAM3AutoMasksDiscoveryProvider(backend=backend)
        candidates = provider.propose(video, config, ctx)
        runtime_proof = backend.runtime_proof()
        if runtime_proof:
            bridge.emit(
                "provider_preflight",
                "succeeded" if runtime_proof.get("runtimeProofStatus") == "verified" else "failed",
                "runtime proof recorded",
                progress={"overallRatio": 0.319},
                metadata={
                    "provider": "sam3-local",
                    "discoveryMode": "sam3_auto_masks",
                    "eventType": "runtime_proof_recorded",
                    "runtimeProof": runtime_proof,
                    "runtimeContract": runtime_proof,
                },
            )
        result_path = Path(str(request.get("resultPath") or "")).expanduser()
        result_path.write_text(
            json.dumps({"candidates": [candidate.to_dict() for candidate in candidates]}, sort_keys=True),
            encoding="utf-8",
        )
    except Exception as exc:  # pragma: no cover - parent integration tests cover subprocess failure behavior.
        _emit(
            {
                "type": "error",
                "errorType": type(exc).__name__,
                "message": _redact_runtime_text(str(exc) or type(exc).__name__, model_path),
            }
        )
        return 2
    _emit({"type": "result", "status": "ok"})
    return 0


def _load_video(request: Mapping[str, Any]) -> VideoSource:
    frames_path = Path(str(request.get("framesPath") or "")).expanduser()
    with np.load(frames_path) as loaded:
        frames_array = np.asarray(loaded["frames"], dtype=np.uint8)
        frame_indexes = np.asarray(loaded["frame_indexes"], dtype=np.int64) if "frame_indexes" in loaded else np.arange(frames_array.shape[0])
        frame_out_indexes = np.asarray(loaded["frame_out_indexes"], dtype=np.int64) if "frame_out_indexes" in loaded else np.arange(frames_array.shape[0])
        frame_times = np.asarray(loaded["frame_times"], dtype=np.float64) if "frame_times" in loaded else np.zeros(frames_array.shape[0], dtype=np.float64)
    frame_count = int(frames_array.shape[0])
    frames = [
        Frame(
            index=int(frame_indexes[index]) if index < len(frame_indexes) else index,
            out_index=int(frame_out_indexes[index]) if index < len(frame_out_indexes) else index,
            time_sec=float(frame_times[index]) if index < len(frame_times) else 0.0,
            rgb=frames_array[index],
        )
        for index in range(frame_count)
    ]
    video_payload = request.get("video") if isinstance(request.get("video"), Mapping) else {}
    info = VideoInfo(
        width=int(video_payload.get("width") or (frames_array.shape[2] if frames_array.ndim >= 4 else 0)),
        height=int(video_payload.get("height") or (frames_array.shape[1] if frames_array.ndim >= 4 else 0)),
        source_fps=float(video_payload.get("sourceFps") or 0.0),
        sample_fps=float(video_payload.get("sampleFps") or 0.0),
        total_source_frames=int(video_payload.get("totalSourceFrames") or len(frames)),
    )
    return VideoSource(path=Path(str(video_payload.get("path") or "")), info=info, frames=frames)


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, sort_keys=True), flush=True)


def _redact_runtime_payload(value: Any, model_path: str) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _redact_runtime_payload(item, model_path) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_runtime_payload(item, model_path) for item in value]
    if isinstance(value, str):
        return _redact_runtime_text(value, model_path)
    return value


def _redact_runtime_text(value: Any, model_path: str) -> str:
    text = str(value or "")
    raw = str(model_path or "").strip()
    if not _looks_like_local_path(raw):
        return text
    replacements = {raw}
    try:
        replacements.add(str(Path(raw.replace("file://", "", 1)).expanduser()))
    except (OSError, RuntimeError):
        pass
    for candidate in sorted(replacements, key=len, reverse=True):
        if candidate:
            text = text.replace(candidate, LOCAL_PATH_REDACTION)
    return text


def _looks_like_local_path(value: str) -> bool:
    return bool(value.startswith(("/", "~", "./", "../", "file://")) or "\\" in value)


if __name__ == "__main__":
    raise SystemExit(main())
