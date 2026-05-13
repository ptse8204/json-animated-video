from __future__ import annotations

from pathlib import Path
from typing import Any

from .scene_graph import write_json
from ..vectorize import polygon_to_lottie_shape


def build_silhouette_lottie(
    width: int,
    height: int,
    fps: float,
    frames: list[dict[str, Any]],
    fill_rgb: tuple[float, float, float] = (1.0, 0.1, 0.1),
) -> dict[str, Any]:
    """Create a minimal Lottie JSON silhouette animation.

    This uses hold keyframes, so each sampled frame can have a different polygon vertex count.
    It is meant for masks/outlines, not high-fidelity photoreal video.
    """
    path_keyframes: list[dict[str, Any]] = []
    last_shape = {"i": [], "o": [], "v": [], "c": True}

    for f in frames:
        if f.get("visible") and f.get("polygon"):
            last_shape = polygon_to_lottie_shape(f["polygon"])
        path_keyframes.append({"t": int(f["out_index"]), "s": [last_shape], "h": 1})

    if frames:
        path_keyframes.append({"t": int(frames[-1]["out_index"]) + 1, "s": [last_shape], "h": 1})

    return {
        "v": "5.10.0",
        "fr": fps,
        "ip": 0,
        "op": max(1, len(frames)),
        "w": width,
        "h": height,
        "nm": "motionjson_silhouette",
        "ddd": 0,
        "assets": [],
        "layers": [
            {
                "ddd": 0,
                "ind": 1,
                "ty": 4,
                "nm": "object_silhouette",
                "sr": 1,
                "ks": {
                    "o": {"a": 0, "k": 100},
                    "r": {"a": 0, "k": 0},
                    "p": {"a": 0, "k": [0, 0, 0]},
                    "a": {"a": 0, "k": [0, 0, 0]},
                    "s": {"a": 0, "k": [100, 100, 100]},
                },
                "ao": 0,
                "shapes": [
                    {
                        "ty": "gr",
                        "it": [
                            {"ty": "sh", "ks": {"a": 1, "k": path_keyframes}, "nm": "mask_path"},
                            {"ty": "fl", "c": {"a": 0, "k": [*fill_rgb, 1]}, "o": {"a": 0, "k": 100}, "r": 1, "nm": "fill"},
                            {"ty": "tr", "p": {"a": 0, "k": [0, 0]}, "a": {"a": 0, "k": [0, 0]}, "s": {"a": 0, "k": [100, 100]}, "r": {"a": 0, "k": 0}, "o": {"a": 0, "k": 100}, "sk": {"a": 0, "k": 0}, "sa": {"a": 0, "k": 0}},
                        ],
                        "nm": "object_group",
                    }
                ],
                "ip": 0,
                "op": max(1, len(frames)),
                "st": 0,
                "bm": 0,
            }
        ],
    }


def write_silhouette_lottie(path: str | Path, *, width: int, height: int, fps: float, frames: list[dict[str, Any]]) -> None:
    write_json(path, build_silhouette_lottie(width, height, fps, frames))
