from __future__ import annotations

import textwrap
from types import SimpleNamespace

import numpy as np
import pytest

from motionjson.backend.sam3_discovery_subprocess import run_sam3_auto_masks_proposal_subprocess
from motionjson.providers.base import ProviderExecutionError
from motionjson.tracks import RunContext, VideoSource


class RecordingJobContext:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    def emit(self, stage, status, message, *, progress=None, metadata=None):
        self.events.append(
            {
                "stage": stage,
                "status": status,
                "message": message,
                "progress": progress or {},
                "metadata": metadata or {},
            }
        )


def _video(tmp_path):
    frame = SimpleNamespace(rgb=np.zeros((8, 8, 3), dtype=np.uint8))
    info = SimpleNamespace(width=8, height=8, source_fps=30.0, sample_fps=1.0, total_source_frames=30)
    return VideoSource(path=tmp_path / "video.mp4", info=info, frames=[frame])


def _fake_python(tmp_path, source: str) -> str:
    executable = tmp_path / "fake_python"
    executable.write_text("#!/usr/bin/env python3\n" + textwrap.dedent(source), encoding="utf-8")
    executable.chmod(0o755)
    return str(executable)


def test_sam3_discovery_subprocess_returns_candidates_and_redacts_model_path(tmp_path):
    model_dir = tmp_path / "private-cache" / "models--facebook--sam3"
    fake_python = _fake_python(
        tmp_path,
        """
        import json
        import sys

        request = json.load(sys.stdin)
        model = request["modelId"]
        print(json.dumps({
            "type": "event",
            "stage": "candidate_discovery",
            "status": "running",
            "message": f"loading from {model}",
            "progress": {"overallRatio": 0.31},
            "metadata": {"model": model},
        }), flush=True)
        with open(request["resultPath"], "w", encoding="utf-8") as handle:
            json.dump({
                "candidates": [{
                    "id": "sam3_scene_0000_001",
                    "label": "Scene object",
                    "source": "sam3_auto_masks",
                    "frameIndex": 0,
                    "box": {"x": 1, "y": 1, "w": 4, "h": 4},
                    "score": 0.9,
                    "zIndex": 10,
                    "metadata": {"maskDir": "discovery/sam3_auto_masks/sam3_scene_0000_001"},
                }]
            }, handle)
        print(json.dumps({"type": "result", "status": "ok"}), flush=True)
        """,
    )
    recorder = RecordingJobContext()

    candidates = run_sam3_auto_masks_proposal_subprocess(
        _video(tmp_path),
        {"maxCandidatesPerKeyframe": 1},
        RunContext(out_dir=tmp_path / "out", job_context=recorder),
        model_path=str(model_dir),
        device="cuda",
        timeout_seconds=2,
        python_executable=fake_python,
        worker_module="ignored.by.fake.executable",
    )

    assert [candidate.id for candidate in candidates] == ["sam3_scene_0000_001"]
    assert candidates[0].box is not None
    assert candidates[0].box.w == 4
    serialized_events = repr(recorder.events)
    assert str(model_dir) not in serialized_events
    assert "[LOCAL_PATH_REDACTED]" in serialized_events


def test_sam3_discovery_subprocess_times_out_and_marks_candidate_discovery_failed(tmp_path):
    model_dir = tmp_path / "private-cache" / "models--facebook--sam3"
    marker = tmp_path / "worker-finished"
    fake_python = _fake_python(
        tmp_path,
        f"""
        import json
        import pathlib
        import sys
        import time

        json.load(sys.stdin)
        time.sleep(5)
        pathlib.Path({str(marker)!r}).write_text("finished", encoding="utf-8")
        """,
    )
    recorder = RecordingJobContext()

    with pytest.raises(ProviderExecutionError, match="timed out"):
        run_sam3_auto_masks_proposal_subprocess(
            _video(tmp_path),
            {},
            RunContext(out_dir=tmp_path / "out", job_context=recorder),
            model_path=str(model_dir),
            device="cuda",
            timeout_seconds=0.2,
            python_executable=fake_python,
            worker_module="ignored.by.fake.executable",
        )

    assert any(event["metadata"].get("eventType") == "sam3_discovery_timeout" for event in recorder.events)
    assert not marker.exists()
