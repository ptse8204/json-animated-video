from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Protocol

import cv2
import numpy as np
from PIL import Image

from .video import Frame, VideoInfo


class MaskProvider(Protocol):
    """Object mask provider interface used by the extraction pipeline.

    Implementations can be local demo providers, external mask importers, or
    neural segmentation adapters. Masks are uint8 arrays where 255 means selected
    object and 0 means background.
    """

    def prepare(self, video_metadata: VideoInfo) -> None:
        """Initialize provider state for a source video."""

    def get_mask(self, frame_index: int, frame_bgr: np.ndarray) -> np.ndarray:
        """Return a binary mask for one source frame."""

    def close(self) -> None:
        """Release provider resources."""


class BaseMaskProvider:
    def prepare(self, video_metadata: VideoInfo) -> None:
        self.video_metadata = video_metadata

    def close(self) -> None:
        return None

    def masks(self, frames: Iterable[Frame]) -> Iterable[np.ndarray]:
        """Compatibility helper for older pipeline code."""
        metadata: VideoInfo | None = getattr(self, "video_metadata", None)
        if metadata is None:
            first_frame_list = list(frames)
            if not first_frame_list:
                return iter(())
            height, width = first_frame_list[0].rgb.shape[:2]
            self.prepare(VideoInfo(width=width, height=height, source_fps=30, sample_fps=30, total_source_frames=len(first_frame_list)))
            frames = first_frame_list
        for frame in frames:
            bgr = cv2.cvtColor(frame.rgb, cv2.COLOR_RGB2BGR)
            yield self.get_mask(frame.index, bgr)


def _binary(mask: np.ndarray) -> np.ndarray:
    if mask.ndim == 3:
        mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
    return np.where(mask > 127, 255, 0).astype(np.uint8)


def _morph(mask: np.ndarray, open_size: int = 3, close_size: int = 5) -> np.ndarray:
    mask = _binary(mask)
    if open_size > 1:
        kernel = np.ones((open_size, open_size), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    if close_size > 1:
        kernel = np.ones((close_size, close_size), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    return _binary(mask)


@dataclass
class ThresholdMaskProvider(BaseMaskProvider):
    """Demo provider: HSV threshold for simple videos and color-key tests."""

    lower_hsv: tuple[int, int, int]
    upper_hsv: tuple[int, int, int]

    def get_mask(self, frame_index: int, frame_bgr: np.ndarray) -> np.ndarray:
        hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
        lower = np.array(self.lower_hsv, dtype=np.uint8)
        upper = np.array(self.upper_hsv, dtype=np.uint8)
        return _morph(cv2.inRange(hsv, lower, upper))


@dataclass
class MotionMaskProvider(BaseMaskProvider):
    """CPU demo provider: rough moving-foreground masks via background subtraction."""

    history: int = 120
    var_threshold: float = 25.0
    detect_shadows: bool = False
    subtractor: cv2.BackgroundSubtractorMOG2 | None = field(default=None, init=False)

    def prepare(self, video_metadata: VideoInfo) -> None:
        super().prepare(video_metadata)
        self.subtractor = cv2.createBackgroundSubtractorMOG2(
            history=self.history,
            varThreshold=self.var_threshold,
            detectShadows=self.detect_shadows,
        )

    def get_mask(self, frame_index: int, frame_bgr: np.ndarray) -> np.ndarray:
        if self.subtractor is None:
            raise RuntimeError("MotionMaskProvider.prepare() must be called before get_mask().")
        return _morph(self.subtractor.apply(frame_bgr))


@dataclass
class ExternalMaskProvider(BaseMaskProvider):
    """Use precomputed masks from SAM2, Runway, After Effects, DaVinci, etc."""

    mask_dir: str | Path
    files: list[Path] = field(default_factory=list, init=False)
    cursor: int = field(default=0, init=False)

    def prepare(self, video_metadata: VideoInfo) -> None:
        super().prepare(video_metadata)
        directory = Path(self.mask_dir)
        patterns = ("*.png", "*.jpg", "*.jpeg", "*.webp")
        files: list[Path] = []
        for pattern in patterns:
            files.extend(sorted(directory.glob(pattern)))
        if not files:
            raise FileNotFoundError(f"No mask images found in {directory}. Use threshold, motion, or provide PNG/JPG/WebP masks.")
        self.files = sorted(files)
        self.cursor = 0

    def get_mask(self, frame_index: int, frame_bgr: np.ndarray) -> np.ndarray:
        if not self.files:
            raise RuntimeError("ExternalMaskProvider.prepare() must be called before get_mask().")
        file_index = min(self.cursor, len(self.files) - 1)
        self.cursor += 1
        image = Image.open(self.files[file_index]).convert("L")
        arr = np.array(image)
        height, width = frame_bgr.shape[:2]
        if arr.shape[:2] != (height, width):
            arr = cv2.resize(arr, (width, height), interpolation=cv2.INTER_NEAREST)
        return _binary(arr)


@dataclass
class SAM2Provider(BaseMaskProvider):
    """Future neural segmentation adapter stub.

    This class intentionally does not hardcode a paid API call. A production
    implementation should inject a provider client here or subclass this adapter.
    """

    prompt_point: tuple[int, int] | None = None
    prompt_box: tuple[int, int, int, int] | None = None
    client: object | None = None

    def prepare(self, video_metadata: VideoInfo) -> None:
        super().prepare(video_metadata)
        if self.client is None:
            raise RuntimeError(
                "SAM2 mask provider is configured as a stub. No SAM2 client or credentials were provided. "
                "Use --mask-provider threshold, --mask-provider motion, or --mask-provider external for the local MVP, "
                "or inject a SAM2 client in src/motionjson/adapters/sam2_provider.py."
            )

    def get_mask(self, frame_index: int, frame_bgr: np.ndarray) -> np.ndarray:
        raise NotImplementedError("SAM2Provider.get_mask() is a TODO until a concrete SAM2 client is configured.")


# Backward-compatible names from the starter prototype.
ColorThresholdMaskProvider = ThresholdMaskProvider
ExternalMaskSequenceProvider = ExternalMaskProvider
