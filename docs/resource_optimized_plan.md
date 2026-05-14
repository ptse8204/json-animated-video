# Adjusted Plan: AI-Assisted Resource-Efficient Video Editing

## Corrected product goal

The goal is not to convert every video into JSON or Lottie. The goal is to make editing faster and lighter by converting selected parts of a video into cached, reusable, JSON-controlled layers.

The system should behave like an AI preprocessor plus a fast scene-graph renderer:

```text
source video stays video
+ AI identifies object layers once
+ raster/vector assets are cached
+ JSON controls transforms, timing, z-order, masks, and edits
+ Canvas/WebGL/PixiJS previews the edit cheaply
+ Remotion/FFmpeg/WebCodecs exports the final video
```

## Why this is faster

Traditional editing often forces the preview/export pipeline to decode, composite, and render full frames repeatedly. The proposed pipeline runs neural networks only when object understanding is needed, then caches the result.

After extraction, most editing operations become cheap scene-graph edits:

```text
move object     -> update x/y in JSON
resize object   -> update scale in JSON
hide object     -> update visibility/opacity
replace bg      -> composite cached cutout over new layer
add outline     -> draw mask-derived outline in WebGL/SVG
reuse object    -> reference the same cached asset in another timeline
```

## Rendering strategy

Use a hybrid strategy instead of forcing one format:

| Source content | Best asset type | Motion control | Renderer |
|---|---|---|---|
| Photoreal object | transparent WebM/WebP/AVIF/PNG sequence | JSON track | Canvas/WebGL/PixiJS |
| Simple flat object | SVG/Lottie/dotLottie | JSON/Lottie keyframes | Lottie/SVG renderer |
| UI/labels/arrows | SVG/HTML/Lottie | JSON state/timing | DOM/SVG/Lottie |
| Original background | MP4/WebM | video timeline | native video/WebCodecs |

## AI usage rule

Run AI only at these points:

1. Initial object selection and tracking.
2. User correction/refinement.
3. Optional high-quality matting or clean-plate generation.
4. Optional auto-routing: decide whether object should be vector, raster, or regular video.

Do not run AI during normal playback, timeline scrubbing, or simple transform edits.

## MVP pipeline

```text
upload short clip
-> user selects/clicks object
-> neural segmentation/tracking creates mask track
-> masks are stabilized and scored
-> object cutout is cached as raster alpha frames or packed alpha video
-> motion track is stored as JSON
-> browser editor renders via Canvas/WebGL/PixiJS
-> final export uses Remotion/FFmpeg/WebCodecs
```

## Quality router

The system should classify each extracted object before export:

```text
if flat colors + stable edges + low detail:
    export SVG/Lottie vector path + JSON motion
elif photoreal object + stable mask:
    export raster alpha asset + JSON motion
elif unstable mask or heavy occlusion:
    keep as normal video layer and offer assisted mask refinement
```

## What the current prototype implements

The starter repo now includes:

- sampled-frame decoding
- demo mask providers
- external mask input for neural models
- contour/polygon extraction
- transparent cutout frames
- cropped reusable object-layer cutouts
- WebP/PNG spritesheet for website preview
- `scene_graph.json`
- `object_motion.json`
- `web_asset_manifest.json`
- `silhouette_lottie.json`
- `resource_profile.json`
- optional `benchmark_report.json`
- Canvas preview
- opt-in production asset generation from cached cutouts:
  - WebP sprite atlas with frame metadata
  - transparent VP9/WebM when local `ffmpeg` is available
  - optional AVIF sprite atlas when requested and supported by Pillow

`resource_profile.json` is the first step toward measuring whether an extraction actually improves an editing workflow. It records source size, object package size, payload breakdown, PNG warnings, sprite size, pixel work estimates, and the intended runtime strategy.
`benchmark_report.json` adds a runtime comparison between naive sampled video decoding and cached cropped-layer compositing, which is closer to the browser preview loop used after extraction.
When production mode is enabled, the profile also compares the authoring/debug package with production WebP/WebM/AVIF payloads and records explicit encoder support status.

## Production optimization path

1. Keep WebP/AVIF sprites and transparent WebM as production package options derived from cached cutouts.
2. Use GPU texture atlases for browser preview.
3. Cache mask tracks and object cutouts per source clip.
4. Re-render only changed layers during preview.
5. Batch segmentation requests.
6. Self-host segmentation only after usage proves API cost/latency bottlenecks.
7. Use quality routing to avoid expensive vectorization when raster is better.

## Commercial acceptance

Editors will accept this if it feels like faster editing, not like a new file-format science project. The product should be sold as:

> Select an object in a video. Edit it like a reusable layer. Render faster.

The strongest early users are web video editors, short-form creator tools, ecommerce/social video teams, education-video teams, and API customers that need object-aware editing without building segmentation infrastructure.

## Differentiation

Existing products mostly provide one of these:

- object masks inside a single editor
- background removal
- cutout stickers
- video-to-Lottie conversion by embedding frames
- programmatic video rendering from templates

The differentiated product is the combination:

```text
AI object selection
+ reusable object assets
+ JSON edit graph
+ fast WebGL preview
+ final video export
+ portable asset package
+ rights/attribution metadata
```

That is closer to an object-aware editing engine than a one-off cutout feature.
