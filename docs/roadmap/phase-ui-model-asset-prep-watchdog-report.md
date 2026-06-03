# Phase UI Model Asset Prep Watchdog Report

## Summary

- Implemented backend reconciliation for the copied log pattern where a run
  remains `running` after the latest event is `asset_preparation`.
- Running jobs whose latest event is stale in `asset_preparation` now become a
  terminal `failed` job with reason code `asset_preparation_stalled`.
- The structured failure records object id, prepared frame count, total frames,
  last event time, detection time, threshold, and the exact user-facing message.
- Local UI polling now triggers that reconciliation before returning job
  snapshots, progress, job center, or event views.
- The UI now shows asset-prep-specific recovery copy: `Retry asset prep`,
  `Retry from Model setup`, and `Choose different model`.
- The sticky mobile primary action also changes to `Retry asset prep` for this
  terminal state.

## Changed Files

- `src/motionjson/backend/stale_jobs.py`
  - Added the asset-preparation stall detector and reconciliation helper.
- `src/motionjson/backend/job_lifecycle.py`
  - Added `asset_preparation_stalled` reason handling, retry action flags, and
    stage-aware latest-event phase detection.
- `src/motionjson/ui/server.py`
  - Reconciles stale asset-preparation jobs before public job snapshots.
- `src/motionjson/ui/static/app.js`
  - Adds asset-prep recovery labels, terminal-state mock capture, and
    retry-specific workflow primary action.
- `scripts/check_local_ui_layout.mjs`
  - Adds `workflow-run-asset-stalled` capture mapping and assertions.
- `scripts/test_ui_config_builder.mjs`
  - Adds frontend contract tests for asset-prep retry labels/actions.
- `tests/test_backend_jobs_worker.py`
  - Adds stale/fresh asset-preparation reconciliation tests.
- `tests/test_job_lifecycle.py`
  - Adds lifecycle and Local UI API polling tests for the terminal failure.
- `docs/troubleshooting.md`
  - Documents `asset_preparation_stalled` and recovery actions.
- `docs/design/screenshots/phase-ui-model-asset-prep-watchdog-before/`
  - Captured stale running run-monitor states before changes.
- `docs/design/screenshots/phase-ui-model-asset-prep-watchdog-after/`
  - Captured terminal asset-preparation stalled state after changes.

## Tests Run

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest -q tests/test_backend_jobs_worker.py::test_reconcile_stale_asset_preparation_fails_running_job tests/test_backend_jobs_worker.py::test_reconcile_asset_preparation_keeps_fresh_running_job tests/test_job_lifecycle.py::test_job_lifecycle_summarizes_asset_preparation_stall tests/test_job_lifecycle.py::test_local_ui_job_poll_reconciles_stale_asset_preparation`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m py_compile src/motionjson/backend/stale_jobs.py src/motionjson/backend/job_lifecycle.py src/motionjson/ui/server.py`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest -q tests/test_job_lifecycle.py tests/test_backend_jobs_worker.py tests/test_local_ui_api.py::test_local_ui_api_runs_mock_job_from_run_config_and_exposes_review_metadata tests/test_local_ui_api.py::test_local_ui_artifact_review_surfaces_fallback_without_private_storage tests/test_phase9_ui_job_review_smoke.py`
- `npm run build`
- `npm test`
- `npm run ui:layout -- --state workflow-run-stale,workflow-run-logs-open --screenshot-dir docs/design/screenshots/phase-ui-model-asset-prep-watchdog-before`
- `npm run ui:layout -- --state workflow-run-asset-stalled --screenshot-dir docs/design/screenshots/phase-ui-model-asset-prep-watchdog-after`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli --help`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli backend --help`
- `git diff --check`

The layout command emitted Python multiprocessing `resource_tracker` warnings
about one leaked semaphore during process shutdown, but returned `status: ok`
and wrote all expected screenshots.

## Browser Evidence

- Before screenshots: 12 files covering `workflow-run-stale` and
  `workflow-run-logs-open` across 390x844, 768x1024, 1024x768, 1366x768,
  1440x900, and 1920x1080.
- After screenshots: 6 files covering `workflow-run-asset-stalled` across the
  same viewport matrix.
- Visual inspection confirmed:
  - desktop shows `failed`, object/frame-specific diagnostic text, and the
    `Retry asset prep` / `Retry from Model setup` recovery buttons;
  - mobile first viewport shows the terminal failure and sticky primary
    `Retry asset prep` action.

## Known Limitations

- Reconciliation is poll-driven. A process that never serves job/progress/event
  requests will not update the stale row until the Local UI/API is read again.
- This does not interrupt an already blocked Python call; it prevents the UI and
  backend database from leaving the job indefinitely active after the watchdog
  window.
- Partial vectorization data is not registered as exportable artifacts in this
  patch. The failure records that no export artifacts were produced.
- The default backend asset-preparation stall threshold is 4 minutes and can be
  adjusted with `MOTIONJSON_ASSET_PREP_STALL_SECONDS`.

## Follow-Up Tasks

- Add a resumable asset-preparation worker that can continue from the last
  successfully materialized frame instead of rerunning the whole extraction.
- Register safe intermediate vectorization summaries before raster asset prep
  so review can preserve partial evidence when artifact writing fails.
- Add a backend job maintenance command for reconciling stale jobs outside the
  Local UI polling path.
