from __future__ import annotations

import json
import textwrap
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from motionjson.backend.sam3_discovery_subprocess import SubprocessSAM3AutoMasksDiscoveryProvider, _write_frame_store, run_sam3_auto_masks_proposal_subprocess
from motionjson.backend.sam3_discovery_worker import _load_video
from motionjson.pipeline import run_multi_object_pipeline
from motionjson.providers.base import ObjectCandidateProvider, ProviderExecutionError
from motionjson.providers.discovery import object_specs_from_candidates
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
    frame = SimpleNamespace(index=7, out_index=0, time_sec=1.25, rgb=np.zeros((8, 8, 3), dtype=np.uint8))
    info = SimpleNamespace(width=8, height=8, source_fps=30.0, sample_fps=1.0, total_source_frames=30)
    return VideoSource(path=tmp_path / "video.mp4", info=info, frames=[frame])


def _fake_python(tmp_path, source: str) -> str:
    executable = tmp_path / "fake_python"
    executable.write_text("#!/usr/bin/env python3\n" + textwrap.dedent(source), encoding="utf-8")
    executable.chmod(0o755)
    return str(executable)


def _tiny_video(path):
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 12, (40, 32))
    if not writer.isOpened():
        raise RuntimeError("Could not open test video writer")
    frame = np.full((32, 40, 3), 245, dtype=np.uint8)
    frame[8:18, 8:20] = (230, 20, 20)
    writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
    writer.release()


def test_sam3_discovery_subprocess_provider_satisfies_candidate_provider_contract(tmp_path):
    provider = SubprocessSAM3AutoMasksDiscoveryProvider(model_path=str(tmp_path / "private-cache" / "models--facebook--sam3"))

    assert isinstance(provider, ObjectCandidateProvider)
    assert provider.name == "sam3_auto_masks"
    assert provider.provider_name == "sam3-local"


def test_sam3_discovery_worker_restores_sampled_frame_metadata(tmp_path):
    frames_path = tmp_path / "frames.npz"
    _write_frame_store(_video(tmp_path), frames_path)

    video = _load_video(
        {
            "framesPath": str(frames_path),
            "video": {
                "path": str(tmp_path / "video.mp4"),
                "width": 8,
                "height": 8,
                "sourceFps": 30.0,
                "sampleFps": 1.0,
                "totalSourceFrames": 30,
            },
        }
    )

    assert video.frames[0].index == 7
    assert video.frames[0].out_index == 0
    assert video.frames[0].time_sec == 1.25
    assert video.info.width == 8


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


def test_sam3_discovery_subprocess_provider_feeds_multi_object_pipeline_without_gpu(tmp_path):
    video = tmp_path / "tiny.mp4"
    out = tmp_path / "out"
    model_dir = tmp_path / "private-cache" / "models--facebook--sam3"
    _tiny_video(video)
    fake_python = _fake_python(
        tmp_path,
        """
        import json
        import sys
        from pathlib import Path

        import numpy as np
        from PIL import Image

        request = json.load(sys.stdin)
        frames = np.load(request["framesPath"])["frames"]
        mask_dir_rel = "discovery/sam3_auto_masks/sam3_scene_0000_001"
        mask_dir = Path(request["outDir"]) / mask_dir_rel
        mask_dir.mkdir(parents=True, exist_ok=True)
        for index in range(frames.shape[0]):
            mask = np.zeros(frames.shape[1:3], dtype=np.uint8)
            mask[8:18, 8:20] = 255
            Image.fromarray(mask).save(mask_dir / f"mask_{index + 1:06d}.png")
        print(json.dumps({
            "type": "event",
            "stage": "candidate_discovery",
            "status": "running",
            "message": f"fake SAM3 loaded from {request['modelId']}",
            "progress": {"overallRatio": 0.31},
            "metadata": {"model": request["modelId"], "candidates": 1},
        }), flush=True)
        with open(request["resultPath"], "w", encoding="utf-8") as handle:
            json.dump({
                "candidates": [{
                    "id": "sam3_scene_0000_001",
                    "label": "Scene object",
                    "source": "sam3_auto_masks",
                    "frameIndex": 0,
                    "box": {"x": 8, "y": 8, "w": 12, "h": 10},
                    "score": 0.91,
                    "zIndex": 10,
                    "metadata": {"maskDir": mask_dir_rel, "maskFiles": int(frames.shape[0])},
                }]
            }, handle)
        print(json.dumps({"type": "result", "status": "ok"}), flush=True)
        """,
    )
    provider = SubprocessSAM3AutoMasksDiscoveryProvider(
        model_path=str(model_dir),
        device="cuda",
        timeout_seconds=2,
        python_executable=fake_python,
        worker_module="ignored.by.fake.executable",
    )
    recorder = RecordingJobContext()

    scene = run_multi_object_pipeline(
        video_path=video,
        out_dir=out,
        object_specs=[],
        candidate_provider=provider,
        candidate_config={"maxCandidatesPerKeyframe": 1},
        candidate_to_specs=lambda candidates: object_specs_from_candidates(candidates, base_dir=out),
        sample_fps=12,
        max_frames=1,
        min_area=1,
        job_context=recorder,
    )

    candidates_payload = json.loads((out / "candidates.json").read_text(encoding="utf-8"))
    assert scene["objects"][0]["id"] == "sam3_scene_0000_001"
    assert candidates_payload["provider"] == "sam3_auto_masks"
    assert candidates_payload["candidates"][0]["source"] == "sam3_auto_masks"
    serialized_events = repr(recorder.events)
    assert str(model_dir) not in serialized_events
    assert "[LOCAL_PATH_REDACTED]" in serialized_events
