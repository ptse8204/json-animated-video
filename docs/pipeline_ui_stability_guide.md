# Pipeline And UI Stability Guide

This guide is the short map for future engineers and Codex sessions working on
SAM3 Scene Sweep stability, partial outputs, job watchdogs, or Local UI state.

## Where To Look

| Area | Main files |
| --- | --- |
| Multi-object pipeline | `src/motionjson/pipeline.py` |
| Track filtering and fallback reasons | `src/motionjson/track_filters.py` |
| Artifact registration | `src/motionjson/backend/assets.py`, `src/motionjson/backend/worker.py` |
| Job watchdog and lifecycle | `src/motionjson/backend/stale_jobs.py`, `src/motionjson/backend/job_lifecycle.py` |
| Review metadata from artifacts | `src/motionjson/ui/server.py` |
| Local UI workflow state | `src/motionjson/ui/static/app.js` |
| UI selector tests | `scripts/test_ui_config_builder.mjs` |
| Backend regression tests | `tests/test_provider_pipeline.py`, `tests/test_track_filtering.py`, `tests/test_job_artifacts.py`, `tests/test_backend_jobs_worker.py`, `tests/test_job_lifecycle.py` |

## Pipeline Object Lifecycle

1. Discovery produces object candidates and object ids.
2. Mask/tracker stages produce per-frame mask records.
3. Vectorization adds lightweight review metrics: bbox, centroid, polygons,
   contour count, visibility, area, mask shape, mask area, confidence, and
   provider metadata.
4. Asset preparation writes object masks, cutouts, previews, manifests, and
   optional sprite assets.
5. Each completed object is checkpointed immediately through object-scoped
   artifact registration. A later object failure should not erase earlier
   reviewable objects.
6. Completed tracks stored for later linking/filtering drop heavy `rgb` and
   `mask` arrays after checkpointing. Filtering must use preserved `maskArea`
   and `maskShape` metadata when raw arrays are absent.
7. Final output-tree registration is idempotent by
   `project_id/source_job_id/rel_path`, so incremental checkpoints and final
   registration do not create duplicate artifact rows.

The cutout materialization budget is controlled by
`MOTIONJSON_MAX_OBJECT_CUTOUT_PIXELS` and defaults to `64000000`. If an object
exceeds the budget, keep masks and diagnostics, skip cutouts/spritesheets, and
mark the object review-required instead of trying to materialize a giant
background-like layer.

## Job Events And Watchdogs

Asset preparation emits per-frame and per-object events:

- `asset_preparation_frame_started`
- `asset_preparation_frame_finished`
- `asset_preparation_object_finished`
- `asset_preparation_object_failed`

Frame events should include object id, frame position, source frame index, bbox,
mask area, crop size, written files, byte sizes, and elapsed milliseconds when
known.

Watchdog reason codes:

- `asset_preparation_frame_timeout`: a frame-start event did not receive a
  matching frame-finish event before the frame timeout.
- `worker_heartbeat_stale`: no heartbeat/progress arrived and no in-flight
  frame is known.
- `asset_preparation_stalled`: compatibility umbrella reason preserved as
  `compatibilityReasonCode`.

When the watchdog sees one of these conditions after completed
`object_manifest` artifacts already exist, it marks the failed object with an
`asset_preparation_object_failed` event and completes the job as partial
success. The Local UI should route that run to review/export for the completed
objects while showing the failed object/frame in the event log.

Timeout env vars:

- `MOTIONJSON_ASSET_PREP_FRAME_TIMEOUT_SECONDS`
- `MOTIONJSON_WORKER_HEARTBEAT_STALE_SECONDS`

Both default to the conservative asset-prep watchdog window when unset.

## UI State Selector Contract

Local UI workflow decisions should be derived from snapshot objects, not DOM
classes or direct global state reads.

Current selector entry points in `app.js`:

- `workflowReadinessFromSnapshot`
- `workflowJobStatusFromSnapshot`
- `workflowModelSetupStatusFromSnapshot`
- `workflowRecoveryActionsFromSnapshot`
- `workflowExportAvailabilityFromSnapshot`
- `workflowPrimaryActionFromSnapshot`
- `workflowBlockedReasonFromSnapshot`
- `workflowStepContractFromSnapshot`
- `screenContractFromSnapshot`

These selectors must not read the DOM, mutate `state`, call APIs, use storage,
or depend on CSS classes. The adapter boundary is `workflowSnapshot()` inside
`init()`: it is allowed to read DOM and mutable state, then pass plain values to
selectors.

## Troubleshooting Map

- Partial object exists but job failed: inspect
  `objects/<objectId>/object_manifest.json` artifacts and review metadata. The
  UI should surface completed object
  manifests even when the selected job is failed.
- Frame timeout: search events for the latest
  `asset_preparation_frame_started` without a later finish for the same object
  and frame.
- Heartbeat stale: search the latest `asset_preparation` event and worker logs;
  the worker may have blocked or died outside a known frame write.
- Budget-skipped object: look for
  `asset_materialization_budget_exceeded` in track metadata or fallback
  diagnostics; reduce proposal scope or raise the budget only when memory
  capacity is known.
