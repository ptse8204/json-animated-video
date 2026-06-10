---
historical: true
default_context: false
---

# Phase Stability 02 Report

## Summary

- Added a memory-bounded object boundary in the multi-object pipeline.
- Completed tracks now drop retained full-frame `rgb` and `mask` arrays after
  object checkpointing, while preserving `maskShape` and `maskArea` metadata.
- Track filtering now uses preserved mask metadata when raw masks are absent.
- Added `MOTIONJSON_MAX_OBJECT_CUTOUT_PIXELS`, defaulting to `64000000`.
- Objects whose estimated cutout pixels exceed the budget skip cutout and
  spritesheet materialization, keep masks and object manifests, and receive a
  review-required fallback diagnostic.

## Changed Files

- `src/motionjson/pipeline.py`
  - Adds cutout pixel-budget estimation and heavy-array stripping.
  - Records asset materialization budget details in object discovery metadata.
- `src/motionjson/track_filters.py`
  - Adds `asset_materialization_budget_exceeded` fallback handling.
  - Reads preserved mask metadata after arrays are stripped.
- `src/motionjson/tracks.py`
  - Keeps `maskShape` and `maskArea` in summaries when raw masks are absent.
- Tests updated in `tests/test_track_filtering.py` and
  `tests/test_provider_pipeline.py`.

## Tests Run

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest -q tests/test_track_filtering.py::test_track_filter_uses_preserved_mask_area_after_arrays_are_stripped tests/test_track_filtering.py::test_asset_materialization_budget_skips_cutouts_and_records_diagnostic tests/test_provider_pipeline.py::test_single_prompt_pipeline_preserves_legacy_outputs`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest -q tests/test_track_filtering.py tests/test_provider_pipeline.py tests/test_job_artifacts.py tests/test_backend_jobs_worker.py tests/test_job_lifecycle.py`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m py_compile src/motionjson/pipeline.py src/motionjson/track_filters.py src/motionjson/tracks.py`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli --help`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli extract --help`
- `git diff --check`

## Browser Evidence

- Not required for this phase. No Local UI layout or visual behavior changed.

## Known Limitations

- The budget uses estimated crop pixels from vectorized bounding boxes. It does
  not estimate encoder-specific memory overhead for PNG/WebP internals.
- A budget-skipped object remains reviewable through masks and diagnostics, but
  it is not exportable as a raster cutout layer until rerun with a smaller
  candidate/frame set or a larger budget.
- The default budget is intentionally conservative but may still need runtime
  tuning for very small or very large Colab machines.

## Follow-Up Tasks

- Use frame start/finish events from Phase 1 to produce typed timeout reasons.
- Surface budget-skipped objects in the Run monitor with clearer recovery copy.
- Consider an adaptive budget that accounts for current process memory once a
  reliable cross-platform memory signal is available.
