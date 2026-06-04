# Phase Stability 05 Report

## Summary

- Started from a clean working tree after Phase Stability 04.
- Added a concise engineering guide for the stabilized pipeline and Local UI
  state contract.
- Updated existing docs instead of creating a large new manual.
- Documented partial object recovery, typed watchdog meanings, asset-prep
  timeout env vars, memory-bounded auto-mask runs, and where future engineers
  or Codex sessions should look first.

## Changed Files

- `docs/pipeline_ui_stability_guide.md`
  - Adds the short object lifecycle, watchdog, UI selector, and troubleshooting
    map.
- `docs/troubleshooting.md`
  - Replaces the generic asset-prep stall text with typed
    `asset_preparation_frame_timeout`, `worker_heartbeat_stale`, and
    compatibility `asset_preparation_stalled` guidance.
  - Adds memory budget troubleshooting for
    `asset_materialization_budget_exceeded`.
- `docs/job_artifacts.md`
  - Documents asset-prep stage events and object-level failure diagnostics.
- `docs/provider_pipeline.md`
  - Documents object checkpoints, heavy-array stripping, idempotent artifact
    registration, and the cutout materialization budget.
- `docs/index.md`
  - Links the new guide from extraction and provider-development paths.

## Tests Run

- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `python3 -m pytest -q tests/test_backend_jobs_worker.py tests/test_job_lifecycle.py tests/test_track_filtering.py tests/test_job_artifacts.py`
- `npm test`
- `npm run build`
- `git diff --check`

## Browser Evidence

- Not required for this phase. Documentation changed only; no Local UI layout or
  visual behavior changed.

## Known Limitations

- The new guide is intentionally concise and does not replace the detailed
  provider, artifact, and troubleshooting docs.
- There is no dedicated markdown link-check command in the repository scripts.
  Links were added using existing doc paths.

## Follow-Up Tasks

- Keep the guide synchronized when mature selectors move out of `app.js`.
- Add a small docs link checker if documentation churn continues.
- Add a UI fixture that demonstrates partial objects after typed asset-prep
  failure once richer lifecycle metadata is surfaced in the Run monitor.
