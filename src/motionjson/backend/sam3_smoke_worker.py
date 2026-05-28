from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from motionjson.providers.sam3 import sam3_scene_sweep_warmup


LOCAL_PATH_REDACTION = "[LOCAL_PATH_REDACTED]"


def main() -> int:
    try:
        request = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        _emit({"type": "error", "errorType": type(exc).__name__, "message": "Invalid SAM3 warmup worker request."})
        return 2
    model_id = str(request.get("modelId") or request.get("model") or "")
    device = str(request.get("device") or "cuda")

    def progress(event_type: str, message: str, percent: int | float | None = None, known: bool = False) -> None:
        _emit(
            {
                "type": "progress",
                "eventType": event_type,
                "message": _redact_runtime_text(message, model_id),
                "percent": percent,
                "known": bool(known),
            }
        )

    try:
        result = sam3_scene_sweep_warmup(model_id, device=device, progress=progress)
    except Exception as exc:  # pragma: no cover - exercised by subprocess parent integration tests.
        _emit(
            {
                "type": "error",
                "errorType": type(exc).__name__,
                "message": _redact_runtime_text(str(exc) or type(exc).__name__, model_id),
            }
        )
        return 2
    _emit({"type": "result", "result": result})
    return 0


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, sort_keys=True), flush=True)


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


if __name__ == "__main__":
    raise SystemExit(main())
