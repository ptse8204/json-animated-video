# MotionJSON Core Schemas

MotionJSON core artifacts use JSON Schema Draft 2020-12. Each core JSON document declares its schema with a top-level `schema` field, and validation infers the packaged schema from that value.

## Core Schema IDs

- `motionjson.scene_graph.v0.1`: authoring scene graph with source video metadata, object layers, editable motion frames, canvas metadata, and runtime guidance.
- `motionjson.object_manifest.v0.1`: per-object asset manifest with cutouts, masks, spritesheet metadata, motion frames, quality scores, and the recommended output route.
- `motionjson.object_motion.v0.1`: compact per-object motion track for JSON transform editing.
- `motionjson.web_asset_manifest.v0.1`: website/runtime package for canvas sprite-layer playback.
- `motionjson.resource_profile.v0.1`: measured package sizes, pixel-work estimates, warnings, and cached-preview strategy.

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

## Auxiliary Lottie

`silhouette_lottie.json` is intentionally not a MotionJSON core schema. It is an auxiliary Lottie export for simple vector-like silhouettes, outlines, labels, annotations, icons, and flat graphics. Photoreal objects remain raster/alpha assets by default and are controlled by MotionJSON transforms.
