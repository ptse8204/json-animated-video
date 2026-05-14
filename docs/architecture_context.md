# MotionJSON Architecture Context

## Core idea

MotionJSON uses AI to convert selected video elements into reusable motion layers.

The product is not a generic video-to-JSON converter. JSON is the edit graph and runtime control format.

## Correct pipeline

```text
source video
→ AI or mask provider identifies object
→ mask sequence / alpha matte
→ cropped raster/alpha object asset
→ optional vector silhouette/outline
→ scene_graph.json
→ web_asset_manifest.json
→ Canvas/WebGL/PixiJS preview
→ export to video or website package
```

## Why photorealistic objects stay raster

Photorealistic objects contain texture, motion blur, shadows, reflections, occlusions, hair/fur/edge detail, camera noise, and lighting changes. These are usually worse as SVG/Lottie. The safe default is:

```text
raster/alpha asset + JSON motion
```

SVG/Lottie is appropriate for:

```text
silhouettes
outlines
labels
icons
annotations
flat logos
simple vector-like objects
```

## Editing performance thesis

Traditional editing often reprocesses full frames.

MotionJSON should do:

```text
expensive AI extraction once
→ cached object assets
→ cheap JSON transform edits
→ partial preview invalidation
→ final render only when needed
```

Small edits become JSON deltas:

```json
{
  "objectId": "object_0",
  "edit": {
    "translate": [40, -20],
    "scale": 1.12,
    "rotation": 0.08,
    "opacity": 0.92
  }
}
```

## Runtime model

Preview:

```text
Canvas2D for MVP
WebGL/PixiJS for production
```

Export:

```text
FFmpeg for server video
Remotion for programmatic timeline rendering
Website package for web graphics
```

## Backend placement

The SaaS backend sits behind the ingest/export boundary. It owns users,
sessions, projects, assets, jobs, queues, workers, local storage, and usage
events, while the extraction and export engines still operate on cached
raster/alpha assets and JSON transforms. Backend workers call MotionJSON Python
functions directly; they do not shell out to the CLI and do not run AI during
normal drag, scale, rotate, or preview edits.

## Core artifacts

```text
scene_graph.json
object_manifest.json
web_asset_manifest.json
resource_profile.json
transparent object media
sprite atlas
optional silhouette_lottie.json
```
