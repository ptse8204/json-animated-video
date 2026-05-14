from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from .benchmark import benchmark_scene
from .corrections import build_correction_request, correct_output_dir
from .exporters.final_render import export_mp4, final_export_entry, load_scene, write_final_export_manifest
from .exporters.production_assets import export_transparent_webm_object
from .exporters.remotion import write_remotion_plan
from .exporters.scene_graph import write_json
from .exporters.website_package import export_website_package
from .masks import ExternalMaskProvider, MotionMaskProvider, SAM2Provider, ThresholdMaskProvider
from .pipeline import run_pipeline, write_profiled_outputs
from .providers.mask_cache import MaskCache
from .providers.sam2 import HostedSAM2SegmentationProvider, LocalSAM2SegmentationProvider
from .providers.segmentation import MaskProviderSegmentationAdapter, SegmentationMaskProvider
from .validation import MotionJSONValidationError, validate_document, validate_path


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


def parse_json_object(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(f"Expected JSON object: {exc}") from exc
    if not isinstance(parsed, dict):
        raise argparse.ArgumentTypeError("Expected JSON object")
    return parsed


def parse_brush_points(value: str | None) -> list[list[int]]:
    if not value:
        return []
    points: list[list[int]] = []
    for raw_point in value.split(";"):
        parts = [int(x.strip()) for x in raw_point.split(",")]
        if len(parts) != 2:
            raise argparse.ArgumentTypeError("Brush points must be x,y;x,y")
        points.append([parts[0], parts[1]])
    return points


def add_extract_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("video", type=str, help="Input video file")
    p.add_argument("--out", type=str, default="out/motionjson", help="Output directory")
    p.add_argument(
        "--mask-provider",
        "--mode",
        dest="mask_provider",
        choices=["external", "threshold", "motion", "sam2", "sam2-local", "sam2-hosted"],
        default="threshold",
    )
    p.add_argument("--mask-dir", type=str, help="Mask directory for --mask-provider external")
    p.add_argument("--lower-hsv", type=parse_hsv, default=(0, 80, 80), help="Lower HSV threshold, e.g. 0,80,80")
    p.add_argument("--upper-hsv", type=parse_hsv, default=(12, 255, 255), help="Upper HSV threshold, e.g. 12,255,255")
    p.add_argument("--prompt-point", type=parse_point, default=None, help="SAM2 point prompt, x,y")
    p.add_argument("--prompt-box", type=parse_box, default=None, help="SAM2 box prompt, x,y,w,h")
    p.add_argument("--sam2-checkpoint", type=str, default=None, help="Local SAM2 checkpoint path for --mask-provider sam2-local")
    p.add_argument("--sam2-config", "--sam2-model-config", dest="sam2_model_config", type=str, default=None, help="Local SAM2 model config for --mask-provider sam2-local")
    p.add_argument("--sam2-device", type=str, default=None, help="Local SAM2 device, e.g. cpu, cuda, mps")
    p.add_argument("--sam2-prompt-frame", type=int, default=0, help="Frame index where the SAM2 prompt is applied")
    p.add_argument("--sam2-endpoint", type=str, default=None, help="Hosted SAM2 endpoint for --mask-provider sam2-hosted")
    p.add_argument("--sam2-auth-env", type=str, default="HOSTED_SEGMENTATION_API_KEY", help="Env var containing hosted SAM2 auth token")
    p.add_argument("--sam2-endpoint-env", type=str, default="HOSTED_SEGMENTATION_URL", help="Env var containing hosted SAM2 endpoint")
    p.add_argument("--sam2-hosted-config", type=parse_json_object, default={}, help='Hosted SAM2 JSON config, e.g. {"model":"sam2"}')
    p.add_argument("--sam2-hosted-allow-network", action="store_true", help="Allow real hosted SAM2 network calls when endpoint and auth are configured")
    p.add_argument("--mask-cache-dir", type=str, default=".motionjson-cache/masks", help="Ignored cache directory for SAM2 binary PNG masks")
    p.add_argument("--no-mask-cache", action="store_true", help="Disable SAM2 mask cache for this extraction")
    p.add_argument("--sample-fps", type=float, default=12.0)
    p.add_argument("--max-frames", type=int, default=None)
    p.add_argument("--object-id", type=str, default="object_0")
    p.add_argument("--label", type=str, default="selected_object")
    p.add_argument("--min-area", type=float, default=100.0)
    p.add_argument("--simplify", type=float, default=0.006, help="Contour simplification ratio")
    p.add_argument("--feather", type=int, default=0, help="Alpha feather kernel size; 0 disables")
    p.add_argument("--layer-padding", type=int, default=4, help="Padding around cropped reusable object layers")
    p.add_argument("--sprite-format", choices=["webp", "png"], default="webp", help="Sprite sheet image format")
    p.add_argument("--output-mode", choices=["authoring", "production", "both"], default="authoring", help="authoring keeps current debug assets; production/both add production asset exports")
    p.add_argument("--production-avif", action="store_true", help="Try to write an AVIF sprite atlas when Pillow AVIF encoding is available")
    p.add_argument("--benchmark", action="store_true", help="Write benchmark_report.json comparing naive video processing with cached layer preview")
    p.add_argument("--benchmark-iterations", type=int, default=3, help="Number of benchmark playback passes")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Turn selected video objects into JSON-controlled reusable motion layers")
    sub = parser.add_subparsers(dest="command")
    extract = sub.add_parser("extract", help="Extract one selected object layer from a short video")
    add_extract_args(extract)
    validate = sub.add_parser("validate", help="Validate a MotionJSON file or output directory")
    validate.add_argument("path", type=str, help="MotionJSON JSON file or output directory")
    validate.add_argument("--object-id", type=str, default="object_0", help="Object id to require when validating an output directory")
    correct = sub.add_parser("correct", help="Apply local deterministic mask corrections to an existing extraction")
    add_correct_args(correct)
    export = sub.add_parser("export", help="Export final video, object alpha video, website package, or adapter plan")
    add_export_args(export)
    return parser


def _legacy_extract_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert video object masks into JSON motion assets")
    add_extract_args(parser)
    return parser


def add_export_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("out_dir", type=str, help="Existing MotionJSON extraction output directory")
    p.add_argument(
        "--format",
        choices=["mp4", "webm-alpha", "website-zip", "remotion-plan", "all"],
        required=True,
        help="Final export format",
    )
    p.add_argument("--out", type=str, required=True, help="Output file for one format, or output directory for --format all")
    p.add_argument("--object-id", type=str, default="object_0", help="Object id for object-specific exports")
    p.add_argument("--background-color", type=str, default="#fbfaf6", help="Final render background color")
    p.add_argument("--editor-state", type=str, default=None, help="Optional Phase 7 timeline editor-state JSON")


def add_correct_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("out_dir", type=str, help="Existing MotionJSON extraction output directory")
    p.add_argument("--out", type=str, default=None, help="Corrected output directory; defaults to <out_dir>_corrected")
    p.add_argument("--in-place", action="store_true", help="Overwrite the input output directory with corrected assets")
    p.add_argument("--object-id", type=str, default="object_0", help="Object id to correct")
    p.add_argument("--request", type=str, default=None, help="Correction request JSON file")
    p.add_argument("--add-point", action="append", type=parse_point, default=[], help="Add mask point x,y")
    p.add_argument("--remove-point", action="append", type=parse_point, default=[], help="Remove mask point x,y")
    p.add_argument("--box", action="append", type=parse_box, default=[], help="Box correction x,y,w,h")
    p.add_argument("--box-mode", choices=["constrain", "replace", "add", "remove"], default="constrain", help="How --box modifies masks")
    p.add_argument("--brush", action="append", type=parse_brush_points, default=[], help="Brush stroke points x,y;x,y")
    p.add_argument("--brush-mode", choices=["add", "remove"], default="add", help="How --brush modifies masks")
    p.add_argument("--frame", type=int, default=1, help="1-based frame for inline correction operations")
    p.add_argument("--radius", type=int, default=10, help="Point/brush radius in pixels")
    p.add_argument("--propagate", action="store_true", help="Apply inline operations across sampled frames")
    p.add_argument("--propagation-mode", choices=["same_coordinates", "centroid_delta"], default="same_coordinates", help="How propagated corrections move across frames")
    p.add_argument("--propagate-window", type=int, default=None, help="Limit propagated inline corrections to +/- this many sampled frames around --frame")
    p.add_argument("--smooth", action="store_true", help="Apply deterministic temporal mask smoothing after corrections")
    p.add_argument("--smooth-radius", type=int, default=1, help="Temporal smoothing radius in sampled frames")


def build_provider(args: argparse.Namespace):
    if args.mask_provider == "external":
        if not args.mask_dir:
            raise SystemExit("--mask-dir is required when --mask-provider external")
        mask_provider = ExternalMaskProvider(args.mask_dir)
    elif args.mask_provider == "motion":
        mask_provider = MotionMaskProvider()
    elif args.mask_provider == "sam2":
        mask_provider = SAM2Provider(prompt_point=args.prompt_point, prompt_box=args.prompt_box)
    elif args.mask_provider == "sam2-local":
        mask_cache = None if args.no_mask_cache else MaskCache(args.mask_cache_dir)
        checkpoint = args.sam2_checkpoint or os.environ.get("SAM2_LOCAL_CHECKPOINT")
        model_config = args.sam2_model_config or os.environ.get("SAM2_LOCAL_CONFIG")
        device = args.sam2_device or os.environ.get("SAM2_LOCAL_DEVICE", "cpu")
        segmentation_provider = LocalSAM2SegmentationProvider(
            source_video=args.video,
            checkpoint=checkpoint,
            model_config=model_config,
            device=device,
            prompt_frame_index=args.sam2_prompt_frame,
            object_id=args.object_id,
            prompt_point=args.prompt_point,
            prompt_box=args.prompt_box,
            mask_cache=mask_cache,
        )
        return SegmentationMaskProvider(
            segmentation_provider,
            prompt_point=args.prompt_point,
            prompt_box=args.prompt_box,
        )
    elif args.mask_provider == "sam2-hosted":
        mask_cache = None if args.no_mask_cache else MaskCache(args.mask_cache_dir)
        segmentation_provider = HostedSAM2SegmentationProvider(
            source_video=args.video,
            endpoint=args.sam2_endpoint,
            config=args.sam2_hosted_config,
            auth_env=args.sam2_auth_env,
            endpoint_env=args.sam2_endpoint_env,
            prompt_frame_index=args.sam2_prompt_frame,
            object_id=args.object_id,
            prompt_point=args.prompt_point,
            prompt_box=args.prompt_box,
            allow_network=args.sam2_hosted_allow_network,
            mask_cache=mask_cache,
        )
        return SegmentationMaskProvider(
            segmentation_provider,
            prompt_point=args.prompt_point,
            prompt_box=args.prompt_box,
        )
    else:
        mask_provider = ThresholdMaskProvider(args.lower_hsv, args.upper_hsv)

    segmentation_provider = MaskProviderSegmentationAdapter(mask_provider)
    return SegmentationMaskProvider(
        segmentation_provider,
        prompt_point=args.prompt_point,
        prompt_box=args.prompt_box,
    )


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
            output_mode=args.output_mode,
            production_avif=args.production_avif,
        )
    except RuntimeError as exc:
        if args.mask_provider in {"sam2", "sam2-local", "sam2-hosted"}:
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
        write_profiled_outputs(
            out_dir=out,
            video_path=Path(args.video),
            object_id=args.object_id,
            scene=scene,
            profile_updates={"benchmarkSummary": report["comparison"]},
        )
        print(f"Wrote {out / 'benchmark_report.json'}")

    print(f"Wrote {out / 'scene_graph.json'}")
    print(f"Wrote {out / 'object_motion.json'}")
    print(f"Wrote {out / 'web_asset_manifest.json'}")
    print(f"Wrote {out / 'resource_profile.json'}")
    print(f"Wrote {out / 'silhouette_lottie.json'}")
    print(f"Wrote {out / 'preview' / 'canvas_player.html'}")
    print(f"Wrote {out / 'preview' / 'pixi_player.html'}")
    print(f"Wrote {out / 'preview' / 'plain_js_embed.html'}")
    print(f"Wrote {out / 'preview' / 'timeline_editor.html'}")
    print(f"Wrote {out / 'preview' / 'runtime'}")
    print(f"Frames: {scene['source']['sampledFrameCount']}; canvas: {scene['source']['width']}x{scene['source']['height']}")
    return scene


def run_validate(args: argparse.Namespace) -> None:
    result = validate_path(args.path, object_id=args.object_id)
    for issue in result.issues:
        print(issue.format(), file=sys.stderr)
    if result.ok:
        print(f"Validated {len(result.checked)} MotionJSON file(s); skipped {len(result.skipped)} auxiliary JSON file(s).")
        return
    raise SystemExit(1)


def _default_corrected_out_dir(source: Path) -> Path:
    return source.with_name(f"{source.name}_corrected")


def _load_correction_request(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    try:
        request = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid correction request JSON: {exc}") from exc
    if not isinstance(request, dict):
        raise SystemExit("--request must point to a JSON object")
    return request


def _validate_correction_request(request: dict[str, Any]) -> dict[str, Any]:
    try:
        errors = validate_document(request, schema_id="motionjson.correction_request.v0.1")
    except MotionJSONValidationError as exc:
        raise SystemExit(f"Invalid correction request: {exc}") from exc
    if errors:
        details = "; ".join(error.message for error in errors[:4])
        raise SystemExit(f"Invalid correction request: {details}")
    return request


def _inline_correction_operations(args: argparse.Namespace) -> list[dict[str, Any]]:
    operations: list[dict[str, Any]] = []
    for point in args.add_point:
        operations.append({"type": "add_point", "x": point[0], "y": point[1], "frame": args.frame, "radius": args.radius})
    for point in args.remove_point:
        operations.append({"type": "remove_point", "x": point[0], "y": point[1], "frame": args.frame, "radius": args.radius})
    for box in args.box:
        operations.append({"type": "box", "x": box[0], "y": box[1], "w": box[2], "h": box[3], "frame": args.frame, "mode": args.box_mode})
    for points in args.brush:
        operations.append({"type": "brush", "points": points, "frame": args.frame, "radius": args.radius, "mode": args.brush_mode})
    return operations


def build_correction_request_from_args(args: argparse.Namespace) -> dict[str, Any]:
    request = _load_correction_request(args.request)
    inline_operations = _inline_correction_operations(args)
    if request and inline_operations:
        raise SystemExit("Use either --request or inline correction operations, not both")
    if request:
        request.setdefault("objectId", args.object_id)
        request.setdefault("schema", "motionjson.correction_request.v0.1")
        request.setdefault("operations", [])
        request.setdefault("propagation", {"enabled": False, "mode": "same_coordinates"})
        request.setdefault("temporalSmoothing", {"enabled": False, "radius": args.smooth_radius, "threshold": 0.5})
        request.setdefault("aiUsage", "none")
        return _validate_correction_request(request)
    if not inline_operations and not args.smooth:
        raise SystemExit("Provide --request, --add-point, --remove-point, --box, --brush, or --smooth")
    frame_range = None
    if args.propagate and args.propagate_window is not None:
        window = max(0, int(args.propagate_window))
        frame_range = [max(1, int(args.frame) - window), int(args.frame) + window]
    request = build_correction_request(
        object_id=args.object_id,
        operations=inline_operations,
        propagate=args.propagate,
        propagation_mode=args.propagation_mode,
        frame_range=frame_range,
        smooth=args.smooth,
        smooth_radius=args.smooth_radius,
    )
    return _validate_correction_request(request)


def run_correct(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    source_dir = Path(args.out_dir)
    if not (source_dir / "scene_graph.json").exists():
        raise SystemExit(f"{source_dir / 'scene_graph.json'} does not exist")
    output_dir = source_dir if args.in_place else Path(args.out) if args.out else _default_corrected_out_dir(source_dir)
    if output_dir.resolve() == source_dir.resolve() and not args.in_place:
        raise SystemExit("Refusing in-place correction without --in-place")
    request = build_correction_request_from_args(args)
    try:
        scene, manifest = correct_output_dir(
            source_dir=source_dir,
            output_dir=output_dir,
            request=request,
            in_place=args.in_place,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc

    print(f"Wrote {output_dir / 'scene_graph.json'}")
    print(f"Wrote {output_dir / 'object_motion.json'}")
    print(f"Wrote {output_dir / 'web_asset_manifest.json'}")
    print(f"Wrote {output_dir / 'resource_profile.json'}")
    print(f"Wrote {output_dir / 'correction_request.json'}")
    print(f"Wrote {output_dir / 'correction_manifest.json'}")
    print(f"Corrected frames: {len(manifest.get('changedFrames', []))}; recommended output: {manifest.get('recommendedOutput')}")
    return scene, manifest


def _first_object(scene: dict[str, Any], object_id: str) -> dict[str, Any]:
    for obj in scene.get("objects", []):
        if obj.get("id") == object_id:
            return obj
    raise SystemExit(f"Object {object_id!r} not found in scene_graph.json")


def _canvas(scene: dict[str, Any]) -> dict[str, Any]:
    source = scene.get("source", {})
    canvas = scene.get("canvas", {})
    return {
        "width": int(source.get("width") or canvas.get("width") or 1),
        "height": int(source.get("height") or canvas.get("height") or 1),
        "fps": float(source.get("sampleFps") or canvas.get("fps") or 12),
        "frameCount": int(source.get("sampledFrameCount") or canvas.get("frame_count") or 0),
    }


def _write_export_manifest(args: argparse.Namespace, exports: list[dict[str, Any]], manifest_path: Path) -> None:
    scene = load_scene(args.out_dir)
    write_final_export_manifest(
        manifest_path=manifest_path,
        out_dir=args.out_dir,
        scene=scene,
        exports=exports,
        object_id=args.object_id,
    )
    print(f"Wrote {manifest_path}")


def _fail_if_unavailable(entry: dict[str, Any]) -> None:
    if entry.get("status") in {"ready", "plan_ready"}:
        return
    reason = entry.get("reason") or f"export status is {entry.get('status')}"
    raise SystemExit(f"{entry.get('type', 'export')} unavailable: {reason}")


def _export_webm_alpha(args: argparse.Namespace, output_path: Path) -> dict[str, Any]:
    scene = load_scene(args.out_dir)
    obj = _first_object(scene, args.object_id)
    canvas = _canvas(scene)
    webm = export_transparent_webm_object(
        out_dir=args.out_dir,
        output_path=output_path,
        motion=obj.get("motion", []),
        width=canvas["width"],
        height=canvas["height"],
        fps=canvas["fps"],
    )
    return final_export_entry(
        export_type="transparent_webm_object",
        format_name="webm-alpha",
        output_path=output_path,
        out_dir=args.out_dir,
        status=webm.get("status", "error"),
        mime_type=webm.get("mimeType", "video/webm"),
        width=canvas["width"],
        height=canvas["height"],
        fps=canvas["fps"],
        frame_count=canvas["frameCount"],
        reason=webm.get("reason"),
        extra={
            "objectId": args.object_id,
            "encoder": webm.get("encoder", "ffmpeg"),
            "pixelFormat": "yuva420p",
            "cachedSource": webm.get("cachedSource", "cached_rgba_cutout_png_sequence"),
            "cachedSources": ["scene_graph.json", f"objects/{args.object_id}/cutouts/*.png"],
            "source": webm.get("source", "cached_rgba_cutout_png_sequence_and_json_transforms"),
            "aiUsage": "none",
        },
    )


def run_export(args: argparse.Namespace) -> list[dict[str, Any]]:
    out_dir = Path(args.out_dir)
    if not (out_dir / "scene_graph.json").exists():
        raise SystemExit(f"{out_dir / 'scene_graph.json'} does not exist")

    exports: list[dict[str, Any]] = []
    output = Path(args.out)
    if args.format == "mp4":
        entry = export_mp4(
            out_dir=out_dir,
            output_path=output,
            background_color=args.background_color,
            editor_state_path=args.editor_state,
        )
        _fail_if_unavailable(entry)
        exports.append(entry)
        print(f"Wrote {output}")
        _write_export_manifest(args, exports, output.parent / "final_export_manifest.json")
        return exports

    if args.format == "webm-alpha":
        entry = _export_webm_alpha(args, output)
        _fail_if_unavailable(entry)
        exports.append(entry)
        print(f"Wrote {output}")
        _write_export_manifest(args, exports, output.parent / "final_export_manifest.json")
        return exports

    if args.format == "website-zip":
        entry = export_website_package(out_dir=out_dir, output_path=output)
        _fail_if_unavailable(entry)
        exports.append(entry)
        print(f"Wrote {output}")
        _write_export_manifest(args, exports, output.parent / "final_export_manifest.json")
        return exports

    if args.format == "remotion-plan":
        entry = write_remotion_plan(out_dir=out_dir, output_path=output)
        _fail_if_unavailable(entry)
        exports.append(entry)
        print(f"Wrote {output}")
        _write_export_manifest(args, exports, output.parent / "final_export_manifest.json")
        return exports

    output.mkdir(parents=True, exist_ok=True)
    all_targets = {
        "mp4": output / "final.mp4",
        "webm-alpha": output / f"{args.object_id}.webm",
        "website-zip": output / "website_package.zip",
        "remotion-plan": output / "remotion_export_plan.json",
    }
    exports.append(
        export_mp4(
            out_dir=out_dir,
            output_path=all_targets["mp4"],
            background_color=args.background_color,
            editor_state_path=args.editor_state,
        )
    )
    exports.append(_export_webm_alpha(args, all_targets["webm-alpha"]))
    exports.append(export_website_package(out_dir=out_dir, output_path=all_targets["website-zip"]))
    exports.append(write_remotion_plan(out_dir=out_dir, output_path=all_targets["remotion-plan"]))
    for entry in exports:
        _fail_if_unavailable(entry)
        print(f"Wrote {entry['path']}")
    _write_export_manifest(args, exports, output / "final_export_manifest.json")
    return exports


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] not in {"extract", "validate", "correct", "export"} and not argv[0].startswith("-"):
        args = _legacy_extract_parser().parse_args(argv)
        run_extract(args)
        return

    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "extract":
        run_extract(args)
        return
    if args.command == "validate":
        run_validate(args)
        return
    if args.command == "correct":
        run_correct(args)
        return
    if args.command == "export":
        run_export(args)
        return
    parser.print_help()


if __name__ == "__main__":
    main()
