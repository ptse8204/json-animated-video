from __future__ import annotations

import os
import textwrap

import pytest

from motionjson.backend.sam3_smoke_subprocess import run_sam3_scene_sweep_warmup_subprocess
from motionjson.providers.base import ProviderExecutionError


def _fake_python(tmp_path, source: str) -> str:
    executable = tmp_path / "fake_python"
    executable.write_text("#!/usr/bin/env python3\n" + textwrap.dedent(source), encoding="utf-8")
    executable.chmod(0o755)
    return str(executable)


def test_sam3_smoke_subprocess_streams_progress_and_redacts_local_model_path(tmp_path):
    model_dir = tmp_path / "private-cache" / "models--facebook--sam3"
    fake_python = _fake_python(
        tmp_path,
        """
        import json
        import sys

        request = json.load(sys.stdin)
        model = request["modelId"]
        print(json.dumps({
            "type": "progress",
            "eventType": "loading_sam3_tracker_model_weights",
            "message": f"Loading from {model}",
            "percent": 55,
            "known": False,
        }), flush=True)
        print(json.dumps({
            "type": "result",
            "result": {
                "status": "ok",
                "warmupStatus": "succeeded",
                "loadedOnCuda": True,
                "deviceActual": "cuda:0",
                "resolvedModelDir": model,
            },
        }), flush=True)
        """,
    )
    events: list[dict[str, object]] = []

    result = run_sam3_scene_sweep_warmup_subprocess(
        str(model_dir),
        device="cuda",
        progress=lambda event_type, message, percent, known: events.append(
            {"type": event_type, "message": message, "percent": percent, "known": known}
        ),
        timeout_seconds=2,
        python_executable=fake_python,
        worker_module="ignored.by.fake.executable",
    )

    assert result["warmupStatus"] == "succeeded"
    assert result["resolvedModelDir"] == "[LOCAL_PATH_REDACTED]"
    assert any(event["type"] == "loading_sam3_tracker_model_weights" for event in events)
    serialized_events = repr(events)
    assert str(model_dir) not in serialized_events
    assert "[LOCAL_PATH_REDACTED]" in serialized_events


def test_sam3_smoke_subprocess_times_out_and_terminates_worker(tmp_path):
    model_dir = tmp_path / "private-cache" / "models--facebook--sam3"
    marker = tmp_path / "worker-finished"
    fake_python = _fake_python(
        tmp_path,
        f"""
        import json
        import pathlib
        import sys
        import time

        request = json.load(sys.stdin)
        print(json.dumps({{
            "type": "progress",
            "eventType": "loading_sam3_tracker_model_weights",
            "message": "still loading",
            "percent": 55,
            "known": False,
        }}), flush=True)
        time.sleep(5)
        pathlib.Path({str(marker)!r}).write_text("finished", encoding="utf-8")
        """,
    )
    events: list[dict[str, object]] = []

    with pytest.raises(ProviderExecutionError, match="timed out"):
        run_sam3_scene_sweep_warmup_subprocess(
            str(model_dir),
            device="cuda",
            progress=lambda event_type, message, percent, known: events.append(
                {"type": event_type, "message": message, "percent": percent, "known": known}
            ),
            timeout_seconds=0.2,
            python_executable=fake_python,
            worker_module="ignored.by.fake.executable",
        )

    assert any(event["type"] == "sam3_smoke_timeout" for event in events)
    assert str(model_dir) not in repr(events)
    assert not marker.exists()
