# Troubleshooting

Use this page when MotionJSON does not launch, a provider is unavailable, masks
look wrong, or an export falls back to raster-only output. Start by collecting
diagnostics:

```bash
python3 -m motionjson.cli backend diagnostics --text
python3 -m motionjson.cli backend diagnostics --json
python3 -m motionjson.cli validate out/demo_red_ball
```

The local UI shows the same capability status in the First Run and Capabilities
panels.

## Python Command Not Found

On macOS and Linux, use `python3` if `python` is not installed:

```bash
python3 -m motionjson.cli --help
```

On Windows PowerShell, use `py -3` for virtualenv creation, then `python` after
activation:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m motionjson.cli --help
```

## FFmpeg Is Missing

FFmpeg is optional for the base install. MotionJSON JSON output, masks,
cutouts, website manifests, and browser runtime previews can still work without
it. MP4, WebM, and some final video export paths need FFmpeg.

Check diagnostics first:

```bash
python3 -m motionjson.cli backend diagnostics --json
```

If FFmpeg is unavailable, use JSON/runtime exports or install FFmpeg through
your operating system package manager before rendering video outputs.

## CUDA Is Missing Or CPU-Only

CUDA is not required for the no-model path. `mock`, `threshold`, `motion`, and
`external` providers are intended to run on CPU. Optional heavy providers may
report `available_cpu_only`, `missing_dependency`, or `not_configured`.

Use a CPU-safe workflow:

```bash
python3 -m motionjson.cli ui --no-open --mock
python3 -m motionjson.cli extract examples/demo_red_ball.mp4 \
  --out out/demo_red_ball \
  --mask-provider threshold \
  --lower-hsv 0,80,80 \
  --upper-hsv 12,255,255 \
  --max-frames 12
```

## SAM2 Is Missing

SAM2 is optional and is not installed by the default package. A missing SAM2
dependency, checkpoint, or config should appear in diagnostics instead of
failing the base install.

No-model alternatives:

- use `threshold` for simple color demos;
- use `motion` or `motion_foreground` for simple moving objects;
- use `external` or `external_masks` when masks already exist;
- use `mock` for UI and smoke checks.

If you need local SAM2, install the optional extra and configure model paths:

```bash
python3 -m pip install -e ".[sam2]"
export SAM2_LOCAL_CHECKPOINT=/path/to/checkpoint.pt
export SAM2_LOCAL_CONFIG=/path/to/config.yaml
python3 -m motionjson.cli backend diagnostics --json
```

SAM2 tracks a prompted object. It does not discover every semantic object by
itself.

## Text Or Class Detectors Are Missing

Text prompts and class presets need detector candidates before segmentation.
Missing detector packages or model weights should be shown as diagnostics.

Optional installs:

```bash
python3 -m pip install -e ".[detectors]"
python3 -m pip install -e ".[yolo]"
```

Then configure the relevant detector model path and rerun diagnostics. If you
only need a local smoke path, use manual prompts, motion foreground, external
masks, or mock mode instead.

## Bad Masks Or Whole-Frame Masks

A point prompt or automatic proposal can select background, floor, wall, or the
whole frame. MotionJSON should flag these cases before export.

Inspect:

```bash
cat out/demo_red_ball/tracks.json
cat out/demo_red_ball/fallback_diagnostics.json
```

Look for reason codes such as:

- `masks_too_large_whole_frame`
- `no_masks_accepted`
- `mask_area_below_minimum`
- `track_too_short`
- `duplicate_track`

Useful fixes:

- use a tighter box or a more precise prompt point;
- reduce automatic proposal count;
- import explicit external masks;
- delete or hide bad tracks in the local UI before export;
- lower the scope to one object first, then add more objects after review.

See [Track filtering and fallback diagnostics](track_filtering.md).

## Raster-Only Output

Photoreal objects are expected to stay raster/alpha layers controlled by JSON.
That is normal. Raster-only fallback is different: it means vector/object tracks
were unavailable, rejected, or intentionally bypassed.

When this happens, read:

- `fallback_diagnostics.json`
- `tracks.json`
- `provider_diagnostics.json`
- the local UI job review panel

Common causes:

- no object candidates were found;
- masks were too large or too small;
- the selected provider was unavailable;
- vectorization failed;
- the run was configured for raster fallback.

Do not assume a raster-only result is successful object extraction until the
diagnostics explain why object tracks were unavailable.

## The UI Cannot Read A Video Path

The local UI backend can only register files that are readable by the process
running `motionjson ui`. If the UI is inside a container or Codespace, use a
path that exists inside that environment.

Try the bundled demo first:

```bash
python3 examples/make_demo_video.py --out examples/demo_red_ball.mp4
python3 -m motionjson.cli ui --no-open --mock
```

Then register `examples/demo_red_ball.mp4` in the UI.

## Where To Look Next

- [First run setup](first_run.md)
- [Run locally](run_local.md)
- [Provider capabilities and diagnostics](provider_capabilities.md)
- [Discovery providers](discovery_providers.md)
- [Track filtering and fallback diagnostics](track_filtering.md)
- [Migration and known limitations](migration_and_known_limitations.md)
