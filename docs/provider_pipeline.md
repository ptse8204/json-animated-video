# Extraction Provider Pipeline

Phase 4 splits extraction into provider stages while preserving the existing
CLI and output files.

The current stage order is:

1. `ObjectCandidateProvider`: proposes object candidates.
2. `MaskProvider`: initializes seed masks or mask-provider plans.
3. `VideoTracker`: expands masks across sampled frames.
4. `TrackLinker`: preserves or links stable object identities.
5. `Vectorizer`: converts tracked masks into contours, boxes, centroids, and
   frame visibility.
6. `Exporter`: writes or describes MotionJSON artifacts.

The legacy `run_pipeline()` and `run_multi_object_pipeline()` signatures still
work. Existing `ThresholdMaskProvider`, `ExternalMaskProvider`, motion masks,
and SAM2 segmentation adapters are bridged through the staged pipeline by
`ObjectSpecCandidateProvider`, `ObjectSpecInitialMaskProvider`,
`PerFrameMaskVideoTracker`, `IdentityTrackLinker`, and `ContourVectorizer`.

No heavy ML dependency is imported by these interfaces. SAM2 remains optional
and is only constructed through the explicit SAM2 provider paths.

## Debug Summaries

Every successful extraction writes:

- `candidates.json`: discovered candidate IDs, labels, source provider, prompt
  frame, z-index, and provider metadata.
- `tracks.json`: linked track IDs, frame coverage, visibility, bboxes, masks,
  cutout assets, vectorization metadata, and quality routing.

These files use `format` fields rather than core MotionJSON schemas, so
`motionjson validate <out_dir>` skips them while validating render artifacts.

## No-Model Development

Use `--mask-provider mock` for deterministic local/UI smoke runs:

```bash
python3 -m motionjson.cli extract examples/demo_red_ball.mp4 --out out/mock --mask-provider mock --max-frames 2
```

The mock provider path produces stable masks, tracks, and export artifacts
without CUDA, model weights, network access, or paid services.

## Discovery Providers

Phase 5 adds discovery providers that can feed this same pipeline:

- `motion_foreground` and `external_masks` can produce candidates with
  generated or imported mask directories, so they run through the existing
  mask-tracking/vectorization/export path without GPU dependencies.
- `sam_auto_masks` can use the optional local SAM2 automatic-mask adapter when
  SAM2/torch/model paths are configured, and still exposes mock mode for local
  UI/test runs. `sam3_concept`, `sam3_exemplar`, and `sam3_auto_masks` expose
  mock modes for concept/exemplar/high-recall review flows, and can use the
  optional local SAM3 adapter when SAM3 Python/CUDA/model diagnostics pass.
  `text_detector` and `class_detector` remain scaffolded behind capability checks.
- `manual_prompt` generalizes point/box/mask references for one or more
  user-created objects.

See [Discovery providers](discovery_providers.md) for mode guidance and CLI
examples.

## Track Filtering

Phase 6 runs linked tracks through deterministic filtering and duplicate
analysis before writing `tracks.json`. Whole-frame masks, no-mask tracks, short
tracks, and duplicate tracks receive explicit reason codes and suggested fixes
in `fallback_diagnostics.json`. Core scene output remains schema-compatible;
review tooling should read the auxiliary diagnostics when deciding what to
show, hide, merge, or repair.
