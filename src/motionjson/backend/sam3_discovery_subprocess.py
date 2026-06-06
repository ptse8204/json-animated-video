from __future__ import annotations

import json
import os
import queue
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from motionjson.providers.base import ProviderExecutionError
from motionjson.tracks import Box, ObjectCandidate, RunContext, VideoSource


SAM3_DISCOVERY_WORKER_MODULE = "motionjson.backend.sam3_discovery_worker"
DEFAULT_SAM3_DISCOVERY_TIMEOUT_SECONDS = 1800.0
SAM3_DISCOVERY_WAIT_REPORT_SECONDS = 30.0
DEFAULT_SAM3_STACK_PROBE_SECONDS = 90.0
LOCAL_PATH_REDACTION = "[LOCAL_PATH_REDACTED]"


@dataclass
class SubprocessSAM3AutoMasksDiscoveryProvider:
    """Run real SAM3 scene-sweep proposal work in a killable subprocess."""

    model_path: str
    device: str = "cuda"
    timeout_seconds: float = DEFAULT_SAM3_DISCOVERY_TIMEOUT_SECONDS
    name: str = "sam3_auto_masks"
    provider_name: str = "sam3-local"
    environ: Mapping[str, str] | None = None
    python_executable: str | None = None
    worker_module: str = SAM3_DISCOVERY_WORKER_MODULE

    def propose(self, video: VideoSource, config: Mapping[str, Any], ctx: RunContext) -> Sequence[ObjectCandidate]:
        return run_sam3_auto_masks_proposal_subprocess(
            video,
            config,
            ctx,
            model_path=self.model_path,
            device=self.device,
            timeout_seconds=self.timeout_seconds,
            environ=self.environ,
            python_executable=self.python_executable,
            worker_module=self.worker_module,
        )


def run_sam3_auto_masks_proposal_subprocess(
    video: VideoSource,
    config: Mapping[str, Any],
    ctx: RunContext,
    *,
    model_path: str,
    device: str,
    timeout_seconds: float = DEFAULT_SAM3_DISCOVERY_TIMEOUT_SECONDS,
    environ: Mapping[str, str] | None = None,
    python_executable: str | None = None,
    worker_module: str = SAM3_DISCOVERY_WORKER_MODULE,
) -> list[ObjectCandidate]:
    timeout = _bounded_timeout(timeout_seconds)
    with tempfile.TemporaryDirectory(prefix="motionjson-sam3-discovery-") as temp_name:
        temp_dir = Path(temp_name)
        frames_path = temp_dir / "frames.npz"
        result_path = temp_dir / "candidates.json"
        stack_path = temp_dir / "sam3_child_stack.txt"
        _write_frame_store(video, frames_path)
        request = {
            "modelId": str(model_path or ""),
            "device": str(device or "cuda"),
            "config": dict(config),
            "framesPath": str(frames_path),
            "resultPath": str(result_path),
            "stackDiagnosticsPath": str(stack_path),
            "outDir": str(ctx.out_dir) if ctx.out_dir is not None else "",
            "video": _video_payload(video),
        }
        _emit_ctx(
            ctx,
            "candidate_discovery",
            "running",
            f"Starting isolated SAM3 scene sweep process with a {int(timeout)}s timeout",
            progress={"overallRatio": 0.30},
            metadata={"provider": "sam3-local", "discoveryMode": "sam3_auto_masks", "eventType": "sam3_discovery_subprocess_started"},
        )
        _run_worker_process(
            request,
            ctx,
            model_path=model_path,
            timeout_seconds=timeout,
            environ=environ,
            python_executable=python_executable,
            worker_module=worker_module,
        )
        return _read_candidate_result(result_path)


def _run_worker_process(
    request: Mapping[str, Any],
    ctx: RunContext,
    *,
    model_path: str,
    timeout_seconds: float,
    environ: Mapping[str, str] | None,
    python_executable: str | None,
    worker_module: str,
) -> None:
    command = [python_executable or sys.executable, "-m", worker_module]
    child_env = dict(os.environ)
    if environ:
        child_env.update({str(key): str(value) for key, value in environ.items()})
    child_env["PYTHONUNBUFFERED"] = "1"
    process = subprocess.Popen(  # noqa: S603 - command is the current Python interpreter and an internal module.
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env=child_env,
    )
    assert process.stdin is not None
    process.stdin.write(json.dumps(request, sort_keys=True))
    process.stdin.write("\n")
    process.stdin.close()

    output_queue: queue.Queue[tuple[str, str | None]] = queue.Queue()
    readers = [
        _start_reader_thread("stdout", process.stdout, output_queue),
        _start_reader_thread("stderr", process.stderr, output_queue),
    ]
    deadline = time.monotonic() + timeout_seconds
    child_error = ""
    stderr_tail: list[str] = []
    stdout_tail: list[str] = []
    streams_closed: set[str] = set()
    started_at = time.monotonic()
    last_child_event: dict[str, Any] = {}
    last_child_event_at = started_at
    last_stdout_line_at = started_at
    last_stderr_line_at = started_at
    last_wait_report_at = started_at
    last_stack_probe_at = 0.0
    current_operations: dict[str, dict[str, Any]] = {}
    stack_path = Path(str(request.get("stackDiagnosticsPath") or "")) if request.get("stackDiagnosticsPath") else None
    stack_probe_seconds = _stack_probe_seconds()

    while True:
        now = time.monotonic()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            inflight = _inflight_detail(last_child_event)
            suffix = f" Last in-flight operation: {inflight}." if inflight else ""
            current_operation = _current_operation(last_child_event, current_operations, now=now)
            message = (
                f"SAM3 scene sweep extraction timed out after {int(timeout_seconds)}s while loading or running the model. "
                "The isolated process was terminated so the run can fail cleanly instead of staying active forever."
                f"{suffix}"
            )
            timeout_metadata = {
                "provider": "sam3-local",
                "discoveryMode": "sam3_auto_masks",
                "eventType": "sam3_discovery_timeout",
                "subprocessElapsedSeconds": round(time.monotonic() - started_at, 3),
                "secondsSinceChildEvent": round(time.monotonic() - last_child_event_at, 3),
                "secondsSinceStdoutLine": round(time.monotonic() - last_stdout_line_at, 3),
                "secondsSinceStderrLine": round(time.monotonic() - last_stderr_line_at, 3),
                "subprocessAlive": process.poll() is None,
                "returnCode": process.poll(),
                "pid": process.pid,
                "stdoutReaderAlive": readers[0].is_alive(),
                "stderrReaderAlive": readers[1].is_alive(),
                "currentOperation": current_operation,
                "gpuProbe": _gpu_probe(process.pid),
                **_stack_probe_metadata(stack_path, model_path=model_path),
            }
            if last_child_event:
                timeout_metadata["lastChildEvent"] = dict(last_child_event)
            _emit_ctx(
                ctx,
                "candidate_discovery",
                "failed",
                message,
                progress={"overallRatio": 0.30},
                metadata=timeout_metadata,
            )
            _terminate_process(process)
            raise ProviderExecutionError(_redact_runtime_text(message, model_path))

        try:
            stream_name, line = output_queue.get(timeout=min(0.2, max(0.01, remaining)))
        except queue.Empty:
            now = time.monotonic()
            if now - last_wait_report_at >= SAM3_DISCOVERY_WAIT_REPORT_SECONDS:
                current_operation = _current_operation(last_child_event, current_operations, now=now)
                stack_metadata: dict[str, Any] = {}
                if now - last_child_event_at >= stack_probe_seconds and now - last_stack_probe_at >= stack_probe_seconds:
                    stack_metadata = _request_stack_probe(process, stack_path, model_path=model_path)
                    last_stack_probe_at = now
                stack_metadata = {**stack_metadata, **_stack_probe_metadata(stack_path, model_path=model_path)}
                wait_metadata = {
                    "provider": "sam3-local",
                    "discoveryMode": "sam3_auto_masks",
                    "eventType": "sam3_discovery_subprocess_waiting",
                    **_sam3_subprocess_operation_metadata(current_operation, started_at=started_at),
                    "subprocessElapsedSeconds": round(now - started_at, 3),
                    "secondsSinceChildEvent": round(now - last_child_event_at, 3),
                    "secondsSinceStdoutLine": round(now - last_stdout_line_at, 3),
                    "secondsSinceStderrLine": round(now - last_stderr_line_at, 3),
                    "subprocessAlive": process.poll() is None,
                    "returnCode": process.poll(),
                    "pid": process.pid,
                    "stdoutReaderAlive": readers[0].is_alive(),
                    "stderrReaderAlive": readers[1].is_alive(),
                    "currentOperation": current_operation,
                    "gpuProbe": _gpu_probe(process.pid),
                    **stack_metadata,
                }
                if last_child_event:
                    wait_metadata["lastChildEvent"] = dict(last_child_event)
                _emit_ctx(
                    ctx,
                    "candidate_discovery",
                    "running",
                    _waiting_message(last_child_event),
                    progress={"overallRatio": 0.315},
                    metadata=wait_metadata,
                )
                last_wait_report_at = now
            if process.poll() is not None and len(streams_closed) >= 2:
                break
            continue

        if line is None:
            streams_closed.add(stream_name)
            if process.poll() is not None and len(streams_closed) >= 2:
                break
            continue

        clean_line = _redact_runtime_text(line.strip(), model_path)
        if stream_name == "stderr":
            last_stderr_line_at = time.monotonic()
            if clean_line:
                stderr_tail = (stderr_tail + [clean_line])[-12:]
            continue
        last_stdout_line_at = time.monotonic()

        parsed = _json_line(clean_line)
        if not parsed:
            if clean_line:
                stdout_tail = (stdout_tail + [clean_line])[-12:]
            continue
        message_type = str(parsed.get("type") or "")
        if message_type == "event":
            child_metadata = parsed.get("metadata") if isinstance(parsed.get("metadata"), Mapping) else {}
            last_child_event = _summarize_child_event(parsed, child_metadata)
            last_child_event_at = time.monotonic()
            _update_current_operations(current_operations, last_child_event, last_child_event_at)
            _emit_ctx(
                ctx,
                str(parsed.get("stage") or "candidate_discovery"),
                str(parsed.get("status") or "running"),
                _redact_runtime_text(str(parsed.get("message") or "SAM3 scene sweep progress"), model_path),
                progress=parsed.get("progress") if isinstance(parsed.get("progress"), Mapping) else None,
                metadata=_redact_runtime_payload(child_metadata, model_path),
            )
        elif message_type == "result":
            # The result is written to resultPath so large candidate metadata does not need to stream over stdout.
            continue
        elif message_type == "error":
            child_error = _redact_runtime_text(str(parsed.get("message") or parsed.get("errorType") or "SAM3 scene sweep failed"), model_path)

    return_code = process.wait(timeout=1)
    for reader in readers:
        reader.join(timeout=0.2)
    if return_code == 0:
        return
    detail = child_error or (stderr_tail[-1] if stderr_tail else "") or (stdout_tail[-1] if stdout_tail else "")
    if not detail:
        detail = f"worker exited with status {return_code}"
    raise ProviderExecutionError(f"SAM3 isolated scene sweep failed: {_redact_runtime_text(detail, model_path)}")


def _write_frame_store(video: VideoSource, path: Path) -> None:
    frames = [np.asarray(getattr(frame, "rgb"), dtype=np.uint8) for frame in video.frames]
    if not frames:
        raise ProviderExecutionError("SAM3 scene sweep needs sampled video frames before extraction.")
    frame_indexes = [int(getattr(frame, "index", index) or 0) for index, frame in enumerate(video.frames)]
    frame_out_indexes = [int(getattr(frame, "out_index", index) or 0) for index, frame in enumerate(video.frames)]
    frame_times = [float(getattr(frame, "time_sec", 0.0) or 0.0) for frame in video.frames]
    np.savez_compressed(
        path,
        frames=np.stack(frames, axis=0),
        frame_indexes=np.asarray(frame_indexes, dtype=np.int64),
        frame_out_indexes=np.asarray(frame_out_indexes, dtype=np.int64),
        frame_times=np.asarray(frame_times, dtype=np.float64),
    )


def _video_payload(video: VideoSource) -> dict[str, Any]:
    info = getattr(video, "info", None)
    return {
        "path": str(getattr(video, "path", "")),
        "width": int(getattr(info, "width", 0) or 0),
        "height": int(getattr(info, "height", 0) or 0),
        "sourceFps": float(getattr(info, "source_fps", 0.0) or 0.0),
        "sampleFps": float(getattr(info, "sample_fps", 0.0) or 0.0),
        "totalSourceFrames": int(getattr(info, "total_source_frames", 0) or 0),
    }


def _read_candidate_result(path: Path) -> list[ObjectCandidate]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ProviderExecutionError("SAM3 isolated scene sweep did not write candidate results.") from exc
    raw_candidates = payload.get("candidates") if isinstance(payload, Mapping) else None
    if not isinstance(raw_candidates, list):
        raise ProviderExecutionError("SAM3 isolated scene sweep returned an invalid candidate payload.")
    return [_candidate_from_dict(item) for item in raw_candidates if isinstance(item, Mapping)]


def _candidate_from_dict(payload: Mapping[str, Any]) -> ObjectCandidate:
    box_payload = payload.get("box") if isinstance(payload.get("box"), Mapping) else None
    box = None
    if box_payload:
        box = Box(
            x=int(box_payload.get("x", 0)),
            y=int(box_payload.get("y", 0)),
            w=int(box_payload.get("w", 1)),
            h=int(box_payload.get("h", 1)),
        )
    return ObjectCandidate(
        id=str(payload.get("id") or ""),
        label=str(payload.get("label")) if payload.get("label") is not None else None,
        source=str(payload.get("source") or "sam3_auto_masks"),
        frame_index=int(payload.get("frameIndex", payload.get("frame_index", 0)) or 0),
        box=box,
        mask_ref=str(payload.get("maskRef")) if payload.get("maskRef") is not None else None,
        score=float(payload["score"]) if payload.get("score") is not None else None,
        z_index=int(payload.get("zIndex", payload.get("z_index", 10)) or 10),
        metadata=dict(payload.get("metadata") or {}),
    )


def _start_reader_thread(
    name: str,
    stream: Any,
    output_queue: queue.Queue[tuple[str, str | None]],
) -> threading.Thread:
    def read_stream() -> None:
        try:
            if stream is not None:
                for line in iter(stream.readline, ""):
                    output_queue.put((name, line))
        finally:
            output_queue.put((name, None))

    thread = threading.Thread(target=read_stream, name=f"motionjson-sam3-discovery-{name}", daemon=True)
    thread.start()
    return thread


def _terminate_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _json_line(line: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(line)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _bounded_timeout(value: Any) -> float:
    try:
        timeout = float(value)
    except (TypeError, ValueError):
        timeout = DEFAULT_SAM3_DISCOVERY_TIMEOUT_SECONDS
    return min(max(timeout, 0.1), 7200.0)


def _stack_probe_seconds() -> float:
    try:
        value = float(os.environ.get("MOTIONJSON_SAM3_STACK_PROBE_SECONDS", DEFAULT_SAM3_STACK_PROBE_SECONDS))
    except (TypeError, ValueError):
        value = DEFAULT_SAM3_STACK_PROBE_SECONDS
    return max(5.0, min(value, 7200.0))


def _summarize_child_event(parsed: Mapping[str, Any], metadata: Mapping[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "stage": str(parsed.get("stage") or "candidate_discovery"),
        "status": str(parsed.get("status") or "running"),
        "message": str(parsed.get("message") or ""),
    }
    for key in (
        "eventType",
        "objectId",
        "frameIndex",
        "keyframe",
        "keyframeOrdinal",
        "keyframeCount",
        "recordIndex",
        "recordOrdinal",
        "recordCount",
        "pointsPerBatch",
        "pointCount",
        "batchOrdinal",
        "batchCount",
        "sourceFrameIndex",
        "keyframeIndex",
        "frame",
        "totalFrames",
        "operationId",
        "operationKind",
        "operationStatus",
        "operationStartedAt",
        "operationElapsedMs",
        "elapsedMs",
        "trackingProvider",
        "rejectionReason",
    ):
        if key in metadata and metadata[key] not in (None, ""):
            summary[key] = metadata[key]
    return summary


def _update_current_operations(current_operations: dict[str, dict[str, Any]], event: Mapping[str, Any], event_at: float) -> None:
    operation_id = str(event.get("operationId") or "")
    if not operation_id:
        return
    status = str(event.get("operationStatus") or "").lower()
    payload = dict(event)
    payload["observedAtMonotonic"] = event_at
    if status in {"finished", "failed"}:
        current_operations.pop(operation_id, None)
        return
    current_operations[operation_id] = payload


def _current_operation(last_child_event: Mapping[str, Any], current_operations: Mapping[str, Mapping[str, Any]], *, now: float) -> dict[str, Any]:
    if current_operations:
        operation = dict(max(current_operations.values(), key=lambda item: float(item.get("observedAtMonotonic") or 0.0)))
    else:
        operation = dict(last_child_event or {})
    if not operation:
        return {}
    observed_at = operation.pop("observedAtMonotonic", None)
    if isinstance(observed_at, (int, float)):
        seconds_since_event = max(0.0, now - float(observed_at))
        operation["secondsSinceOperationEvent"] = round(seconds_since_event, 3)
        if "operationElapsedMs" not in operation:
            operation["operationElapsedMs"] = round(seconds_since_event * 1000, 3)
    started_at = _parse_monotonic_operation_start(operation, now=now)
    if started_at is not None:
        operation["operationElapsedMs"] = round(max(0.0, now - started_at) * 1000, 3)
    return operation


def _parse_monotonic_operation_start(operation: Mapping[str, Any], *, now: float) -> float | None:
    elapsed = operation.get("operationElapsedMs")
    if isinstance(elapsed, (int, float)):
        return now - max(0.0, float(elapsed)) / 1000.0
    return None


def _sam3_subprocess_operation_metadata(current_operation: Mapping[str, Any], *, started_at: float) -> dict[str, Any]:
    return {
        "operationId": str(current_operation.get("operationId") or f"sam3-subprocess-{int(started_at * 1000)}"),
        "operationKind": "subprocess_wait",
        "operationStatus": "waiting",
        "operationElapsedMs": current_operation.get("operationElapsedMs"),
    }


def _request_stack_probe(process: subprocess.Popen[str], stack_path: Path | None, *, model_path: str) -> dict[str, Any]:
    if stack_path is None:
        return {"stackProbeStatus": "unavailable", "stackProbeReason": "no diagnostics path"}
    if process.poll() is not None:
        return {"stackProbeStatus": "skipped", "stackProbeReason": "subprocess exited"}
    if not hasattr(signal, "SIGUSR1") or os.name == "nt":
        return {"stackProbeStatus": "unsupported", "stackProbeReason": "SIGUSR1 unavailable"}
    if not stack_path.exists():
        return {"stackProbeStatus": "waiting_for_registration", "stackProbeReason": "child has not registered faulthandler yet"}
    try:
        os.kill(process.pid, signal.SIGUSR1)
    except Exception as exc:
        return {"stackProbeStatus": "failed", "stackProbeReason": _redact_runtime_text(f"{type(exc).__name__}: {exc}", model_path)}
    return {"stackProbeStatus": "requested"}


def _stack_probe_metadata(stack_path: Path | None, *, model_path: str) -> dict[str, Any]:
    if stack_path is None:
        return {}
    try:
        text = stack_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError as exc:
        return {"stackProbeStatus": "read_failed", "stackProbeReason": _redact_runtime_text(str(exc), model_path)}
    lines = [_redact_runtime_text(line.strip(), model_path) for line in text.splitlines() if line.strip()]
    if not lines:
        return {}
    return {"stackProbeStatus": "captured", "pythonStackTop": lines[-12:]}


def _gpu_probe(pid: int | None) -> dict[str, Any]:
    if not pid:
        return {"gpuProbeStatus": "unavailable", "reason": "missing pid"}
    if shutil.which("nvidia-smi") is None:
        return {"gpuProbeStatus": "unavailable", "reason": "nvidia-smi not found"}
    probe: dict[str, Any] = {"gpuProbeStatus": "ok", "pidVisibleInNvidiaSmi": False}
    try:
        gpu = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used", "--format=csv,noheader,nounits"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
        first_line = (gpu.stdout or "").splitlines()[0] if gpu.stdout else ""
        if first_line:
            parts = [part.strip() for part in first_line.split(",")]
            if len(parts) >= 1 and parts[0]:
                probe["gpuUtilizationPercent"] = int(float(parts[0]))
            if len(parts) >= 2 and parts[1]:
                probe["gpuMemoryUsedBytes"] = int(float(parts[1]) * 1024 * 1024)
    except Exception as exc:
        probe["gpuProbeStatus"] = "partial"
        probe["gpuProbeReason"] = f"gpu query failed: {type(exc).__name__}"
    try:
        apps = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
        for line in (apps.stdout or "").splitlines():
            parts = [part.strip() for part in line.split(",")]
            if len(parts) >= 2 and parts[0] and int(float(parts[0])) == int(pid):
                probe["pidVisibleInNvidiaSmi"] = True
                probe["computeProcessMemoryBytes"] = int(float(parts[1]) * 1024 * 1024)
                break
    except Exception as exc:
        probe.setdefault("gpuProbeStatus", "partial")
        probe["computeProbeReason"] = f"compute query failed: {type(exc).__name__}"
    return probe


def _waiting_message(last_child_event: Mapping[str, Any]) -> str:
    if not last_child_event:
        return "SAM3 scene sweep subprocess is running; no child progress event has arrived yet"
    event_type = str(last_child_event.get("eventType") or "")
    message = str(last_child_event.get("message") or "SAM3 scene sweep operation")
    object_id = str(last_child_event.get("objectId") or "")
    keyframe = last_child_event.get("keyframe", last_child_event.get("frameIndex"))
    detail = event_type or message
    if object_id:
        detail = f"{detail} for {object_id}"
    if keyframe not in (None, ""):
        detail = f"{detail} at keyframe {keyframe}"
    return f"SAM3 scene sweep subprocess still waiting after {detail}"


def _inflight_detail(last_child_event: Mapping[str, Any]) -> str:
    if not last_child_event:
        return ""
    event_type = str(last_child_event.get("eventType") or "")
    message = str(last_child_event.get("message") or "").strip()
    object_id = str(last_child_event.get("objectId") or "").strip()
    keyframe = last_child_event.get("keyframe", last_child_event.get("frameIndex"))
    parts = [part for part in (event_type, message) if part]
    detail = " / ".join(parts)
    if object_id:
        detail = f"{detail} for {object_id}" if detail else f"candidate {object_id}"
    if keyframe not in (None, ""):
        detail = f"{detail} at keyframe {keyframe}" if detail else f"keyframe {keyframe}"
    return detail


def _emit_ctx(
    ctx: RunContext,
    stage: str,
    status: str,
    message: str,
    *,
    progress: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    if ctx is not None and hasattr(ctx, "emit"):
        ctx.emit(stage, status, message, progress=dict(progress or {}), metadata=dict(metadata or {}))


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
