# Mask Correction

Phase 10 adds a deterministic local correction loop for existing MotionJSON extraction outputs. It is designed for correction time only. Normal editing and runtime preview continue to use cached raster/alpha assets plus JSON transforms, with no AI rerun.

## Correction Operations

`motionjson correct` reads a previous extraction output directory, applies local mask edits, and writes a corrected output directory by default.

Supported operations:

- `add_point`: add foreground near `x,y`.
- `remove_point`: remove foreground near `x,y`.
- `box`: constrain to, replace with, add, or remove a rectangular mask region.
- `brush`: add or remove a stroke from a list of points.
- propagation: optionally apply operations across all sampled frames or a bounded frame range using same coordinates or centroid-delta motion.
- temporal smoothing: deterministic majority-vote smoothing across neighboring masks.

All operations run on existing binary mask PNGs. They do not call SAM2, OpenRouter, hosted segmentation, network APIs, or paid providers.
When smoothing is enabled, explicit point, box, and brush edits are reapplied after smoothing so direct user corrections are preserved.

## CLI

Write a corrected copy:

```bash
python3 -m motionjson.cli correct out/demo \
  --out out/demo_corrected \
  --add-point 120,80 \
  --frame 4 \
  --radius 12 \
  --propagate \
  --propagate-window 2 \
  --propagation-mode centroid_delta \
  --smooth
```

Use a request file:

```bash
python3 -m motionjson.cli correct out/demo \
  --out out/demo_corrected \
  --request correction_request.json
```

In-place correction is intentionally opt in:

```bash
python3 -m motionjson.cli correct out/demo --in-place --request correction_request.json
```

Without `--in-place`, the command refuses to overwrite the source output directory.

## Regenerated Outputs

Correction reruns the local extraction packaging path with corrected masks and regenerates:

- `masks/<object_id>/mask_*.png`
- `objects/<object_id>/cutouts/*.png`
- `objects/<object_id>/spritesheet.*`
- `scene_graph.json`
- `object_motion.json`
- `objects/<object_id>/object_manifest.json`
- `web_asset_manifest.json`
- `resource_profile.json`
- quality scores and recommended routing
- `correction_request.json`
- `correction_manifest.json`

The corrected manifests keep the same product model: cached raster/alpha assets for photoreal objects, JSON transforms for editing, and vector output only as optional silhouette assistance when quality routing allows it.
