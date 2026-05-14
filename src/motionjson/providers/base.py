from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable

import numpy as np

from ..video import VideoInfo


class ProviderError(RuntimeError):
    """Base error for swappable provider failures."""


class ProviderConfigError(ProviderError):
    """Raised when a provider is missing required local configuration."""


class ProviderExecutionError(ProviderError):
    """Raised when a configured provider fails during execution."""


@dataclass(frozen=True)
class ProviderAttempt:
    """Deterministic provider attempt record for routing, latency, and cost reports."""

    provider: str
    operation: str
    status: str
    elapsed_ms: float
    frame_index: int | None = None
    error: str | None = None
    estimated_cost_units: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PhaseTiming:
    """Named phase timing for extraction and backend job metadata."""

    phase: str
    elapsed_ms: float
    count: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BatchSegmentationRequest:
    """Optional GPU/batched segmentation request shape.

    Providers can accept these requests without MotionJSON depending on CUDA,
    torch, or any specific GPU runtime.
    """

    frame_index: int
    frame_bgr: np.ndarray
    prompt_point: tuple[int, int] | None = None
    prompt_box: tuple[int, int, int, int] | None = None


@dataclass(frozen=True)
class CompressionOutcome:
    """Compression candidate outcome derived from cached assets."""

    name: str
    status: str
    bytes: int
    source_bytes: int
    path: str | None = None
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        saved = max(0, self.source_bytes - self.bytes) if self.status == "ready" else 0
        ratio = round(self.bytes / self.source_bytes, 4) if self.source_bytes and self.status == "ready" else None
        return {**asdict(self), "bytesSaved": saved, "ratioToSource": ratio, "aiUsage": "none"}


@runtime_checkable
class LLMProvider(Protocol):
    """Reasoning provider for labels, prompts, plans, and other text/VLM tasks."""

    def complete(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        tools: Sequence[Mapping[str, Any]] | None = None,
        response_format: Mapping[str, Any] | None = None,
        **routing: Any,
    ) -> Mapping[str, Any]:
        """Return a chat completion response without owning pixel segmentation."""


@runtime_checkable
class SegmentationProvider(Protocol):
    """Pixel mask provider for ingest/correction-time object extraction."""

    def prepare(self, video_metadata: VideoInfo) -> None:
        """Initialize provider state for a source video."""

    def segment(
        self,
        frame_index: int,
        frame_bgr: np.ndarray,
        *,
        prompt_point: tuple[int, int] | None = None,
        prompt_box: tuple[int, int, int, int] | None = None,
    ) -> np.ndarray:
        """Return a binary uint8 mask where 255 is selected object."""

    def close(self) -> None:
        """Release provider resources."""


@runtime_checkable
class BatchSegmentationProvider(SegmentationProvider, Protocol):
    """Optional segmentation provider extension for GPU/provider batching."""

    def segment_batch(self, requests: Sequence[BatchSegmentationRequest]) -> Sequence[np.ndarray]:
        """Return masks for a batch of frame requests in request order."""


@runtime_checkable
class MattingProvider(Protocol):
    """Alpha refinement provider for turning binary masks into reusable assets."""

    def refine_alpha(self, frame_rgb: np.ndarray, binary_mask: np.ndarray) -> np.ndarray:
        """Return a uint8 alpha matte aligned to the input frame."""


@runtime_checkable
class RenderProvider(Protocol):
    """Preview/render provider for JSON transform playback over cached assets."""

    def render_preview(self, scene_graph: Mapping[str, Any]) -> Mapping[str, Any]:
        """Render or describe an interactive preview from cached layers."""

    def export_video(self, scene_graph: Mapping[str, Any], output_path: str | Path) -> Mapping[str, Any]:
        """Export a video from cached assets and JSON transforms."""


@runtime_checkable
class StorageProvider(Protocol):
    """Storage provider for cached raster/alpha assets and manifests."""

    def save_bytes(self, key: str, data: bytes, *, content_type: str | None = None) -> str:
        """Store bytes and return a provider-specific URI or key."""

    def load_bytes(self, key: str) -> bytes:
        """Load previously stored bytes."""

    def exists(self, key: str) -> bool:
        """Return whether a key exists."""


@runtime_checkable
class ExportProvider(Protocol):
    """Artifact export provider for MotionJSON manifests and delivery bundles."""

    def export(self, scene_graph: Mapping[str, Any], output_path: str | Path, *, format: str | None = None) -> Mapping[str, Any]:
        """Export a MotionJSON artifact or bundle."""
