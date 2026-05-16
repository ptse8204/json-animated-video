# Provider Capabilities And Diagnostics

MotionJSON can run without SAM2, torch, CUDA, hosted segmentation, OpenRouter,
or FFmpeg. Provider diagnostics report what is usable in the current local
environment before a user starts extraction or export.

## CLI

```bash
python -m motionjson.cli backend diagnostics --json
```

Add a video probe and output-directory writability check when preparing a run:

```bash
python -m motionjson.cli backend diagnostics --json \
  --video examples/demo_red_ball.mp4 \
  --output-dir out/demo \
  --sam2-checkpoint checkpoints/sam2.pt \
  --sam2-config configs/sam2.yaml
```

The command emits JSON with schema `motionjson.provider_diagnostics.v0.1`. It
does not initialize the backend SQLite database, create storage directories,
download models, import SAM2, call hosted providers, or read secret values. It
only reports whether relevant secret environment variables are present. For
SAM2 model paths, explicit `--sam2-checkpoint` and `--sam2-config` values take
precedence over `SAM2_LOCAL_CHECKPOINT` and `SAM2_LOCAL_CONFIG`.

## Status Values

- `ready`: usable in this environment.
- `available_cpu_only`: configured and importable, but CUDA is unavailable.
- `missing_dependency`: a required optional package or executable is missing.
- `missing_model`: an environment path is configured but does not point to an
  existing model/config file.
- `not_configured`: credentials, endpoints, model paths, or provider settings
  are absent.
- `not_implemented`: planned provider surface exists in the diagnostics model,
  but execution is intentionally deferred to a later phase.
- `unavailable`: retained legacy or unsupported path that should not be chosen
  automatically.

## Provider Names

Current no-model providers:

- `threshold`
- `motion`
- `external`
- `mock`

Optional SAM2/hosted providers:

- `sam2`: legacy stub retained for CLI compatibility; it fails clearly unless a
  test/client injects behavior.
- `sam2-local`: local SAM2-compatible segmentation; requires optional SAM2,
  torch, `SAM2_LOCAL_CHECKPOINT`, and `SAM2_LOCAL_CONFIG`.
- `sam2-hosted`: hosted segmentation; requires `HOSTED_SEGMENTATION_URL` and
  `HOSTED_SEGMENTATION_API_KEY`, and extraction still requires explicit network
  opt-in.

Reasoning and future discovery providers:

- `openrouter`: optional LLM/VLM reasoning only. It is not a segmentation
  provider.
- `text-detector`, `class-detector`, `video-tracker`, and `track-linker` are
  reported as planned surfaces until the provider pipeline phases implement
  them.

Export/vector providers:

- `contour-vectorizer`
- `motionjson-json`
- `website-zip`
- `remotion-plan`
- `silhouette-lottie`
- `ffmpeg-video`

## Interpreting Failures

Diagnostics should be shown before UI or backend jobs run. A missing optional
provider is not fatal when the chosen workflow can use a no-model provider such
as `threshold`, `motion`, `external`, or `mock`. A UI should disable unavailable
choices, keep the reason visible, and offer a no-model workflow when possible.

Do not route text prompts directly to raw SAM2. Text-guided object discovery
must use a detector/candidate provider first, then pass candidate prompts or
masks into segmentation/tracking.
