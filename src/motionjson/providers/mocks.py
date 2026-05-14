from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import cv2
import numpy as np

from ..video import VideoInfo


@dataclass
class MockLLMProvider:
    """Deterministic no-network LLM/VLM provider for CI and local tests."""

    content: str = "mock completion"
    model: str = "mock/model"

    def complete(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        tools: Sequence[Mapping[str, Any]] | None = None,
        response_format: Mapping[str, Any] | None = None,
        **routing: Any,
    ) -> Mapping[str, Any]:
        return {
            "id": "mock-chat-completion",
            "model": model or self.model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": self.content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": len(messages), "completion_tokens": len(self.content.split()), "total_tokens": len(messages) + len(self.content.split())},
        }


@dataclass
class MockSegmentationProvider:
    """Deterministic binary mask provider with no AI or network dependency."""

    box: tuple[int, int, int, int] | None = None
    video_metadata: VideoInfo | None = field(default=None, init=False)

    def prepare(self, video_metadata: VideoInfo) -> None:
        self.video_metadata = video_metadata

    def segment(
        self,
        frame_index: int,
        frame_bgr: np.ndarray,
        *,
        prompt_point: tuple[int, int] | None = None,
        prompt_box: tuple[int, int, int, int] | None = None,
    ) -> np.ndarray:
        height, width = frame_bgr.shape[:2]
        mask = np.zeros((height, width), dtype=np.uint8)
        x, y, w, h = prompt_box or self.box or (width // 4, height // 4, max(1, width // 2), max(1, height // 2))
        x0 = max(0, min(width, x))
        y0 = max(0, min(height, y))
        x1 = max(x0, min(width, x + w))
        y1 = max(y0, min(height, y + h))
        mask[y0:y1, x0:x1] = 255
        return mask

    def close(self) -> None:
        return None


@dataclass
class MockMattingProvider:
    """Deterministic matte refinement using optional blur over a binary mask."""

    blur: int = 0

    def refine_alpha(self, frame_rgb: np.ndarray, binary_mask: np.ndarray) -> np.ndarray:
        alpha = np.where(binary_mask > 127, 255, 0).astype(np.uint8)
        if self.blur > 1:
            kernel = self.blur if self.blur % 2 == 1 else self.blur + 1
            alpha = cv2.GaussianBlur(alpha, (kernel, kernel), 0)
        return alpha


@dataclass
class MockRenderProvider:
    """No-op renderer that reports cached-layer render intent."""

    def render_preview(self, scene_graph: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"status": "ok", "mode": "preview", "objects": len(scene_graph.get("objects", []))}

    def export_video(self, scene_graph: Mapping[str, Any], output_path: str | Path) -> Mapping[str, Any]:
        return {"status": "ok", "mode": "video", "output": str(output_path), "objects": len(scene_graph.get("objects", []))}


@dataclass
class MockStorageProvider:
    """In-memory storage provider for deterministic tests."""

    objects: dict[str, bytes] = field(default_factory=dict)
    content_types: dict[str, str | None] = field(default_factory=dict)

    def save_bytes(self, key: str, data: bytes, *, content_type: str | None = None) -> str:
        self.objects[key] = bytes(data)
        self.content_types[key] = content_type
        return f"mock://{key}"

    def load_bytes(self, key: str) -> bytes:
        if key not in self.objects:
            raise FileNotFoundError(f"Mock storage key not found: {key}")
        return self.objects[key]

    def exists(self, key: str) -> bool:
        return key in self.objects

    def put_bytes(self, key: str, data: bytes, *, content_type: str | None = None) -> str:
        """Backward-compatible alias for early Phase 2 callers."""
        return self.save_bytes(key, data, content_type=content_type)

    def get_bytes(self, key: str) -> bytes:
        """Backward-compatible alias for early Phase 2 callers."""
        return self.load_bytes(key)


@dataclass
class MockExportProvider:
    """Deterministic JSON exporter for manifests and bundle metadata."""

    def export(self, scene_graph: Mapping[str, Any], output_path: str | Path, *, format: str | None = None) -> Mapping[str, Any]:
        path = Path(output_path)
        export_format = format or path.suffix.lstrip(".") or "json"
        if export_format == "json":
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(scene_graph, indent=2, sort_keys=True), encoding="utf-8")
        return {"status": "ok", "format": export_format, "output": str(path)}
