# First Run Setup

Use this page when setting up MotionJSON on a new local machine. The default
path is CPU/no-model and does not require SAM2, CUDA, detectors, hosted
services, or network access at runtime.

## Install Profiles

Base install for CLI extraction, benchmarks, validation, and the dependency-free
local UI:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -U pip
python3 -m pip install -e ".[ui]"
```

Windows PowerShell equivalent:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[ui]"
```

Optional extras are only needed for heavier provider families:

| Extra | Use When | Notes |
| --- | --- | --- |
| `.[sam2]` | Local SAM2 promptable segmentation/tracking | Also set `SAM2_LOCAL_CHECKPOINT` and `SAM2_LOCAL_CONFIG`. |
| `.[detectors]` | Open-vocabulary text detector candidates | Text prompts become detector boxes before segmentation. |
| `.[yolo]` | Known-class detector candidates | Useful for common classes when a YOLO model is configured. |
| `.[hosted-segmentation]` | Explicit hosted SAM2-style endpoint experiments | Network use remains opt-in through provider flags/config. |
| `.[openrouter]` | LLM/VLM reasoning integrations | OpenRouter is not a segmentation provider. |
| `.[dev]` | Tests, packaging checks, and local build validation | Use for development and release checks. |

## First Diagnostics

Run diagnostics before choosing a provider:

```bash
python3 -m motionjson.cli backend diagnostics --json
python3 -m motionjson.cli benchmark --fixtures red_ball,whole_frame_regression --modes external --out out/benchmarks
python3 -m motionjson.cli ui --no-open --mock
```

PowerShell:

```powershell
python -m motionjson.cli backend diagnostics --json
python -m motionjson.cli benchmark --fixtures red_ball,whole_frame_regression --modes external --out out\benchmarks
python -m motionjson.cli ui --no-open --mock
```

The UI sidebar includes a First Run checklist backed by the same capability
diagnostics. Missing optional dependencies, model paths, FFmpeg, CUDA, hosted
endpoint variables, and detector packages are reported as diagnostics instead of
being hidden or treated as successful extraction.

## Red-Ball Tutorial

Create or refresh the bundled red-ball clip, run deterministic threshold
extraction, then validate the output:

```bash
python3 examples/make_demo_video.py --out examples/demo_red_ball.mp4
python3 -m motionjson.cli extract examples/demo_red_ball.mp4 \
  --out out/demo_red_ball \
  --mask-provider threshold \
  --lower-hsv 0,80,80 \
  --upper-hsv 12,255,255 \
  --sample-fps 12 \
  --max-frames 12
python3 -m motionjson.cli validate out/demo_red_ball
```

PowerShell:

```powershell
python examples\make_demo_video.py --out examples\demo_red_ball.mp4
python -m motionjson.cli extract examples\demo_red_ball.mp4 `
  --out out\demo_red_ball `
  --mask-provider threshold `
  --lower-hsv 0,80,80 `
  --upper-hsv 12,255,255 `
  --sample-fps 12 `
  --max-frames 12
python -m motionjson.cli validate out\demo_red_ball
```

Expected behavior: one accepted red-ball track, no whole-frame accepted object,
and clear fallback diagnostics if a provider emits background-like masks.

## Multi-Object Tutorial

Generate the deterministic multi-object fixture and use its masks as a local
external-mask demo:

```bash
python3 -m motionjson.cli benchmark --fixtures multi_object --modes external --out out/benchmarks
python3 -m motionjson.cli extract out/benchmarks/fixtures/multi_object/video.mp4 \
  --out out/demo_multi_object \
  --object-mask-dir red_ball=out/benchmarks/fixtures/multi_object/masks/red_ball \
  --object-label red_ball="Red ball" \
  --object-mask-dir blue_block=out/benchmarks/fixtures/multi_object/masks/blue_block \
  --object-label blue_block="Blue block" \
  --max-frames 6
python3 -m motionjson.cli validate out/demo_multi_object --object-id red_ball
python3 -m motionjson.cli validate out/demo_multi_object --object-id blue_block
```

PowerShell:

```powershell
python -m motionjson.cli benchmark --fixtures multi_object --modes external --out out\benchmarks
python -m motionjson.cli extract out\benchmarks\fixtures\multi_object\video.mp4 `
  --out out\demo_multi_object `
  --object-mask-dir red_ball=out\benchmarks\fixtures\multi_object\masks\red_ball `
  --object-label red_ball="Red ball" `
  --object-mask-dir blue_block=out\benchmarks\fixtures\multi_object\masks\blue_block `
  --object-label blue_block="Blue block" `
  --max-frames 6
python -m motionjson.cli validate out\demo_multi_object --object-id red_ball
python -m motionjson.cli validate out\demo_multi_object --object-id blue_block
```

Expected behavior: two accepted object tracks with stable IDs, one layer per
object, and no duplicate-overlap rejection.

## UI Project Flow

1. Launch `motionjson ui` or `python3 -m motionjson.cli ui --no-open --mock`.
2. Confirm the First Run and Capabilities panels show the no-model providers as
   ready.
3. Create a local project.
4. Register `examples/demo_red_ball.mp4` or the generated multi-object fixture.
5. Use `Trace one object`, `Find moving objects`, `Import external masks`, or
   `Review existing result` for the CPU/no-model path.
6. Validate the config before starting the run, then review tracks before
   export.

## Troubleshooting

- `python: command not found`: use `python3` on macOS/Linux or `py -3` on
  Windows.
- SAM2 reports `missing_dependency`: install the `sam2` extra and configure
  checkpoint/model paths, or use `mock`, `threshold`, `motion`, or `external`
  for no-model work.
- Text or class detectors report `missing_dependency`: install the detector or
  YOLO extras only when you need those provider modes.
- FFmpeg is missing: MotionJSON JSON export still works; install FFmpeg for
  MP4/WebM encoding.
- Whole-frame output: inspect `fallback_diagnostics.json` and track warnings for
  `masks_too_large_whole_frame` before export.
