# Phase Stability-06 Report - Partial Success Watchdog Recovery

## Summary

Started from a clean working tree on `main`.

This phase changes asset-preparation watchdog reconciliation so a stale SAM3
asset-prep worker does not hard-fail the whole extraction when completed object
manifests were already registered. The watchdog now:

- keeps the existing hard-failure behavior when no reviewable object manifests
  exist;
- detects completed `object_manifest` artifacts for the job;
- records the stale reason and a synthetic `asset_preparation_object_failed`
  event for the failed object/frame when known;
- marks the job `succeeded` with `partialSuccess: true` result metadata;
- emits `asset_preparation_partial_success` so debug reports can show that
  completed objects are reviewable.

No CLI flags or required dependencies changed. No UI layout changed, so browser
screenshots were not required.

## Changed Files

- `src/motionjson/backend/stale_jobs.py`
  - Adds reviewable object-manifest detection during stale asset-prep
    reconciliation.
  - Converts watchdog-stale jobs with completed object artifacts into partial
    success instead of hard failure.
  - Preserves failed object/frame diagnostics in job result and events.
- `tests/test_backend_jobs_worker.py`
  - Adds regression coverage for heartbeat-stale after frame 41/48 with
    completed object manifests.
  - Keeps existing no-artifact stale jobs on the hard-failure path.
- `docs/job_artifacts.md`
  - Documents partial-success job result and watchdog object-failed event.
- `docs/pipeline_ui_stability_guide.md`
  - Documents UI/debug behavior for watchdog partial success.
- `docs/troubleshooting.md`
  - Updates asset-prep stall guidance to prefer reviewing partial objects first.

## Tests Run

- `python3 -m pytest -q tests/test_backend_jobs_worker.py::test_reconcile_worker_heartbeat_stale_with_partial_objects_succeeds_for_review tests/test_backend_jobs_worker.py::test_reconcile_stale_asset_preparation_fails_running_job`
- `python3 -m pytest -q tests/test_backend_jobs_worker.py -q`
- `python3 -m pytest -q tests/test_job_lifecycle.py tests/test_backend_jobs_worker.py`
- `python3 -m pytest -q tests/test_backend_jobs_worker.py tests/test_job_lifecycle.py tests/test_track_filtering.py tests/test_job_artifacts.py`
- `npm test`
- `npm run build`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `git diff --check`

## Known Limitations

- The watchdog cannot restart or continue a dead worker in-process. This phase
  recovers already checkpointed objects and marks the missing object failed for
  review/debugging.
- The synthetic failed-object diagnostic is stored in job events/result
  metadata, not as an `objects/<object_id>/failure.json` asset, because the
  watchdog may not have a live worker output directory.
- Multi-agent scout review was not used because the available delegation tool
  currently requires explicit user authorization for spawning sub-agents.

## Follow-Up Tasks

- Add an explicit UI badge/copy for `partialSuccess` if users still miss that
  reviewable objects are available.
- Consider a per-object resume path that skips already checkpointed objects and
  retries only failed object ids.
- Add optional backend repair tooling to materialize a
  `objects/<object_id>/failure.json` diagnostic from watchdog events when the
  output tree can be located safely.
