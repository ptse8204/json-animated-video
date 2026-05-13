from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .benchmark import benchmark_scene
from .exporters.scene_graph import write_json
from .exporters.web_manifest import write_web_asset_manifest
from .masks import ExternalMaskProvider, MotionMaskProvider, SAM2Provider, ThresholdMaskProvider
from .metrics import build_resource_profile
from .pipeline import run_pipeline


def parse_hsv(value: str) -> tuple[int, int, int]:
    parts = [int(x.strip()) for x in value.split(",")]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("HSV must be h,s,v")
    h, s, v = parts
    if not (0 <= h <= 179 and 0 <= s <= 255 and 0 <= v <= 255):
        raise argparse.ArgumentTypeError("HSV range is h=0..179, s/v=0..255 for OpenCV")
    return h, s, v


def parse_point(value: str | None) -> tuple[int, int] | None:
    if value is None:
        return None
    parts = [int(x.strip()) for x in value.split(",")]
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("Point must be x,y")
    return parts[0], parts[1]


def parse_box(value: str | None) -> tuple[int, int, int, int] | None:
    if value is None:
        return None
    parts = [int(x.strip()) for x in value.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("Box must be x,y,w,h")
    return parts[0], parts[1], parts[2], parts[3]


def add_extract_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("video", type=str, help="Input video file")
    p.add_argument("--out", type=str, default="out/motionjson", help="Output directory")
    p.add_argument("--mask-provider", "--mode", dest="mask_provider", choices=["external", "threshold", "motion", "sam2"], default="threshold")
    p.add_argument("--mask-dir", type=str, help="Mask directory for --mask-provider external")
    p.add_argument("--lower-hsv", type=parse_hsv, default=(0, 80, 80), help="Lower HSV threshold, e.g. 0,80,80")
    p.add_argument("--upper-hsv", type=parse_hsv, default=(12, 255, 255), help="Upper HSV threshold, e.g. 12,255,255")
    p.add_argument("--prompt-point", type=parse_point, default=None, help="SAM2 point prompt, x,y")
    p.add_argument("--prompt-box", type=parse_box, default=None, help="SAM2 box prompt, x,y,w,h")
    p.add_argument("--sample-fps", type=float, default=12.0)
    p.add_argument("--max-frames", type=int, default=None)
    p.add_argument("--object-id", type=str, default="object_0")
    p.add_argument("--label", type=str, default="selected_object")
    p.add_argument("--min-area", type=float, default=100.0)
    p.add_argument("--simplify", type=float, default=0.006, help="Contour simplification ratio")
    p.add_argument("--feather", type=int, default=0, help="Alpha feather kernel size; 0 disables")
    p.add_argument("--layer-padding", type=int, default=4, help="Padding around cropped reusable object layers")
    p.add_argument("--sprite-format", choices=["webp", "png"], default="webp", help="Sprite sheet image format")
    p.add_argument("--benchmark", action="store_true", help="Write benchmark_report.json comparing naive video processing with cached layer preview")
    p.add_argument("--benchmark-iterations", type=int, default=3, help="Number of benchmark playback passes")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Turn selected video objects into JSON-controlled reusable motion layers")
    sub = parser.add_subparsers(dest="command")
    extract = sub.add_parser("extract", help="Extract one selected object layer from a short video")
    add_extract_args(extract)
    return parser


def _legacy_extract_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert video object masks into JSON motion assets")
    add_extract_args(parser)
    return parser


def build_provider(args: argparse.Namespace):
    if args.mask_provider == "external":
        if not args.mask_dir:
            raise SystemExit("--mask-dir is required when --mask-provider external")
        return ExternalMaskProvider(args.mask_dir)
    if args.mask_provider == "motion":
        return MotionMaskProvider()
    if args.mask_provider == "sam2":
        return SAM2Provider(prompt_point=args.prompt_point, prompt_box=args.prompt_box)
    return ThresholdMaskProvider(args.lower_hsv, args.upper_hsv)


def run_extract(args: argparse.Namespace) -> dict:
    provider = build_provider(args)
    try:
        scene = run_pipeline(
            video_path=args.video,
            out_dir=args.out,
            mask_provider=provider,
            object_id=args.object_id,
            object_label=args.label,
            sample_fps=args.sample_fps,
            max_frames=args.max_frames,
            min_area=args.min_area,
            simplify_ratio=args.simplify,
            feather=args.feather,
            layer_padding=args.layer_padding,
            sprite_format=args.sprite_format,
        )
    except RuntimeError as exc:
        if args.mask_provider == "sam2":
            raise SystemExit(str(exc)) from exc
        raise

    out = Path(args.out)
    if args.benchmark:
        report = benchmark_scene(
            video_path=args.video,
            out_dir=out,
            scene=scene,
            iterations=args.benchmark_iterations,
        )
        write_json(out / "benchmark_report.json", report)
        profile = build_resource_profile(video_path=args.video, out_dir=out, object_id=args.object_id, scene=scene)
        profile["benchmarkSummary"] = report["comparison"]
        scene["resource_profile"] = profile
        write_json(out / "resource_profile.json", profile)
        write_json(out / "scene_graph.json", scene)
        write_web_asset_manifest(out / "web_asset_manifest.json", scene, object_id=args.object_id)
        print(f"Wrote {out / 'benchmark_report.json'}")

    print(f"Wrote {out / 'scene_graph.json'}")
    print(f"Wrote {out / 'object_motion.json'}")
    print(f"Wrote {out / 'web_asset_manifest.json'}")
    print(f"Wrote {out / 'resource_profile.json'}")
    print(f"Wrote {out / 'silhouette_lottie.json'}")
    print(f"Wrote {out / 'preview' / 'canvas_player.html'}")
    print(f"Frames: {scene['source']['sampledFrameCount']}; canvas: {scene['source']['width']}x{scene['source']['height']}")
    return scene


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] != "extract" and not argv[0].startswith("-"):
        args = _legacy_extract_parser().parse_args(argv)
        run_extract(args)
        return

    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "extract":
        run_extract(args)
        return
    parser.print_help()


if __name__ == "__main__":
    main()
