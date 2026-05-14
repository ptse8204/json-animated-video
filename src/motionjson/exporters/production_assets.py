from __future__ import annotations

import shutil
import subprocess
import tempfile
import warnings
from pathlib import Path
from typing import Any

from PIL import Image, features

from ..layers import write_spritesheet


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


def _safe_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except FileNotFoundError:
        return 0


def _visible_cutout_paths(out_dir: Path, motion: list[dict[str, Any]]) -> list[Path]:
    paths: list[Path] = []
    for entry in motion:
        asset = entry.get("asset")
        if entry.get("visible") and asset:
            path = out_dir / asset
            if path.exists():
                paths.append(path)
    return paths


def pillow_supports_avif() -> bool:
    """Return whether this Pillow build can write AVIF images."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            if features.check("avif"):
                return True
    except Exception:
        return False
    return ".avif" in Image.registered_extensions()


def _sprite_asset_metadata(
    *,
    sprite_meta: dict[str, Any] | None,
    output_path: Path,
    out_dir: Path,
    asset_type: str,
    format_name: str,
    mime_type: str,
) -> dict[str, Any]:
    if not sprite_meta or not output_path.exists():
        return {
            "type": asset_type,
            "status": "error",
            "format": format_name,
            "mimeType": mime_type,
            "path": None,
            "bytes": 0,
            "reason": "sprite atlas was not written",
        }

    return {
        "type": asset_type,
        "status": "ready",
        "format": format_name,
        "mimeType": mime_type,
        "path": _rel(output_path, out_dir),
        "bytes": _safe_size(output_path),
        "width": sprite_meta["width"],
        "height": sprite_meta["height"],
        "columns": sprite_meta["columns"],
        "rows": sprite_meta["rows"],
        "cellWidth": sprite_meta["cellWidth"],
        "cellHeight": sprite_meta["cellHeight"],
        "frames": sprite_meta["frames"],
        "source": "cached_rgba_cutout_png_sequence",
    }


def _export_webp_sprite_atlas(*, cutout_paths: list[Path], output_path: Path, out_dir: Path) -> dict[str, Any]:
    if not cutout_paths:
        return {
            "type": "webp_sprite_atlas",
            "status": "skipped",
            "format": "webp",
            "mimeType": "image/webp",
            "path": None,
            "bytes": 0,
            "reason": "no visible cached cutouts",
        }
    sprite_meta = write_spritesheet(cutout_paths=cutout_paths, output_path=output_path, format="WEBP")
    return _sprite_asset_metadata(
        sprite_meta=sprite_meta,
        output_path=output_path,
        out_dir=out_dir,
        asset_type="webp_sprite_atlas",
        format_name="webp",
        mime_type="image/webp",
    )


def _export_avif_sprite_atlas(
    *,
    cutout_paths: list[Path],
    output_path: Path,
    out_dir: Path,
    requested: bool,
) -> dict[str, Any]:
    base = {
        "type": "avif_sprite_atlas",
        "format": "avif",
        "mimeType": "image/avif",
        "path": None,
        "bytes": 0,
    }
    if not requested:
        return {**base, "status": "skipped", "reason": "not requested"}
    if not cutout_paths:
        return {**base, "status": "skipped", "reason": "no visible cached cutouts"}
    if not pillow_supports_avif():
        return {**base, "status": "unsupported", "reason": "Pillow AVIF encoder is not available"}

    try:
        sprite_meta = write_spritesheet(cutout_paths=cutout_paths, output_path=output_path, format="AVIF")
    except Exception as exc:
        return {**base, "status": "error", "reason": str(exc)}
    return _sprite_asset_metadata(
        sprite_meta=sprite_meta,
        output_path=output_path,
        out_dir=out_dir,
        asset_type="avif_sprite_atlas",
        format_name="avif",
        mime_type="image/avif",
    )


def _write_transparent_canvas_frames(
    *,
    out_dir: Path,
    motion: list[dict[str, Any]],
    frame_dir: Path,
    width: int,
    height: int,
) -> int:
    frame_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for index, entry in enumerate(motion, start=1):
        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        asset = entry.get("asset")
        if entry.get("visible") and asset:
            cutout_path = out_dir / asset
            if cutout_path.exists():
                cutout = Image.open(cutout_path).convert("RGBA")
                canvas.alpha_composite(
                    cutout,
                    (int(entry.get("x") or 0), int(entry.get("y") or 0)),
                )
        canvas.save(frame_dir / f"frame_{index:06d}.png")
        written += 1
    return written


def _export_transparent_webm(
    *,
    out_dir: Path,
    production_dir: Path,
    motion: list[dict[str, Any]],
    width: int,
    height: int,
    fps: float,
) -> dict[str, Any]:
    output_path = production_dir / "transparent_layer.webm"
    return export_transparent_webm_object(
        out_dir=out_dir,
        output_path=output_path,
        motion=motion,
        width=width,
        height=height,
        fps=fps,
    )


def export_transparent_webm_object(
    *,
    out_dir: str | Path,
    output_path: str | Path,
    motion: list[dict[str, Any]],
    width: int,
    height: int,
    fps: float,
) -> dict[str, Any]:
    """Write a transparent VP9/WebM object layer from cached cutouts and JSON transforms."""
    out_dir = Path(out_dir)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    base = {
        "type": "transparent_webm_vp9_alpha",
        "format": "webm",
        "mimeType": "video/webm; codecs=vp9",
        "path": None,
        "bytes": 0,
        "width": width,
        "height": height,
        "fps": fps,
        "frameCount": len(motion),
        "encoder": "ffmpeg",
        "source": "cached_rgba_cutout_png_sequence_and_json_transforms",
        "cachedSource": "cached_rgba_cutout_png_sequence",
        "aiUsage": "none",
    }
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return {**base, "status": "unavailable", "reason": "ffmpeg executable was not found"}
    if not motion:
        return {**base, "status": "skipped", "reason": "no motion frames"}

    with tempfile.TemporaryDirectory(prefix="motionjson_webm_") as tmp:
        frame_dir = Path(tmp)
        frame_count = _write_transparent_canvas_frames(
            out_dir=out_dir,
            motion=motion,
            frame_dir=frame_dir,
            width=width,
            height=height,
        )
        if frame_count == 0:
            return {**base, "status": "skipped", "reason": "no transparent canvas frames were written"}

        cmd = [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-framerate",
            str(fps),
            "-i",
            str(frame_dir / "frame_%06d.png"),
            "-c:v",
            "libvpx-vp9",
            "-pix_fmt",
            "yuva420p",
            "-auto-alt-ref",
            "0",
            "-an",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            return {
                **base,
                "status": "error",
                "reason": (result.stderr or result.stdout or "ffmpeg failed").strip(),
            }

    if not output_path.exists() or output_path.stat().st_size == 0:
        return {**base, "status": "error", "reason": "ffmpeg completed but produced no output bytes"}

    return {
        **base,
        "status": "ready",
        "path": _rel(output_path, out_dir),
        "bytes": _safe_size(output_path),
    }


def export_production_assets(
    *,
    out_dir: str | Path,
    object_id: str,
    motion: list[dict[str, Any]],
    canvas_width: int,
    canvas_height: int,
    fps: float,
    include_avif: bool = False,
) -> dict[str, Any]:
    """Write production assets derived only from cached cutouts and motion JSON."""
    out_dir = Path(out_dir)
    production_dir = out_dir / "objects" / object_id / "production"
    production_dir.mkdir(parents=True, exist_ok=True)
    for stale in ("sprite_atlas.webp", "sprite_atlas.avif", "transparent_layer.webm"):
        path = production_dir / stale
        if path.exists():
            path.unlink()

    cutout_paths = _visible_cutout_paths(out_dir, motion)
    webp = _export_webp_sprite_atlas(
        cutout_paths=cutout_paths,
        output_path=production_dir / "sprite_atlas.webp",
        out_dir=out_dir,
    )
    avif = _export_avif_sprite_atlas(
        cutout_paths=cutout_paths,
        output_path=production_dir / "sprite_atlas.avif",
        out_dir=out_dir,
        requested=include_avif,
    )
    webm = _export_transparent_webm(
        out_dir=out_dir,
        production_dir=production_dir,
        motion=motion,
        width=canvas_width,
        height=canvas_height,
        fps=fps,
    )

    statuses = [webp["status"], avif["status"], webm["status"]]
    ready_count = sum(1 for status in statuses if status == "ready")
    return {
        "mode": "production",
        "status": "ready" if ready_count else "no_ready_assets",
        "source": "cached_cutout_pngs_and_motion_json",
        "aiUsage": "none",
        "assets": {
            "webpSpriteAtlas": webp,
            "transparentWebm": webm,
            "avifSpriteAtlas": avif,
        },
    }
