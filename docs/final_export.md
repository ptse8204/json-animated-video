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
- `object_layer_pack.json` with selected object ids, relative artifact paths,
  runtime snippets, and handoff templates
- `package_manifest.json` with file bytes and rights metadata

The package excludes `.env*`, caches, `node_modules`, debug frames, masks, and object debug/layer scratch directories by default.

Headless API asset-package jobs can pass `objectIds` to package only selected
object layers. The package `scene_graph.json`, `package_manifest.json`, and
`object_layer_pack.json` then list the selected and excluded object ids, while
all paths remain relative.

## Remotion Plan

`--format remotion-plan` writes an adapter plan only. It does not add a Remotion dependency, run npm, call the network, or invoke APIs. The plan status is `plan_ready` and contains the composition, scene/assets, selected object ids, object review/export metadata, and component contract an application can wire into its own Remotion project.

## Manifest

`final_export_manifest.json` uses schema id `motionjson.final_export_manifest.v0.1`. It records export type, format, status, output path, bytes, fps, frame count, source scene, object id, `aiUsage: none`, and rights passthrough. The manifest uses `source.directory: "."` to avoid embedding machine-specific local paths.

Validated local UI exports add optional manifest blocks:

- `provenance`: app/version, source job id, source asset id when known, export
  id, preset, correction event count, included/excluded object ids, diagnostics,
  and `aiUsage: none`.
- `config`: sanitized run payload, correction state, preset, and artifact
  toggles used for the export.
- `validation`: checked document count, issue count, and overall validation
  status.
- `qualityRouting`: cached export routing decisions for each included object,
  plus preview route status. It records whether the handoff selected raster
  alpha, optional vector silhouettes, sprite atlas/WebM delivery, and MP4
  preview availability without rerunning providers.
- `objectLayerPack`: location and selected/excluded object summary for
  `object_layer_pack.json`.
- `exportValidationMessages`: user-visible export messages, including
  unreviewed auto-discovered objects that are blocked from selected-object
  handoff until review accepts them.
- `exportWarnings`: user-visible rights/lineage warnings, such as unverified
  commercial-use rights, missing creator approval, unverified licenses, or
  attribution requirements.

## Object Layer Pack

Validated exports and website packages write `object_layer_pack.json` using
format `motionjson.object_layer_pack.v0.1`. It is a compact handoff manifest
for selected reusable motion layers. It includes:

- `selectedObjectIds` and `excludedObjectIds`.
- Per-object relative paths to `object_manifest.json`, `object_motion.json`,
  and `web_asset_manifest.json`.
- Review, discovery, delivery, quality, and rights summaries for the selected
  objects.
- Copyable plain JavaScript, single-object, React, and Remotion snippets.
- Website canvas, single-object embed, and Remotion composition templates.
- Export validation messages that explain review gates before publishing.

## Export Quality Routing

Validated local UI exports also write `quality_routing.json` with format
`motionjson.export_quality_routing.v0.1`. The file is generated from existing
object quality scores, `recommendedOutput`, cached production assets, and the
resource profile. It does not invoke SAM2, detectors, matting, LLMs, hosted AI,
or network services.

For each included object, routing reports:

- `selectedOutput`: `raster_alpha_sequence` by default, or
  `hybrid_vector_silhouette_plus_raster` when object quality and the selected
  export preset both allow contours.
- `selectedDelivery`: the smallest ready production route when known
  (`sprite_atlas_webp`, `sprite_atlas_avif`, or `transparent_webm`), falling
  back to cached raster alpha cutouts.
- `routingReasons`: quality and preset reasons explaining why vector assistance
  was or was not selected.

The preview section reports the SVG overlay and optional `preview/preview.mp4`.
If FFmpeg is unavailable or encoding fails, the MP4 route is marked
`unavailable` or `error` with a reason while the rest of the MotionJSON export
continues.

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
`final_export_manifest.json`, `validation_report.json`, `quality_routing.json`,
`object_layer_pack.json`, a selected-object `website_package.zip`, an SVG
overlay preview, optional MP4 preview, and a ZIP bundle. The `debug` preset also
copies cached mask PNGs and writes contour/box JSON. Export does not run SAM2,
detectors, matting, LLMs, hosted providers, or network calls; it packages cached
artifacts and saved correction state only.

Preflight validation reports the MP4 preview route as `plan_ready` when FFmpeg
is available, but it does not encode the MP4 until the final export request.
Both preflight and final export include `rightsSummary` and `exportWarnings`.
Warnings do not block local export, but they explain when source attribution,
creator approval, license scope, or commercial-use review still needs attention
before publishing.
