# Phase UI Model SAM3 Asset Stall Recovery Report

## Summary

- Investigated the live Colab/Chrome stalled SAM3 Scene Sweep run from the copied run debug report.
- The selected run was `aac6d1ace3c24ef38197810d8cb40baa`, provider `sam3-local`, phase `extracting`, progress `70%`, with the last event `contours vectorized for sam3_grid_018`.
- The stall happened after model discovery/vectorization, not during CUDA inference: the visible Colab resources panel showed GPU RAM at 0.0 GB while the UI had no new extraction events.
- Fixed the pipeline gap where whole-frame/background-like tracks were filtered only after expensive raster cutout and spritesheet materialization.
- Added asset-preparation progress events so users can distinguish model work from local artifact writing.

## Root Cause

The pipeline already had a `masks_too_large_whole_frame` track filter, but the filter ran after `_extract_object()` had written masks, full-frame cutouts, and a spritesheet. For a SAM3 grid candidate that passed initial keyframe filtering but became a whole-frame/background-like propagated track, the backend could spend minutes encoding useless raster assets before reaching track linking and fallback diagnostics.

That matched the live report:

- last event: `contours vectorized for sam3_grid_018`;
- next expected phase: `track_linking`;
- artifacts: `0`;
- GPU memory: no active model allocation shown in the Colab resources panel;
- UI watchdog: no progress after several minutes.

## Changed Files

- `src/motionjson/pipeline.py`
  - Runs the existing track filter immediately after vectorization.
  - Skips cutout/spritesheet/production-asset materialization for tracks already rejected as `masks_too_large_whole_frame` or `no_masks_accepted`.
  - Keeps masks, track summaries, fallback diagnostics, review metadata, and schema-valid scene artifacts.
  - Emits `asset_preparation` progress events, including a `skipped` event with reason codes.
- `tests/test_track_filtering.py`
  - Adds regression coverage proving whole-frame tracks skip cutouts/spritesheets, emit a skipped asset-preparation event, and still produce fallback diagnostics.

## Tests Run

- `python3 -m pytest -q tests/test_track_filtering.py`
- `python3 -m pytest -q tests/test_track_filtering.py tests/test_sam3_discovery_subprocess.py tests/test_backend_jobs_worker.py`
- `python3 -m pytest -q tests/test_discovery_providers.py tests/test_sam3_providers.py`
- `python3 -m pytest -q tests/test_local_ui_api.py::test_local_ui_api_runs_mock_job_from_run_config_and_exposes_review_metadata tests/test_local_ui_api.py::test_local_ui_artifact_review_surfaces_fallback_without_private_storage tests/test_phase9_ui_job_review_smoke.py`
- `python3 -m py_compile src/motionjson/pipeline.py tests/test_track_filtering.py`

All listed commands passed.

## Chrome Evidence

- Used the Chrome-controlled Colab/MotionJSON tabs, not the disconnected earlier Local UI URL.
- Confirmed the visible debug report and current UI state showed no new extraction progress after `contours vectorized for sam3_grid_018`.
- Confirmed the Colab runtime panel reported an L4 GPU runtime and 0.0 GB GPU RAM in use during the stale UI state, consistent with a post-model CPU/artifact stage rather than active CUDA inference.
- A direct temporary Chrome tab request to the Colab-served `/api/jobs` endpoint was blocked by the browser client extension stack, so live backend API inspection stayed limited to the UI-visible report and page state.

## Known Limitations

- This patch prevents the same class of future SAM3/background-fragment stalls after the updated backend is running. It cannot retroactively recover an already stuck Colab worker using older code; that run should be canceled and retried after restarting/updating the UI runtime.
- SAM3 setup and discovery model loading remain bounded by their existing subprocess timeouts. A setup job can still legitimately show loading progress while the model warms up, but it should become terminal after the configured timeout rather than remain active forever.

## Follow-Ups

- Add a provider setup debug-report button similar to the run debug report so users can copy model-setup stalls without opening raw logs.
- Retest the real Colab SAM3 Scene Sweep flow after deploying this commit to the Colab runtime.
