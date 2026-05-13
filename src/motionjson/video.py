from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import cv2
import numpy as np


@dataclass(frozen=True)
class Frame:
    index: int          # original video frame index
    out_index: int      # sampled frame index
    time_sec: float
    rgb: np.ndarray     # H x W x 3, RGB uint8


@dataclass(frozen=True)
class VideoInfo:
    width: int
    height: int
    source_fps: float
    sample_fps: float
    total_source_frames: int


def iter_sampled_frames(
    video_path: str | Path,
    sample_fps: float | None = None,
    max_frames: int | None = None,
) -> tuple[VideoInfo, Iterator[Frame]]:
    """Return video metadata and a generator of sampled RGB frames."""
    path = Path(video_path)
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise FileNotFoundError(f"Could not open video: {path}")

    source_fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

    if sample_fps is None or sample_fps <= 0 or sample_fps >= source_fps:
        step = 1
        effective_fps = source_fps
    else:
        step = max(1, round(source_fps / sample_fps))
        effective_fps = source_fps / step

    info = VideoInfo(width=width, height=height, source_fps=source_fps, sample_fps=effective_fps, total_source_frames=total)

    def gen() -> Iterator[Frame]:
        out_idx = 0
        src_idx = 0
        while True:
            ok, bgr = cap.read()
            if not ok:
                break
            if src_idx % step == 0:
                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                yield Frame(index=src_idx, out_index=out_idx, time_sec=src_idx / source_fps, rgb=rgb)
                out_idx += 1
                if max_frames is not None and out_idx >= max_frames:
                    break
            src_idx += 1
        cap.release()

    return info, gen()
