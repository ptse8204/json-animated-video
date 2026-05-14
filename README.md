# JSON Animated Video

Turn video elements into reusable motion layers for editors and websites.

This prototype is not a “convert video to JSON/SVG/Lottie” project. The practical goal is to run object extraction once, cache the selected object as raster/alpha assets, and control it with a compact JSON scene graph so editing, previewing, reuse, and website embeds are cheaper.

## What It Does

- Decodes and samples short videos with OpenCV.
- Extracts one selected object using a mask provider:
  - `threshold`: HSV threshold for offline demos.
  - `motion`: rough background subtraction for demos.
  - `external`: import mask PNG/JPG/WebP sequences from SAM2, Runway, Adobe, DaVinci, etc.
  - `sam2`: legacy stub adapter path that fails clearly until a client is injected.
  - `sam2-local`: optional local SAM2-compatible provider with injected test fakes and lazy SAM2 imports.
  - `sam2-hosted`: hosted SAM2-compatible provider with injected client/transport and no default network calls.
- Saves sampled frames, masks, cropped alpha cutouts, an object manifest, and a WebP/PNG sprite sheet.
- Writes an editable `scene_graph.json` with object identity, motion, z-index, render mode, interaction states, quality scores, and rights placeholders.
- Writes a website-focused `web_asset_manifest.json`.
- Writes `resource_profile.json` with honest size and workflow tradeoffs.
- Writes `silhouette_lottie.json` as auxiliary Lottie for optional vector-like silhouette use.
- Copies dependency-light browser previews into `out/.../preview/`.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .

python examples/make_demo_video.py --out examples/demo_red_ball.mp4

python -m motionjson.cli extract examples/demo_red_ball.mp4 \
  --out out/demo \
  --mask-provider threshold \
  --lower-hsv 0,80,80 \
  --upper-hsv 12,255,255 \
  --sample-fps 12 \
  --max-frames 80 \
  --benchmark

python -m http.server 8080
```

Open:

- Runtime package: `http://localhost:8080/examples/canvas_player.html?scene=/out/demo/web_asset_manifest.json`
- Authoring graph: `http://localhost:8080/examples/canvas_player.html?scene=/out/demo/scene_graph.json`
- Website hero: `http://localhost:8080/examples/website_graphics_hero.html`

## Schema Validation

Core MotionJSON artifacts declare JSON Schema Draft 2020-12 ids in their top-level `schema` field:

- `motionjson.scene_graph.v0.1`
- `motionjson.object_manifest.v0.1`
- `motionjson.object_motion.v0.1`
- `motionjson.web_asset_manifest.v0.1`
- `motionjson.resource_profile.v0.1`

Validate one file or a generated output directory:

```bash
motionjson validate out/demo/scene_graph.json
motionjson validate out/demo
motionjson validate out/demo --object-id object_0
```

Directory validation requires the core package files and skips auxiliary JSON files that do not declare a MotionJSON core schema. `silhouette_lottie.json` remains auxiliary Lottie output, not a MotionJSON core schema.

## External Masks

```bash
python -m motionjson.cli extract input.mp4 \
  --out out/external \
  --mask-provider external \
  --mask-dir masks/
```

Mask files are loaded in sorted order. They are resized to match the video frame when needed.

## SAM2-Compatible Providers

```bash
python -m motionjson.cli extract input.mp4 \
  --out out/sam2-local \
  --mask-provider sam2-local \
  --sam2-checkpoint /path/to/checkpoint.pt \
  --sam2-config /path/to/config.yaml \
  --sam2-device cuda \
  --prompt-point 410,230
```

Local SAM2 and torch are optional; MotionJSON lazy-imports SAM2 only when the local provider is selected without an injected predictor. Hosted SAM2 is also explicit:

```bash
python -m motionjson.cli extract input.mp4 \
  --out out/sam2-hosted \
  --mask-provider sam2-hosted \
  --sam2-endpoint "$HOSTED_SEGMENTATION_URL" \
  --sam2-hosted-allow-network \
  --prompt-point 410,230
```

Hosted auth is read from `HOSTED_SEGMENTATION_API_KEY` by default. Without an injected client/transport, hosted mode refuses to make network calls unless `--sam2-hosted-allow-network` is set. SAM2 modes cache normalized binary PNG masks under `.motionjson-cache/masks` by default. See `docs/sam2_segmentation.md`.

## Output Layout

```text
out/demo/
  scene_graph.json
  object_motion.json
  web_asset_manifest.json
  resource_profile.json
  silhouette_lottie.json
  frames/
    frame_000001.png
  masks/
    object_0/
      mask_000001.png
  objects/
    object_0/
      cutouts/
        cutout_000001.png
      spritesheet.webp
      object_manifest.json
  preview/
    canvas_player.html
    website_graphics_hero.html
```

## Why JSON

JSON stores object identity and edits: timing, x/y, scale, rotation, opacity, z-index, interaction states, render mode, quality scores, and rights metadata. Moving or hiding an extracted object becomes a small JSON change instead of a new AI run or full video re-render.

## Why Raster Stays Raster

Photorealistic objects have texture, blur, hair, shadows, reflections, and edge detail that do not convert cleanly into SVG or Lottie. The safe default is `raster_alpha_sequence`. Lottie/SVG is kept for silhouettes, outlines, labels, annotations, logos, icons, and clean flat graphics.

## Resource Profile

`resource_profile.json` is intentionally honest:

- It reports source video size, extracted package size, frame/mask/cutout counts, scene graph size, Lottie size, sprite size, and preview strategy.
- It warns when PNG sequences or the debug package are larger than the source video.
- It recommends transparent WebM, WebP/AVIF sprite atlases, or GPU texture atlases for production.
- It frames the advantage as faster editing, cached preview reuse, partial invalidation, and avoiding repeated AI inference, not guaranteed smaller files.

## Current Limitations

- One object per run.
- Demo mask providers are rough and CPU-first.
- Sprite sheet packing is simple row-major packing.
- No final video exporter yet.
- SAM2 providers are adapter-compatible, but real local SAM2 and hosted services are optional setup, not default dependencies.
- Browser preview uses Canvas2D; production should move to WebGL/PixiJS for many objects or large assets.

## Roadmap

1. Add mask smoothing, matting, and occlusion QA.
2. Add multi-object extraction and timeline editing.
3. Add transparent WebM/AVIF export and GPU atlas generation.
4. Add final export via FFmpeg, Remotion, or WebCodecs.
5. Add editor integrations and website embed helpers.

## Positioning

Say: “Turn video elements into reusable motion layers for editors and websites.”

Do not say: “Convert video to JSON,” “convert video to SVG,” or “convert all video to Lottie.”
