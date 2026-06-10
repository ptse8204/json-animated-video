from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from motionjson.benchmark import benchmark_scene
from motionjson.layers import crop_rgba_layer
from motionjson.masks import ThresholdMaskProvider
from motionjson.pipeline import run_pipeline
from motionjson.raster_accel import benchmark_raster_operations, resolve_raster_acceleration
from motionjson.vectorize import mask_to_largest_polygon


class RecordingJobContext:
    def __init__(self) -> None:
        self.events: list[dict] = []
        self.cancel_checks: list[str] = []

    def emit(self, stage, status, message, *, event_type="progress", progress=None, metadata=None):
        self.events.append(
            {
                "stage": stage,
                "status": status,
                "message": message,
                "event_type": event_type,
                "progress": progress or {},
                "metadata": metadata or {},
            }
        )

    def check_cancel(self, stage):
        self.cancel_checks.append(stage)


def test_raster_acceleration_resolver_keeps_cpu_fallback_outputs_stable() -> None:
    status = resolve_raster_acceleration("unsupported-device")
    assert status.actual_device == "cpu"
    assert status.backend == "cpu"
    assert status.reason == "unsupported_device_requested"
    invalid_cuda = resolve_raster_acceleration("cuda:999999")
    assert invalid_cuda.actual_device == "cpu"
    assert invalid_cuda.reason in {"cuda_unavailable", "cuda_device_unavailable", "torch_unavailable"}

    rgb = np.zeros((32, 40, 3), dtype=np.uint8)
    rgb[8:22, 12:28] = (230, 20, 20)
    mask = np.zeros((32, 40), dtype=np.uint8)
    mask[8:22, 12:28] = 255
    bbox = [12, 8, 16, 14]

    cpu_crop = crop_rgba_layer(rgb, mask, bbox, feather=3, padding=2, device="cpu")
    fallback_crop = crop_rgba_layer(rgb, mask, bbox, feather=3, padding=2, device="unsupported-device")
    assert np.array_equal(cpu_crop.rgba, fallback_crop.rgba)
    assert cpu_crop.bbox == fallback_crop.bbox

    cpu_contour = mask_to_largest_polygon(mask, min_area=1, device="cpu")
    fallback_contour = mask_to_largest_polygon(mask, min_area=1, device="unsupported-device")
    assert fallback_contour.visible is True
    assert fallback_contour.bbox == cpu_contour.bbox
    assert fallback_contour.area == cpu_contour.area


def test_raster_acceleration_benchmark_reports_selected_path_without_gpu() -> None:
    report = benchmark_raster_operations(width=40, height=32, iterations=1, device="unsupported-device")

    assert report["schema"] == "motionjson.raster_acceleration_benchmark.v0.1"
    assert report["rasterAcceleration"]["actualDevice"] == "cpu"
    assert report["rasterAcceleration"]["finalContourBackend"] == "cpu-opencv"
    assert report["cpuPath"]["processedPixels"] > 0
    assert "selectedVsCpuSpeedup" in report["comparison"]


def test_pipeline_events_and_scene_metadata_include_raster_acceleration(tmp_path: Path) -> None:
    video = tmp_path / "tiny.mp4"
    out = tmp_path / "out"
    _make_tiny_video(video, frame_count=3)
    context = RecordingJobContext()

    scene = run_pipeline(
        video_path=video,
        out_dir=out,
        mask_provider=ThresholdMaskProvider((0, 80, 80), (12, 255, 255)),
        object_label="Red square",
        sample_fps=12,
        max_frames=2,
        min_area=1,
        raster_device="unsupported-device",
        job_context=context,
    )

    acceleration = scene["providerPerformance"]["rasterAcceleration"]
    assert acceleration["actualDevice"] == "cpu"
    assert acceleration["reason"] == "unsupported_device_requested"
    assert any(item["phase"] == "raster_acceleration_probe" for item in scene["latencyMetrics"]["phaseTimings"])

    object_perf = scene["providerPerformance"]["objects"][0]
    assert object_perf["rasterAcceleration"]["actualDevice"] == "cpu"
    assert object_perf["trackingElapsedMs"] >= 0
    assert object_perf["vectorizationElapsedMs"] >= 0
    assert object_perf["assetPreparationElapsedMs"] >= 0

    runtime_event = next(event for event in context.events if event["stage"] == "runtime_acceleration")
    assert runtime_event["metadata"]["reason"] == "unsupported_device_requested"
    vector_event = next(event for event in context.events if event["stage"] == "vectorization" and event["status"] == "running")
    assert vector_event["metadata"]["finalContourBackend"] == "cpu-opencv"
    frame_event = next(event for event in context.events if event["event_type"] == "asset_preparation_frame_finished")
    assert frame_event["metadata"]["rasterBackend"] == "cpu"
    assert frame_event["metadata"]["writtenFiles"]["mask"]["path"].startswith("masks/")

    benchmark = benchmark_scene(video_path=video, out_dir=out, scene=scene, iterations=1, raster_device="unsupported-device")
    assert benchmark["raster_acceleration"]["rasterAcceleration"]["actualDevice"] == "cpu"
    assert benchmark["comparison"]["raster_selected_vs_cpu_speedup"] is not None
    assert json.loads((out / "scene_graph.json").read_text(encoding="utf-8"))["providerPerformance"]["rasterAcceleration"]["actualDevice"] == "cpu"


def _make_tiny_video(path: Path, frame_count: int = 3) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 12, (40, 32))
    if not writer.isOpened():
        raise RuntimeError("Could not open test video writer")
    for index in range(frame_count):
        rgb = np.full((32, 40, 3), 245, dtype=np.uint8)
        rgb[8:22, 12 + index : 28 + index] = (230, 20, 20)
        writer.write(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    writer.release()
