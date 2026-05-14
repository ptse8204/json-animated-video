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
- Optionally writes production assets from cached cutouts: a WebP sprite atlas, transparent VP9/WebM when local `ffmpeg` is available, and an AVIF sprite atlas when requested and supported by the local Pillow build.
- Writes an editable `scene_graph.json` with object identity, motion, z-index, render mode, interaction states, quality scores, and rights placeholders.
- Writes a website-focused `web_asset_manifest.json`.
- Scores extraction quality from cached metadata: mask drift, edge quality, missing frames, occlusion risk, vector suitability, and production readiness.
- Applies local mask corrections to existing outputs and regenerates cached masks, cutouts, manifests, quality, and routing.
- Writes `resource_profile.json` with honest size and workflow tradeoffs.
- Writes `silhouette_lottie.json` as auxiliary Lottie for optional vector-like silhouette use.
- Copies dependency-light browser previews and runtime modules into `out/.../preview/`.
- Exports final MP4 renders, transparent object WebM files, website ZIP packages, and Remotion adapter plans from cached assets and JSON transforms.
- Provides a dependency-light local developer API, hashed API keys, signed webhook delivery records, and a JavaScript SDK for building with reusable motion layers.

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
  --output-mode both \
  --benchmark

python -m http.server 8080
```

Open:

- Runtime package: `http://localhost:8080/examples/canvas_player.html?scene=/out/demo/web_asset_manifest.json`
- Authoring graph: `http://localhost:8080/examples/canvas_player.html?scene=/out/demo/scene_graph.json`
- Pixi/WebGL path with graceful Canvas2D fallback: `http://localhost:8080/examples/pixi_player.html?scene=/out/demo/web_asset_manifest.json`
- Plain JS embed: `http://localhost:8080/examples/plain_js_embed.html?manifest=/out/demo/web_asset_manifest.json`
- Object selection workflow: `http://localhost:8080/examples/object_selection_workflow.html?manifest=/out/demo/web_asset_manifest.json&scene=/out/demo/scene_graph.json`
- Timeline editor MVP: `http://localhost:8080/examples/timeline_editor.html?scene=/out/demo/scene_graph.json`
- Website hero: `http://localhost:8080/examples/website_graphics_hero.html`
- Website templates:
  `http://localhost:8080/examples/website_templates/hero.html?manifest=/out/demo/web_asset_manifest.json`,
  `http://localhost:8080/examples/website_templates/ecommerce.html?manifest=/out/demo/web_asset_manifest.json`,
  `http://localhost:8080/examples/website_templates/education.html?manifest=/out/demo/web_asset_manifest.json`

## Schema Validation

Core MotionJSON artifacts declare JSON Schema Draft 2020-12 ids in their top-level `schema` field:

- `motionjson.scene_graph.v0.1`
- `motionjson.object_manifest.v0.1`
- `motionjson.object_motion.v0.1`
- `motionjson.web_asset_manifest.v0.1`
- `motionjson.resource_profile.v0.1`
- `motionjson.final_export_manifest.v0.1`

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
      production/
        sprite_atlas.webp
        transparent_layer.webm
      spritesheet.webp
      object_manifest.json
  preview/
    canvas_player.html
    pixi_player.html
    plain_js_embed.html
    object_selection_workflow.html
    object_selection_workflow.js
    timeline_editor.html
    timeline_editor.js
    website_graphics_hero.html
    website_templates/
      hero.html
      ecommerce.html
      education.html
    website_snippets/
      webflow-style.html
      framer-style.html
      react-embed.jsx
    runtime/
      index.js
```

## Web Runtime

The runtime package lives in `packages/motionjson-runtime`. It accepts both `web_asset_manifest.json` and `scene_graph.json`, resolves relative asset URLs, prefers spritesheets, falls back to alpha PNG sequences, and exposes cleanup through `destroy()`.

Runtime playback and interactions use cached assets plus JSON transforms only. Pixi/WebGL and React are optional peer-style integrations: applications inject `PIXI` or `React`; tests run without installing either package. See `docs/runtime.md`.

Website templates are available for hero, ecommerce, and education use cases. Plain embeds can set `data-motionjson-template="hero"`, `ecommerce`, or `education`; React apps can use template-oriented factories from `@motionjson/runtime/react`. The examples under `examples/website_snippets/` are style-compatible snippets for Webflow-like, Framer-like, and React projects, not official platform integrations or plugins.

The timeline editor MVP lives at `examples/timeline_editor.html` and is copied into generated `preview/` folders. It provides a layer panel, canvas stage drag/scale/rotate handles, opacity and z-index controls, timeline scrub/playback, duplicate/reuse layer instances, and background replacement by compositing a checker, solid color, or local image behind alpha object layers. Duplicate/reuse creates a new layer instance that references the same cached object asset in JSON; it does not copy raster frames or rerun extraction.

## Developer API And SDK

The local backend can serve a dependency-light REST API:

```bash
python -m motionjson.cli backend create-api-key --session-token-env MOTIONJSON_SESSION_TOKEN --name "local sdk"
python -m motionjson.cli backend serve-api --host 127.0.0.1 --port 8765
```

API keys are stored as hashes and the raw key is printed only once. The API
covers projects, assets, extraction jobs, website asset packages, cached-asset
renders, webhooks, and delivery records. Render jobs keep `aiUsage: none` and
use cached raster/alpha assets plus JSON transforms; `remotion-plan` is
deterministic, while `mp4` and `webm-alpha` use local `ffmpeg` when available.

The JavaScript SDK lives in `packages/motionjson-sdk`:

```js
import { MotionJSONClient } from "@motionjson/sdk";

const client = new MotionJSONClient({
  baseUrl: "http://127.0.0.1:8765",
  apiKey: process.env.MOTIONJSON_API_KEY
});
```

See `docs/developer_api.md`.

## Why JSON

JSON stores object identity and edits: timing, x/y, scale, rotation, opacity, z-index, interaction states, render mode, quality scores, and rights metadata. Moving or hiding an extracted object becomes a small JSON change instead of a new AI run or full video re-render.

## Why Raster Stays Raster

Photorealistic objects have texture, blur, hair, shadows, reflections, and edge detail that do not convert cleanly into SVG or Lottie. The safe default is `raster_alpha_sequence`. Lottie/SVG is kept for silhouettes, outlines, labels, annotations, logos, icons, and clean flat graphics.

## Quality Routing

MotionJSON computes quality from generated extraction metadata only: visibility, area, bbox, centroid, contour point count, and polygon. It does not rerun AI during editing or preview. Quality objects include mask drift consistency, edge quality, missing-frame coverage, occlusion risk, vector suitability, production readiness, readiness labels, and routing reasons.

Routing is conservative. The default is `raster_alpha_sequence`; `hybrid_vector_silhouette_plus_raster` is used only for stable, simple, low-risk layers. Pure SVG/Lottie is never recommended for extracted photoreal objects. See `docs/quality_engine.md`.

## Mask Correction

Correct existing extractions locally without network calls:

```bash
python3 -m motionjson.cli correct out/demo \
  --out out/demo_corrected \
  --add-point 120,80 \
  --frame 4 \
  --radius 12 \
  --propagate \
  --propagate-window 2 \
  --smooth
```

The correction loop supports add/remove points, box correction, brush refine, same-coordinate or centroid-delta propagation, and temporal smoothing. It rewrites corrected masks/cutouts/spritesheets/manifests/resource profile/quality/routing and writes `correction_request.json` plus `correction_manifest.json`. In-place correction requires `--in-place`. See `docs/mask_correction.md`.

## Resource Profile

`resource_profile.json` is intentionally honest:

- It reports source video size, extracted package size, frame/mask/cutout counts, scene graph size, Lottie size, sprite size, and preview strategy.
- It warns when PNG sequences or the debug package are larger than the source video.
- It compares authoring/debug assets with production assets when `--output-mode production` or `--output-mode both` is used.
- It recommends transparent WebM, WebP/AVIF sprite atlases, or GPU texture atlases for production.
- It frames the advantage as faster editing, cached preview reuse, partial invalidation, and avoiding repeated AI inference, not guaranteed smaller files.

## Production Assets

Authoring output remains the default. Add `--output-mode production` or `--output-mode both` to derive production assets from the already-cached PNG cutouts and JSON motion transforms. This does not rerun AI.

```bash
python -m motionjson.cli extract examples/demo_red_ball.mp4 \
  --out out/demo \
  --mask-provider threshold \
  --output-mode both \
  --production-avif
```

The production package records explicit status for each asset. Transparent WebM requires local `ffmpeg`; if it is missing, the manifest reports `unavailable`. AVIF is optional; if Pillow lacks AVIF encoding, the manifest reports `unsupported` and tests do not require an AVIF file.

## Final Export

Final exports consume cached raster/alpha assets and JSON transforms only. They do not rerun AI providers.

```bash
python3 -m motionjson.cli export out/demo --format mp4 --out out/demo/exports/final.mp4 --background-color "#fbfaf6"
python3 -m motionjson.cli export out/demo --format webm-alpha --out out/demo/exports/object_0.webm --object-id object_0
python3 -m motionjson.cli export out/demo --format website-zip --out out/demo/exports/website_package.zip
python3 -m motionjson.cli export out/demo --format remotion-plan --out out/demo/exports/remotion_export_plan.json
python3 -m motionjson.cli export out/demo --format all --out out/demo/exports --background-color "#fbfaf6"
```

MP4 and transparent WebM require local `ffmpeg`; direct CLI exports fail clearly if the requested encoder is unavailable. The Remotion export is an honest plan file only: it does not add dependencies, run npm, call the network, or invoke APIs. See `docs/final_export.md`.

The website ZIP includes runtime modules, preview pages, website templates, embed snippets, scene/object/resource JSON, rights metadata, cached raster/alpha assets, and production assets when available. Package manifests record `aiUsage: "none"` because the ZIP is assembled from cached assets and JSON transforms.

## Current Limitations

- One object per run.
- Demo mask providers are rough and CPU-first.
- Sprite sheet packing is simple row-major packing.
- Transparent object-layer WebM and final MP4 export are available when `ffmpeg` is installed.
- SAM2 providers are adapter-compatible, but real local SAM2 and hosted services are optional setup, not default dependencies.
- Browser runtime includes Canvas2D, optional Pixi/WebGL injection, plain JS embed, and a React component factory.
- Timeline editor MVP is browser-side authoring; final MP4 export is local FFmpeg-based, while hosted/batched render orchestration remains future work.

## Roadmap

1. Add mask smoothing, matting, and occlusion QA.
2. Add multi-object extraction and timeline editing.
3. Add GPU atlas generation and richer final timeline export.
4. Add hosted/batched render infrastructure and WebCodecs experiments.
5. Add editor integrations and website embed helpers.

## Positioning

Say: “Turn video elements into reusable motion layers for editors and websites.”

Do not say: “Convert video to JSON,” “convert video to SVG,” or “convert all video to Lottie.”
