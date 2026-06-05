# MotionJSON Core Schemas

MotionJSON core artifacts use JSON Schema Draft 2020-12. Each core JSON document declares its schema with a top-level `schema` field, and validation infers the packaged schema from that value.

## Core Schema IDs

- `motionjson.scene_graph.v0.1`: authoring scene graph with source video metadata, object layers, editable motion frames, canvas metadata, and runtime guidance.
- `motionjson.object_manifest.v0.1`: per-object asset manifest with cutouts, masks, spritesheet metadata, optional production asset metadata, motion frames, quality scores, and the recommended output route.
- `motionjson.object_motion.v0.1`: compact per-object motion track for JSON transform editing.
- `motionjson.web_asset_manifest.v0.1`: website/runtime package for canvas sprite-layer playback, with optional production WebP/WebM/AVIF asset references.
- `motionjson.resource_profile.v0.1`: measured package sizes, production resource comparisons, pixel-work estimates, warnings, and cached-preview strategy.
- Resource profiles also include provider performance, latency metrics, cost dashboard data, and optional compression optimizer metadata.
- `motionjson.final_export_manifest.v0.1`: final export metadata for MP4 renders, transparent WebM object exports, website ZIPs, and Remotion adapter plans.
- `motionjson.rights_manifest.v0.1`: structured rights metadata, source attribution, license details, creator approval, commercial-use review status, asset lineage, and audit records.
- `motionjson.correction_request.v0.1`: local mask correction request with add/remove points, box corrections, brush strokes, same-coordinate or centroid-delta propagation, and temporal smoothing settings.
- `motionjson.correction_manifest.v0.1`: correction result metadata, changed frames, regenerated artifacts, quality, routing, and `aiUsage: none`.
- `motionjson.partial_review_payload.v0.1`: auxiliary recovery payload written when completed per-object extraction checkpoints can be reviewed even though a later object failed before the global export finished.
- `motionjson.evaluation_benchmark.v0.1`: Phase 12 CPU benchmark summary
  written by `motionjson benchmark`, with relative run paths, validation
  status, track counts, fallback reason counts, continuity, coverage, and
  runtime metrics.

Schema files are packaged under `src/motionjson/schemas/`.

## Auxiliary Export Formats

Validated local UI exports also write `quality_routing.json` with format
identifier `motionjson.export_quality_routing.v0.1`. It records object output
choice, production delivery choice, and preview route status. The same object is
embedded in validated final export manifests as `qualityRouting`. It is not a
standalone recursively validated core schema in this phase.

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
rights_manifest.json
objects/<object_id>/object_manifest.json
```

It also recursively checks other JSON files that declare a recognized MotionJSON core schema. Auxiliary JSON files without a MotionJSON `schema` field are skipped. The default object id is `object_0`; use `--object-id` when validating an output directory generated with another id.

Extraction job files such as `run_config.json`, `job.json`, `events.jsonl`,
`metrics.json`, `artifacts.json`, `provider_diagnostics.json`, and
`failure.json` are auxiliary artifacts. `partial_review.json` is also an
auxiliary artifact; it records partial-object recovery state for the Local UI
and is not a standalone recursively validated core schema. Directory validation skips the
extraction run config and provider diagnostics schemas because they are
preflight/job metadata, not MotionJSON render payloads.

Final export manifests are optional for directory validation, but any `final_export_manifest.json` that declares `motionjson.final_export_manifest.v0.1` is validated recursively. Phase 11 validated UI exports also validate the corrected `scene_graph.json` and manifest before registering export artifacts. `quality_routing.json` is an auxiliary export report and is embedded in the validated manifest under `qualityRouting`.

Correction request and manifest files are optional for ordinary extraction outputs. When `motionjson correct` writes `correction_request.json` and `correction_manifest.json`, directory validation checks them recursively.

## Partial Review Recovery

Multi-object extraction checkpoints per-object manifests before the final
global export. If one later object fails during asset preparation, the worker
may synthesize review artifacts from the completed object directories instead
of leaving the run with no reviewable payload. This recovery path writes the
normal review files where possible:

```text
scene_graph.json
tracks.json
fallback_diagnostics.json
rights_manifest.json
web_asset_manifest.json
objects/<object_id>/object_manifest.json
objects/<object_id>/web_asset_manifest.json
preview/*.html
partial_review.json
```

`partial_review.json` includes `partialSuccess`, `reviewableObjectIds`,
`reviewableObjectCount`, the failed `objectId` or frame when known, diagnostic
reason/message fields, and runtime proof if the job captured it. The generated
scene graph also carries `partialSuccess: true` and an embedded
`partialReview` block. Recovered tracks default to review-required and are not
export-included until the user explicitly reviews them.

## Rights Fields

Phase 13 adds `rights_manifest.json` and structured embedded rights blocks. Generated scene graphs point to the canonical file with `rightsManifest: "rights_manifest.json"`. Object manifests, web asset manifests, final export manifests, Remotion plans, and website package manifests preserve the same structured rights metadata.

Each rights block contains source attribution, license details, creator approval, commercial-use status, asset lineage, and audit log fields. Defaults are conservative: user-uploaded rights are unverified and commercial use requires review until callers provide explicit metadata. Exports preserve rights while keeping `aiUsage: none`; export and preview use cached raster/alpha assets and JSON transforms only.

See `docs/rights_and_lineage.md`.

## Discovery Metadata Fields

Discovered or selected objects now carry a stable optional `discovery` block in
`scene_graph.json` objects and raster layers, `object_manifest.json`,
`object_motion.json`, and `web_asset_manifest.json`. Older outputs without this
block remain schema-valid.

The block records candidate lineage and review state without requiring clients
to parse auxiliary `candidates.json`:

- candidate identity/source: `candidateId`, `source`, `providerName`,
  `providerModel`, and `qualityPreset`;
- scores: `candidateScore`, `stabilityScore`, `motionScore`,
  `trackConfidence`, `frameCoverageEstimate`, and `motionCoverage`;
- review/export state: `reviewStatus`, `rejectionReason`,
  `selectedForTracking`, `defaultSelected`, `reviewRequired`, and
  `exportStatus`;
- operational context: provider `filters`, preview/mask `artifacts`,
  `warnings`, `trackingProvider`, `correctionHistoryRef`, and rights/source
  `lineage`.

The `discovery` block allows additive future provider fields while keeping the
core object/layer schemas strict. Runtime clients should read the known fields
they need and ignore unknown fields.

## Production Asset Fields

Production assets are additive and opt in through extraction flags such as `--output-mode production` or `--output-mode both`. The schemas accept optional production metadata under:

- `scene_graph.json`: `objects[].assets.production`
- `objects/<object_id>/object_manifest.json`: `production`
- `web_asset_manifest.json`: `assets.production`
- `resource_profile.json`: `productionAssets` and `resourceComparison`

Each production export reports a status such as `ready`, `skipped`, `unavailable`, `unsupported`, or `error`. Transparent WebM reports `unavailable` when local `ffmpeg` is missing. AVIF reports `unsupported` when the installed Pillow build cannot encode AVIF. These assets are derived from cached raster/alpha cutouts and JSON transforms; they do not trigger AI inference.

When production assets are present, `compressionOptimizer` compares local
candidates such as WebP sprite atlas, transparent WebM, and optional AVIF
sprite atlas against the cached PNG cutout sequence. It selects the smallest
ready candidate and reports bytes saved, status, path, and `aiUsage: none`.

## Performance Fields

Phase 16 adds additive observability fields:

- `scene_graph.json`: `providerPerformance`, `latencyMetrics`, and
  `costDashboard`
- `resource_profile.json`: `providerPerformance`, `latencyMetrics`,
  `costDashboard`, and optional `compressionOptimizer`

`providerPerformance` records provider attempts, batch usage, fallback results,
provider names, timings, and cache summaries where available. `latencyMetrics`
records extraction phase timings. `costDashboard` summarizes provider attempts,
explicit zero or unknown provider costs, cache hit/miss data, latency, and
compression optimizer status. OpenRouter remains LLM/VLM-only and is never
reported as a segmentation provider.

## Quality Fields

Every core artifact that carries object quality uses the same quality contract:

- Preserved compatibility fields: `maskStability`, `edgeComplexity`, `bboxStability`, and `vectorSuitability`.
- Phase 9 scores: `maskDriftScore`, `edgeQualityScore`, `missingFrameScore`, `occlusionRiskScore`, and `productionReadinessScore`.
- Diagnostics: `visibleFrameRatio`, `missingFrameRatio`, `longestMissingFrameRun`, `productionReadiness`, and `routingReasons`.

All numeric score fields are deterministic, bounded `0..1`, rounded, and computed from generated extraction metadata only: visibility, area, bbox, centroid, contour point count, and polygon. Invisible or missing frames may use `centroid: null`.

Routing remains conservative. `raster_alpha_sequence` is the default, and `hybrid_vector_silhouette_plus_raster` is allowed only for stable, simple, low-risk layers. Pure SVG/Lottie is not a recommended route for extracted photoreal objects.

See `docs/quality_engine.md` for scoring and readiness rules.

## Correction Schemas

Mask correction is represented by two core schemas:

- `correction_request.json` declares deterministic operations and smoothing/propagation settings.
- `correction_manifest.json` records the source output directory, corrected output directory, changed frames, regenerated artifacts, final quality, final route, and `providerPolicy: deterministic_local_correction_only`.

Correction schemas are provider-neutral. They do not encode OpenRouter, hosted segmentation credentials, network endpoints, or paid API calls. See `docs/mask_correction.md`.

## Auxiliary Lottie

`silhouette_lottie.json` is intentionally not a MotionJSON core schema. It is an auxiliary Lottie export for simple vector-like silhouettes, outlines, labels, annotations, icons, and flat graphics. Photoreal objects remain raster/alpha assets by default and are controlled by MotionJSON transforms.

## Final Export Manifest

Phase 8 writes `final_export_manifest.json` next to final exports. Each entry reports type, format, status, output path, bytes, fps, frame count, source scene, optional object id, rights passthrough, `rightsManifest`, and `aiUsage: none`. Export status can be `ready`, `plan_ready`, `not_configured`, `skipped`, `unavailable`, `unsupported`, or `error`.

Validated UI exports add optional `provenance`, `config`, `qualityRouting`, and
`objectLayerPack`, `exportValidationMessages`, `exportWarnings`, and
`validation` blocks to the same schema for local UI validated exports. These
blocks record sanitized source job/config metadata, correction history state,
export preset, included and excluded object ids, export quality routing, preview
route status, selected-object handoff metadata, review/export gate messages,
rights/lineage warnings, validation status, and `aiUsage: none`. Export
manifests now use `source.directory: "."` instead of embedding local absolute
paths.
