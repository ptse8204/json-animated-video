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

The existing CLI interface is unchanged in Phase 11. Validated corrected-state
MotionJSON exports are exposed through the local UI API so they can consume
review corrections and export-inclusion state before writing handoff artifacts.

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

`final_export_manifest.json` uses schema id `motionjson.final_export_manifest.v0.1`. It records export type, format, status, output path, bytes, fps, frame count, source scene, object id, `aiUsage: none`, and rights passthrough. The manifest uses `source.directory: "."` to avoid embedding machine-specific local paths.

Phase 11 adds optional manifest blocks for validated local UI exports:

- `provenance`: app/version, source job id, source asset id when known, export
  id, preset, correction event count, included/excluded object ids, diagnostics,
  and `aiUsage: none`.
- `config`: sanitized run payload, correction state, preset, and artifact
  toggles used for the export.
- `validation`: checked document count, issue count, and overall validation
  status.

## Local UI Validated MotionJSON Export

From the local UI, select a completed run, make any correction edits, then use
the Export panel to validate and export MotionJSON. The backend route is:

```http
POST /api/jobs/JOB_ID/exports
```

Preflight validation uses the same payload without writing artifacts:

```http
POST /api/jobs/JOB_ID/validate
```

Example payload:

```json
{
  "preset": "debug",
  "includeMasks": true,
  "includeContours": true,
  "includePreview": true
}
```

The response includes a validated corrected `scene_graph.json`,
`final_export_manifest.json`, `validation_report.json`, an SVG overlay preview,
and a ZIP bundle. The `debug` preset also copies cached mask PNGs and writes
contour/box JSON. Export does not run SAM2, detectors, matting, LLMs, hosted
providers, or network calls; it packages cached artifacts and saved correction
state only.
