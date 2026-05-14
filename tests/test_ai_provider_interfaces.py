from pathlib import Path

import numpy as np

from motionjson.masks import ThresholdMaskProvider
from motionjson.providers import (
    ExportProvider,
    LLMProvider,
    MattingProvider,
    MockExportProvider,
    MockLLMProvider,
    MockMattingProvider,
    MockRenderProvider,
    MockSegmentationProvider,
    MockStorageProvider,
    RenderProvider,
    SegmentationMaskProvider,
    SegmentationProvider,
    StorageProvider,
)
from motionjson.providers.segmentation import MaskProviderSegmentationAdapter
from motionjson.video import VideoInfo


def test_provider_protocols_are_exported_and_mocked(tmp_path):
    scene = {"objects": [{"id": "object_0"}]}
    frame = np.zeros((8, 10, 3), dtype=np.uint8)
    mask = np.zeros((8, 10), dtype=np.uint8)
    output = tmp_path / "scene.json"

    llm = MockLLMProvider(content="object label")
    segmentation = MockSegmentationProvider(box=(1, 2, 3, 4))
    matting = MockMattingProvider()
    render = MockRenderProvider()
    storage = MockStorageProvider()
    exporter = MockExportProvider()

    assert isinstance(llm, LLMProvider)
    assert isinstance(segmentation, SegmentationProvider)
    assert isinstance(matting, MattingProvider)
    assert isinstance(render, RenderProvider)
    assert isinstance(storage, StorageProvider)
    assert isinstance(exporter, ExportProvider)

    assert llm.complete([{"role": "user", "content": "label"}])["choices"][0]["message"]["content"] == "object label"
    segmentation.prepare(VideoInfo(width=10, height=8, source_fps=12, sample_fps=12, total_source_frames=1))
    assert segmentation.segment(0, frame).sum() == 3 * 4 * 255
    assert matting.refine_alpha(frame, mask).shape == (8, 10)
    assert render.render_preview(scene)["objects"] == 1
    assert storage.save_bytes("asset.bin", b"abc") == "mock://asset.bin"
    assert storage.load_bytes("asset.bin") == b"abc"
    assert storage.exists("asset.bin")
    assert exporter.export(scene, output)["format"] == "json"
    assert output.exists()


def test_existing_mask_provider_can_run_through_segmentation_adapter():
    mask_provider = ThresholdMaskProvider((0, 80, 80), (12, 255, 255))
    segmentation = MaskProviderSegmentationAdapter(mask_provider)
    pipeline_provider = SegmentationMaskProvider(segmentation)
    info = VideoInfo(width=16, height=16, source_fps=12, sample_fps=12, total_source_frames=1)
    frame_bgr = np.zeros((16, 16, 3), dtype=np.uint8)
    frame_bgr[4:12, 4:12] = (20, 20, 230)

    pipeline_provider.prepare(info)
    mask = pipeline_provider.get_mask(0, frame_bgr)
    pipeline_provider.close()

    assert mask.shape == (16, 16)
    assert set(np.unique(mask)).issubset({0, 255})
    assert mask.sum() > 0


def test_mock_export_provider_can_report_non_json_without_final_export(tmp_path):
    exporter = MockExportProvider()
    output = Path(tmp_path / "bundle.motionjson")

    result = exporter.export({"objects": []}, output, format="bundle")

    assert result == {"status": "ok", "format": "bundle", "output": str(output)}
    assert not output.exists()
