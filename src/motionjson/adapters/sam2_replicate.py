"""Hosted SAM 2 video adapter sketch.

This module intentionally does not force Replicate as a hard dependency.
Install with `pip install replicate` and set `REPLICATE_API_TOKEN` to use it.

Replicate's public SAM 2 video model accepts click coordinates, labels, frames,
and object IDs. Its output shape may change, so production code should validate
and normalize the returned artifact into a PNG mask sequence before passing it to
`ExternalMaskSequenceProvider`.
"""
from __future__ import annotations

from typing import Any


def run_sam2_video_replicate(
    *,
    video_url_or_file: str,
    click_coordinates: str,
    click_labels: str = "1",
    click_frames: str = "0",
    click_object_ids: str = "object_0",
) -> Any:
    try:
        import replicate  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Install replicate first: pip install replicate") from exc

    return replicate.run(
        "meta/sam-2-video",
        input={
            "video": video_url_or_file,
            "click_coordinates": click_coordinates,
            "click_labels": click_labels,
            "click_frames": click_frames,
            "click_object_ids": click_object_ids,
        },
    )
