from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..masks import BaseMaskProvider, MaskProvider
from ..video import VideoInfo
from .base import SegmentationProvider


@dataclass
class MaskProviderSegmentationAdapter:
    """Expose an existing MaskProvider through the SegmentationProvider contract."""

    mask_provider: MaskProvider

    def prepare(self, video_metadata: VideoInfo) -> None:
        self.mask_provider.prepare(video_metadata)

    def segment(
        self,
        frame_index: int,
        frame_bgr: np.ndarray,
        *,
        prompt_point: tuple[int, int] | None = None,
        prompt_box: tuple[int, int, int, int] | None = None,
    ) -> np.ndarray:
        return self.mask_provider.get_mask(frame_index, frame_bgr)

    def close(self) -> None:
        self.mask_provider.close()


@dataclass
class SegmentationMaskProvider(BaseMaskProvider):
    """Let a SegmentationProvider run in the existing extraction pipeline."""

    segmentation_provider: SegmentationProvider
    prompt_point: tuple[int, int] | None = None
    prompt_box: tuple[int, int, int, int] | None = None

    def prepare(self, video_metadata: VideoInfo) -> None:
        super().prepare(video_metadata)
        self.segmentation_provider.prepare(video_metadata)

    def get_mask(self, frame_index: int, frame_bgr: np.ndarray) -> np.ndarray:
        return self.segmentation_provider.segment(
            frame_index,
            frame_bgr,
            prompt_point=self.prompt_point,
            prompt_box=self.prompt_box,
        )

    def close(self) -> None:
        self.segmentation_provider.close()


def as_segmentation_provider(mask_provider: MaskProvider) -> SegmentationProvider:
    """Wrap a legacy mask provider unless it already implements segmentation."""

    if isinstance(mask_provider, SegmentationProvider):
        return mask_provider
    return MaskProviderSegmentationAdapter(mask_provider)
