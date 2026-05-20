# SAM2 Segmentation Providers

MotionJSON supports SAM2-compatible segmentation as an ingest-time mask provider. Normal editing and preview still use cached raster/alpha assets plus JSON transforms; they do not rerun SAM2 during drag, scale, rotate, or timeline preview.

## CLI Modes

Existing modes remain available:

```bash
--mask-provider threshold
--mask-provider motion
--mask-provider external
--mask-provider sam2
```

`sam2` is the legacy stub and still fails clearly unless a client is injected. Phase 3 adds explicit modes:

```bash
--mask-provider sam2-local
--mask-provider sam2-hosted
```

Both SAM2 modes accept prompts:

```bash
--prompt-point 410,230
--prompt-box 380,180,120,140
--sam2-prompt-frame 0
```

`--prompt-box` is `x,y,w,h` at the CLI boundary.

## Diagnose Before Running

Use provider diagnostics to confirm whether SAM2, torch, CUDA, model paths,
hosted endpoint settings, FFmpeg, video IO, and local output permissions are
available:

```bash
python3 -m motionjson.cli backend diagnostics --json \
  --video examples/demo_red_ball.mp4 \
  --output-dir out/sam2-local \
  --sam2-checkpoint /path/to/sam2_checkpoint.pt \
  --sam2-config /path/to/sam2_config.yaml
```

Diagnostics do not import SAM2, download weights, call hosted services, or read
secret token values. `sam2-local` can report `missing_dependency`,
`not_configured`, `missing_model`, or `available_cpu_only`; those statuses
should be surfaced before a user starts an extraction run.

## Local SAM2 Setup

The local provider lives at `motionjson.providers.sam2.LocalSAM2SegmentationProvider`. SAM2 and torch are optional and are not default MotionJSON dependencies.

Install SAM2 in your own environment, then run:

```bash
python3 -m motionjson.cli extract input.mp4 \
  --out out/sam2-local \
  --mask-provider sam2-local \
  --sam2-checkpoint /path/to/sam2_checkpoint.pt \
  --sam2-config /path/to/sam2_config.yaml \
  --sam2-device cuda \
  --prompt-point 410,230
```

The provider lazy-imports SAM2 only when no predictor or predictor factory is injected. Tests inject a fake predictor, so CI does not need SAM2, torch, GPUs, credentials, or network.

The local provider follows the SAM2 video flow:

- `prepare()` initializes predictor state for the source video.
- The first requested segment applies a point or box prompt at `--sam2-prompt-frame`.
- Masks are propagated through the video.
- Returned logits or masks are normalized to 2D binary `uint8` arrays with values `0` or `255`.

## Automatic Object Proposals

`motionjson.providers.sam2.LocalSAM2AutomaticMaskProposalBackend` adds an
optional SAM2 automatic-mask path for discovery providers. It is used by
`auto_object_proposals` and `sam_auto_masks` only when local SAM2 diagnostics
pass or a fake backend is injected in tests.

Example:

```bash
SAM2_LOCAL_CHECKPOINT=/path/to/sam2_checkpoint.pt \
SAM2_LOCAL_CONFIG=/path/to/sam2_config.yaml \
python3 -m motionjson.cli extract input.mp4 \
  --out out/sam2-auto \
  --discovery-provider auto_object_proposals \
  --discovery-config '{"providerPreference":"sam2-local","qualityPreset":"clean"}' \
  --mask-provider mock
```

The adapter:

- lazy-imports `sam2.automatic_mask_generator` only after checkpoint/config
  paths are supplied;
- samples keyframes from the selected discovery preset;
- filters proposals by area, stability, whole-frame/background-like shape, and
  duplicate overlap;
- writes accepted and rejected candidates into `candidates.json` with preview
  artifacts under `discovery/`;
- uses SAM2 video propagation for accepted candidate mask sequences when the
  local predictor is available.

This is object proposal and tracking infrastructure, not semantic discovery.
Text or concept search still needs a detector/SAM3-style provider before SAM2
receives boxes or masks.

## Hosted SAM2 Contract

The hosted provider lives at `motionjson.providers.sam2.HostedSAM2SegmentationProvider`. It accepts an injected client or JSON transport and makes no network calls by default.

For a real hosted deployment:

```bash
HOSTED_SEGMENTATION_URL=https://your-segmentation-service.example/sam2
HOSTED_SEGMENTATION_API_KEY=...

python3 -m motionjson.cli extract input.mp4 \
  --out out/sam2-hosted \
  --mask-provider sam2-hosted \
  --sam2-hosted-allow-network \
  --prompt-point 410,230
```

Without an injected client/transport, the CLI requires explicit `--sam2-hosted-allow-network`, a configured endpoint, and auth from `--sam2-auth-env` before any request can be made.

The hosted request payload contains:

- `source_video`
- `frame_index`
- `prompt_frame_index`
- `object_id`
- `prompt_point`
- `prompt_box`
- `config`
- `video` metadata

The response must include either:

- `mask`: a 2D array-like mask or logits
- `mask_png_base64`: a base64-encoded grayscale PNG

MotionJSON normalizes the response before the extraction pipeline sees it.

## Mask Cache

SAM2 CLI modes use `.motionjson-cache/masks` by default. This directory is ignored by git.

The cache stores:

- Binary PNG masks normalized to `0` or `255`.
- A root `manifest.json` with schema `motionjson.mask_cache.v0.1`.
- Per-cache-key directories containing `mask_<frame_index>.png` files and a key-local `manifest.json`.
- Keys that include provider, config, source video, prompt, object id, and video metadata. Individual mask filenames carry the frame index.

Cache output is provider-independent: downstream code receives the same binary array shape whether the mask came from local SAM2, hosted SAM2, external masks, or a fake test provider.

Use `--mask-cache-dir` to move the cache, or `--no-mask-cache` to disable it:

```bash
--mask-cache-dir .motionjson-cache/masks
--no-mask-cache
```

Each `MaskCache` instance also exposes a deterministic summary with hits,
misses, hit rate, read bytes, written bytes, stored bytes, entry count, and
mask count. SAM2 provider performance reports include this cache summary so a
caller can see whether ingest/correction work reused cached masks.

## Batch Hooks And Fallback

SAM2 providers implement the optional `segment_batch()` hook. If an injected
predictor or hosted client exposes a native batch method, the provider can use
it. Otherwise MotionJSON routes the batch request shape through the existing
per-frame `segment()` path. This adds GPU batching hooks without making GPU
libraries default dependencies.

The CLI can route a SAM2 provider through a deterministic segmentation fallback:

```bash
python3 -m motionjson.cli extract input.mp4 \
  --out out/sam2-with-fallback \
  --mask-provider sam2-local \
  --fallback-mask-provider threshold \
  --prompt-point 410,230
```

Fallback routing records primary failures, fallback successes or failures,
provider names, and timings in `providerPerformance`. OpenRouter, LLM, and VLM
providers are rejected as segmentation fallbacks.

## Optional Hosted Stubs

`motionjson.adapters.sam2_replicate` and `motionjson.adapters.sam2_runpod` are explicit integration stubs. They are credential-gated and are not default dependencies.

- Replicate requires `REPLICATE_API_TOKEN` or an explicit `api_token`.
- RunPod requires `RUNPOD_API_KEY`, `RUNPOD_SAM2_ENDPOINT_ID`, and an injected transport/client.

These stubs are not used by default CLI modes.

## No-Network Tests

Phase 3 tests use fake predictors and fake hosted clients:

```bash
pytest -q tests/test_sam2_providers.py tests/test_mask_cache.py
```

They do not import SAM2, torch, Replicate, RunPod, or make network calls.

## Correction Loop

`motionjson correct` is separate from SAM2 provider execution. It applies deterministic local corrections to cached mask PNGs, then regenerates cutouts, spritesheets, manifests, quality scores, and routing. Add/remove points, box correction, brush refine, same-coordinate or centroid-delta propagation, and temporal smoothing are represented as `motionjson.correction_request.v0.1`.

The correction loop does not call SAM2, hosted segmentation, OpenRouter, Replicate, RunPod, or any network API by default. Future provider-specific correction hooks must remain explicit ingest/correction-time actions and must not run during normal drag, scale, rotate, timeline, or runtime preview.

## OpenRouter Separation

OpenRouter remains an optional `LLMProvider` for text/VLM reasoning tasks such as labels, prompt interpretation, and optimization notes. It is not a pixel segmentation engine and is not used by `sam2-local` or `sam2-hosted`.
