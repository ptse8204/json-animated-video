from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Mapping

from motionjson.providers.base import ProviderExecutionError


SAM3_SMOKE_WORKER_MODULE = "motionjson.backend.sam3_smoke_worker"
DEFAULT_SAM3_SMOKE_TIMEOUT_SECONDS = 900.0
LOCAL_PATH_REDACTION = "[LOCAL_PATH_REDACTED]"
SetupProgressCallback = Callable[[str, str, int | float | None, bool], None]


def run_sam3_scene_sweep_warmup_subprocess(
    model_id: str,
    *,
    device: str,
    progress: SetupProgressCallback | None = None,
    timeout_seconds: float = DEFAULT_SAM3_SMOKE_TIMEOUT_SECONDS,
    environ: Mapping[str, str] | None = None,
    python_executable: str | None = None,
    worker_module: str = SAM3_SMOKE_WORKER_MODULE,
) -> dict[str, Any]:
    """Run the heavy SAM3 warmup in a process the UI backend can terminate."""

    timeout = _bounded_timeout(timeout_seconds)
    command = [python_executable or sys.executable, "-m", worker_module]
    child_env = dict(os.environ)
    if environ:
        child_env.update({str(key): str(value) for key, value in environ.items()})
    child_env["PYTHONUNBUFFERED"] = "1"
    request = {"modelId": str(model_id or ""), "device": str(device or "cuda")}
    if progress:
        progress(
            "sam3_smoke_subprocess_started",
            f"Starting isolated SAM3 warmup process with a {int(timeout)}s timeout",
            40,
            False,
        )

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
    deadline = time.monotonic() + timeout
    result: dict[str, Any] | None = None
    child_error = ""
    stderr_tail: list[str] = []
    stdout_tail: list[str] = []
    streams_closed: set[str] = set()

    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            message = (
                f"SAM3 Scene Sweep warmup timed out after {int(timeout)}s while loading or warming up the model. "
                "The isolated process was terminated so the UI can recover. Restart the Colab runtime, verify "
                "torch/transformers/accelerate versions, then retry Prepare local model."
            )
            if progress:
                progress("sam3_smoke_timeout", message, 0, False)
            _terminate_process(process)
            raise ProviderExecutionError(_redact_runtime_text(message, model_id))

        try:
            stream_name, line = output_queue.get(timeout=min(0.2, max(0.01, remaining)))
        except queue.Empty:
            if process.poll() is not None and len(streams_closed) >= 2:
                break
            continue

        if line is None:
            streams_closed.add(stream_name)
            if process.poll() is not None and len(streams_closed) >= 2:
                break
            continue

        clean_line = _redact_runtime_text(line.strip(), model_id)
        if stream_name == "stderr":
            if clean_line:
                stderr_tail = (stderr_tail + [clean_line])[-12:]
            continue

        parsed = _json_line(clean_line)
        if not parsed:
            if clean_line:
                stdout_tail = (stdout_tail + [clean_line])[-12:]
            continue
        message_type = str(parsed.get("type") or "")
        if message_type == "progress":
            event_type = str(parsed.get("eventType") or parsed.get("event_type") or "sam3_smoke_progress")
            message = _redact_runtime_text(str(parsed.get("message") or event_type), model_id)
            percent = parsed.get("percent")
            known = bool(parsed.get("known"))
            if progress:
                progress(event_type, message, percent, known)
        elif message_type == "result":
            raw_result = parsed.get("result")
            if isinstance(raw_result, Mapping):
                result = _redact_runtime_payload(dict(raw_result), model_id)
        elif message_type == "error":
            child_error = _redact_runtime_text(str(parsed.get("message") or parsed.get("errorType") or "SAM3 warmup failed"), model_id)

    return_code = process.wait(timeout=1)
    for reader in readers:
        reader.join(timeout=0.2)
    if return_code == 0 and result is not None:
        return result
    detail = child_error or (stderr_tail[-1] if stderr_tail else "") or (stdout_tail[-1] if stdout_tail else "")
    if not detail:
        detail = f"worker exited with status {return_code}"
    raise ProviderExecutionError(f"SAM3 isolated warmup process failed: {_redact_runtime_text(detail, model_id)}")


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

    thread = threading.Thread(target=read_stream, name=f"motionjson-sam3-smoke-{name}", daemon=True)
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
        timeout = DEFAULT_SAM3_SMOKE_TIMEOUT_SECONDS
    return min(max(timeout, 0.1), 7200.0)


def _redact_runtime_payload(value: Any, model_id: str) -> Any:
    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key).replace("_", "").replace("-", "").lower()
            if key_text.endswith("path") or key_text.endswith("dir") or key_text.endswith("directory"):
                redacted[key] = LOCAL_PATH_REDACTION if item else item
            else:
                redacted[key] = _redact_runtime_payload(item, model_id)
        return redacted
    if isinstance(value, list):
        return [_redact_runtime_payload(item, model_id) for item in value]
    if isinstance(value, str):
        return _redact_runtime_text(value, model_id)
    return value


def _redact_runtime_text(value: Any, model_id: str) -> str:
    text = str(value or "")
    raw = str(model_id or "").strip()
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
