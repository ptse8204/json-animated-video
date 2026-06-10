---
historical: true
default_context: false
---

# Phase Stability 03 Report

## Summary

- Started from a clean working tree after Phase Stability 02.
- Split asset-preparation watchdog failures into typed reasons:
  - `asset_preparation_frame_timeout` for an in-flight frame that never emits a
    matching finish event.
  - `worker_heartbeat_stale` for asset-prep event silence when no in-flight
    frame is known.
  - `asset_preparation_stalled` remains as `compatibilityReasonCode`.
- Added env overrides:
  - `MOTIONJSON_ASSET_PREP_FRAME_TIMEOUT_SECONDS`
  - `MOTIONJSON_WORKER_HEARTBEAT_STALE_SECONDS`
- Updated job lifecycle recovery state and UI recovery labels so all three
  asset-prep reason codes remain retryable from the Run monitor.

## Changed Files

- `src/motionjson/backend/stale_jobs.py`
  - Adds typed watchdog reason codes and timeout env readers.
  - Emits typed diagnostic events while preserving the compatibility umbrella
    reason in metadata.
  - Includes frame, position, object id, thresholds, and latest-event details in
    the diagnostic payload.
- `src/motionjson/backend/job_lifecycle.py`
  - Maps typed watchdog messages to distinct lifecycle failure summaries.
  - Keeps asset-prep recovery actions available for the typed reason codes.
- `src/motionjson/ui/static/app.js`
  - Treats typed asset-prep watchdog reasons as retryable asset-prep failures.
- Tests updated in `tests/test_backend_jobs_worker.py`,
  `tests/test_job_lifecycle.py`, and `scripts/test_ui_config_builder.mjs`.
- Screenshot evidence added under
  `docs/design/screenshots/phase-stability-03/`.

## Tests Run

- `python3 -m py_compile src/motionjson/backend/stale_jobs.py src/motionjson/backend/job_lifecycle.py`
- `python3 -m pytest -q tests/test_backend_jobs_worker.py::test_asset_preparation_watchdog_timeout_env_overrides tests/test_backend_jobs_worker.py::test_reconcile_stale_asset_preparation_fails_running_job tests/test_backend_jobs_worker.py::test_reconcile_asset_preparation_frame_start_timeout_fails_running_job tests/test_backend_jobs_worker.py::test_reconcile_asset_preparation_keeps_fresh_running_job tests/test_job_lifecycle.py::test_job_lifecycle_summarizes_typed_asset_preparation_failures tests/test_job_lifecycle.py::test_local_ui_job_poll_reconciles_stale_asset_preparation`
- `node scripts/test_ui_config_builder.mjs`
- `python3 -m pytest -q tests/test_backend_jobs_worker.py tests/test_job_lifecycle.py tests/test_track_filtering.py tests/test_job_artifacts.py`
- `npm test`
- `npm run build`
- `npm run ui:layout -- --state workflow-run-asset-stalled,workflow-review --screenshot-dir docs/design/screenshots/phase-stability-03`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `git diff --check`

## Browser Evidence

- Captured `workflow-run-asset-stalled` and `workflow-review` across:
  - `mobile-390`
  - `tablet-768`
  - `tablet-1024`
  - `laptop-1366`
  - `desktop-1440`
  - `desktop-1920`
- The layout smoke returned `status: ok`.
- Python emitted a shutdown resource-tracker warning for one leaked semaphore
  during the layout smoke teardown; no layout failure was reported.

## Known Limitations

- The frame-timeout classifier depends on the latest event being
  `asset_preparation_frame_started`. Older runs without per-frame start events
  still classify as `worker_heartbeat_stale`.
- The compatibility umbrella reason remains metadata-only for typed watchdog
  events. New UI/debug-report consumers should prefer `reasonCode`.
- The watchdog uses event timestamps and does not inspect process liveness
  beyond heartbeat/progress silence.

## Follow-Up Tasks

- Surface the exact failed object and frame more prominently in Run monitor
  recovery copy when lifecycle metadata includes it.
- Keep partial-object review state visible for typed watchdog failures.
- Move the next UI simplification into pure state selectors before splitting
  files.
