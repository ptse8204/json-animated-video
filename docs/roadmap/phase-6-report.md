---
historical: true
default_context: false
---

# Phase 6 Report - Object Tracks And Fallback Diagnostics

## Summary

Phase 6 adds deterministic track filtering, duplicate-track analysis, and
raster fallback diagnostics. Existing core MotionJSON outputs stay
schema-compatible; new review data is written to `tracks.json`,
`fallback_diagnostics.json`, provider performance metadata, and the
`ObjectTrack` summary model.

The working tree was still dirty at the start of Phase 6 because of
pre-existing `README.md`, backup files, and generated `out/demo/*` changes.
Phase 6 changes were kept to track models, filter/fallback helpers, pipeline
wiring, tests, docs, and this report.

## Subagent Findings

- `backend_cv_architect`: recommended keeping strict scene schema untouched and
  placing Phase 6 diagnostics in auxiliary artifacts or existing diagnostic
  objects.
- `qa_benchmark_engineer`: confirmed the required selector already passed with
  baseline tests, then proposed focused whole-frame, fallback, duplicate, and
  pipeline artifact coverage.
- `reviewer`: completed final staged review with no blocking findings; the
  non-blocking artifact-registration assertion was added before commit.

## Implementation

- Extended `ObjectTrack` with `warnings` and `exportStatus`.
- Added `src/motionjson/track_filters.py` with:
  `TrackFilterConfig`, `TrackDecision`, `TrackFilterReport`,
  `RasterFallbackDiagnostic`, `evaluate_track()`,
  `filter_and_dedupe_tracks()`, `track_iou()`, and `build_raster_fallback()`.
- Added reason codes and suggested fixes for no candidates, no accepted masks,
  whole-frame masks, vectorization failure, provider unavailable, tracking
  failure, user-chosen raster mode, duplicate tracks, tiny masks, short tracks,
  and low confidence.
- Wired linked tracks through filter/dedupe reporting before writing
  `tracks.json`.
- Added `fallback_diagnostics.json` as an auxiliary artifact and registered its
  job artifact kind.
- Preserved core scene/object schema validity; rejected tracks remain visible
  in diagnostics rather than being silently dropped from the core output.

## Compatibility Notes

- No CLI flags were removed or changed.
- Existing single-object and multi-object extraction still write the same core
  artifacts.
- `fallback_diagnostics.json` uses a `format` field, not a core schema, so
  `motionjson validate` skips it while still validating core artifacts.
- Heavy ML dependencies remain optional; the new filter code uses only numpy
  and existing track metadata.

## Tests Run

Required command:

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest tests -k 'track or fallback or filter' -q` - failed because `python` is not on PATH in this shell.

Equivalent and additional verification:

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests -k 'track or fallback or filter' -q` - passed, 14 tests, 163 deselected.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests/test_track_filtering.py -q` - passed, 6 tests.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests/test_job_artifacts.py -q` - passed, 11 tests.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests/test_track_filtering.py tests/test_provider_pipeline.py tests/test_job_artifacts.py tests/test_quality_engine.py -q` - passed, 26 tests.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest -q` - passed, 177 tests.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli extract --help` - passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli backend --help` - passed.
- Whole-frame external-mask CLI smoke with `examples/demo_red_ball.mp4`, three full-frame masks, and `--mask-provider external` - passed, wrote `fallback_diagnostics.json` with `masks_too_large_whole_frame`, and `motionjson validate <tmp>/out` passed.
- `npm test` - passed, 18 Node tests.
- `npm run lint` - passed.

## Changed Files

- `src/motionjson/tracks.py`
- `src/motionjson/track_filters.py`
- `src/motionjson/pipeline.py`
- `src/motionjson/job_artifacts.py`
- `tests/test_track_filtering.py`
- `tests/test_job_artifacts.py`
- `docs/track_filtering.md`
- `docs/job_artifacts.md`
- `docs/provider_pipeline.md`
- `docs/index.md`
- `docs/roadmap/phase-6-report.md`

## Known Limitations

- Phase 6 marks rejected and duplicate tracks in diagnostics but does not remove
  core scene objects. This preserves schema compatibility and CLI behavior for
  later UI review/correction phases.
- Duplicate detection currently uses mean bounding-box IoU, not pixel-mask IoU.
- Provider-unavailable, tracking-failed, and vectorization-failed reason codes
  are modeled for diagnostics, but only no-candidate and track-filter outcomes
  are currently emitted by the happy-path pipeline.

## Follow-Up Tasks

- Phase 7+: expose `tracks.json` and `fallback_diagnostics.json` in the local
  API/UI.
- Phase 8+: let users hide, merge, repair, or relabel rejected tracks before
  export.
