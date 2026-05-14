# Final Render and Export

Phase 8 adds final exports from existing MotionJSON extraction output. Export uses cached raster/alpha cutouts, spritesheets, production assets, and JSON transforms. It does not rerun segmentation, matting, LLM, VLM, or hosted AI providers during drag/scale/rotate preview or final export.

## CLI

```bash
python3 -m motionjson.cli export out/demo --format mp4 --out out/demo/exports/final.mp4 --background-color "#fbfaf6"
python3 -m motionjson.cli export out/demo --format webm-alpha --out out/demo/exports/object_0.webm --object-id object_0
python3 -m motionjson.cli export out/demo --format website-zip --out out/demo/exports/website_package.zip
python3 -m motionjson.cli export out/demo --format remotion-plan --out out/demo/exports/remotion_export_plan.json
python3 -m motionjson.cli export out/demo --format all --out out/demo/exports --background-color "#fbfaf6"
```

Each export writes or updates `final_export_manifest.json` next to the export output. Direct CLI video exports fail clearly if local `ffmpeg` is unavailable.

## MP4 Final Render

The MP4 path composites frames with Pillow from `scene_graph.json` and cached object cutouts. It honors object/layer `x`, `y`, `scale`, `rotation`, `opacity`, `visible`, `z-index`, and background color, then encodes with local `ffmpeg` using `libx264`, `yuv420p`, and `+faststart`.

The optional `--editor-state` argument accepts Phase 7 `motionjson.timeline_editor_state.v0.1` JSON when available. Editor layers are treated as reusable object-layer instances; duplicate layers reference the same cached source assets.

## Transparent WebM Object Export

`--format webm-alpha` reuses the production transparent VP9/WebM path and can write to an explicit output file. It reports:

- `aiUsage: none`
- `cachedSource: cached_rgba_cutout_png_sequence`
- source metadata from cached cutouts and JSON transforms

This is an object-layer export, not a full-scene render.

## Website Package ZIP

`--format website-zip` creates a relative-path-only ZIP for website use. The package includes:

- `index.html`
- `runtime/`
- preview files under `preview/`
- `scene_graph.json`
- `web_asset_manifest.json`
- `object_motion.json`
- `resource_profile.json`
- `objects/<object_id>/object_manifest.json`
- spritesheets, poster/cutout sequence fallback, and ready production assets
- `package_manifest.json` with file bytes and rights metadata

The package excludes `.env*`, caches, `node_modules`, debug frames, masks, and object debug/layer scratch directories by default.

## Remotion Plan

`--format remotion-plan` writes an adapter plan only. It does not add a Remotion dependency, run npm, call the network, or invoke APIs. The plan status is `plan_ready` and contains the composition, scene/assets, and component contract an application can wire into its own Remotion project.

## Manifest

`final_export_manifest.json` uses schema id `motionjson.final_export_manifest.v0.1`. It records export type, format, status, output path, bytes, fps, frame count, source scene, object id, `aiUsage: none`, and rights passthrough.
