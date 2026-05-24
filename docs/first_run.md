# First Run Setup

Use this page when setting up MotionJSON on a new local machine. The default
path is CPU/no-model and does not require SAM2, CUDA, detectors, hosted
services, or network access at runtime.

For hardware and provider expectations, see
[System requirements](system_requirements.md). Start with short clips until the
chosen provider is proven on your machine.

## Install Profiles

Base install for CLI extraction, benchmarks, validation, and the
dependency-light local UI. The UI has no frontend build/runtime dependency for
normal use:

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
| `.[sam3]` | MotionJSON local SAM3 diagnostics and adapter support | Real local SAM3 still needs official SAM3 package/model access, Python/CUDA compatibility, and `SAM3_LOCAL_MODEL`. |
| `.[detectors]` | Open-vocabulary text detector candidates | Text prompts become detector boxes before segmentation. |
| `.[yolo]` | Known-class detector candidates | Useful for common classes when a YOLO model is configured. |
| `.[hosted-segmentation]` | Explicit hosted SAM2-style endpoint experiments | Network use remains opt-in through provider flags/config. |
| `.[openrouter]` | LLM/VLM reasoning integrations | OpenRouter is not a segmentation provider. |
| `.[dev]` | Tests, packaging checks, and local build validation | Use for development and release checks. |

## Which Path Should I Choose?

| Path | Start here when | UI names | Main requirements |
| --- | --- | --- | --- |
| CPU/no-model demo | You want the safest first run. | `Use demo video`, `Find moving things`, `Import masks`, or the red-ball CLI demo. | Python `>=3.10`; 4 GB RAM minimum for tiny demos, 8 GB recommended; no GPU or keys. |
| Local SAM2 | You want prompted object tracing and local media. | `Cut out one object` -> `Model Connections` -> `SAM2 local`. | SAM2 package, checkpoint, config, torch/CUDA; 16 GB RAM minimum for small clips, 32 GB recommended; 8 GB VRAM minimum for small experiments, 12-16+ GB recommended. |
| Hosted SAM2 | You want SAM2-style tracing without local GPU. | `Model Connections` -> `Replicate SAM2 video` or custom SAM2 endpoint. | API key, hosted-call opt-in, cost/privacy acknowledgement. |
| Local SAM3 | You want local concept/exemplar discovery. | `Find by description` -> `Model Connections` -> `SAM3 local`. | Official SAM3 package, real local `sam3.pt`, compatible Python/CUDA, 32 GB RAM recommended, 16+ GB VRAM recommended. |
| Hosted SAM3 | You want text/concept discovery without local SAM3 hardware. | `Model Connections` -> `Roboflow SAM3`, `Fal SAM3 image`, or custom SAM3 endpoint. | API key, hosted-call opt-in, cost/privacy acknowledgement. |
| Motion foreground | The object moves against a stable background. | `Find moving things`. | CPU/no-model; false positives are common with camera motion or shadows. |
| External masks | Another tool already produced masks. | `Import masks`. | Mask directory or manifest with frame/object IDs. |

## First Diagnostics

Run diagnostics before choosing a provider:

```bash
python3 -m motionjson.cli backend diagnostics --text
python3 -m motionjson.cli backend diagnostics --json
python3 -m motionjson.cli benchmark --fixtures red_ball,whole_frame_regression --modes external --out out/benchmarks
python3 -m motionjson.cli ui --no-open
```

PowerShell:

```powershell
python -m motionjson.cli backend diagnostics --text
python -m motionjson.cli backend diagnostics --json
python -m motionjson.cli benchmark --fixtures red_ball,whole_frame_regression --modes external --out out\benchmarks
python -m motionjson.cli ui --no-open
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

1. Launch `motionjson ui` or `python3 -m motionjson.cli ui --no-open`.
2. Start at the guided stepper: `Start`, `Video`, `Model`, `Prepare & run`,
   and `Review & export`.
3. Keep the left menu collapsed when you want more workspace; reopen it with
   Menu. Open `Show details` only when you need diagnostics, jobs, review,
   corrections, export, or library panels.
4. Open Model Connections and diagnose the recommended SAM provider for the
   selected goal. Missing SAM2, SAM3, CUDA, detectors, FFmpeg, model weights,
   or hosted settings remain visible as diagnostics.
5. Register `examples/demo_red_ball.mp4`, choose `Use demo video`, or open an
   existing result. Guided mode creates a starter local project when needed.
6. Use the `Model` step only for model-backed goals. CPU/no-model workflows
   report that no SAM model setup is needed.
7. Use `Cut out one object`, `Find moving things`, `Import masks`, or
   `Review previous result` for no-model/local paths. Use `Find by
   description` only after a SAM3 or detector-style provider is diagnosed.
8. In `Prepare & run`, validate the readable run plan before starting. Debug
   smoke jobs are available only when the UI was launched with `--debug-mock`.
9. After a run starts, use **Job Center** / **Run monitor** to inspect the
   selected job, active jobs, failures, logs, and retry/cancel state.
10. In `Review & export`, follow `Candidates` -> `Track selected` -> `Tracks`
   -> `Corrections` -> `Export`. The primary action should say exactly what is
   missing, such as `Track selected`, `Mark reviewed`, or
   `Export reviewed objects`.

## Troubleshooting

- `python: command not found`: use `python3` on macOS/Linux or `py -3` on
  Windows.
- SAM2 reports `missing_dependency`: install the `sam2` extra and configure
  checkpoint/model paths, or use `mock`, `threshold`, `motion`, or `external`
  for no-model work.
- Text or class detectors report `missing_dependency`: install the detector or
  YOLO extras only when you need those real provider modes; mock class presets
  remain available for local UI and benchmark smoke checks.
- FFmpeg is missing: MotionJSON JSON export still works; install FFmpeg for
  MP4/WebM encoding.
- Whole-frame output: inspect `fallback_diagnostics.json` and track warnings for
  `masks_too_large_whole_frame` before export.
