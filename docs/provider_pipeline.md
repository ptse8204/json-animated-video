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
