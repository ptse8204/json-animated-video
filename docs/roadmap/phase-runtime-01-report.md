---
historical: true
default_context: false
---

# Phase runtime-01: Worker heartbeat and safe stale diagnostics

## Summary

This phase fixes the Colab failure mode where a SAM3 Scene Sweep run could be marked stale from event silence even though the worker had not proven it was dead. The backend now emits independent `worker_heartbeat` events while a job is running, classifies unmatched asset-prep frame starts separately from worker-heartbeat staleness, and makes Local UI job polling read-only.

It also removes the unconditional `tqdm` asset-prep loop from backend/UI workers. `tqdm` is now opt-in with `MOTIONJSON_TQDM=1`, which avoids notebook/stdout backpressure during Colab runs. Runtime proof is surfaced through job lifecycle/debug summaries when it is present in result JSON or provider preflight events.

No layout surfaces were changed in this phase, so browser screenshot evidence was not required.

## Changed files

- `src/motionjson/job_artifacts.py`
  - Added independent worker heartbeat support to `LocalJobRun`.
  - Added `MOTIONJSON_WORKER_HEARTBEAT_INTERVAL_SECONDS`.
  - Heartbeat events preserve current stage/object/frame metadata.
- `src/motionjson/backend/worker.py`
  - Mirrors heartbeat events into SQLite through a separate connection.
  - Emits `runtime_proof_recorded` when provider preflight supplies runtime proof.
  - Re-registers lightweight final job bookkeeping files after `job_run.succeed()`.
- `src/motionjson/backend/stale_jobs.py`
  - Separates in-flight `asset_preparation_frame_timeout` from `worker_heartbeat_stale`.
  - Preserves runtime proof in explicit partial-success recovery.
- `src/motionjson/ui/server.py`
  - Removed stale reconciliation side effects from `GET /api/jobs/{jobId}`.
  - Adds a non-mutating watchdog diagnostic to public job snapshots.
- `src/motionjson/backend/job_lifecycle.py`
  - Exposes runtime proof and watchdog diagnostics in lifecycle summaries.
- `src/motionjson/ui/static/app.js`
  - Prefers server watchdog diagnostics when present.
- `src/motionjson/pipeline.py`
  - Removed unconditional `tqdm`; backend progress bars are opt-in.
- `src/motionjson/backend/db.py`
  - Adds `busy_timeout` and WAL where supported.
- `tests/test_backend_jobs_worker.py`
  - Adds watchdog classification tests for heartbeat freshness and frame timeouts.
- `tests/test_job_artifacts.py`
  - Adds independent heartbeat event coverage.
- `tests/test_job_lifecycle.py`
  - Updates polling test to assert read-only behavior.
  - Adds runtime-proof lifecycle coverage.

## Tests run

- `python3 -m py_compile src/motionjson/job_artifacts.py src/motionjson/backend/worker.py src/motionjson/backend/stale_jobs.py src/motionjson/backend/job_lifecycle.py src/motionjson/ui/server.py src/motionjson/pipeline.py src/motionjson/backend/db.py`
- `python3 -m pytest -q tests/test_backend_jobs_worker.py tests/test_job_lifecycle.py tests/test_job_artifacts.py`
- `python3 -m pytest -q tests/test_provider_settings.py tests/test_capabilities.py tests/test_local_ui_api.py tests/test_backend_jobs_worker.py tests/test_job_lifecycle.py tests/test_job_artifacts.py`
- `npm test`
- `npm run build`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `git diff --check`

## Known limitations

- This phase does not synthesize partial global `scene_graph.json` and `web_asset_manifest.json` if only per-object checkpoints exist. That belongs to the next phase.
- Heartbeat DB mirroring uses a short-lived SQLite connection per heartbeat event to avoid cross-thread connection use. This is intentionally conservative; it can be optimized later if profiling shows overhead.
- Existing explicit `reconcile_stale_asset_preparation_job(...)` still performs terminal recovery when directly called. The Local UI polling path no longer calls it.
- CUDA proof is now surfaced when recorded, but this phase does not add a new setup endpoint for proving CUDA inside the notebook runtime.

## Follow-up tasks

- Build partial review payload synthesis for completed object checkpoints.
- Add a setup/runtime endpoint that proves CUDA/MPS/CPU for the current notebook process and stores proof before extraction starts.
- Make high-quality/adaptive effort reporting explicit when the UI reduces requested FPS/frame counts after prior failures.
- Move production spritesheet/cutout materialization later in the review workflow so rejected candidates do not consume asset-prep time.
