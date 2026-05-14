# MotionJSON Core Schemas

MotionJSON core artifacts use JSON Schema Draft 2020-12. Each core JSON document declares its schema with a top-level `schema` field, and validation infers the packaged schema from that value.

## Core Schema IDs

- `motionjson.scene_graph.v0.1`: authoring scene graph with source video metadata, object layers, editable motion frames, canvas metadata, and runtime guidance.
- `motionjson.object_manifest.v0.1`: per-object asset manifest with cutouts, masks, spritesheet metadata, optional production asset metadata, motion frames, quality scores, and the recommended output route.
- `motionjson.object_motion.v0.1`: compact per-object motion track for JSON transform editing.
- `motionjson.web_asset_manifest.v0.1`: website/runtime package for canvas sprite-layer playback, with optional production WebP/WebM/AVIF asset references.
- `motionjson.resource_profile.v0.1`: measured package sizes, production resource comparisons, pixel-work estimates, warnings, and cached-preview strategy.
- `motionjson.final_export_manifest.v0.1`: final export metadata for MP4 renders, transparent WebM object exports, website ZIPs, and Remotion adapter plans.

Schema files are packaged under `src/motionjson/schemas/`.

## Validation

Validate one file:

```bash
motionjson validate out/demo/scene_graph.json
```

Validate an output directory:

```bash
motionjson validate out/demo
```

Directory validation requires these core artifacts:

```text
scene_graph.json
object_motion.json
web_asset_manifest.json
resource_profile.json
objects/<object_id>/object_manifest.json
```

It also recursively checks other JSON files that declare a recognized MotionJSON core schema. Auxiliary JSON files without a MotionJSON `schema` field are skipped. The default object id is `object_0`; use `--object-id` when validating an output directory generated with another id.

Final export manifests are optional for directory validation, but any `final_export_manifest.json` that declares `motionjson.final_export_manifest.v0.1` is validated recursively.

## Production Asset Fields

Production assets are additive and opt in through extraction flags such as `--output-mode production` or `--output-mode both`. The schemas accept optional production metadata under:

- `scene_graph.json`: `objects[].assets.production`
- `objects/<object_id>/object_manifest.json`: `production`
- `web_asset_manifest.json`: `assets.production`
- `resource_profile.json`: `productionAssets` and `resourceComparison`

Each production export reports a status such as `ready`, `skipped`, `unavailable`, `unsupported`, or `error`. Transparent WebM reports `unavailable` when local `ffmpeg` is missing. AVIF reports `unsupported` when the installed Pillow build cannot encode AVIF. These assets are derived from cached raster/alpha cutouts and JSON transforms; they do not trigger AI inference.

## Auxiliary Lottie

`silhouette_lottie.json` is intentionally not a MotionJSON core schema. It is an auxiliary Lottie export for simple vector-like silhouettes, outlines, labels, annotations, icons, and flat graphics. Photoreal objects remain raster/alpha assets by default and are controlled by MotionJSON transforms.

## Final Export Manifest

Phase 8 writes `final_export_manifest.json` next to final exports. Each entry reports type, format, status, output path, bytes, fps, frame count, source scene, optional object id, rights passthrough, and `aiUsage: none`. Export status can be `ready`, `plan_ready`, `not_configured`, `skipped`, `unavailable`, `unsupported`, or `error`.
