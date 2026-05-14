"""Hosted SAM 2 video adapter sketch.

This module intentionally does not force Replicate as a hard dependency.
Install with `pip install replicate` and set `REPLICATE_API_TOKEN` to use it.

Replicate's public SAM 2 video model accepts click coordinates, labels, frames,
and object IDs. Its output shape may change, so production code should validate
and normalize the returned artifact into a PNG mask sequence before passing it to
`ExternalMaskSequenceProvider`.
"""
from __future__ import annotations

import os
from typing import Any

from ..providers.base import ProviderConfigError


def run_sam2_video_replicate(
    *,
    video_url_or_file: str,
    click_coordinates: str,
    click_labels: str = "1",
    click_frames: str = "0",
    click_object_ids: str = "object_0",
    api_token: str | None = None,
    model: str = "meta/sam-2-video",
    client: Any | None = None,
) -> Any:
    token = api_token or os.environ.get("REPLICATE_API_TOKEN")
    if not token:
        raise ProviderConfigError("Set REPLICATE_API_TOKEN or pass api_token before using the Replicate SAM2 stub.")
    if client is None:
        try:
            import replicate as client  # type: ignore
        except ImportError as exc:
            raise ProviderConfigError("Install replicate first: pip install replicate") from exc

    return client.run(
        model,
        input={
            "video": video_url_or_file,
            "click_coordinates": click_coordinates,
            "click_labels": click_labels,
            "click_frames": click_frames,
            "click_object_ids": click_object_ids,
        },
    )
